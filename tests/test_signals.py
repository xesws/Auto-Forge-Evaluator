"""Derived signal vector (no GPU)."""

from __future__ import annotations

import json
import logging
import tempfile
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src.signals import (  # noqa: E402
    PilotLossJsonlHandler,
    build_signal_vector,
    gen_len_stats,
    headroom,
    parse_train_loss_log,
    pass_at_1,
    pass_at_k,
    pilot_loss_descriptors,
)

_RUNS = _ROOT / "runs"
_SEALED = [
    {
        "task": "gsm8k",
        "run": "gsm8k__pv2__tv3__20260821-1038",
        "log": "gate0_gsm8k.log",
        "steps_to_0_01": 15,
        "train_n": 7473,
        "full_n": 7473,
    },
    {
        "task": "winogrande",
        "run": "winogrande__pv2__tv3__20260821-2105",
        "log": "gate1_winogrande.log",
        "steps_to_0_01": 6,
        "train_n": 8000,
        "full_n": 8000,
    },
    {
        "task": "spider",
        "run": "spider__pv2__tv3__20260821-2137",
        "log": "gate1_spider.log",
        "steps_to_0_01": 19,
        "train_n": 8659,
        "full_n": 8000,
    },
]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def _greedy_row(example_id: str, text: str, passed: bool) -> dict:
    return {
        "id": example_id,
        "samples": [
            {
                "output": text,
                "pass": passed,
                "parsed": "A" if passed else None,
                "note": json.dumps({"unparseable": not passed}),
            }
        ],
    }


class TestLossParse(unittest.TestCase):
    def test_crosses_threshold_last_write_wins(self) -> None:
        text = "\n".join(
            [
                "train step 1/3 loss=0.5",
                "train step 1/3 loss=0.4",
                "train step 2/3 loss=0.009",
                "train step 3/3 loss=0.001",
                "train step 1/1500 loss=9.9",
            ]
        )
        series = parse_train_loss_log(text, 3)
        self.assertEqual(series, [(1, 0.4), (2, 0.009), (3, 0.001)])
        desc = pilot_loss_descriptors(series)
        self.assertEqual(desc["start"], 0.4)
        self.assertEqual(desc["end"], 0.001)
        self.assertEqual(desc["steps_to_0_01"], 2)
        self.assertEqual(desc["n_points"], 3)

    def test_never_reaches_threshold(self) -> None:
        text = "train step 1/2 loss=0.5\ntrain step 2/2 loss=0.02\n"
        desc = pilot_loss_descriptors(parse_train_loss_log(text, 2))
        self.assertIsNone(desc["steps_to_0_01"])
        self.assertEqual(desc["n_points"], 2)

    def test_missing_log_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            parse_train_loss_log("/no/such/loss.log", 100)


class TestGenLenAndHeadroom(unittest.TestCase):
    def test_char_stats_and_empty(self) -> None:
        rows = [
            _greedy_row("a", "ab", True),
            _greedy_row("b", "abcd", False),
        ]
        stats = gen_len_stats(rows)
        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["mean"], 3.0)
        self.assertEqual(stats["median"], 3.0)
        self.assertEqual(stats["unit"], "chars")
        empty = gen_len_stats([])
        self.assertEqual(empty["n"], 0)
        self.assertIsNone(empty["mean"])
        self.assertIsNone(empty["median"])
        with tempfile.TemporaryDirectory() as tmp:
            missing = gen_len_stats(Path(tmp) / "eval_base_greedy.jsonl")
            self.assertEqual(missing["n"], 0)

    def test_headroom_and_delta(self) -> None:
        self.assertAlmostEqual(headroom(0.69, 0.89), 0.20)
        base = [_greedy_row("a", "x", True), _greedy_row("b", "y", False)]
        pilot = [_greedy_row("a", "x", False), _greedy_row("b", "y", False)]
        self.assertEqual(pass_at_1(base), 0.5)
        self.assertEqual(pass_at_1(pilot) - pass_at_1(base), -0.5)
        sampled = [
            {
                "id": "a",
                "samples": [{"pass": False}, {"pass": True}],
            },
            {
                "id": "b",
                "samples": [{"pass": False}, {"pass": False}],
            },
        ]
        self.assertEqual(pass_at_k(sampled), 0.5)


