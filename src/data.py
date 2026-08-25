"""Task loading, hashing, chat examples, and storage (MANUAL §4, §7)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
from pathlib import Path
from typing import Any, Callable

import yaml

LOG = logging.getLogger("forge.data")
PROMPT_TOKEN_LIMIT = 4000


class Storage:
    def put(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def list(self, prefix: str = "") -> list[str]:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError(f"storage key escapes root: {key}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def list(self, prefix: str = "") -> list[str]:
        base = self._path(prefix) if prefix else self.root
        if base.is_file():
            return [prefix]
        if not base.exists():
            return []
        out = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                out.append(str(path.relative_to(self.root)))
        return out


class S3Storage(Storage):
    """Stub. Credentials from the environment; not configured in this phase."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "S3Storage stub: credentials via AWS_ACCESS_KEY_ID / "
            "AWS_SECRET_ACCESS_KEY / S3_BUCKET. Not configured this phase."
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_protocol(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_task_json(task_dir: Path) -> dict[str, Any]:
    return json.loads((task_dir / "task.json").read_text(encoding="utf-8"))


def verify_task_manifest(task_dir: Path) -> None:
    manifest = task_dir / "MANIFEST.sha256"
    if not manifest.is_file():
        raise SystemExit(f"missing {manifest}")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, name = line.split()
        path = task_dir / name
        if not path.is_file():
            raise SystemExit(f"manifest file missing: {path}")
        got = sha256_file(path)
        if got != digest:
            raise SystemExit(f"hash mismatch {path}: got {got} expected {digest}")


def verify_spider_zip(task: dict[str, Any], repo_root: Path) -> None:
    expected = str(task["source"]["sha256"])
    zip_path = repo_root / "data_cache" / "spider" / "spider.zip"
    gdrive_id = task["source"].get("yale_zip_gdrive_id", "")
    if not zip_path.is_file():
        raise SystemExit(
            f"Spider zip missing at {zip_path}. Download Yale GDrive id={gdrive_id} "
            f"and verify sha256={expected} before consuming this task."
        )
    got = sha256_file(zip_path)
    if got != expected:
        raise SystemExit(
            f"Spider zip sha256 {got} != pinned {expected}. Refuse to run."
        )


BIRD_TRAIN_ZIP_NAMES = ("train_databases.zip", "train.zip")
BIRD_DEV_ZIP_NAMES = ("dev_databases.zip", "dev.zip")
BIRD_DEV_EXTRACT_NAMES = ("dev_extract", "dev_databases")
BIRD_TRAIN_EXTRACT_NAMES = ("train_extract", "train_databases")


def bird_dual_shas(task: dict[str, Any]) -> tuple[str, str]:
    """Frozen dual-sha schema. `source.sha256` is not a BIRD field."""
    source = task.get("source") or {}
    train_sha = source.get("train_zip_sha256")
    dev_sha = source.get("dev_zip_sha256")
    if not train_sha or not dev_sha:
        raise SystemExit(
            "BIRD task.json must pin source.train_zip_sha256 and "
            "source.dev_zip_sha256 (dual sha). source.sha256 is not used."
        )
    return str(train_sha), str(dev_sha)


def _bird_named(cache: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = cache / name
        if path.exists():
            return path
    return None


def verify_bird_zip(task: dict[str, Any], repo_root: Path) -> None:
    """Check dual zip shas, or reuse materialized DDL/dev sqlite. Never Mini-Dev."""
    train_sha, dev_sha = bird_dual_shas(task)
    cache = repo_root / "data_cache" / "bird"
    train_zip = _bird_named(cache, BIRD_TRAIN_ZIP_NAMES)
    dev_zip = _bird_named(cache, BIRD_DEV_ZIP_NAMES)
    if train_zip is not None:
        got = sha256_file(train_zip)
        if got != train_sha:
            raise SystemExit(
                f"BIRD train zip sha256 {got} != pinned {train_sha}. Refuse to run."
            )
    if dev_zip is not None:
        got = sha256_file(dev_zip)
        if got != dev_sha:
            raise SystemExit(
                f"BIRD dev zip sha256 {got} != pinned {dev_sha}. Refuse to run."
            )
    meta_path = cache / "bird_pack_meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta_train = meta.get("train_zip_sha256")
        meta_dev = meta.get("dev_zip_sha256")
        if meta_train and str(meta_train) != train_sha:
            raise SystemExit(
                f"BIRD bird_pack_meta train sha {meta_train} != pinned {train_sha}."
            )
        if meta_dev and str(meta_dev) != dev_sha:
            raise SystemExit(
                f"BIRD bird_pack_meta dev sha {meta_dev} != pinned {dev_sha}."
            )
    dev_extract = _bird_named(cache, BIRD_DEV_EXTRACT_NAMES)
    sqlite_ok = bool(
        dev_extract is not None
        and dev_extract.is_dir()
        and any(dev_extract.rglob("*.sqlite"))
    )
    if sqlite_ok:
        return
    if train_zip is not None and dev_zip is not None:
        return
    raise SystemExit(
        "BIRD artifacts missing under data_cache/bird/: need train+dev zips "
        f"(sha {train_sha[:8]}… / {dev_sha[:8]}…) or dev_extract sqlite. "
        "Do not substitute Mini-Dev."
    )


def load_verifier(task_dir: Path) -> Any:
    path = task_dir / "verifier.py"
    spec = importlib.util.spec_from_file_location(f"{task_dir.name}_verifier", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "verify"):
        raise SystemExit(f"{path} has no verify()")
    return module


def completion_from_reference(task_id: str, reference: dict[str, Any]) -> str:
    if reference.get("completion"):
        return str(reference["completion"])
    if task_id == "gsm8k":
        solution = reference.get("solution")
        if not solution:
            raise SystemExit("gsm8k completion requires reference.solution (not answer-only)")
        return str(solution)
    if task_id == "winogrande":
        return str(reference["gold"])
    if task_id == "spider":
        return str(reference["query"])
    raise SystemExit(f"unknown task_id {task_id}")


def warn_long_prompts(rows: list[dict[str, Any]], encode: Callable[[str], int]) -> None:
    for row in rows:
        content = row["messages"][0]["content"]
        n_tokens = encode(content)
        if n_tokens > PROMPT_TOKEN_LIMIT:
            LOG.warning(
                "prompt over %s tokens: id=%s n_tokens=%s",
                PROMPT_TOKEN_LIMIT,
                row.get("id"),
                n_tokens,
            )


def _note(sample: dict[str, Any]) -> dict[str, Any]:
    raw = sample.get("note") or "{}"
    try:
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except json.JSONDecodeError:
        payload = {}
    return payload


def format_compliance_for_split(path: Path, task_id: str) -> dict[str, Any]:
    """Derived extractor-channel counts. Does not change labels or scores."""
    if not path.is_file():
        return {"n": 0, "missing": True}
    rows = load_jsonl(path)
    if task_id == "gsm8k":
        hashed = last_only = none = diverge = 0
        for row in rows:
            note = _note(row["samples"][0])
            if note.get("diverge"):
                diverge += 1
            if note.get("hash_raw") is not None:
                hashed += 1
            elif note.get("last_raw") is not None:
                last_only += 1
            else:
                none += 1
        return {
            "n": len(rows),
            "hash": hashed,
            "last_only": last_only,
            "none": none,
            "diverge": diverge,
        }
    if task_id == "math":
        boxed = last_only = none = diverge = 0
        for row in rows:
            note = _note(row["samples"][0])
            if note.get("diverge"):
                diverge += 1
            if note.get("boxed_raw") is not None:
                boxed += 1
            elif note.get("last_raw") is not None:
                last_only += 1
            else:
                none += 1
        return {
            "n": len(rows),
            "boxed": boxed,
            "last_only": last_only,
            "none": none,
            "diverge": diverge,
        }
    parsed: dict[str, int] = {}
    unparseable = 0
    exceptions: dict[str, int] = {}
    for row in rows:
        sample = row["samples"][0]
        note = _note(sample)
        if sample.get("parsed") is None or note.get("unparseable") is True:
            unparseable += 1
        else:
            key = str(sample["parsed"])
            if task_id == "spider":
                key = "parsed"
            parsed[key] = parsed.get(key, 0) + 1
        exc = note.get("exception")
        if exc:
            exceptions[str(exc)] = exceptions.get(str(exc), 0) + 1
    out: dict[str, Any] = {
        "n": len(rows),
        "unparseable": unparseable,
        "parsed": parsed,
    }
    if exceptions:
        out["exception"] = exceptions
    return out


def format_compliance_block(run_dir: Path, task_id: str) -> dict[str, Any]:
    return {
        split: format_compliance_for_split(run_dir / f"eval_{split}_greedy.jsonl", task_id)
        for split in ("base", "pilot", "full")
    }


def latest_tasks_ver(repo_root: Path) -> str:
    manifest = repo_root / "MANIFEST.sha256"
    versions: list[int] = []
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or "tasks_v" not in line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[-1]
            if name.startswith("tasks_v") and name.endswith(".tar.gz"):
                versions.append(int(name[len("tasks_v") : -len(".tar.gz")]))
    if not versions:
        return "tv1"
    return f"tv{max(versions)}"
