#!/usr/bin/env python3
"""Reload base (no LoRA) and greedy-eval a subset. Pre-reg determinism."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import load_jsonl, load_protocol, load_task_json, load_verifier  # noqa: E402
from src.eval_greedy import eval_split  # noqa: E402
from src.train_lora import load_base_model, resolve_device  # noqa: E402


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260820)
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    task_id = metrics["task_id"]
    protocol = load_protocol(ROOT / "configs" / metrics["protocol"])
    device = resolve_device(False)
    task_dir = ROOT / "tasks" / task_id
    task = load_task_json(task_dir)
    orig = load_jsonl(run / "eval_base_greedy.jsonl")
    orig_ids = [row["id"] for row in orig]
    if args.n >= len(orig_ids):
        keep = set(orig_ids)
    else:
        keep = set(random.Random(args.seed).sample(orig_ids, args.n))
    gold_rows = load_jsonl(task_dir / "eval.jsonl")
    rows = [row for row in gold_rows if row["id"] in keep]
    verifier = load_verifier(task_dir)
    model, tokenizer, _name, rev = load_base_model(
        protocol, dry_run=False, device=device
    )
    greedy = eval_split(
        model,
        tokenizer,
        rows,
        verifier,
        max_new_tokens=int(task["max_new_tokens"]),
        device=device,
        do_sample=False,
    )
    out = run / "eval_base_greedy_rerun.jsonl"
    dump_jsonl(out, greedy)
    orig_pass = {row["id"]: bool(row["samples"][0]["pass"]) for row in orig}
    new_pass = {row["id"]: bool(row["samples"][0]["pass"]) for row in greedy}
    mismatch = [key for key in sorted(new_pass) if orig_pass.get(key) != new_pass[key]]
    print(
        json.dumps(
            {
                "task_id": task_id,
                "revision": rev,
                "n_rerun": len(greedy),
                "mismatch": len(mismatch),
            }
        ),
        flush=True,
    )
    if mismatch:
        raise SystemExit("DETERMINISM_FAIL")
    print("DETERMINISM_OK", flush=True)


if __name__ == "__main__":
    main()
