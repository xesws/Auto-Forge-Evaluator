"""CPU tests for revision-period helpers (no full LOTO)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analysis_v2 as v2  # noqa: E402


class TestMcNemar(unittest.TestCase):
    def test_pairs_and_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            base = [
                {"id": "a", "samples": [{"pass": False}]},
                {"id": "b", "samples": [{"pass": True}]},
                {"id": "c", "samples": [{"pass": False}]},
            ]
            full = [
                {"id": "a", "samples": [{"pass": True}]},
                {"id": "b", "samples": [{"pass": True}]},
                {"id": "c", "samples": [{"pass": True}]},
            ]
            (d / "eval_base_greedy.jsonl").write_text("\n".join(json.dumps(x) for x in base) + "\n")
            (d / "eval_full_greedy.jsonl").write_text("\n".join(json.dumps(x) for x in full) + "\n")
            n01, n10, p, lab = v2.mcnemar_from_jsonl(d)
            self.assertEqual(n01, 2)
            self.assertEqual(n10, 0)
            self.assertLess(p, 1.0)


class TestJournal(unittest.TestCase):
    def test_stage_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            lines = [
                {"stage": "S2", "event": "start", "ts": "2026-08-22T13:00:00"},
                {"stage": "S2", "event": "done", "ts": "2026-08-22T13:01:40"},
                {"stage": "S4", "event": "start", "ts": "2026-08-22T14:00:00"},
                {"stage": "S4", "event": "done", "ts": "2026-08-22T14:10:00"},
            ]
            (d / "journal.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
            sec = v2.journal_stage_seconds(d)
            self.assertEqual(sec["S2"], 100.0)
            self.assertEqual(sec["S4"], 600.0)
            self.assertIsNone(sec["S1"])


if __name__ == "__main__":
    unittest.main()
