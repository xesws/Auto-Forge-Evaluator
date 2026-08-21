"""WinoGrande verifier (MANUAL §5)."""

from __future__ import annotations

import json
import re
from typing import Any

# First A/B, tolerating "A.", "答案:A", "Answer: B", "(A)", "[B]".
# Lowercase a/b is accepted only in those explicit answer patterns.
# Bare English article "a" is not an answer.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"答案\s*[:：]\s*([ABab])"),
    re.compile(r"[Aa]nswer\s*[:：]\s*([ABab])"),
    re.compile(r"\[\s*([ABab])\s*\]"),
    re.compile(r"\(\s*([ABab])\s*\)"),
    re.compile(r"\b([ABab])[.)]"),
    re.compile(r"(?m)^\s*([ABab])\s*$"),
    re.compile(r"\b([AB])\b"),
)


def _parse_choice(output: str) -> str | None:
    hits: list[tuple[int, str]] = []
    for pat in _PATTERNS:
        for match in pat.finditer(output):
            hits.append((match.start(), match.group(1).upper()))
    if not hits:
        return None
    hits.sort(key=lambda item: item[0])
    return hits[0][1]


def verify(output: str, reference: dict) -> dict[str, Any]:
    parsed = _parse_choice(output)
    gold = str(reference["gold"]).strip().upper()
    if parsed is None:
        note = json.dumps({"unparseable": True}, ensure_ascii=False)
        return {"pass": False, "parsed": None, "note": note}
    note = json.dumps({"unparseable": False, "gold": gold}, ensure_ascii=False)
    return {"pass": parsed == gold, "parsed": parsed, "note": note}
