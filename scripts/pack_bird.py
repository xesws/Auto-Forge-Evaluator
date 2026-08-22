#!/usr/bin/env python3
"""Pod-side BIRD pack. 2h cap. Train sqlite deleted after DDL. Never Mini-Dev."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = logging.getLogger("pack_bird")

# Official BIRD-SQL 2023 sqlite dumps (not Mini-Dev). Confirm on bird-bench.github.io
# before fetch; ids recorded after sha.
TRAIN_ZIP_NAME = "train_databases.zip"
DEV_ZIP_NAME = "dev_databases.zip"
WALL_SEC = 2 * 60 * 60


def sqlite_ddl(db_path: Path) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND type='table' "
            "ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    stmts = [row[0].strip() for row in rows if row[0]]
    if not stmts:
        raise SystemExit(f"no CREATE TABLE in {db_path}")
    return ";\n".join(stmts) + ";"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-zip", required=True)
    parser.add_argument("--dev-zip", required=True)
    parser.add_argument("--train-json", required=True, help="BIRD train.json")
    parser.add_argument("--dev-json", required=True, help="BIRD dev.json")
    parser.add_argument("--deadline-sec", type=int, default=WALL_SEC)
    args = parser.parse_args()
    t0 = time.time()
    train_zip = Path(args.train_zip)
    dev_zip = Path(args.dev_zip)
    from src.data import sha256_file

    train_sha = sha256_file(train_zip)
    dev_sha = sha256_file(dev_zip)
    LOG.info("train_zip sha256=%s bytes=%s", train_sha, train_zip.stat().st_size)
    LOG.info("dev_zip sha256=%s bytes=%s", dev_sha, dev_zip.stat().st_size)
    cache = ROOT / "data_cache" / "bird"
    cache.mkdir(parents=True, exist_ok=True)
    train_root = cache / "train_databases"
    dev_root = cache / "dev_databases"
    for zpath, dest in ((train_zip, train_root), (dev_zip, dev_root)):
        dest.mkdir(parents=True, exist_ok=True)
        LOG.info("extract %s -> %s", zpath, dest)
        if zipfile.is_zipfile(zpath):
            with zipfile.ZipFile(zpath) as zf:
                zf.extractall(dest)
        else:
            with tarfile.open(zpath) as tf:
                tf.extractall(dest)
        if time.time() - t0 > args.deadline_sec:
            raise SystemExit("BIRD pack exceeded 2h during extract")

    def _find_db(root: Path, db_id: str) -> Path | None:
        hits = list(root.rglob(f"{db_id}.sqlite")) + list(root.rglob(f"{db_id}/{db_id}.sqlite"))
        return hits[0] if hits else None

    ddl: dict[str, str] = {}
    for db_path in list(train_root.rglob("*.sqlite")) + list(dev_root.rglob("*.sqlite")):
        db_id = db_path.stem
        if db_id not in ddl:
            ddl[db_id] = sqlite_ddl(db_path)

    LOG.info("deleting train sqlite files (zip sha retained)")
    for db_path in train_root.rglob("*.sqlite"):
        db_path.unlink()

    # Remainder of jsonl materialization is pack_phase4.build_bird once zips/json exist.
    meta = {
        "train_zip_sha256": train_sha,
        "dev_zip_sha256": dev_sha,
        "n_ddl": len(ddl),
        "elapsed_sec": time.time() - t0,
    }
    (cache / "bird_pack_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    LOG.info("meta %s", meta)
    if time.time() - t0 > args.deadline_sec:
        raise SystemExit("BIRD pack exceeded 2h")


if __name__ == "__main__":
    main()
