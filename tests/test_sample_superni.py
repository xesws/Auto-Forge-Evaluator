"""Deterministic SuperNI stratified sample on fixtures."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import sample_superni as samp  # noqa: E402


def _write_task(
    folder: Path,
    name: str,
    *,
    category: str,
    source: str,
    n: int,
    english: bool = True,
) -> None:
    lang = ["English"] if english else ["Spanish"]
    payload = {
        "Categories": [category],
        "Source": [source],
        "Input_language": lang,
        "Output_language": lang,
        "Instances": [
            {"input": f"q{i}", "output": [f"a{i}"]} for i in range(n)
        ],
    }
    (folder / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


class TestSampleSuperNI(unittest.TestCase):
    def test_filters_language_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_task(folder, "ok_a", category="qa", source="s1", n=220)
            _write_task(
                folder, "too_small", category="qa", source="s1", n=50
            )
            _write_task(
                folder,
                "spanish",
                category="qa",
                source="s2",
                n=220,
                english=False,
            )
            metas = samp.discover(folder)
            self.assertEqual([m.task_id for m in metas], ["ok_a"])

    def test_source_cap_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for i in range(6):
                _write_task(
                    folder,
                    f"qa_{i:02d}",
                    category="qa",
                    source="same",
                    n=220,
                )
            for i in range(6):
                _write_task(
                    folder,
                    f"cls_{i:02d}",
                    category="cls",
                    source=f"src{i}",
                    n=220,
                )
            metas = samp.discover(folder)
            a = samp.stratified_sample(metas, n=8, seed=20260822)
            b = samp.stratified_sample(metas, n=8, seed=20260822)
            self.assertEqual([m.task_id for m in a], [m.task_id for m in b])
            from collections import Counter

            counts = Counter(m.source for m in a)
            self.assertTrue(all(v <= 3 for v in counts.values()))
            self.assertEqual(len(a), 8)

    def test_too_few_surviving_stops(self) -> None:
        metas = [
            samp.TaskMeta("a", "a.json", "qa", "s", 220),
        ]
        with self.assertRaises(SystemExit):
            samp.stratified_sample(metas, n=50)


if __name__ == "__main__":
    unittest.main()
