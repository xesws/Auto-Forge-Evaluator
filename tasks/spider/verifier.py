"""Spider verifier (MANUAL §5). Execution match, row-order-independent multiset."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

_TIMEOUT_SEC = 30
_FENCE_RE = re.compile(r"```(?:sql)?\s*([\s\S]*?)```", re.IGNORECASE)
_SQL_KW_RE = re.compile(
    r"\b(SELECT|WITH|INSERT|UPDATE|DELETE|REPLACE)\b", re.IGNORECASE
)


def _parse_sql(output: str) -> str | None:
    fence = _FENCE_RE.search(output)
    candidate = fence.group(1).strip() if fence else output.strip()
    if not candidate or _SQL_KW_RE.search(candidate) is None:
        return None
    return candidate


def _run_sql(db_path: str, sql: str) -> tuple:
    box: dict[str, Any] = {}
    holder: dict[str, sqlite3.Connection] = {}

    def _target() -> None:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        holder["conn"] = conn
        try:
            box["rows"] = conn.execute(sql).fetchall()
        except Exception as exc:  # noqa: BLE001 — surface sqlite error type in note
            box["err"] = (type(exc).__name__, str(exc))
        finally:
            conn.close()

    worker = threading.Thread(target=_target)
    worker.start()
    worker.join(_TIMEOUT_SEC)
    if worker.is_alive():
        conn = holder.get("conn")
        if conn is not None:
            conn.interrupt()
        worker.join(1.0)
        return ("timeout",)
    if "err" in box:
        return ("err", box["err"][0], box["err"][1])
    if "rows" in box:
        return ("ok", box["rows"])
    return ("timeout",)


def _multiset(rows: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = json.dumps(list(row), ensure_ascii=False, default=str)
        counts[key] = counts.get(key, 0) + 1
    return counts


def verify(output: str, reference: dict) -> dict[str, Any]:
    parsed = _parse_sql(output)
    if parsed is None:
        note = json.dumps({"unparseable": True}, ensure_ascii=False)
        return {"pass": False, "parsed": None, "note": note}

    db_path = str(Path(reference["db_path"]).resolve())
    gold_sql = str(reference["query"])

    pred_result = _run_sql(db_path, parsed)
    if pred_result[0] == "timeout":
        note = json.dumps(
            {"unparseable": False, "exception": "TimeoutError"},
            ensure_ascii=False,
        )
        return {"pass": False, "parsed": parsed, "note": note}
    if pred_result[0] == "err":
        note = json.dumps(
            {
                "unparseable": False,
                "exception": pred_result[1],
                "detail": pred_result[2],
            },
            ensure_ascii=False,
        )
        return {"pass": False, "parsed": parsed, "note": note}

    gold_result = _run_sql(db_path, gold_sql)
    if gold_result[0] != "ok":
        note = json.dumps(
            {
                "unparseable": False,
                "exception": "GoldSQLError",
                "gold_result": list(gold_result),
            },
            ensure_ascii=False,
        )
        return {"pass": False, "parsed": parsed, "note": note}

    pred_rows = pred_result[1]
    gold_rows = gold_result[1]
    matched = _multiset(pred_rows) == _multiset(gold_rows)
    note = json.dumps(
        {
            "unparseable": False,
            "exception": None,
            "n_pred": len(pred_rows),
            "n_gold": len(gold_rows),
            "match": matched,
        },
        ensure_ascii=False,
    )
    return {"pass": bool(matched), "parsed": parsed, "note": note}
