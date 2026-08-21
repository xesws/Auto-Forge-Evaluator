#!/usr/bin/env python3
"""Backfill metrics.json format_compliance from existing greedy jsonl. No scores change."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import format_compliance_block  # noqa: E402


def main() -> None:
    run_dir = Path(sys.argv[1]).resolve()
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    task_id = str(metrics["task_id"])
    metrics["format_compliance"] = format_compliance_block(run_dir, task_id)
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics["format_compliance"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
