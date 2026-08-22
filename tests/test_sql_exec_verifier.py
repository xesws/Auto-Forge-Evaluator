"""SQL exec mutation tests (BIRD/Spider shared). Each class ≥3 examples."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.verifiers.sql_exec import verify

_GOLD = "SELECT name FROM pets WHERE age = 3"
_SCHEMA = """
CREATE TABLE pets (id INTEGER, name TEXT, age INTEGER);
INSERT INTO pets VALUES (1, 'ada', 3), (2, 'ada', 3), (3, 'bob', 5);
"""


def _note(result: dict) -> dict:
    return json.loads(result["note"])


class TestSqlExec(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "pets.sqlite")
        conn = sqlite3.connect(self.db_path)
        conn.executescript(_SCHEMA)
        conn.close()
        self.ref = {"query": _GOLD, "db_path": self.db_path}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_gold_select(self) -> None:
        r = verify(_GOLD, self.ref)
        self.assertTrue(r["pass"])

    def test_gold_order_irrelevant(self) -> None:
        r = verify("SELECT name FROM pets WHERE age=3 ORDER BY name DESC", self.ref)
        self.assertTrue(r["pass"])

    def test_gold_fence(self) -> None:
        r = verify("```sql\nSELECT name FROM pets WHERE age = 3\n```", self.ref)
        self.assertTrue(r["pass"])

    def test_wrong_filter(self) -> None:
        r = verify("SELECT name FROM pets WHERE age = 5", self.ref)
        self.assertFalse(r["pass"])
        self.assertIsNotNone(r["parsed"])

    def test_wrong_column(self) -> None:
        r = verify("SELECT id FROM pets WHERE age = 3", self.ref)
        self.assertFalse(r["pass"])

    def test_empty_result_wrong(self) -> None:
        r = verify("SELECT name FROM pets WHERE age = 99", self.ref)
        self.assertFalse(r["pass"])

    def test_format_whitespace(self) -> None:
        r = verify("  SELECT   name FROM pets WHERE age=3;  ", self.ref)
        self.assertTrue(r["pass"])

    def test_format_with(self) -> None:
        sql = "WITH x AS (SELECT name FROM pets WHERE age=3) SELECT name FROM x"
        r = verify(sql, self.ref)
        self.assertTrue(r["pass"])

    def test_format_case(self) -> None:
        r = verify("select name from pets where age = 3", self.ref)
        self.assertTrue(r["pass"])

    def test_garbage_plain(self) -> None:
        r = verify("hello", self.ref)
        self.assertIsNone(r["parsed"])
        self.assertTrue(_note(r)["unparseable"])

    def test_garbage_no_kw(self) -> None:
        r = verify("FROM pets", self.ref)
        self.assertTrue(_note(r)["unparseable"])

    def test_bad_sql_exception(self) -> None:
        r = verify("SELECT nope FROM pets", self.ref)
        self.assertFalse(r["pass"])
        self.assertEqual(_note(r)["exception"], "OperationalError")


if __name__ == "__main__":
    unittest.main()
