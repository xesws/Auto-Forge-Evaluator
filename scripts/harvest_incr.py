#!/usr/bin/env python3
"""Incremental runs tar without adapters. Called after every 10 GPU tasks."""

from __future__ import annotations

import argparse
import hashlib
import tarfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--run-dir", action="append", dest="run_dirs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tar:
        for raw in args.run_dirs:
            run_dir = Path(raw).resolve()
            if not run_dir.is_dir():
                continue
            for path in sorted(run_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(run_dir.parent)
                if "adapters" in rel.parts:
                    continue
                tar.add(path, arcname=str(rel))
    digest = sha256_file(out)
    (out.parent / f"{out.name}.sha256").write_text(f"{digest}  {out.name}\n")
    print(f"{digest}  {out}")


if __name__ == "__main__":
    main()
