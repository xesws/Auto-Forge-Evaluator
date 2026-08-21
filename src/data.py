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
    if task_id == "gsm8k":
        return f"#### {reference['gold']}"
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
