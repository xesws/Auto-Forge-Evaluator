"""Spider verifier mutation tests (MANUAL §5). Each class ≥3 examples."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "spider_verifier", _ROOT / "tasks" / "spider" / "verifier.py"
)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
verify = _MOD.verify

_GOLD = "SELECT name FROM pets WHERE age = 3"
_SCHEMA = """
CREATE TABLE pets (id INTEGER, name TEXT, age INTEGER);
INSERT INTO pets VALUES (1, 'ada', 3), (2, 'ada', 3), (3, 'bob', 5);
"""


def _note(result: dict) -> dict:
    return json.loads(result["note"])


class TestSpiderVerifier(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "pets.sqlite")
        conn = sqlite3.connect(self.db_path)
        conn.executescript(_SCHEMA)
        conn.close()
        self.ref = {"query": _GOLD, "db_id": "pets", "db_path": self.db_path}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_gold_plain(self) -> None:
        r = verify(_GOLD, self.ref)
        self.assertTrue(r["pass"], r)
        self.assertIsNotNone(r["parsed"])

    def test_gold_duplicate_multiset(self) -> None:
        r = verify("SELECT name FROM pets WHERE age = 3", self.ref)
        self.assertTrue(r["pass"])
        self.assertEqual(_note(r)["n_pred"], 2)

    def test_gold_order_independent(self) -> None:
        r = verify(
            "SELECT name FROM pets WHERE age = 3 ORDER BY id DESC", self.ref
        )
        self.assertTrue(r["pass"], r)

    def test_wrong_filter(self) -> None:
        r = verify("SELECT name FROM pets WHERE age = 5", self.ref)
        self.assertFalse(r["pass"])
        self.assertIsNotNone(r["parsed"])
        self.assertIsNone(_note(r).get("exception"))

    def test_wrong_column(self) -> None:
        r = verify("SELECT id FROM pets WHERE age = 3", self.ref)
        self.assertFalse(r["pass"])
        self.assertIsNone(_note(r).get("exception"))

    def test_empty_vs_gold(self) -> None:
        r = verify("SELECT name FROM pets WHERE age = 99", self.ref)
        self.assertFalse(r["pass"])
        self.assertIsNone(_note(r).get("exception"))

    def test_variant_case_and_semicolon(self) -> None:
        r = verify("select name from pets where age = 3;", self.ref)
        self.assertTrue(r["pass"], r)

    def test_variant_fence(self) -> None:
        r = verify("```sql\nSELECT name FROM pets WHERE age = 3\n```", self.ref)
        self.assertTrue(r["pass"], r)

    def test_variant_whitespace(self) -> None:
        r = verify("SELECT   name  FROM  pets  WHERE  age=3", self.ref)
        self.assertTrue(r["pass"], r)

    def test_garbage_text(self) -> None:
        r = verify("hello world", self.ref)
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])
        self.assertTrue(_note(r)["unparseable"])

    def test_garbage_symbols(self) -> None:
        r = verify("???", self.ref)
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])

    def test_garbage_numbers(self) -> None:
        r = verify("12345", self.ref)
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])


if __name__ == "__main__":
    unittest.main()
