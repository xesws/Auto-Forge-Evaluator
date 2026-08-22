#!/usr/bin/env python3
"""Stratified SuperNI sample. Spec: docs/ANALYSIS_PREREG_SUPPLEMENT.md Commit S1."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260822
N_SAMPLE = 50
MAX_PER_SOURCE = 3
MIN_TRAIN = 10
EVAL_N = 200
MIN_INSTANCES = EVAL_N + MIN_TRAIN


@dataclass(frozen=True)
class TaskMeta:
    task_id: str
    path: str
    stratum: str
    source: str
    n_instances: int


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _has_english(value: Any) -> bool:
    return any("english" in item.lower() for item in _as_list(value))


def parse_task_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def task_meta(path: Path, payload: dict[str, Any]) -> TaskMeta:
    sources = _as_list(payload.get("Source") or payload.get("Sources"))
    cats = _as_list(payload.get("Categories") or payload.get("Category"))
    instances = payload.get("Instances") or []
    return TaskMeta(
        task_id=path.stem,
        path=str(path),
        stratum=cats[0] if cats else "unknown",
        source=sources[0] if sources else "unknown",
        n_instances=len(instances),
    )


def is_eligible(payload: dict[str, Any]) -> bool:
    if not _has_english(payload.get("Input_language")):
        return False
    if not _has_english(payload.get("Output_language")):
        return False
    instances = payload.get("Instances") or []
    return len(instances) >= MIN_INSTANCES


def discover(tasks_dir: Path) -> list[TaskMeta]:
    metas: list[TaskMeta] = []
    for path in sorted(tasks_dir.glob("*.json")):
        payload = parse_task_file(path)
        if not is_eligible(payload):
            continue
        metas.append(task_meta(path, payload))
    return metas


def _quotas(strata_sizes: dict[str, int], n: int) -> dict[str, int]:
    strata = sorted(strata_sizes)
    total = sum(strata_sizes[s] for s in strata)
    if total <= 0:
        return {}
    raw = {s: n * strata_sizes[s] / total for s in strata}
    quotas = {s: int(math.floor(raw[s])) for s in strata}
    remainder = n - sum(quotas.values())
    frac_order = sorted(strata, key=lambda s: (-(raw[s] - quotas[s]), s))
    for s in frac_order[:remainder]:
        quotas[s] += 1
    return quotas


def stratified_sample(
    metas: list[TaskMeta],
    n: int = N_SAMPLE,
    seed: int = SEED,
    max_per_source: int = MAX_PER_SOURCE,
) -> list[TaskMeta]:
    if len(metas) < n:
        raise SystemExit(
            f"surviving SuperNI set {len(metas)} < {n}; stop, do not relax filters"
        )
    by_stratum: dict[str, list[TaskMeta]] = defaultdict(list)
    for meta in metas:
        by_stratum[meta.stratum].append(meta)
    for stratum in by_stratum:
        by_stratum[stratum].sort(key=lambda item: item.task_id)
    sizes = {s: len(by_stratum[s]) for s in by_stratum}
    quotas = _quotas(sizes, n)
    rng = random.Random(seed)
    source_count: dict[str, int] = defaultdict(int)
    picked: list[TaskMeta] = []
    picked_ids: set[str] = set()

    def _take_from(pool: list[TaskMeta], want: int) -> list[TaskMeta]:
        ordered = list(pool)
        rng.shuffle(ordered)
        taken: list[TaskMeta] = []
        for item in ordered:
            if len(taken) >= want:
                break
            if item.task_id in picked_ids:
                continue
            if source_count[item.source] >= max_per_source:
                continue
            taken.append(item)
            picked_ids.add(item.task_id)
            source_count[item.source] += 1
        return taken

    leftover = 0
    for stratum in sorted(by_stratum):
        want = quotas.get(stratum, 0)
        got = _take_from(by_stratum[stratum], want)
        picked.extend(got)
        leftover += max(0, want - len(got))

    if leftover:
        remaining = [item for item in metas if item.task_id not in picked_ids]
        remaining.sort(key=lambda item: item.task_id)
        picked.extend(_take_from(remaining, leftover))

    if len(picked) < n:
        raise SystemExit(
            f"source cap left only {len(picked)} tasks after spill; stop"
        )
    picked.sort(key=lambda item: item.task_id)
    return picked[:n]


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample 50 SuperNI tasks")
    parser.add_argument(
        "--tasks-dir",
        default=str(ROOT / "data_cache" / "natural-instructions" / "tasks"),
    )
    parser.add_argument("--n", type=int, default=N_SAMPLE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    tasks_dir = Path(args.tasks_dir)
    if not tasks_dir.is_dir():
        raise SystemExit(f"missing {tasks_dir}; clone natural-instructions first")
    metas = discover(tasks_dir)
    picked = stratified_sample(metas, n=args.n, seed=args.seed)
    rows = [
        {
            "task_id": item.task_id,
            "stratum": item.stratum,
            "source": item.source,
            "n_instances": item.n_instances,
            "path": item.path,
        }
        for item in picked
    ]
    payload = {
        "seed": args.seed,
        "n": args.n,
        "surviving": len(metas),
        "max_per_source": MAX_PER_SOURCE,
        "min_instances": MIN_INSTANCES,
        "tasks": rows,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
