"""MBPP / APPS code execution sandbox: 10s, no net, tmpdir, 2 GiB AS cap."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

TIMEOUT_SEC = 10
AS_LIMIT_KB = 2_097_152  # 2 GiB, frozen in ANALYSIS_PREREG_SUPPLEMENT.md
_FENCE_RE = re.compile(r"```(?:python)?\s*([\s\S]*?)```", re.IGNORECASE)


def _extract_code(output: str) -> str | None:
    fence = _FENCE_RE.search(output)
    if fence:
        body = fence.group(1).strip()
        return body or None
    text = output.strip()
    if not text:
        return None
    return text


def _preexec() -> None:
    try:
        import resource

        resource.setrlimit(
            resource.RLIMIT_AS, (AS_LIMIT_KB * 1024, AS_LIMIT_KB * 1024)
        )
        resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SEC, TIMEOUT_SEC))
    except (ValueError, OSError):
        pass


def _runner_script(kind: str) -> str:
    if kind == "mbpp":
        return """
import json, pathlib, traceback
payload = json.loads(pathlib.Path("payload.json").read_text())
ns = {}
try:
    exec(payload["code"], ns, ns)
    exec(payload["tests"], ns, ns)
except Exception as exc:
    pathlib.Path("result.json").write_text(
        json.dumps({"ok": False, "exc": type(exc).__name__, "detail": str(exc)})
    )
    raise SystemExit(1)
pathlib.Path("result.json").write_text(json.dumps({"ok": True}))
"""
    return """
import json, pathlib, io, contextlib
payload = json.loads(pathlib.Path("payload.json").read_text())
ns = {}
try:
    exec(payload["code"], ns, ns)
except Exception as exc:
    pathlib.Path("result.json").write_text(
        json.dumps({"ok": False, "exc": type(exc).__name__, "detail": str(exc)})
    )
    raise SystemExit(1)
fn = None
for name in ("solution", "solve", "main"):
    if callable(ns.get(name)):
        fn = ns[name]
        break
cases = payload.get("io") or []
failed = []
for i, case in enumerate(cases):
    stdin = str(case.get("input", ""))
    expected = str(case.get("output", "")).strip()
    buf = io.StringIO()
    try:
        if fn is not None:
            import inspect
            if len(inspect.signature(fn).parameters) == 0:
                with contextlib.redirect_stdout(buf):
                    got = fn()
            else:
                with contextlib.redirect_stdout(buf):
                    got = fn(stdin)
            printed = buf.getvalue().strip()
            actual = printed if printed else str(got).strip()
        else:
            import sys as _sys
            old = _sys.stdin
            _sys.stdin = io.StringIO(stdin)
            try:
                with contextlib.redirect_stdout(buf):
                    exec(payload["code"], ns, ns)
            finally:
                _sys.stdin = old
            actual = buf.getvalue().strip()
    except Exception as exc:
        failed.append({"i": i, "exc": type(exc).__name__, "detail": str(exc)})
        continue
    if actual != expected:
        failed.append({"i": i, "got": actual, "expected": expected})
if failed:
    pathlib.Path("result.json").write_text(
        json.dumps({"ok": False, "exc": "AssertError", "failed": failed})
    )
    raise SystemExit(1)
pathlib.Path("result.json").write_text(json.dumps({"ok": True, "n": len(cases)}))
"""


def _run(code: str, reference: dict) -> dict[str, Any]:
    kind = str(reference.get("kind") or "mbpp")
    payload: dict[str, Any] = {"code": code}
    if kind == "mbpp":
        tests = reference.get("tests")
        if not tests:
            return {"ok": False, "exc": "ConfigError", "detail": "missing tests"}
        payload["tests"] = str(tests)
    else:
        payload["io"] = reference.get("io") or []
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": "",
        "HOME": "",
        "LANG": "C",
    }
    with tempfile.TemporaryDirectory(prefix="forge_sandbox_") as tmp:
        root = Path(tmp)
        (root / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
        (root / "run.py").write_text(_runner_script(kind), encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "run.py"],
                cwd=root,
                env=env,
                timeout=TIMEOUT_SEC,
                capture_output=True,
                text=True,
                preexec_fn=_preexec if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "exc": "TimeoutError", "detail": f">{TIMEOUT_SEC}s"}
        result_path = root / "result.json"
        if result_path.is_file():
            try:
                return json.loads(result_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"ok": False, "exc": "ParseError", "detail": "bad result.json"}
        if proc.returncode != 0:
            return {
                "ok": False,
                "exc": "RuntimeError",
                "detail": (proc.stderr or proc.stdout or "")[:500],
            }
        return {"ok": False, "exc": "RuntimeError", "detail": "no result.json"}


def verify(output: str, reference: dict) -> dict[str, Any]:
    parsed = _extract_code(output)
    if parsed is None:
        note = json.dumps({"unparseable": True}, ensure_ascii=False)
        return {"pass": False, "parsed": None, "note": note}
    result = _run(parsed, reference)
    ok = bool(result.get("ok"))
    note = json.dumps(
        {
            "unparseable": False,
            "exception": None if ok else result.get("exc"),
            "detail": None if ok else result.get("detail") or result.get("failed"),
        },
        ensure_ascii=False,
    )
    return {"pass": ok, "parsed": parsed, "note": note}
