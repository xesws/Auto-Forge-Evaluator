"""MATH: \\boxed{} primary extract + last-line fallback. Dual-channel note like GSM8K."""

from __future__ import annotations

import ast
import json
import math
import operator
import re
from fractions import Fraction
from typing import Any

_BOXED_CMD = "\\boxed"


def _extract_boxed_raw(output: str) -> str | None:
    last: str | None = None
    start = 0
    while True:
        index = output.find(_BOXED_CMD, start)
        if index < 0:
            break
        cursor = index + len(_BOXED_CMD)
        while cursor < len(output) and output[cursor].isspace():
            cursor += 1
        if cursor >= len(output) or output[cursor] != "{":
            start = index + 1
            continue
        depth = 0
        end = cursor
        while end < len(output):
            char = output[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    last = output[cursor + 1 : end]
                    break
            end += 1
        start = index + 1
    if last is None:
        return None
    stripped = last.strip()
    return stripped if stripped else None


def _extract_last_raw(output: str) -> str | None:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None
    line = lines[-1]
    if line.startswith("####"):
        line = line[4:].strip()
    return line or None


def _replace_frac(text: str) -> str:
    key = "\\frac"
    while True:
        index = text.find(key)
        if index < 0:
            return text
        cursor = index + len(key)
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1

        def _brace(at: int) -> tuple[str, int] | None:
            if at >= len(text) or text[at] != "{":
                return None
            depth = 0
            end = at
            while end < len(text):
                if text[end] == "{":
                    depth += 1
                elif text[end] == "}":
                    depth -= 1
                    if depth == 0:
                        return text[at + 1 : end], end + 1
                end += 1
            return None

        num = _brace(cursor)
        if num is None:
            return text
        den = _brace(num[1])
        if den is None:
            return text
        text = text[:index] + f"(({num[0]})/({den[0]}))" + text[den[1] :]


def _replace_sqrt(text: str) -> str:
    key = "\\sqrt"
    while True:
        index = text.find(key)
        if index < 0:
            return text
        cursor = index + len(key)
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != "{":
            return text
        depth = 0
        end = cursor
        inner = None
        while end < len(text):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    inner = text[cursor + 1 : end]
                    break
            end += 1
        if inner is None:
            return text
        text = text[:index] + f"sqrt({inner})" + text[end + 1 :]


def normalize_math(text: str) -> str:
    s = text.strip()
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\,", "").replace("\\;", "").replace("\\!", "")
    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = s.replace("$", "")
    s = _replace_frac(s)
    s = _replace_sqrt(s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace(" ", "").replace("\t", "")
    s = s.replace("^{", "^").replace("^", "**")
    return s


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_node(node: ast.AST) -> float | Fraction:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))  # type: ignore[no-any-return]
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(left, Fraction) or isinstance(right, Fraction):
            left_f = Fraction(left).limit_denominator() if not isinstance(left, Fraction) else left
            right_f = (
                Fraction(right).limit_denominator() if not isinstance(right, Fraction) else right
            )
            if type(node.op) is ast.Div:
                return left_f / right_f
        return _BIN_OPS[type(node.op)](left, right)  # type: ignore[no-any-return]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "sqrt" and len(node.args) == 1:
            return math.sqrt(float(_eval_node(node.args[0])))
        if node.func.id == "abs" and len(node.args) == 1:
            return abs(_eval_node(node.args[0]))  # type: ignore[no-any-return]
    raise ValueError("unsafe or unsupported expression")


def _try_numeric(text: str) -> float | None:
    s = normalize_math(text)
    if not s:
        return None
    if re.fullmatch(r"[-+]?\d+/\d+", s):
        num, den = s.split("/")
        try:
            return float(Fraction(int(num), int(den)))
        except ZeroDivisionError:
            return None
    try:
        tree = ast.parse(s, mode="eval")
        value = _eval_node(tree)
        return float(value)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        try:
            return float(s)
        except ValueError:
            return None


def _equal(pred: str, gold: str) -> bool:
    pn = normalize_math(pred)
    gn = normalize_math(gold)
    if pn == gn:
        return True
    pv = _try_numeric(pred)
    gv = _try_numeric(gold)
    if pv is None or gv is None:
        return False
    return abs(pv - gv) <= 1e-6


def verify(output: str, reference: dict) -> dict[str, Any]:
    boxed_raw = _extract_boxed_raw(output)
    last_raw = _extract_last_raw(output)
    gold = str(reference["gold"])
    pred = boxed_raw if boxed_raw is not None else last_raw
    boxed_n = _try_numeric(boxed_raw) if boxed_raw is not None else None
    last_n = _try_numeric(last_raw) if last_raw is not None else None
    diverge = (
        boxed_raw is not None
        and last_raw is not None
        and not _equal(boxed_raw, last_raw)
    )
    note = json.dumps(
        {
            "boxed_raw": boxed_raw,
            "last_raw": last_raw,
            "boxed_n": boxed_n,
            "last_n": last_n,
            "diverge": diverge,
        },
        ensure_ascii=False,
    )
    if pred is None:
        return {"pass": False, "parsed": None, "note": note}
    passed = _equal(pred, gold)
    return {"pass": bool(passed), "parsed": normalize_math(pred), "note": note}
