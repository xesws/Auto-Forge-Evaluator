#!/usr/bin/env python3
"""Serial pod runner: two static lists, no orchestrator. 3h cap per task."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WALL_SEC = 3 * 60 * 60
PROTOCOL = ROOT / "configs" / "protocol_v2.yaml"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Serial task list for one A40 pod")
    parser.add_argument("--list", required=True, help="text file of task ids")
    parser.add_argument("--start-from", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    task_ids = _read_list(Path(args.list))
    if args.start_from:
        if args.start_from not in task_ids:
            raise SystemExit(f"{args.start_from} not in list")
        task_ids = task_ids[task_ids.index(args.start_from) :]
    summary: list[dict] = []
    for index, task_id in enumerate(task_ids):
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
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        print(f"{_now()} START {task_id} ({index + 1}/{len(task_ids)})", flush=True)
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
        run_dir = _latest_run(task_id)
        if run_dir is not None:
            _write_status(run_dir, status, returncode=rc, log=str(log_path))
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
                    run_dir, status, returncode=rc, gate=gate.returncode, log=str(log_path)
                )
        summary.append({"task_id": task_id, "status": status, "returncode": rc})
        print(f"{_now()} DONE {task_id} status={status} rc={rc}", flush=True)
    out = ROOT / "runs" / "pod_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
