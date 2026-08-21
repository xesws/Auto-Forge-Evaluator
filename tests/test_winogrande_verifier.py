"""WinoGrande verifier mutation tests (MANUAL §5). Each class ≥3 examples."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "winogrande_verifier", _ROOT / "tasks" / "winogrande" / "verifier.py"
)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
verify = _MOD.verify


def _note(result: dict) -> dict:
    return json.loads(result["note"])


class TestWinograndeGold(unittest.TestCase):
    def test_plain_a(self) -> None:
        r = verify("A", {"gold": "A"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "A")
        self.assertFalse(_note(r)["unparseable"])

    def test_plain_b(self) -> None:
        r = verify("B", {"gold": "B"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "B")

    def test_sentence_with_letter(self) -> None:
        r = verify("I pick B", {"gold": "B"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "B")


class TestWinograndeWrong(unittest.TestCase):
    def test_opposite_letter(self) -> None:
        r = verify("A", {"gold": "B"})
        self.assertFalse(r["pass"])
        self.assertEqual(r["parsed"], "A")

    def test_opposite_with_period(self) -> None:
        r = verify("B.", {"gold": "A"})
        self.assertFalse(r["pass"])
        self.assertEqual(r["parsed"], "B")

    def test_opposite_answer_prefix(self) -> None:
        r = verify("答案:A", {"gold": "B"})
        self.assertFalse(r["pass"])
        self.assertEqual(r["parsed"], "A")


class TestWinograndeFormatVariants(unittest.TestCase):
    def test_period(self) -> None:
        r = verify("A.", {"gold": "A"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "A")

    def test_chinese_prefix(self) -> None:
        r = verify("答案:A", {"gold": "A"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "A")

    def test_answer_prefix(self) -> None:
        r = verify("Answer: B", {"gold": "B"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "B")


class TestWinograndeGarbage(unittest.TestCase):
    def test_plain_text(self) -> None:
        r = verify("I don't know", {"gold": "A"})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])
        self.assertTrue(_note(r)["unparseable"])

    def test_letter_c(self) -> None:
        r = verify("C", {"gold": "A"})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])

    def test_numeric_choice(self) -> None:
        r = verify("1", {"gold": "A"})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])


if __name__ == "__main__":
    unittest.main()
