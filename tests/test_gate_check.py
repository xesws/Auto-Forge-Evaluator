"""gate_check pass/fail paths. No GPU."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import gate_check  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(example_id: str, passed: bool, parsed: str | None) -> dict:
    return {
        "id": example_id,
        "samples": [
            {
                "output": parsed or "",
                "pass": passed,
                "parsed": parsed,
                "note": json.dumps({"unparseable": parsed is None}),
            }
        ],
    }


class TestGateCheck(unittest.TestCase):
    def _metrics(self, **over: object) -> dict:
        base = {
            "systems": {
                "torch": "2",
                "transformers": "5",
                "cuda": "12.8",
                "driver": "570",
                "gpu_name": "NVIDIA A40",
                "base_revision": "abc",
                "seeds": {},
                "dry_run": False,
            },
            "signals": {
                "pilot_loss": {
                    "start": 0.4,
                    "end": 0.01,
                    "source": "pilot_loss.jsonl",
                }
            },
        }
        base.update(over)
        return base

    def test_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            rows = [_row("a", True, "A"), _row("b", True, "B")]
            _write_jsonl(run / "eval_base_greedy.jsonl", rows)
            (run / "metrics.json").write_text(json.dumps(self._metrics()), encoding="utf-8")
            report = gate_check.check_run(run)
            self.assertTrue(report["pass"])

    def test_unparseable_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            rows = [_row(str(i), False, None) for i in range(10)]
            _write_jsonl(run / "eval_base_greedy.jsonl", rows)
            (run / "metrics.json").write_text(json.dumps(self._metrics()), encoding="utf-8")
            report = gate_check.check_run(run)
            self.assertFalse(report["unparseable"]["ok"])
            self.assertFalse(report["pass"])

    def test_loss_up_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            _write_jsonl(run / "eval_base_greedy.jsonl", [_row("a", True, "A")])
            metrics = self._metrics()
            metrics["signals"]["pilot_loss"] = {
                "start": 0.1,
                "end": 0.2,
                "source": "log",
            }
            (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
            report = gate_check.check_run(run)
            self.assertFalse(report["loss"]["ok"])

    def test_rerun_subset_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            rows = [_row("a", True, "A"), _row("b", False, "B")]
            _write_jsonl(run / "eval_base_greedy.jsonl", rows)
            _write_jsonl(run / "eval_base_greedy_rerun.jsonl", [_row("b", False, "B")])
            (run / "metrics.json").write_text(json.dumps(self._metrics()), encoding="utf-8")
            report = gate_check.check_run(run)
            self.assertTrue(report["determinism"]["ok"])
            self.assertEqual(report["determinism"]["n_rerun"], 1)

    def test_rerun_subset_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            rows = [_row("a", True, "A"), _row("b", False, "B")]
            _write_jsonl(run / "eval_base_greedy.jsonl", rows)
            _write_jsonl(run / "eval_base_greedy_rerun.jsonl", [_row("b", True, "B")])
            (run / "metrics.json").write_text(json.dumps(self._metrics()), encoding="utf-8")
            report = gate_check.check_run(run)
            self.assertFalse(report["determinism"]["ok"])

    def test_systems_missing_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            _write_jsonl(run / "eval_base_greedy.jsonl", [_row("a", True, "A")])
            (run / "metrics.json").write_text(
                json.dumps({"systems": {"torch": "2"}, "signals": {"pilot_loss": {"start": 1, "end": 0, "source": "x"}}}),
                encoding="utf-8",
            )
            report = gate_check.check_run(run)
            self.assertFalse(report["systems"]["ok"])


if __name__ == "__main__":
    unittest.main()
