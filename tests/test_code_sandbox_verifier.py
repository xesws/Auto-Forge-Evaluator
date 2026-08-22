"""MBPP/APPS sandbox mutation tests. Each class ≥3 examples."""

from __future__ import annotations

import json
import unittest

from src.verifiers.code_sandbox import verify


def _note(result: dict) -> dict:
    return json.loads(result["note"])


_MBPP_ADD = {
    "kind": "mbpp",
    "tests": "assert add(1,2)==3\nassert add(0,0)==0\nassert add(-1,1)==0\n",
}


class TestCodeGold(unittest.TestCase):
    def test_mbpp_plain(self) -> None:
        r = verify("def add(a,b):\n    return a+b\n", _MBPP_ADD)
        self.assertTrue(r["pass"])

    def test_mbpp_fenced(self) -> None:
        r = verify("```python\ndef add(a,b):\n    return a+b\n```", _MBPP_ADD)
        self.assertTrue(r["pass"])

    def test_apps_io(self) -> None:
        code = "def solution():\n    return '1'\n"
        ref = {
            "kind": "apps",
            "io": [{"input": "", "output": "1"}],
        }
        r = verify(code, ref)
        self.assertTrue(r["pass"])


class TestCodeWrong(unittest.TestCase):
    def test_mbpp_wrong_return(self) -> None:
        r = verify("def add(a,b):\n    return a-b\n", _MBPP_ADD)
        self.assertFalse(r["pass"])
        self.assertIsNotNone(r["parsed"])

    def test_mbpp_missing_fn(self) -> None:
        r = verify("x = 1\n", _MBPP_ADD)
        self.assertFalse(r["pass"])

    def test_apps_wrong_output(self) -> None:
        r = verify(
            "def solution():\n    return '0'\n",
            {"kind": "apps", "io": [{"input": "", "output": "1"}]},
        )
        self.assertFalse(r["pass"])


class TestCodeFormat(unittest.TestCase):
    def test_fence_language_tag(self) -> None:
        r = verify("```\ndef add(a,b):\n    return a+b\n```", _MBPP_ADD)
        self.assertTrue(r["pass"])

    def test_leading_text(self) -> None:
        r = verify("Sure.\n```python\ndef add(a,b):\n    return a+b\n```\n", _MBPP_ADD)
        self.assertTrue(r["pass"])

    def test_apps_print(self) -> None:
        r = verify(
            "def solution():\n    print(2)\n",
            {"kind": "apps", "io": [{"input": "", "output": "2"}]},
        )
        self.assertTrue(r["pass"])


class TestCodeGarbage(unittest.TestCase):
    def test_empty(self) -> None:
        r = verify("   ", _MBPP_ADD)
        self.assertFalse(r["pass"])
        self.assertIsNone(r["parsed"])
        self.assertTrue(_note(r)["unparseable"])

    def test_syntax_error(self) -> None:
        r = verify("def add(\n", _MBPP_ADD)
        self.assertFalse(r["pass"])
        self.assertIsNotNone(_note(r)["exception"])

    def test_timeout(self) -> None:
        r = verify("while True:\n    pass\n", _MBPP_ADD)
        self.assertFalse(r["pass"])
        self.assertEqual(_note(r)["exception"], "TimeoutError")


if __name__ == "__main__":
    unittest.main()
