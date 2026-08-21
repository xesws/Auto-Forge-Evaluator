"""Helpers for the Phase 3 pipeline (no GPU, no training)."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src.data import (  # noqa: E402
    LocalStorage,
    S3Storage,
    completion_from_reference,
    latest_tasks_ver,
    verify_task_manifest,
)

_SPEC = importlib.util.spec_from_file_location(
    "run_task_mod", _ROOT / "scripts" / "run_task.py"
)
assert _SPEC and _SPEC.loader
run_task_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_task_mod)


class TestStorage(unittest.TestCase):
    def test_local_put_get_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalStorage(Path(tmp))
            store.put("a/b.txt", b"hello")
            self.assertEqual(store.get("a/b.txt"), b"hello")
            self.assertEqual(store.list("a"), ["a/b.txt"])

    def test_s3_stub_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            S3Storage()


class TestCompletions(unittest.TestCase):
    def test_gsm8k(self) -> None:
        self.assertEqual(completion_from_reference("gsm8k", {"gold": "18"}), "#### 18")

    def test_wino(self) -> None:
        self.assertEqual(completion_from_reference("winogrande", {"gold": "A"}), "A")

    def test_spider(self) -> None:
        self.assertEqual(
            completion_from_reference("spider", {"query": "SELECT 1"}), "SELECT 1"
        )


class TestManifestAndJournal(unittest.TestCase):
    def test_gsm8k_manifest_ok(self) -> None:
        verify_task_manifest(_ROOT / "tasks" / "gsm8k")

    def test_tasks_ver_is_tv2(self) -> None:
        self.assertEqual(latest_tasks_ver(_ROOT), "tv2")

    def test_journal_done_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            run_task_mod.append_journal(run_dir, "S0", "start")
            run_task_mod.append_journal(run_dir, "S0", "done")
            run_task_mod.append_journal(run_dir, "S1", "start")
            self.assertEqual(run_task_mod.done_stages(run_dir), {"S0"})
            run_task_mod.append_journal(run_dir, "S1", "done")
            self.assertEqual(run_task_mod.done_stages(run_dir), {"S0", "S1"})


if __name__ == "__main__":
    unittest.main()
