#!/usr/bin/env python3
"""Materialize frozen task packages (MANUAL §4-5)."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sqlite3
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"
CACHE_DIR = ROOT / "data_cache"
PROTOCOL_PATH = ROOT / "configs" / "protocol_v1.yaml"
TAR_NAME = "tasks_v1.tar.gz"
TOP_MANIFEST = "MANIFEST.sha256"
MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024

GSM8K_REV = "740312add88f781978c0658806c59bc2815b9866"
WINOGRANDE_REV = "01e74176c63542e6b0bcb004dcdea22d94fb67b5"
SPIDER_HF_REV = "0c350918f3f29ec754f1181c65cdce76cd6c133c"
SPIDER_DRIVE_ID = "1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J"
SPIDER_PAGE = "https://yale-lily.github.io/spider"

GSM8K_TRAIN_N = 7473
WINOGRANDE_TRAIN_POOL_N = 40398
SPIDER_TRAIN_N = 8659

_HASH_RE = re.compile(r"####\s*(.+)")
_TASK_FILES = ("task.json", "train.jsonl", "eval.jsonl", "verifier.py")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_manifest(task_dir: Path) -> None:
    names = [name for name in _TASK_FILES if (task_dir / name).is_file()]
    extra = sorted(
        p.name
        for p in task_dir.iterdir()
        if p.is_file() and p.name not in names and p.name != "MANIFEST.sha256"
    )
    lines = []
    for name in list(names) + extra:
        lines.append(f"{sha256_file(task_dir / name)}  {name}")
    (task_dir / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_protocol() -> dict[str, Any]:
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


def sample_indices(n: int, k: int, seed: int) -> list[int]:
    if k > n:
        raise SystemExit(f"cannot sample {k} from {n}")
    return random.Random(seed).sample(range(n), k)


def hf_download(repo_id: str, filename: str, revision: str) -> Path:
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        repo_type="dataset",
        revision=revision,
        cache_dir=str(CACHE_DIR / "hf"),
    )
    return Path(path)


def read_parquet(path: Path) -> list[dict[str, Any]]:
    import pandas as pd

    frame = pd.read_parquet(path)
    return frame.to_dict(orient="records")


def dump_task_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def gsm8k_gold(answer: str) -> str:
    matches = _HASH_RE.findall(answer)
    if not matches:
        raise SystemExit("gsm8k gold answer missing #### value")
    return matches[-1].strip()


def build_gsm8k(protocol: dict[str, Any]) -> None:
    train_rows = read_parquet(
        hf_download(
            "openai/gsm8k", "main/train-00000-of-00001.parquet", GSM8K_REV
        )
    )
    test_rows = read_parquet(
        hf_download(
            "openai/gsm8k", "main/test-00000-of-00001.parquet", GSM8K_REV
        )
    )
    if len(train_rows) != GSM8K_TRAIN_N:
        raise SystemExit(
            f"gsm8k train expected {GSM8K_TRAIN_N}, got {len(train_rows)}"
        )
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    eval_idx = sample_indices(len(test_rows), eval_n, eval_seed)

    train_out = []
    for i, row in enumerate(train_rows):
        train_out.append(
            {
                "id": f"gsm8k-train-{i:04d}",
                "messages": [{"role": "user", "content": str(row["question"])}],
                "reference": {"gold": gsm8k_gold(str(row["answer"]))},
            }
        )
    eval_out = []
    for i in eval_idx:
        row = test_rows[i]
        eval_out.append(
            {
                "id": f"gsm8k-test-{i:04d}",
                "messages": [{"role": "user", "content": str(row["question"])}],
                "reference": {"gold": gsm8k_gold(str(row["answer"]))},
            }
        )

    task_dir = TASKS_DIR / "gsm8k"
    task_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(task_dir / "train.jsonl", train_out)
    write_jsonl(task_dir / "eval.jsonl", eval_out)
    dump_task_json(
        task_dir / "task.json",
        {
            "task_id": "gsm8k",
            "source": {
                "dataset": "gsm8k",
                "hf_path": "openai/gsm8k",
                "config": "main",
                "revision": GSM8K_REV,
            },
            "prior_label": None,
            "pool_ref": None,
            "splits": {
                "train_n": len(train_out),
                "eval_n": len(eval_out),
                "seeds": {"eval_slice_seed": eval_seed},
            },
            "max_new_tokens": 512,
            "prompt_style": "user content is the GSM8K question text only",
        },
    )
    write_manifest(task_dir)
    print(f"gsm8k: train={len(train_out)} eval={len(eval_out)}")


def _wino_gold(answer: Any) -> str:
    mapping = {"1": "A", "2": "B"}
    key = str(answer).strip()
    if key not in mapping:
        raise SystemExit(f"winogrande unexpected answer field: {answer!r}")
    return mapping[key]


def _wino_prompt(row: dict[str, Any]) -> str:
    return (
        f"{row['sentence']}\n"
        f"A. {row['option1']}\n"
        f"B. {row['option2']}\n"
        "Reply with only the letter A or B."
    )


def build_winogrande(protocol: dict[str, Any]) -> None:
    train_rows = read_parquet(
        hf_download(
            "allenai/winogrande",
            "winogrande_xl/train-00000-of-00001.parquet",
            WINOGRANDE_REV,
        )
    )
    val_rows = read_parquet(
        hf_download(
            "allenai/winogrande",
            "winogrande_xl/validation-00000-of-00001.parquet",
            WINOGRANDE_REV,
        )
    )
    if len(train_rows) != WINOGRANDE_TRAIN_POOL_N:
        raise SystemExit(
            f"winogrande train pool expected {WINOGRANDE_TRAIN_POOL_N}, got {len(train_rows)}"
        )
    train_seed = int(protocol["full"]["sample_seed"])
    train_cap = int(protocol["full"]["cap"])
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    train_idx = sample_indices(len(train_rows), train_cap, train_seed)
    eval_idx = sample_indices(len(val_rows), eval_n, eval_seed)

    train_out = []
    for i in train_idx:
        row = train_rows[i]
        train_out.append(
            {
                "id": f"winogrande-train-{i:05d}",
                "messages": [{"role": "user", "content": _wino_prompt(row)}],
                "reference": {"gold": _wino_gold(row["answer"])},
            }
        )
    eval_out = []
    for i in eval_idx:
        row = val_rows[i]
        eval_out.append(
            {
                "id": f"winogrande-validation-{i:04d}",
                "messages": [{"role": "user", "content": _wino_prompt(row)}],
                "reference": {"gold": _wino_gold(row["answer"])},
            }
        )

    task_dir = TASKS_DIR / "winogrande"
    task_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(task_dir / "train.jsonl", train_out)
    write_jsonl(task_dir / "eval.jsonl", eval_out)
    dump_task_json(
        task_dir / "task.json",
        {
            "task_id": "winogrande",
            "source": {
                "dataset": "winogrande",
                "hf_path": "allenai/winogrande",
                "config": "winogrande_xl",
                "revision": WINOGRANDE_REV,
            },
            "prior_label": None,
            "pool_ref": None,
            "splits": {
                "train_n": len(train_out),
                "eval_n": len(eval_out),
                "seeds": {
                    "train_sample_seed": train_seed,
                    "eval_slice_seed": eval_seed,
                },
            },
            "max_new_tokens": 16,
            "prompt_style": (
                "sentence plus options A/B; instruction to reply with only the letter"
            ),
        },
    )
    write_manifest(task_dir)
    print(f"winogrande: train={len(train_out)} eval={len(eval_out)}")


def _gdrive_download(file_id: str, dest: Path) -> None:
    try:
        import gdown
    except ImportError as exc:
        raise SystemExit("gdown is required for Spider: pip install gdown") from exc
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Spider DB zip: official Yale GDrive id={file_id} page={SPIDER_PAGE}")
    print(f"MANUAL §5 says ~100MB; abort if downloaded bytes > {MAX_DOWNLOAD_BYTES}")
    out = gdown.download(id=file_id, output=str(dest), quiet=False)
    if not out:
        raise SystemExit("gdown failed to download Spider zip")
    size = dest.stat().st_size
    print(f"Spider zip bytes={size} sha256={sha256_file(dest)}")
    if size > MAX_DOWNLOAD_BYTES:
        dest.unlink()
        raise SystemExit(
            f"Spider zip {size} bytes exceeds {MAX_DOWNLOAD_BYTES}; deleted, not extracted"
        )


def _find_spider_root(extract_dir: Path) -> Path:
    hits = list(extract_dir.rglob("train_spider.json"))
    if len(hits) != 1:
        raise SystemExit(f"expected one train_spider.json, found {len(hits)}")
    return hits[0].parent


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit(f"{path} is not a JSON list")
    return payload


def _create_table_schema(db_path: Path) -> str:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    parts = []
    for (sql,) in rows:
        text = str(sql).rstrip()
        if not text.endswith(";"):
            text += ";"
        parts.append(text)
    if not parts:
        raise SystemExit(f"no CREATE TABLE statements in {db_path}")
    return "\n".join(parts)


def _spider_db_path(db_root: Path, db_id: str) -> Path:
    direct = db_root / db_id / f"{db_id}.sqlite"
    if direct.is_file():
        return direct
    matches = list((db_root / db_id).glob("*.sqlite"))
    if len(matches) == 1:
        return matches[0]
    raise SystemExit(f"sqlite file not found for db_id={db_id}")


def _spider_prompt(schema: str, question: str) -> str:
    return f"{schema}\n\nQuestion: {question}"


def build_spider(protocol: dict[str, Any]) -> None:
    zip_path = CACHE_DIR / "spider" / "spider.zip"
    extract_dir = CACHE_DIR / "spider" / "extract"
    if not zip_path.is_file():
        _gdrive_download(SPIDER_DRIVE_ID, zip_path)
    else:
        print(f"Spider zip cache hit {zip_path} sha256={sha256_file(zip_path)}")
        if zip_path.stat().st_size > MAX_DOWNLOAD_BYTES:
            raise SystemExit("cached Spider zip exceeds 500MB")

    if not (extract_dir / ".done").is_file():
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        (extract_dir / ".done").write_text("ok\n", encoding="utf-8")

    spider_root = _find_spider_root(extract_dir)
    train_spider = _load_json_list(spider_root / "train_spider.json")
    train_others = _load_json_list(spider_root / "train_others.json")
    dev = _load_json_list(spider_root / "dev.json")
    train_rows = train_spider + train_others
    if len(train_rows) != SPIDER_TRAIN_N:
        raise SystemExit(
            f"spider train expected {SPIDER_TRAIN_N} "
            f"(train_spider={len(train_spider)} + train_others={len(train_others)}), "
            f"got {len(train_rows)}"
        )
    if len(dev) < int(protocol["eval"]["slice_n"]):
        raise SystemExit(f"spider dev too small: {len(dev)}")

    db_root = spider_root / "database"
    if not db_root.is_dir():
        raise SystemExit(f"spider database dir missing under {spider_root}")

    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    eval_idx = sample_indices(len(dev), eval_n, eval_seed)

    schema_cache: dict[str, str] = {}

    def rel_db(db_id: str) -> str:
        abs_path = _spider_db_path(db_root, db_id)
        try:
            return str(abs_path.relative_to(ROOT))
        except ValueError:
            return str(abs_path)

    def schema(db_id: str) -> str:
        if db_id not in schema_cache:
            schema_cache[db_id] = _create_table_schema(_spider_db_path(db_root, db_id))
        return schema_cache[db_id]

    def to_row(prefix: str, idx: int, item: dict[str, Any]) -> dict[str, Any]:
        db_id = str(item["db_id"])
        db_path = rel_db(db_id)
        return {
            "id": f"{prefix}-{idx:04d}",
            "messages": [
                {
                    "role": "user",
                    "content": _spider_prompt(schema(db_id), str(item["question"])),
                }
            ],
            "reference": {
                "query": str(item["query"]),
                "db_id": db_id,
                "db_path": db_path,
            },
        }

    train_out = [to_row("spider-train", i, item) for i, item in enumerate(train_rows)]
    eval_out = [to_row("spider-dev", i, dev[i]) for i in eval_idx]

    zip_sha = sha256_file(zip_path)
    task_dir = TASKS_DIR / "spider"
    task_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(task_dir / "train.jsonl", train_out)
    write_jsonl(task_dir / "eval.jsonl", eval_out)
    dump_task_json(
        task_dir / "task.json",
        {
            "task_id": "spider",
            "source": {
                "dataset": "spider",
                "hf_path": "xlangai/spider",
                "config": "spider",
                "revision": SPIDER_HF_REV,
                "database": {
                    "page": SPIDER_PAGE,
                    "drive_id": SPIDER_DRIVE_ID,
                    "filename": zip_path.name,
                    "sha256": zip_sha,
                    "bytes": zip_path.stat().st_size,
                    "local_dir": str((CACHE_DIR / "spider").relative_to(ROOT)),
                },
            },
            "prior_label": None,
            "pool_ref": None,
            "splits": {
                "train_n": len(train_out),
                "eval_n": len(eval_out),
                "seeds": {"eval_slice_seed": eval_seed},
            },
            "max_new_tokens": 256,
            "prompt_style": (
                "CREATE TABLE statements from sqlite_master, then the question"
            ),
        },
    )
    write_manifest(task_dir)
    print(f"spider: train={len(train_out)} eval={len(eval_out)} zip_sha={zip_sha}")


def pack_tar(task_ids: list[str]) -> None:
    tar_path = ROOT / TAR_NAME
    if tar_path.exists():
        raise SystemExit(f"{TAR_NAME} already exists; versions only increase")
    with tarfile.open(tar_path, "w:gz") as tar:
        for task_id in task_ids:
            task_dir = TASKS_DIR / task_id
            for name in (*_TASK_FILES, "MANIFEST.sha256"):
                path = task_dir / name
                if not path.is_file():
                    raise SystemExit(f"missing {path}")
                tar.add(path, arcname=f"tasks/{task_id}/{name}")
    lines = [f"{sha256_file(tar_path)}  {TAR_NAME}"]
    for task_id in task_ids:
        manifest = TASKS_DIR / task_id / "MANIFEST.sha256"
        lines.append(f"{sha256_file(manifest)}  tasks/{task_id}/MANIFEST.sha256")
        for name in _TASK_FILES:
            path = TASKS_DIR / task_id / name
            lines.append(f"{sha256_file(path)}  tasks/{task_id}/{name}")
    (ROOT / TOP_MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {tar_path} and {TOP_MANIFEST}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize tasks_v1 packages")
    parser.add_argument(
        "--task",
        choices=("gsm8k", "winogrande", "spider", "all"),
        default="all",
    )
    parser.add_argument(
        "--pack",
        action="store_true",
        help="write tasks_v1.tar.gz and top-level MANIFEST.sha256 after building",
    )
    parser.add_argument(
        "--pack-only",
        action="store_true",
        help="only write tasks_v1.tar.gz and top-level MANIFEST.sha256",
    )
    args = parser.parse_args()
    if args.pack_only:
        pack_tar(["gsm8k", "winogrande", "spider"])
        return
    protocol = load_protocol()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wanted = ("gsm8k", "winogrande", "spider") if args.task == "all" else (args.task,)
    builders = {
        "gsm8k": build_gsm8k,
        "winogrande": build_winogrande,
        "spider": build_spider,
    }
    for task_id in wanted:
        builders[task_id](protocol)
    if args.pack or args.task == "all":
        pack_tar(["gsm8k", "winogrande", "spider"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
