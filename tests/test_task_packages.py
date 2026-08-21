"""Schema/count checks on materialized task packages (MANUAL §4-5)."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED = {
    "gsm8k": {
        "train_n": 7473,
        "eval_n": 200,
        "max_new_tokens": 512,
        "prior_label": "strong-gain",
    },
    "winogrande": {
        "train_n": 8000,
        "eval_n": 200,
        "max_new_tokens": 16,
        "prior_label": "weak-or-no-gain",
    },
    "spider": {
        "train_n": 8659,
        "eval_n": 200,
        "max_new_tokens": 256,
        "prior_label": "strong-gain",
    },
}
_GSM8K_TAIL = (
    "Reason step by step, then give the final answer on the "
    "last line in the form: #### <number>"
)
_SPIDER_ZIP_SHA = (
    "00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b"
)


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
            self.assertEqual(task["prior_label"], expected["prior_label"])
            self.assertTrue(task["pool_ref"])
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

    def test_gsm8k_instruction_line(self) -> None:
        eval_rows = _jsonl(_ROOT / "tasks" / "gsm8k" / "eval.jsonl")
        train = _jsonl(_ROOT / "tasks" / "gsm8k" / "train.jsonl")
        for row in eval_rows + train[:3]:
            content = row["messages"][0]["content"]
            self.assertTrue(
                content.endswith(_GSM8K_TAIL),
                msg=row["id"],
            )

    def test_gsm8k_train_completion_not_answer_only(self) -> None:
        train = _jsonl(_ROOT / "tasks" / "gsm8k" / "train.jsonl")
        lengths = []
        for row in train:
            solution = row["reference"]["solution"]
            self.assertNotIn("<<", solution, msg=row["id"])
            self.assertIn("####", solution, msg=row["id"])
            lengths.append(len(solution))
        mean_len = sum(lengths) / len(lengths)
        self.assertGreater(mean_len, 100)

    def test_spider_zip_pin_in_task_json(self) -> None:
        task = json.loads(
            (_ROOT / "tasks" / "spider" / "task.json").read_text(encoding="utf-8")
        )
        source = task["source"]
        self.assertEqual(
            source["yale_zip_gdrive_id"], "1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J"
        )
        self.assertEqual(source["sha256"], _SPIDER_ZIP_SHA)
        self.assertEqual(source["train"], "train_spider + train_others = 8659")


if __name__ == "__main__":
    unittest.main()
