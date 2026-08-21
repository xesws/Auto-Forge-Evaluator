"""GSM8K verifier mutation tests (MANUAL §5). Each class ≥3 examples."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "gsm8k_verifier", _ROOT / "tasks" / "gsm8k" / "verifier.py"
)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
verify = _MOD.verify


def _note(result: dict) -> dict:
    return json.loads(result["note"])


class TestGsm8kGold(unittest.TestCase):
    def test_hash_integer(self) -> None:
        r = verify("step\n#### 18", {"gold": "18"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "18")

    def test_hash_decimal(self) -> None:
        r = verify("#### 3.5", {"gold": "3.5"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "3.5")

    def test_last_number_fallback(self) -> None:
        r = verify("the total is 42", {"gold": "42"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "42")
        self.assertIsNone(_note(r)["hash_raw"])


class TestGsm8kWrong(unittest.TestCase):
    def test_wrong_hash(self) -> None:
        r = verify("#### 99", {"gold": "18"})
        self.assertFalse(r["pass"])
        self.assertEqual(r["parsed"], "99")

    def test_wrong_last_number(self) -> None:
        r = verify("I get 5", {"gold": "18"})
        self.assertFalse(r["pass"])
        self.assertEqual(r["parsed"], "5")

    def test_outside_tolerance(self) -> None:
        r = verify("#### 18.001", {"gold": "18"})
        self.assertFalse(r["pass"])


class TestGsm8kFormatVariants(unittest.TestCase):
    def test_commas(self) -> None:
        r = verify("#### 1,000", {"gold": "1000"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "1000")

    def test_spaces_in_number(self) -> None:
        r = verify("#### 1 000", {"gold": "1000"})
        self.assertTrue(r["pass"])

    def test_trailing_decimal_zero(self) -> None:
        r = verify("#### 18.0", {"gold": "18"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "18")


class TestGsm8kGarbage(unittest.TestCase):
    def test_plain_text(self) -> None:
        r = verify("hello world", {"gold": "18"})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])

    def test_hash_without_number(self) -> None:
        r = verify("#### apple", {"gold": "18"})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])

    def test_symbols(self) -> None:
        r = verify("???", {"gold": "18"})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])


class TestGsm8kDivergeNote(unittest.TestCase):
    def test_both_extracts_in_note(self) -> None:
        r = verify("first 3 then #### 18", {"gold": "18"})
        self.assertTrue(r["pass"])
        n = _note(r)
        self.assertEqual(n["hash_raw"], "18")
        self.assertEqual(n["last_raw"], "18")
        self.assertTrue(n["diverge"] is False or n["diverge"] is True)

    def test_diverge_flag(self) -> None:
        r = verify("#### 18\nand then 3 more", {"gold": "18"})
        n = _note(r)
        self.assertTrue(n["diverge"])
        self.assertEqual(n["hash_n"], 18.0)
        self.assertEqual(n["last_n"], 3.0)
        self.assertTrue(r["pass"])


if __name__ == "__main__":
    unittest.main()
