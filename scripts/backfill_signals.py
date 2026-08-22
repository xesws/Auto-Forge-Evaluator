#!/usr/bin/env python3
"""Backfill metrics.json signals from existing logs. No scores or protocol change."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.signals import build_signal_vector  # noqa: E402

ABS_TOL = 1e-12


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= ABS_TOL


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill derived signals into metrics.json")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--loss-log", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    loss_log = Path(args.loss_log).resolve()
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    task_id = str(metrics["task_id"])
    snapshot = json.loads(metrics_path.read_text(encoding="utf-8"))
    signals = build_signal_vector(run_dir, task_id=task_id, loss_path=loss_log)
    if not _close(signals["delta_pilot"], metrics["delta_pilot"]["delta_pilot"]):
        raise SystemExit(
            f"delta_pilot mismatch: {signals['delta_pilot']} vs {metrics['delta_pilot']['delta_pilot']}"
        )
    if not _close(signals["base_pass1"], metrics["base"]["pass1"]):
        raise SystemExit(
            f"base_pass1 mismatch: {signals['base_pass1']} vs {metrics['base']['pass1']}"
        )
    if not _close(signals["base_pass8"], metrics["base"]["pass8"]):
        raise SystemExit(
            f"base_pass8 mismatch: {signals['base_pass8']} vs {metrics['base']['pass8']}"
        )
    metrics["signals"] = signals
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rewritten = json.loads(metrics_path.read_text(encoding="utf-8"))
    for key in snapshot:
        if key == "signals":
            continue
        if rewritten[key] != snapshot[key]:
            raise SystemExit(f"backfill mutated key {key}")
    print(json.dumps(signals, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
