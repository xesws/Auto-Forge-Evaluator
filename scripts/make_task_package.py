#!/usr/bin/env python3
"""Materialize frozen task packages (MANUAL §4-5)."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
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
PROTOCOL_PATH = ROOT / "configs" / "protocol_v2.yaml"
TOP_MANIFEST = "MANIFEST.sha256"
MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024
PROMPT_TOKEN_LIMIT = 4000

GSM8K_REV = "740312add88f781978c0658806c59bc2815b9866"
WINOGRANDE_REV = "01e74176c63542e6b0bcb004dcdea22d94fb67b5"
SPIDER_HF_REV = "0c350918f3f29ec754f1181c65cdce76cd6c133c"
SPIDER_DRIVE_ID = "1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J"
SPIDER_PAGE = "https://yale-lily.github.io/spider"
SPIDER_ZIP_SHA256 = (
    "00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b"
)
PINNED_TARBALLS = {
    1: "2f12baddaf5bf2e6869f427dca8d660d27ae0945a25cc0be3fc1b78862d72380",
    2: "794ec0ea78ae6a6a1b526b7682632d378d6bdd439b68e32680ebe00c2c457d48",
    3: "1deaedcb91d3c98a5c02688f0e83b3a3d124b58a8a5bded570ea2bd2b0f36db0",
    4: "3021a45c78ee182ff2610a83121573ef3f1accae67e5d92a0eaf2f84c8a4c8b0",
    5: "cf25de9ca1c889e75e33a5ce484e0374c4881da422401dad7b01ffce5b338983",
}
GSM8K_MIN_MEAN_COMPLETION = 100

GSM8K_INSTRUCTION = (
    "Reason step by step, then give the final answer on the "
    "last line in the form: #### <number>"
)

TASK_LABELS = {
    "gsm8k": {
        "prior_label": "strong-gain",
        "pool_ref": (
            "pool_v0.2 GSM8K rows: 2503.18892 Table1 "
            "(greedy_vs_temp1 注记), 2502.02737, 2606.06920"
        ),
    },
    "winogrande": {
        "prior_label": "weak-or-no-gain",
        "pool_ref": (
            "pool_v0.2 WinoGrande rows: 2505.12716 "
            "Table11 (51.9→51.2 / 51.4)"
        ),
    },
    "spider": {
        "prior_label": "strong-gain",
        "pool_ref": (
            "pool_v0.2 Spider rows: 2402.16347 "
            "Table4/5 (icl_vs_sft 注记)"
        ),
    },
}

LOG = logging.getLogger("make_task_package")

GSM8K_TRAIN_N = 7473
WINOGRANDE_TRAIN_POOL_N = 40398
SPIDER_TRAIN_N = 8659

_HASH_RE = re.compile(r"####\s*(.+)")
_CALC_RE = re.compile(r"<<[^>]*>>")
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


def gsm8k_solution(answer: str) -> str:
    """Official GSM8K solution: drop <<calc>> annotations, keep steps and #### N."""
    return _CALC_RE.sub("", str(answer)).strip()


def gsm8k_user_content(question: str) -> str:
    return f"{question}\n{GSM8K_INSTRUCTION}"


_TOKENIZER = None
_TOKENIZER_NAME = "unavailable"


