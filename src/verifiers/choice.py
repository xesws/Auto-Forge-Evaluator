"""N-way multiple choice. WinoGrande A/B patterns generalized to A.. letters."""

from __future__ import annotations

import json
import re
from typing import Any


def _letters(n: int) -> str:
    if n < 2 or n > 26:
        raise ValueError(f"n_choices out of range: {n}")
    return "".join(chr(ord("A") + i) for i in range(n))


def _n_choices(reference: dict) -> int:
    if reference.get("n_choices") is not None:
        return int(reference["n_choices"])
    choices = reference.get("choices")
    if isinstance(choices, list) and len(choices) >= 2:
        return len(choices)
    gold = str(reference.get("gold", "A")).strip().upper()
    if len(gold) == 1 and "A" <= gold <= "Z":
        return max(2, ord(gold) - ord("A") + 1)
    return 2


def _patterns(letters: str) -> tuple[re.Pattern[str], ...]:
    both = f"[{letters}{letters.lower()}]"
    upper = f"[{letters}]"
    return (
        re.compile(rf"答案\s*[:：]\s*({both})"),
        re.compile(rf"[Aa]nswer\s*[:：]\s*({both})"),
        re.compile(rf"\[\s*({both})\s*\]"),
        re.compile(rf"\(\s*({both})\s*\)"),
        re.compile(rf"\b({both})[.)]"),
        re.compile(rf"(?m)^\s*({both})\s*$"),
        re.compile(rf"\b({upper})\b"),
    )


def _parse_choice(output: str, letters: str) -> str | None:
    hits: list[tuple[int, str]] = []
    for pat in _patterns(letters):
        for match in pat.finditer(output):
            hits.append((match.start(), match.group(1).upper()))
    if not hits:
        return None
    hits.sort(key=lambda item: item[0])
    parsed = hits[0][1]
    if parsed not in letters:
        return None
    return parsed


def verify(output: str, reference: dict) -> dict[str, Any]:
    n = _n_choices(reference)
    letters = _letters(n)
    parsed = _parse_choice(output, letters)
    gold = str(reference["gold"]).strip().upper()
    if parsed is None:
        note = json.dumps(
            {"unparseable": True, "n_choices": n}, ensure_ascii=False
        )
        return {"pass": False, "parsed": None, "note": note}
    note = json.dumps(
        {"unparseable": False, "gold": gold, "n_choices": n}, ensure_ascii=False
    )
    return {"pass": parsed == gold, "parsed": parsed, "note": note}
