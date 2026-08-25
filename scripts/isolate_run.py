#!/usr/bin/env python3
"""Move a failed run dir to runs/_isolated/ as evidence. Do not delete."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def isolate_run(run_dir: Path, isolated_root: Path | None = None) -> Path:
    src = run_dir.resolve()
    if not src.is_dir():
        raise SystemExit(f"not a run dir: {src}")
    dest_root = isolated_root.resolve() if isolated_root else src.parent / "_isolated"
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / src.name
    if dest.exists():
        raise SystemExit(f"already isolated: {dest}")
    shutil.move(str(src), str(dest))
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolate a failed run dir in place")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--isolated-root", default="")
    args = parser.parse_args()
    dest = isolate_run(
        Path(args.run_dir),
        Path(args.isolated_root) if args.isolated_root else None,
    )
    print(dest)


if __name__ == "__main__":
    main()