def count_tokens(text: str) -> tuple[int, str]:
    """Return (n_tokens, tokenizer_id). Falls back to char/3 if no tokenizer."""
    global _TOKENIZER, _TOKENIZER_NAME
    if _TOKENIZER is None and _TOKENIZER_NAME != "char/3":
        try:
            from transformers import AutoTokenizer

            _TOKENIZER = AutoTokenizer.from_pretrained(
                "Qwen/Qwen2.5-1.5B-Instruct",
                use_fast=True,
            )
            _TOKENIZER_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
        except Exception as exc:  # noqa: BLE001
            LOG.warning("tokenizer unavailable (%s); using char/3 estimate", exc)
            _TOKENIZER_NAME = "char/3"
    if _TOKENIZER is not None:
        return len(_TOKENIZER.encode(text, add_special_tokens=False)), _TOKENIZER_NAME
    return max(1, (len(text) + 2) // 3), "char/3"


def log_if_over_token_limit(example_id: str, text: str) -> None:
    n_tokens, method = count_tokens(text)
    if n_tokens > PROMPT_TOKEN_LIMIT:
        LOG.warning(
            "prompt over %s tokens: id=%s n_tokens=%s method=%s",
            PROMPT_TOKEN_LIMIT,
            example_id,
            n_tokens,
            method,
        )


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
        answer = str(row["answer"])
        train_out.append(
            {
                "id": f"gsm8k-train-{i:04d}",
                "messages": [{"role": "user", "content": gsm8k_user_content(str(row["question"]))}],
                "reference": {
                    "gold": gsm8k_gold(answer),
                    "solution": gsm8k_solution(answer),
                },
            }
        )
    mean_len = sum(len(row["reference"]["solution"]) for row in train_out) / len(
        train_out
    )
    if mean_len <= GSM8K_MIN_MEAN_COMPLETION:
        raise SystemExit(
            f"gsm8k train completion mean length {mean_len:.1f} "
            f"<= {GSM8K_MIN_MEAN_COMPLETION} (answer-only regression?)"
        )
    eval_out = []
    for i in eval_idx:
        row = test_rows[i]
        eval_out.append(
            {
                "id": f"gsm8k-test-{i:04d}",
                "messages": [{"role": "user", "content": gsm8k_user_content(str(row["question"]))}],
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
            "prior_label": TASK_LABELS["gsm8k"]["prior_label"],
            "pool_ref": TASK_LABELS["gsm8k"]["pool_ref"],
            "splits": {
                "train_n": len(train_out),
                "eval_n": len(eval_out),
                "seeds": {"eval_slice_seed": eval_seed},
            },
            "max_new_tokens": 512,
            "prompt_style": (
                "GSM8K question, then one instruction line: "
                + GSM8K_INSTRUCTION
            ),
        },
    )
    write_manifest(task_dir)
    print(
        f"gsm8k: train={len(train_out)} eval={len(eval_out)} "
        f"train_completion_mean_len={mean_len:.1f}"
    )


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
            "prior_label": TASK_LABELS["winogrande"]["prior_label"],
            "pool_ref": TASK_LABELS["winogrande"]["pool_ref"],
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
    zip_sha = sha256_file(zip_path)
    if zip_sha != SPIDER_ZIP_SHA256:
        raise SystemExit(
            f"Spider zip sha256 mismatch: got {zip_sha}, pinned {SPIDER_ZIP_SHA256}"
        )

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
        example_id = f"{prefix}-{idx:04d}"
        content = _spider_prompt(schema(db_id), str(item["question"]))
        log_if_over_token_limit(example_id, content)
        return {
            "id": example_id,
            "messages": [
                {
                    "role": "user",
                    "content": content,
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
                "yale_zip_gdrive_id": SPIDER_DRIVE_ID,
                "sha256": zip_sha,
                "train": "train_spider + train_others = 8659",
                "database": {
                    "page": SPIDER_PAGE,
                    "drive_id": SPIDER_DRIVE_ID,
                    "filename": zip_path.name,
                    "sha256": zip_sha,
                    "bytes": zip_path.stat().st_size,
                    "local_dir": str((CACHE_DIR / "spider").relative_to(ROOT)),
                },
            },
            "prior_label": TASK_LABELS["spider"]["prior_label"],
            "pool_ref": TASK_LABELS["spider"]["pool_ref"],
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


def pack_tar(task_ids: list[str], version: int) -> None:
    tar_name = f"tasks_v{version}.tar.gz"
    tar_path = ROOT / tar_name
    if tar_path.exists():
        raise SystemExit(f"{tar_name} already exists; versions only increase")
    with tarfile.open(tar_path, "w:gz") as tar:
        for task_id in task_ids:
            task_dir = TASKS_DIR / task_id
            for name in (*_TASK_FILES, "MANIFEST.sha256"):
                path = task_dir / name
                if not path.is_file():
                    raise SystemExit(f"missing {path}")
                tar.add(path, arcname=f"tasks/{task_id}/{name}")
    lines = ["# published tarballs (never overwrite)"]
    listed = set()
    for ver, pinned in sorted(PINNED_TARBALLS.items()):
        name = f"tasks_v{ver}.tar.gz"
        path = ROOT / name
        if path.is_file():
            digest = sha256_file(path)
            if digest != pinned:
                raise SystemExit(f"{name} sha256 {digest} != pinned {pinned}")
        lines.append(f"{pinned}  {name}")
        listed.add(name)
    new_digest = sha256_file(tar_path)
    if tar_name not in listed:
        lines.append(f"{new_digest}  {tar_name}")
    elif PINNED_TARBALLS.get(version) not in (None, new_digest):
        raise SystemExit(f"new {tar_name} hash {new_digest} != pin")
    lines.append("# current unpacked files (match the newest tarball)")
    unpacked = sorted(
        p.name
        for p in TASKS_DIR.iterdir()
        if p.is_dir() and (p / "task.json").is_file()
    )
    for task_id in unpacked:
        manifest = TASKS_DIR / task_id / "MANIFEST.sha256"
        lines.append(f"{sha256_file(manifest)}  tasks/{task_id}/MANIFEST.sha256")
        for name in _TASK_FILES:
            path = TASKS_DIR / task_id / name
            lines.append(f"{sha256_file(path)}  tasks/{task_id}/{name}")
    (ROOT / TOP_MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {tar_path} sha256={new_digest} and {TOP_MANIFEST}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Materialize frozen task packages")
    parser.add_argument(
        "--task",
        choices=("gsm8k", "winogrande", "spider", "all"),
        default="all",
    )
    parser.add_argument(
        "--pack",
        action="store_true",
        help="write tasks_vN.tar.gz and top-level MANIFEST.sha256 after building",
    )
    parser.add_argument(
        "--pack-only",
        action="store_true",
        help="only write tasks_vN.tar.gz and top-level MANIFEST.sha256",
    )
    parser.add_argument("--pack-version", type=int, default=3)
    args = parser.parse_args()
    if args.pack_only:
        pack_tar(["gsm8k", "winogrande", "spider"], version=args.pack_version)
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
    if args.pack:
        pack_tar(["gsm8k", "winogrande", "spider"], version=args.pack_version)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
