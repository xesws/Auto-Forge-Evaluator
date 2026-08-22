#!/usr/bin/env python3
"""Serial single-pod runner. 3h cap, PARTIAL isolation, pre-reg determinism, incr harvest."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WALL_SEC = 3 * 60 * 60
PROTOCOL = ROOT / "configs" / "protocol_v2.yaml"
DET_SEED = 20260820


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_list(path: Path) -> list[str]:
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line.split()[0])
    return ids


def _write_status(run_dir: Path, status: str, **extra: object) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"status": status, "ts": _now(), **extra}
    (run_dir / "STATUS").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _latest_run(task_id: str) -> Path | None:
    runs = ROOT / "runs"
    if not runs.is_dir():
        return None
    cands = sorted(
        [p for p in runs.iterdir() if p.is_dir() and p.name.startswith(f"{task_id}__")],
        key=lambda p: p.name,
    )
    return cands[-1] if cands else None


def _full_rerun(started: int) -> bool:
    return started == 1 or started % 10 == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Serial task list for one A40 pod")
    parser.add_argument(
        "--list",
        default=str(ROOT / "docs" / "prod_lists" / "prod_serial.txt"),
    )
    parser.add_argument("--start-from", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    task_ids = _read_list(Path(args.list))
    if args.start_from:
        if args.start_from not in task_ids:
            raise SystemExit(f"{args.start_from} not in list")
        task_ids = task_ids[task_ids.index(args.start_from) :]
    summary: list[dict] = []
    completed_dirs: list[Path] = []
    started = 0
    harvest_k = 0
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    for task_id in task_ids:
        task_json = ROOT / "tasks" / task_id / "task.json"
        if not task_json.is_file():
            rec = {"task_id": task_id, "status": "skipped_missing", "returncode": None}
            summary.append(rec)
            print(f"{_now()} SKIP {task_id} missing task.json", flush=True)
            continue
        started += 1
        log_path = ROOT / "runs" / f"pod_{task_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            "-u",
            str(ROOT / "scripts" / "run_task.py"),
            "--task",
            task_id,
            "--protocol",
            str(PROTOCOL),
        ]
        if args.dry_run:
            cmd.append("--dry-run")
        print(f"{_now()} START {task_id} started={started}", flush=True)
        t0 = time.time()
        with log_path.open("w", encoding="utf-8") as log:
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=ROOT,
                    env=env,
                    timeout=WALL_SEC,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                rc = proc.returncode
                status = "ok" if rc == 0 else "PARTIAL"
            except subprocess.TimeoutExpired:
                rc = 124
                status = "over_budget"
        elapsed = time.time() - t0
        remain = max(1, int(WALL_SEC - elapsed))
        run_dir = _latest_run(task_id)
        if run_dir is not None and status != "over_budget":
            n_det = 200 if _full_rerun(started) else 30
            rerun_cmd = [
                sys.executable,
                str(ROOT / "scripts" / "rerun_eval_base.py"),
                "--run-dir",
                str(run_dir),
                "--n",
                str(n_det),
                "--seed",
                str(DET_SEED),
            ]
            try:
                det = subprocess.run(
                    rerun_cmd,
                    cwd=ROOT,
                    env=env,
                    timeout=remain,
                    check=False,
                )
                if det.returncode != 0 and status == "ok":
                    status = "PARTIAL"
            except subprocess.TimeoutExpired:
                status = "over_budget"
                rc = 124
            gate = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "gate_check.py"),
                    "--run-dir",
                    str(run_dir),
                ],
                cwd=ROOT,
                env=env,
                check=False,
            )
            if gate.returncode != 0 and status == "ok":
                status = "PARTIAL"
            _write_status(
                run_dir,
                status,
                returncode=rc,
                started=started,
                det_n=n_det,
                log=str(log_path),
            )
            completed_dirs.append(run_dir)
        elif run_dir is not None:
            _write_status(run_dir, status, returncode=rc, log=str(log_path))
            completed_dirs.append(run_dir)
        summary.append({"task_id": task_id, "status": status, "returncode": rc})
        print(f"{_now()} DONE {task_id} status={status} rc={rc}", flush=True)
        finished_gpu = [row for row in summary if row["status"] != "skipped_missing"]
        if len(finished_gpu) % 10 == 0 and completed_dirs:
            harvest_k += 1
            batch_dirs = completed_dirs[-10:]
            out = Path(f"/tmp/forge_incr_{harvest_k}.tar.gz")
            hcmd = [
                sys.executable,
                str(ROOT / "scripts" / "harvest_incr.py"),
                "--batch",
                str(harvest_k),
                "--out",
                str(out),
            ]
            for path in batch_dirs:
                hcmd.extend(["--run-dir", str(path)])
            subprocess.run(hcmd, cwd=ROOT, check=False)
            print(f"{_now()} HARVEST {out}", flush=True)
    out = ROOT / "runs" / "pod_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
