"""pass@1 / pass@8 signals (MANUAL §2, §6). Labels are always greedy pass@1."""

from __future__ import annotations

from typing import Any


def pass_at_1(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    hits = 0
    for row in results:
        samples = row["samples"]
        hits += int(bool(samples and samples[0]["pass"]))
    return hits / len(results)


def pass_at_k(results: list[dict[str, Any]]) -> float:
    """Fraction of examples with at least one passing sample (pass@k)."""
    if not results:
        return 0.0
    hits = 0
    for row in results:
        hits += int(any(sample["pass"] for sample in row["samples"]))
    return hits / len(results)
