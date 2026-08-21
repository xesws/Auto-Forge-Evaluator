"""GSM8K verifier (MANUAL §5)."""

from __future__ import annotations

import json
import re
from typing import Any

# MANUAL: prefer the value after "#### "; optional space after hashes.
_HASH_RE = re.compile(r"####\s*(.+)")
# Integers with commas, decimals, optional sign.
_NUM_RE = re.compile(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")


def _normalize(text: str) -> float | None:
    s = text.strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _extract_hash_raw(output: str) -> str | None:
    matches = _HASH_RE.findall(output)
    if not matches:
        return None
    return matches[-1].strip()


def _extract_last_raw(output: str) -> str | None:
    matches = _NUM_RE.findall(output)
    if not matches:
        return None
    return matches[-1]


def _canonical(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return repr(value)


def verify(output: str, reference: dict) -> dict[str, Any]:
    hash_raw = _extract_hash_raw(output)
    last_raw = _extract_last_raw(output)
    hash_n = _normalize(hash_raw) if hash_raw is not None else None
    last_n = _normalize(last_raw) if last_raw is not None else None

    gold_n = _normalize(str(reference["gold"]))
    diverge = (
        hash_n is not None
        and last_n is not None
        and abs(hash_n - last_n) > 1e-6
    )
    note = json.dumps(
        {
            "hash_raw": hash_raw,
            "last_raw": last_raw,
            "hash_n": hash_n,
            "last_n": last_n,
            "diverge": diverge,
        },
        ensure_ascii=False,
    )

    if hash_n is not None:
        parsed_n = hash_n
    elif last_n is not None:
        parsed_n = last_n
    else:
        return {"pass": False, "parsed": None, "note": note}

    if gold_n is None:
        return {"pass": False, "parsed": None, "note": note}

    passed = abs(parsed_n - gold_n) <= 1e-6
    return {"pass": bool(passed), "parsed": _canonical(parsed_n), "note": note}
