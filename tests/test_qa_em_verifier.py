"""DROP/TyDiQA EM mutation tests. Token-F1 recorded, not scored."""

from __future__ import annotations

import json
import unittest

from src.verifiers.em_norm import verify as em_verify
from src.verifiers.qa_em import verify


def _note(result: dict) -> dict:
    return json.loads(result["note"])


class TestQaGold(unittest.TestCase):
    def test_span_exact(self) -> None:
        r = verify("Paris", {"golds": ["Paris"], "answer_type": "span"})
        self.assertTrue(r["pass"])

    def test_number_normalize(self) -> None:
        r = verify("1,000", {"golds": ["1000"], "answer_type": "number"})
        self.assertTrue(r["pass"])

    def test_multi_gold_any(self) -> None:
        r = verify("NYC", {"golds": ["New York City", "NYC"], "answer_type": "span"})
        self.assertTrue(r["pass"])


class TestQaWrong(unittest.TestCase):
    def test_wrong_span(self) -> None:
        r = verify("London", {"golds": ["Paris"], "answer_type": "span"})
        self.assertFalse(r["pass"])
        self.assertIsNotNone(r["parsed"])

    def test_wrong_number(self) -> None:
        r = verify("3", {"golds": ["4"], "answer_type": "number"})
        self.assertFalse(r["pass"])

    def test_partial_overlap_not_em(self) -> None:
        r = verify("the city of Paris France", {"golds": ["Paris"], "answer_type": "span"})
        self.assertFalse(r["pass"])
        self.assertGreater(_note(r)["token_f1"], 0)


class TestQaFormat(unittest.TestCase):
    def test_articles_punct(self) -> None:
        r = verify("The Paris.", {"golds": ["paris"], "answer_type": "span"})
        self.assertTrue(r["pass"])

    def test_date_string(self) -> None:
        r = verify("July 4, 1776", {"golds": ["July 4 1776"], "answer_type": "date"})
        self.assertTrue(r["pass"])

    def test_em_norm_alias(self) -> None:
        r = em_verify("Hello", {"golds": ["hello"]})
        self.assertTrue(r["pass"])


class TestQaGarbage(unittest.TestCase):
    def test_empty(self) -> None:
        r = verify("  ", {"golds": ["Paris"]})
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])
        self.assertTrue(_note(r)["unparseable"])

    def test_blank_vs_gold(self) -> None:
        r = verify("", {"golds": ["x"]})
        self.assertTrue(_note(r)["unparseable"])

    def test_f1_not_pass(self) -> None:
        r = verify("Paris France", {"golds": ["Paris"]})
        self.assertFalse(r["pass"])
        self.assertGreater(_note(r)["token_f1"], 0.0)


if __name__ == "__main__":
    unittest.main()
