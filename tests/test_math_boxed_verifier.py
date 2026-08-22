"""MATH boxed mutation tests. Fractions / radicals / negatives required."""

from __future__ import annotations

import json
import unittest

from src.verifiers.math_boxed import verify


def _note(result: dict) -> dict:
    return json.loads(result["note"])


class TestMathGold(unittest.TestCase):
    def test_boxed_integer(self) -> None:
        r = verify("steps\n\\boxed{18}", {"gold": "18"})
        self.assertTrue(r["pass"])
        self.assertEqual(_note(r)["boxed_raw"], "18")

    def test_fraction_equiv(self) -> None:
        r = verify("\\boxed{\\frac{1}{2}}", {"gold": "0.5"})
        self.assertTrue(r["pass"])

    def test_radical_equiv(self) -> None:
        r = verify("\\boxed{\\sqrt{4}}", {"gold": "2"})
        self.assertTrue(r["pass"])


class TestMathWrong(unittest.TestCase):
    def test_wrong_boxed(self) -> None:
        r = verify("\\boxed{99}", {"gold": "18"})
        self.assertFalse(r["pass"])
        self.assertEqual(_note(r)["boxed_raw"], "99")

    def test_negative_not_abs(self) -> None:
        r = verify("\\boxed{-3}", {"gold": "3"})
        self.assertFalse(r["pass"])

    def test_wrong_last_line(self) -> None:
        r = verify("the answer is 5", {"gold": "18"})
        self.assertFalse(r["pass"])


class TestMathFormat(unittest.TestCase):
    def test_last_line_fallback(self) -> None:
        r = verify("work\n18", {"gold": "18"})
        self.assertTrue(r["pass"])
        self.assertIsNone(_note(r)["boxed_raw"])

    def test_negative_gold(self) -> None:
        r = verify("\\boxed{-3}", {"gold": "-3"})
        self.assertTrue(r["pass"])

    def test_frac_string_gold(self) -> None:
        r = verify("\\boxed{1/2}", {"gold": "\\frac{1}{2}"})
        self.assertTrue(r["pass"])


class TestMathGarbage(unittest.TestCase):
    def test_empty(self) -> None:
        r = verify("   ", {"gold": "1"})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])

    def test_words_only(self) -> None:
        r = verify("I cannot solve this", {"gold": "1"})
        self.assertFalse(r["pass"])

    def test_diverge_channels(self) -> None:
        r = verify("last line 9\n\\boxed{8}", {"gold": "8"})
        self.assertTrue(r["pass"])
        self.assertTrue(_note(r)["diverge"])


if __name__ == "__main__":
    unittest.main()
