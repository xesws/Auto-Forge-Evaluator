"""pass@1 / pass@8 signals (MANUAL §2, §6). Labels are always greedy pass@1.

Derived feature vector is computed from sealed run artifacts only.
"""

from __future__ import annotations

import json
import logging
import re
import statistics
from pathlib import Path
from typing import Any

from src.data import format_compliance_block, load_jsonl

TRAIN_STEP_RE = re.compile(r"train step (\d+)/(\d+) loss=([0-9.eE+-]+)")
LOSS_THRESHOLD = 0.01
PILOT_LOSS_JSONL = "pilot_loss.jsonl"


def pass_at_1(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    hits = 0
    for row in results:
        samples = row["samples"]
        hits += int(bool(samples and samples[0]["pass"]))
    return hits / len(results)


def pass_at_k(results: list[dict[str, Any]]) -> float:
    """Fraction of examples with at least one passing sample (pass@k)."""
    if not results:
        return 0.0
    hits = 0
    for row in results:
        hits += int(any(sample["pass"] for sample in row["samples"]))
    return hits / len(results)


def headroom(pass1: float, pass8: float) -> float:
    return pass8 - pass1


def _as_loss_text(source: str | Path) -> str:
    if isinstance(source, Path):
        if not source.is_file():
            raise FileNotFoundError(source)
        return source.read_text(encoding="utf-8", errors="replace")
    path = Path(source)
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    if TRAIN_STEP_RE.search(source) or "\n" in source:
        return source
    raise FileNotFoundError(source)


def parse_train_loss_log(source: str | Path, denom: int) -> list[tuple[int, float]]:
    """Parse `train step i/n loss=` lines. Last write wins per step. Filter by n=denom."""
    text = _as_loss_text(source)
    latest: dict[int, float] = {}
    for line in text.splitlines():
        match = TRAIN_STEP_RE.search(line)
        if not match:
            continue
        step, steps, loss = int(match.group(1)), int(match.group(2)), float(match.group(3))
        if steps == denom:
            latest[step] = loss
    return [(step, latest[step]) for step in sorted(latest)]


def parse_pilot_loss_jsonl(
    path: Path, denom: int | None = None
) -> list[tuple[int, float]]:
    """Read run_dir/pilot_loss.jsonl. Last write wins per step."""
    if not path.is_file():
        raise FileNotFoundError(path)
    latest: dict[int, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        step = int(rec["step"])
        steps = int(rec["steps"])
        if denom is not None and steps != denom:
            continue
        latest[step] = float(rec["loss"])
    return [(step, latest[step]) for step in sorted(latest)]


def pilot_loss_descriptors(series: list[tuple[int, float]]) -> dict[str, Any]:
    if not series:
        return {
            "start": None,
            "end": None,
            "steps_to_0_01": None,
            "n_points": 0,
        }
    hit = next((step for step, loss in series if loss <= LOSS_THRESHOLD), None)
    return {
        "start": series[0][1],
        "end": series[-1][1],
        "steps_to_0_01": hit,
        "n_points": len(series),
    }


def gen_len_stats(source: Path | list[dict[str, Any]]) -> dict[str, Any]:
    """Character length of greedy `samples[0].output`. Log-pure; not tokens."""
    if isinstance(source, Path):
        if not source.is_file():
            return {"n": 0, "mean": None, "median": None, "unit": "chars"}
        rows = load_jsonl(source)
    else:
        rows = source
    lengths = [len(row["samples"][0]["output"]) for row in rows]
    if not lengths:
        return {"n": 0, "mean": None, "median": None, "unit": "chars"}
    return {
        "n": len(lengths),
        "mean": statistics.mean(lengths),
        "median": statistics.median(lengths),
        "unit": "chars",
    }


class PilotLossJsonlHandler(logging.Handler):
    """Capture `forge.train` step-loss lines into jsonl. Does not change the train loop."""

    def __init__(self, path: Path) -> None:
        super().__init__(level=logging.INFO)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            match = TRAIN_STEP_RE.search(record.getMessage())
            if not match:
                return
            row = {
                "step": int(match.group(1)),
                "steps": int(match.group(2)),
                "loss": float(match.group(3)),
            }
            self._fh.write(json.dumps(row) + "\n")
            self._fh.flush()
        except Exception:  # noqa: BLE001
            self.handleError(record)

    def close(self) -> None:
        try:
            self._fh.close()
        finally:
            super().close()


def _journal_done(run_dir: Path, stage: str) -> dict[str, Any] | None:
    path = run_dir / "journal.jsonl"
    if not path.is_file():
        return None
    last: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("stage") == stage and rec.get("event") == "done":
            last = rec
    return last


def _load_task_id(run_dir: Path, task_id: str | None) -> str:
    if task_id:
        return task_id
    metrics_path = run_dir / "metrics.json"
    if metrics_path.is_file():
        return str(json.loads(metrics_path.read_text(encoding="utf-8"))["task_id"])
    s0_path = run_dir / "s0_loaded.json"
    if s0_path.is_file():
        return str(json.loads(s0_path.read_text(encoding="utf-8"))["task_id"])
    raise FileNotFoundError(f"task_id missing under {run_dir}")


def _resolve_loss_series(
    run_dir: Path,
    *,
    denom: int,
    loss_text: str | None,
    loss_path: Path | None,
) -> tuple[list[tuple[int, float]], str]:
    if loss_text is not None:
        return parse_train_loss_log(loss_text, denom), "loss_text"
    if loss_path is not None:
        path = Path(loss_path)
        if path.suffix == ".jsonl":
            return parse_pilot_loss_jsonl(path, denom), str(path)
        return parse_train_loss_log(path, denom), str(path)
    jsonl_path = run_dir / PILOT_LOSS_JSONL
    if jsonl_path.is_file():
        return parse_pilot_loss_jsonl(jsonl_path, denom), PILOT_LOSS_JSONL
    return [], "missing"


def build_signal_vector(
    run_dir: Path,
    *,
    task_id: str | None = None,
    loss_text: str | None = None,
    loss_path: Path | None = None,
) -> dict[str, Any]:
    """Assemble the derived signal object from existing run artifacts. No train/eval."""
    run_dir = Path(run_dir)
    task_id = _load_task_id(run_dir, task_id)
    base_rows = load_jsonl(run_dir / "eval_base_greedy.jsonl")
    pilot_rows = load_jsonl(run_dir / "eval_pilot_greedy.jsonl")
    pass8_path = run_dir / "eval_base_pass8.jsonl"
    base_pass1 = pass_at_1(base_rows)
    pilot_pass1 = pass_at_1(pilot_rows)
    base_pass8: float | None
    if pass8_path.is_file():
        base_pass8 = pass_at_k(load_jsonl(pass8_path))
    else:
        base_pass8 = None

    s2 = _journal_done(run_dir, "S2")
    denom = int(s2["steps"]) if s2 and s2.get("steps") is not None else 100
    series, source = _resolve_loss_series(
        run_dir, denom=denom, loss_text=loss_text, loss_path=loss_path
    )
    loss_block = pilot_loss_descriptors(series)
    loss_block["source"] = source

    s0_path = run_dir / "s0_loaded.json"
    train_n = None
    if s0_path.is_file():
        train_n = json.loads(s0_path.read_text(encoding="utf-8")).get("train_n")
    s4 = _journal_done(run_dir, "S4")
    full_n = None if not s4 else s4.get("n")

    return {
        "delta_pilot": pilot_pass1 - base_pass1,
        "pilot_loss": loss_block,
        "base_pass1": base_pass1,
        "base_pass8": base_pass8,
        "headroom": None if base_pass8 is None else headroom(base_pass1, base_pass8),
        "format_compliance": format_compliance_block(run_dir, task_id),
        "gen_len": {
            "base": gen_len_stats(run_dir / "eval_base_greedy.jsonl"),
            "pilot": gen_len_stats(run_dir / "eval_pilot_greedy.jsonl"),
            "full": gen_len_stats(run_dir / "eval_full_greedy.jsonl"),
        },
        "train_n": train_n,
        "full_n": full_n,
    }
