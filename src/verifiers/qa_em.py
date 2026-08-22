"""Reading QA: official-style normalized EM is pass; token-F1 recorded, not scored."""

from __future__ import annotations

import json
import re
import string
from typing import Any

_ARTICLES = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)
_WS = re.compile(r"\s+")
_PUNCT = str.maketrans({char: " " for char in string.punctuation})


def normalize_answer(text: str) -> str:
    s = str(text).strip().lower()
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"(?<=\d),(?=\d)", "", s)
    s = s.translate(_PUNCT)
    s = _ARTICLES.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    if re.fullmatch(r"[-+]?\d+\.0+", s):
        s = s.split(".")[0]
    return s


def _tokens(text: str) -> list[str]:
    return [tok for tok in normalize_answer(text).split(" ") if tok]


def token_f1(pred: str, gold: str) -> float:
    pred_toks = _tokens(pred)
    gold_toks = _tokens(gold)
    if not pred_toks and not gold_toks:
        return 1.0
    if not pred_toks or not gold_toks:
        return 0.0
    common: dict[str, int] = {}
    for tok in gold_toks:
        common[tok] = common.get(tok, 0) + 1
    overlap = 0
    for tok in pred_toks:
        if common.get(tok, 0) > 0:
            overlap += 1
            common[tok] -= 1
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_toks)
    recall = overlap / len(gold_toks)
    return 2 * precision * recall / (precision + recall)


def _golds(reference: dict) -> list[str]:
    if "golds" in reference and reference["golds"] is not None:
        return [str(item) for item in reference["golds"]]
    if "gold" in reference and reference["gold"] is not None:
        gold = reference["gold"]
        if isinstance(gold, list):
            return [str(item) for item in gold]
        return [str(gold)]
    return []


def verify(output: str, reference: dict) -> dict[str, Any]:
    pred = output.strip()
    golds = _golds(reference)
    if not pred:
        note = json.dumps(
            {
                "unparseable": True,
                "answer_type": reference.get("answer_type"),
                "token_f1": 0.0,
            },
            ensure_ascii=False,
        )
        return {"pass": False, "parsed": None, "note": note}
    pred_n = normalize_answer(pred)
    hit = any(pred_n == normalize_answer(gold) for gold in golds)
    f1 = max((token_f1(pred, gold) for gold in golds), default=0.0)
    note = json.dumps(
        {
            "unparseable": False,
            "answer_type": reference.get("answer_type"),
            "token_f1": f1,
            "norm": pred_n,
        },
        ensure_ascii=False,
    )
    return {"pass": bool(hit), "parsed": pred_n, "note": note}
