"""Citable figures consume the sealed n=61 table only."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


class TestPlotData(unittest.TestCase):
    def test_results_n61(self) -> None:
        blob = json.loads((_ROOT / "docs" / "ANALYSIS_RESULTS.json").read_text(encoding="utf-8"))
        main = blob["main_bundle"]
        self.assertEqual(main["n"], 61)
        self.assertEqual(main["n_go"], 53)
        self.assertEqual(len(main["task_ids"]), 61)
        self.assertNotIn("bird", main["task_ids"])
        self.assertNotIn("apps", main["task_ids"])

    def test_plot_data_if_present(self) -> None:
        path = _ROOT / "docs" / "figures" / "plot_data.json"
        if not path.is_file():
            self.skipTest("plot_data.json not generated yet")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["n"], 61)
        self.assertEqual(data["n_go"], 53)
        self.assertEqual(len(data["p_main"]), 61)
        self.assertEqual(sum(data["go"]), 53)


if __name__ == "__main__":
    unittest.main()