class TestBuildSignalVector(unittest.TestCase):
    def test_missing_loss_is_explicit_not_invented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            rows = [_greedy_row("a", "hi", True)]
            _write_jsonl(run_dir / "eval_base_greedy.jsonl", rows)
            _write_jsonl(run_dir / "eval_pilot_greedy.jsonl", rows)
            _write_jsonl(run_dir / "eval_full_greedy.jsonl", rows)
            _write_jsonl(
                run_dir / "eval_base_pass8.jsonl",
                [{"id": "a", "samples": [{"pass": True}]}],
            )
            (run_dir / "s0_loaded.json").write_text(
                json.dumps({"task_id": "winogrande", "train_n": 12}) + "\n",
                encoding="utf-8",
            )
            (run_dir / "journal.jsonl").write_text(
                json.dumps({"stage": "S2", "event": "done", "steps": 100})
                + "\n"
                + json.dumps({"stage": "S4", "event": "done", "n": 8})
                + "\n",
                encoding="utf-8",
            )
            vec = build_signal_vector(run_dir, task_id="winogrande")
            self.assertEqual(vec["pilot_loss"]["source"], "missing")
            self.assertIsNone(vec["pilot_loss"]["steps_to_0_01"])
            self.assertEqual(vec["pilot_loss"]["n_points"], 0)
            self.assertEqual(vec["delta_pilot"], 0.0)
            self.assertEqual(vec["base_pass1"], 1.0)
            self.assertEqual(vec["base_pass8"], 1.0)
            self.assertEqual(vec["headroom"], 0.0)
            self.assertEqual(vec["train_n"], 12)
            self.assertEqual(vec["full_n"], 8)
            self.assertEqual(vec["gen_len"]["base"]["median"], 2)

    def test_jsonl_handler_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pilot_loss.jsonl"
            handler = PilotLossJsonlHandler(path)
            log = logging.getLogger("forge.train.test_handler")
            log.setLevel(logging.INFO)
            log.addHandler(handler)
            log.propagate = False
            try:
                log.info("train step %s/%s loss=%s", 1, 2, 0.5)
                log.info("unrelated")
                log.info("train step %s/%s loss=%s", 2, 2, 0.001)
            finally:
                log.removeHandler(handler)
                handler.close()
            text = path.read_text(encoding="utf-8")
            self.assertIn('"step": 1', text)
            vec_series = parse_train_loss_log(
                "train step 1/2 loss=0.5\ntrain step 2/2 loss=0.001\n", 2
            )
            self.assertEqual(vec_series[-1][1], 0.001)


class TestSealedRunsIfPresent(unittest.TestCase):
    def test_sealed_descriptors(self) -> None:
        missing = [
            spec["run"]
            for spec in _SEALED
            if not (_RUNS / spec["run"] / "metrics.json").is_file()
            or not (_RUNS / spec["log"]).is_file()
        ]
        if missing:
            self.skipTest(f"sealed runs/logs not present: {missing}")
        for spec in _SEALED:
            run_dir = _RUNS / spec["run"]
            metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
            vec = build_signal_vector(
                run_dir,
                task_id=spec["task"],
                loss_path=_RUNS / spec["log"],
            )
            self.assertAlmostEqual(
                vec["delta_pilot"],
                metrics["delta_pilot"]["delta_pilot"],
                places=12,
                msg=spec["task"],
            )
            self.assertAlmostEqual(
                vec["base_pass1"], metrics["base"]["pass1"], places=12, msg=spec["task"]
            )
            self.assertAlmostEqual(
                vec["base_pass8"], metrics["base"]["pass8"], places=12, msg=spec["task"]
            )
            self.assertEqual(vec["pilot_loss"]["steps_to_0_01"], spec["steps_to_0_01"])
            self.assertEqual(vec["train_n"], spec["train_n"])
            self.assertEqual(vec["full_n"], spec["full_n"])
            self.assertEqual(vec["pilot_loss"]["n_points"], 100)
            self.assertEqual(vec["gen_len"]["base"]["unit"], "chars")


if __name__ == "__main__":
    unittest.main()
