"""Schema/count checks on materialized task packages (MANUAL §4-5)."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED = {
    "gsm8k": {"train_n": 7473, "eval_n": 200, "max_new_tokens": 512},
    "winogrande": {"train_n": 8000, "eval_n": 200, "max_new_tokens": 16},
    "spider": {"train_n": 8659, "eval_n": 200, "max_new_tokens": 256},
}


def _jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class TestTaskPackages(unittest.TestCase):
    def test_counts_and_row_schema(self) -> None:
        for task_id, expected in _EXPECTED.items():
            task_dir = _ROOT / "tasks" / task_id
            task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            train = _jsonl(task_dir / "train.jsonl")
            eval_rows = _jsonl(task_dir / "eval.jsonl")
            self.assertEqual(task["task_id"], task_id)
            self.assertEqual(task["max_new_tokens"], expected["max_new_tokens"])
            self.assertEqual(task["splits"]["train_n"], expected["train_n"])
            self.assertEqual(task["splits"]["eval_n"], expected["eval_n"])
            self.assertEqual(len(train), expected["train_n"])
            self.assertEqual(len(eval_rows), expected["eval_n"])
            self.assertEqual(task["splits"]["seeds"]["eval_slice_seed"], 20260820)
            ids = [row["id"] for row in train + eval_rows]
            self.assertEqual(len(ids), len(set(ids)), f"{task_id} ids not unique")
            for row in eval_rows:
                self.assertIn("id", row)
                self.assertEqual(row["messages"][0]["role"], "user")
                self.assertTrue(row["messages"][0]["content"])
                self.assertIsInstance(row["reference"], dict)

    def test_manifests_list_core_files(self) -> None:
        for task_id in _EXPECTED:
            text = (_ROOT / "tasks" / task_id / "MANIFEST.sha256").read_text(
                encoding="utf-8"
            )
            names = [line.split()[-1] for line in text.splitlines() if line.strip()]
            for name in ("task.json", "train.jsonl", "eval.jsonl", "verifier.py"):
                self.assertIn(name, names, msg=f"{task_id} missing {name}")

    def test_manifest_hashes_match_files(self) -> None:
        for task_id in _EXPECTED:
            task_dir = _ROOT / "tasks" / task_id
            text = (task_dir / "MANIFEST.sha256").read_text(encoding="utf-8")
            for line in text.splitlines():
                if not line.strip():
                    continue
                digest, name = line.split()
                path = task_dir / name
                self.assertTrue(path.is_file(), path)
                hasher = hashlib.sha256()
                hasher.update(path.read_bytes())
                self.assertEqual(hasher.hexdigest(), digest, msg=name)


if __name__ == "__main__":
    unittest.main()
