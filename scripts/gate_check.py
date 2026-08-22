#!/usr/bin/env python3
"""Post-S6 five-eye automation. Spec: docs/ANALYSIS_PREREG_SUPPLEMENT.md."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import load_jsonl  # noqa: E402

UNPARSEABLE_MAX = 0.05
SYSTEMS_KEYS = (
    "torch",
    "transformers",
    "cuda",
    "driver",
    "gpu_name",
    "base_revision",
    "seeds",
    "dry_run",
)


def _note(sample: dict[str, Any]) -> dict[str, Any]:
    raw = sample.get("note") or "{}"
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except json.JSONDecodeError:
        return {}


def unparseable_rate(path: Path) -> tuple[int, int, float]:
    if not path.is_file():
        return 0, 0, 1.0
    rows = load_jsonl(path)
    bad = 0
    for row in rows:
        sample = row["samples"][0]
        note = _note(sample)
        if sample.get("parsed") is None or note.get("unparseable") is True:
            bad += 1
    n = len(rows)
    return bad, n, (1.0 if n == 0 else bad / n)


def check_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else {}
    bad, n, rate = unparseable_rate(run_dir / "eval_base_greedy.jsonl")
    unp_ok = n > 0 and rate < UNPARSEABLE_MAX
    loss = (metrics.get("signals") or {}).get("pilot_loss") or {}
    start = loss.get("start")
    end = loss.get("end")
    source = loss.get("source")
    loss_ok = (
        source not in (None, "missing")
        and start is not None
        and end is not None
        and float(end) < float(start)
    )
    systems = metrics.get("systems") or {}
    missing = [key for key in SYSTEMS_KEYS if key not in systems]
    dry = systems.get("dry_run")
    systems_ok = not missing and dry is False
    rerun_path = run_dir / "eval_base_greedy_rerun.jsonl"
    det: dict[str, Any] = {"skipped": not rerun_path.is_file()}
    det_ok = True
    if rerun_path.is_file():
        orig = {
            row["id"]: row["samples"][0]["pass"]
            for row in load_jsonl(run_dir / "eval_base_greedy.jsonl")
        }
        new = {
            row["id"]: row["samples"][0]["pass"]
            for row in load_jsonl(rerun_path)
        }
        extra = [key for key in new if key not in orig]
        mismatch = [key for key in new if orig.get(key) != new[key]]
        det = {
            "skipped": False,
            "n_orig": len(orig),
            "n_rerun": len(new),
            "mismatch": len(mismatch),
            "extra": len(extra),
        }
        det_ok = len(mismatch) == 0 and len(extra) == 0 and len(new) > 0
    passed = bool(unp_ok and loss_ok and systems_ok and det_ok)
    return {
        "pass": passed,
        "unparseable": {"bad": bad, "n": n, "rate": rate, "ok": unp_ok},
        "loss": {"start": start, "end": end, "source": source, "ok": loss_ok},
        "systems": {"missing": missing, "dry_run": dry, "ok": systems_ok},
        "determinism": {**det, "ok": det_ok},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="S6 five-eye gate")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    report = check_run(run_dir)
    out = run_dir / "gate_check.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
