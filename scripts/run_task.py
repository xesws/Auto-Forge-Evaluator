#!/usr/bin/env python3
"""Single-task pipeline S0–S6 (MANUAL §6). Resume from journal stage boundaries."""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import (  # noqa: E402
    LocalStorage,
    latest_tasks_ver,
    load_jsonl,
    load_protocol,
    load_task_json,
    load_verifier,
    sha256_file,
    verify_spider_zip,
    verify_task_manifest,
    warn_long_prompts,
)
from src.eval_greedy import eval_split  # noqa: E402
from src.signals import pass_at_1, pass_at_k  # noqa: E402
from src.train_lora import (  # noqa: E402
    attach_lora,
    load_adapter,
    load_base_model,
    resolve_device,
    train_lora,
)

LOG = logging.getLogger("forge.run")
STAGES = ("S0", "S1", "S2", "S3", "S4", "S5", "S6")
DRY_RUN_STEPS = 2
DRY_RUN_EVAL_N = 5


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M")


def protocol_ver(protocol_path: Path) -> str:
    name = protocol_path.stem  # protocol_v1
    if name.startswith("protocol_"):
        return name.split("_", 1)[1]  # v1
    return name


def journal_path(run_dir: Path) -> Path:
    return run_dir / "journal.jsonl"


def append_journal(run_dir: Path, stage: str, event: str, **extra: Any) -> None:
    rec = {"stage": stage, "event": event, "ts": _now(), **extra}
    with journal_path(run_dir).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(rec, ensure_ascii=False) + "\n")


def done_stages(run_dir: Path) -> set[str]:
    path = journal_path(run_dir)
    if not path.is_file():
        return set()
    done: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("event") == "done" and rec.get("stage") in STAGES:
            done.add(rec["stage"])
    return done


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def sample_rows(rows: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
    if n >= len(rows):
        return list(rows)
    rng = random.Random(seed)
    idxs = rng.sample(range(len(rows)), n)
    return [rows[i] for i in idxs]


def collect_systems(
    protocol: dict[str, Any],
    model_name: str,
    resolved_rev: str | None,
    device: torch.device,
    dry_run: bool,
    seeds: dict[str, Any],
) -> dict[str, Any]:
    cuda = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda else None
    driver = None
    if cuda:
        try:
            import subprocess

            driver = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                text=True,
            ).strip().splitlines()[0]
        except Exception:  # noqa: BLE001
            driver = None
    import transformers

    return {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cuda": torch.version.cuda,
        "cuda_available": cuda,
        "device": str(device),
        "gpu_name": gpu_name,
        "driver": driver,
        "base_model": model_name,
        "base_revision": resolved_rev or protocol.get("base_revision"),
        "dry_run": dry_run,
        "seeds": seeds,
    }


def stage_eval(
    *,
    tag: str,
    model: Any,
    tokenizer: Any,
    rows: list[dict[str, Any]],
    verifier: Any,
    task: dict[str, Any],
    protocol: dict[str, Any],
    device: torch.device,
    run_dir: Path,
    with_pass8: bool,
    dry_run: bool,
) -> dict[str, float]:
    max_new = 16 if dry_run else int(task["max_new_tokens"])
    extract_div = run_dir / "extract_div.jsonl"
    greedy = eval_split(
        model,
        tokenizer,
        rows,
        verifier,
        max_new_tokens=max_new,
        device=device,
        do_sample=False,
        extract_div_path=extract_div,
    )
    dump_jsonl(run_dir / f"eval_{tag}_greedy.jsonl", greedy)
    metrics = {"pass1": pass_at_1(greedy)}
    if with_pass8:
        sig = protocol["signals"]["pass8"]
        sampled = eval_split(
            model,
            tokenizer,
            rows,
            verifier,
            max_new_tokens=max_new,
            device=device,
            do_sample=True,
            temperature=float(sig["temperature"]),
            top_p=float(sig["top_p"]),
            num_return=int(sig["k"]),
        )
        dump_jsonl(run_dir / f"eval_{tag}_pass8.jsonl", sampled)
        metrics["pass8"] = pass_at_k(sampled)
    dump_json(run_dir / f"eval_{tag}_metrics.json", metrics)
    return metrics


