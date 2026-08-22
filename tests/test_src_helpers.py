"""Helpers for the Phase 3 pipeline (no GPU, no training)."""

from __future__ import annotations

import importlib.util
import json
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
    format_compliance_for_split,
    latest_tasks_ver,
    load_protocol,
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


class TestFormatCompliance(unittest.TestCase):
    def test_gsm8k_channels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval_base_greedy.jsonl"
            rows = [
                {
                    "id": "a",
                    "samples": [
                        {
                            "pass": True,
                            "parsed": "10",
                            "note": json.dumps(
                                {
                                    "hash_raw": "10",
                                    "last_raw": "10",
                                    "diverge": False,
                                }
                            ),
                        }
                    ],
                },
                {
                    "id": "b",
                    "samples": [
                        {
                            "pass": True,
                            "parsed": "5",
                            "note": json.dumps(
                                {
                                    "hash_raw": None,
                                    "last_raw": "5",
                                    "diverge": False,
                                }
                            ),
                        }
                    ],
                },
            ]
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            stats = format_compliance_for_split(path, "gsm8k")
            self.assertEqual(stats["n"], 2)
            self.assertEqual(stats["hash"], 1)
            self.assertEqual(stats["last_only"], 1)
            self.assertEqual(stats["diverge"], 0)


class TestCompletions(unittest.TestCase):
    def test_gsm8k(self) -> None:
        self.assertEqual(
            completion_from_reference(
                "gsm8k", {"gold": "18", "solution": "n = 3+15\n#### 18"}
            ),
            "n = 3+15\n#### 18",
        )
        with self.assertRaises(SystemExit):
            completion_from_reference("gsm8k", {"gold": "18"})

    def test_wino(self) -> None:
        self.assertEqual(completion_from_reference("winogrande", {"gold": "A"}), "A")

    def test_spider(self) -> None:
        self.assertEqual(
            completion_from_reference("spider", {"query": "SELECT 1"}), "SELECT 1"
        )

    def test_completion_field_wins(self) -> None:
        self.assertEqual(
            completion_from_reference("math", {"gold": "1", "completion": "boxed"}),
            "boxed",
        )


class TestMathFormatCompliance(unittest.TestCase):
    def test_boxed_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval_base_greedy.jsonl"
            rows = [
                {
                    "id": "a",
                    "samples": [
                        {
                            "pass": True,
                            "parsed": "1",
                            "note": json.dumps(
                                {
                                    "boxed_raw": "1",
                                    "last_raw": "1",
                                    "diverge": False,
                                }
                            ),
                        }
                    ],
                },
                {
                    "id": "b",
                    "samples": [
                        {
                            "pass": True,
                            "parsed": "2",
                            "note": json.dumps(
                                {
                                    "boxed_raw": None,
                                    "last_raw": "2",
                                    "diverge": False,
                                }
                            ),
                        }
                    ],
                },
            ]
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            stats = format_compliance_for_split(path, "math")
            self.assertEqual(stats["n"], 2)
            self.assertEqual(stats["boxed"], 1)
            self.assertEqual(stats["last_only"], 1)
            self.assertEqual(stats["diverge"], 0)


class TestManifestAndJournal(unittest.TestCase):
    def test_gsm8k_manifest_ok(self) -> None:
        verify_task_manifest(_ROOT / "tasks" / "gsm8k")

    def test_tasks_ver_is_latest(self) -> None:
        self.assertEqual(latest_tasks_ver(_ROOT), "tv5")

    def test_protocol_v2_deltas(self) -> None:
        v1 = load_protocol(_ROOT / "configs" / "protocol_v1.yaml")
        v2 = load_protocol(_ROOT / "configs" / "protocol_v2.yaml")
        self.assertEqual(v2["max_seq_len"], 4096)
        self.assertEqual(v2["train"]["per_device_batch"], 2)
        self.assertEqual(v2["train"]["grad_accum"], 8)
        self.assertEqual(
            v2["base_revision"], "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
        )
        self.assertEqual(v2["base_model"], v1["base_model"])
        self.assertEqual(v2["lora"], v1["lora"])
        self.assertEqual(v2["pilot"], v1["pilot"])
        self.assertEqual(v2["full"], v1["full"])
        self.assertEqual(v2["eval"], v1["eval"])
        self.assertEqual(v2["signals"], v1["signals"])
        self.assertEqual(v2["seeds"], v1["seeds"])
        self.assertEqual(v2["train"]["lr"], v1["train"]["lr"])
        self.assertEqual(v2["train"]["loss"], v1["train"]["loss"])

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
