"""N-way choice mutation tests. Each class ≥3 examples."""

from __future__ import annotations

import json
import unittest

from src.verifiers.choice import verify


def _note(result: dict) -> dict:
    return json.loads(result["note"])


class TestChoiceGold(unittest.TestCase):
    def test_plain_a_two_way(self) -> None:
        r = verify("A", {"gold": "A", "n_choices": 2})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "A")

    def test_four_way_d(self) -> None:
        r = verify("D", {"gold": "D", "n_choices": 4})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "D")

    def test_five_way_e_in_sentence(self) -> None:
        r = verify("I pick E", {"gold": "E", "n_choices": 5})
        self.assertTrue(r["pass"])
        self.assertEqual(r["parsed"], "E")


class TestChoiceWrong(unittest.TestCase):
    def test_opposite_two_way(self) -> None:
        r = verify("A", {"gold": "B", "n_choices": 2})
        self.assertFalse(r["pass"])
        self.assertEqual(r["parsed"], "A")

    def test_wrong_four_way(self) -> None:
        r = verify("B.", {"gold": "C", "n_choices": 4})
        self.assertFalse(r["pass"])
        self.assertEqual(r["parsed"], "B")

    def test_wrong_prefix(self) -> None:
        r = verify("答案:A", {"gold": "C", "n_choices": 4})
        self.assertFalse(r["pass"])
        self.assertEqual(r["parsed"], "A")


class TestChoiceFormat(unittest.TestCase):
    def test_period(self) -> None:
        r = verify("C.", {"gold": "C", "n_choices": 4})
        self.assertTrue(r["pass"])

    def test_chinese_prefix(self) -> None:
        r = verify("答案:C", {"gold": "C", "n_choices": 4})
        self.assertTrue(r["pass"])

    def test_answer_prefix(self) -> None:
        r = verify("Answer: E", {"gold": "E", "n_choices": 5})
        self.assertTrue(r["pass"])


class TestChoiceGarbage(unittest.TestCase):
    def test_plain_text(self) -> None:
        r = verify("I don't know", {"gold": "A", "n_choices": 4})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])
        self.assertTrue(_note(r)["unparseable"])

    def test_bare_article_a(self) -> None:
        r = verify("a cat sat", {"gold": "A", "n_choices": 2})
        self.assertIsNone(r["parsed"])

    def test_letter_outside_range(self) -> None:
        r = verify("E", {"gold": "A", "n_choices": 4})
        self.assertIsNone(r["parsed"])
        self.assertTrue(_note(r)["unparseable"])


if __name__ == "__main__":
    unittest.main()