def run(args: argparse.Namespace) -> None:
    protocol_path = Path(args.protocol).resolve()
    protocol = load_protocol(protocol_path)
    task_id = args.task
    task_dir = ROOT / "tasks" / task_id
    pver = protocol_ver(protocol_path)
    tver = args.tasks_ver or latest_tasks_ver(ROOT)
    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    else:
        run_dir = ROOT / "runs" / f"{task_id}__p{pver}__{tver}__{_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    storage = LocalStorage(run_dir)
    done = done_stages(run_dir)
    dry_run = bool(args.dry_run)
    if "S6" in done:
        LOG.info("run already sealed at %s", run_dir)
        return
    if not dry_run and not torch.cuda.is_available():
        raise SystemExit(
            "non-dry-run requires CUDA. This machine has none. Use --dry-run."
        )

    device = resolve_device(dry_run)
    task = load_task_json(task_dir)
    train_rows = load_jsonl(task_dir / "train.jsonl")
    eval_rows = load_jsonl(task_dir / "eval.jsonl")
    if dry_run:
        eval_rows = eval_rows[:DRY_RUN_EVAL_N]
        steps_pilot = DRY_RUN_STEPS
        steps_full = DRY_RUN_STEPS
    else:
        steps_pilot = int(protocol["pilot"]["steps"])
        # full: epochs over cap; step count not in protocol — train by epochs via steps
        # MANUAL full is cap × 3ep. Approximate steps from n/batch.
        cap = min(int(protocol["full"]["cap"]), len(train_rows))
        batch = int(protocol["train"]["per_device_batch"])
        accum = int(protocol["train"]["grad_accum"])
        steps_per_epoch = max(1, (cap + batch * accum - 1) // (batch * accum))
        steps_full = steps_per_epoch * int(protocol["full"]["epochs"])

    seeds = {
        "train_seed": int(protocol["seeds"]["train_seed"]),
        "pilot_sample_seed": int(protocol["pilot"]["sample_seed"]),
        "full_sample_seed": int(protocol["full"]["sample_seed"]),
        "eval_slice_seed": int(protocol["eval"]["slice_seed"]),
    }
    state: dict[str, Any] = {"base_pass1": None, "pilot_pass1": None, "full_pass1": None}

    # S0
    if "S0" not in done:
        append_journal(run_dir, "S0", "start")
        verify_task_manifest(task_dir)
        if task_id == "spider":
            verify_spider_zip(task, ROOT)
        verifier = load_verifier(task_dir)
        model, tokenizer, model_name, resolved_rev = load_base_model(
            protocol, dry_run=dry_run, device=device
        )
        warn_long_prompts(
            eval_rows + train_rows[: min(32, len(train_rows))],
            lambda text: len(tokenizer.encode(text, add_special_tokens=False)),
        )
        dump_json(
            run_dir / "s0_loaded.json",
            {
                "task_id": task_id,
                "model_name": model_name,
                "resolved_rev": resolved_rev,
                "eval_n": len(eval_rows),
                "train_n": len(train_rows),
                "dry_run": dry_run,
            },
        )
        append_journal(run_dir, "S0", "done", model=model_name, revision=resolved_rev)
    else:
        LOG.info("skip S0 (already done)")
        verifier = load_verifier(task_dir)
        model, tokenizer, model_name, resolved_rev = load_base_model(
            protocol, dry_run=dry_run, device=device
        )

    def reload_base() -> Any:
        base, _, _, _ = load_base_model(protocol, dry_run=dry_run, device=device)
        return base

    # S1 eval_base
    if "S1" not in done:
        append_journal(run_dir, "S1", "start")
        metrics = stage_eval(
            tag="base",
            model=model,
            tokenizer=tokenizer,
            rows=eval_rows,
            verifier=verifier,
            task=task,
            protocol=protocol,
            device=device,
            run_dir=run_dir,
            with_pass8=True,
            dry_run=dry_run,
        )
        state["base_pass1"] = metrics["pass1"]
        append_journal(run_dir, "S1", "done", **metrics)
    else:
        LOG.info("skip S1 (already done)")
        prev = json.loads((run_dir / "eval_base_metrics.json").read_text(encoding="utf-8"))
        state["base_pass1"] = prev["pass1"]

    # S2 pilot_train
    if "S2" not in done:
        append_journal(run_dir, "S2", "start")
        n_pilot = int(protocol["pilot"]["n"])
        pilot_rows = sample_rows(train_rows, n_pilot, seeds["pilot_sample_seed"])
        base = reload_base()
        lora_model = attach_lora(base, protocol, dry_run=dry_run)
        train_lora(
            lora_model,
            tokenizer,
            pilot_rows,
            task_id,
            protocol,
            device,
            steps=steps_pilot,
            out_dir=run_dir / "adapters" / "pilot",
            dry_run=dry_run,
            seed=seeds["train_seed"],
        )
        append_journal(run_dir, "S2", "done", n=len(pilot_rows), steps=steps_pilot)
    else:
        LOG.info("skip S2 (already done)")

    # S3 eval_pilot
    if "S3" not in done:
        append_journal(run_dir, "S3", "start")
        base = reload_base()
        model_p = load_adapter(base, run_dir / "adapters" / "pilot")
        model_p.to(device)
        metrics = stage_eval(
            tag="pilot",
            model=model_p,
            tokenizer=tokenizer,
            rows=eval_rows,
            verifier=verifier,
            task=task,
            protocol=protocol,
            device=device,
            run_dir=run_dir,
            with_pass8=False,
            dry_run=dry_run,
        )
        state["pilot_pass1"] = metrics["pass1"]
        delta = metrics["pass1"] - float(state["base_pass1"])
        dump_json(run_dir / "delta_pilot.json", {"delta_pilot": delta, **metrics})
        append_journal(run_dir, "S3", "done", pass1=metrics["pass1"], delta_pilot=delta)
        del model_p
    else:
        LOG.info("skip S3 (already done)")
        prev = json.loads((run_dir / "eval_pilot_metrics.json").read_text(encoding="utf-8"))
        state["pilot_pass1"] = prev["pass1"]

    # S4 full_train
    if "S4" not in done:
        append_journal(run_dir, "S4", "start")
        cap = min(int(protocol["full"]["cap"]), len(train_rows))
        full_rows = sample_rows(train_rows, cap, seeds["full_sample_seed"])
        base = reload_base()
        lora_model = attach_lora(base, protocol, dry_run=dry_run)
        train_lora(
            lora_model,
            tokenizer,
            full_rows,
            task_id,
            protocol,
            device,
            steps=steps_full,
            out_dir=run_dir / "adapters" / "full",
            dry_run=dry_run,
            seed=seeds["train_seed"],
        )
        append_journal(run_dir, "S4", "done", n=len(full_rows), steps=steps_full)
    else:
        LOG.info("skip S4 (already done)")

    # S5 eval_full
    if "S5" not in done:
        append_journal(run_dir, "S5", "start")
        base = reload_base()
        model_f = load_adapter(base, run_dir / "adapters" / "full")
        model_f.to(device)
        metrics = stage_eval(
            tag="full",
            model=model_f,
            tokenizer=tokenizer,
            rows=eval_rows,
            verifier=verifier,
            task=task,
            protocol=protocol,
            device=device,
            run_dir=run_dir,
            with_pass8=False,
            dry_run=dry_run,
        )
        state["full_pass1"] = metrics["pass1"]
        delta = metrics["pass1"] - float(state["base_pass1"])
        dump_json(run_dir / "delta_full.json", {"delta_full": delta, **metrics})
        append_journal(run_dir, "S5", "done", pass1=metrics["pass1"], delta_full=delta)
        del model_f
    else:
        LOG.info("skip S5 (already done)")
        prev = json.loads((run_dir / "eval_full_metrics.json").read_text(encoding="utf-8"))
        state["full_pass1"] = prev["pass1"]

    # S6 seal
    if "S6" not in done:
        append_journal(run_dir, "S6", "start")
        hashes = {}
        for path in sorted(run_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.name in {"metrics.json", "journal.jsonl"}:
                continue
            hashes[str(path.relative_to(run_dir))] = sha256_file(path)
        metrics = {
            "task_id": task_id,
            "protocol": protocol_path.name,
            "tasks_ver": tver,
            "run_dir": str(run_dir),
            "dry_run": dry_run,
            "base": json.loads((run_dir / "eval_base_metrics.json").read_text(encoding="utf-8")),
            "pilot": json.loads((run_dir / "eval_pilot_metrics.json").read_text(encoding="utf-8")),
            "full": json.loads((run_dir / "eval_full_metrics.json").read_text(encoding="utf-8")),
            "delta_pilot": json.loads((run_dir / "delta_pilot.json").read_text(encoding="utf-8")),
            "delta_full": json.loads((run_dir / "delta_full.json").read_text(encoding="utf-8")),
            "systems": collect_systems(
                protocol,
                model_name,
                resolved_rev,
                device,
                dry_run,
                seeds,
            ),
            "hashes": hashes,
        }
        dump_json(run_dir / "metrics.json", metrics)
        storage.put("metrics.json", (run_dir / "metrics.json").read_bytes())
        append_journal(
            run_dir,
            "S6",
            "done",
            metrics_sha256=sha256_file(run_dir / "metrics.json"),
        )
    else:
        LOG.info("skip S6 (already done)")
    LOG.info("run complete %s", run_dir)


def main() -> None:
    import os

    os.chdir(ROOT)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Run one task pipeline")
    parser.add_argument("--task", required=True, choices=("gsm8k", "winogrande", "spider"))
    parser.add_argument("--protocol", default=str(ROOT / "configs" / "protocol_v2.yaml"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-dir", default=None)
    parser.add_argument("--tasks-ver", default=None)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
