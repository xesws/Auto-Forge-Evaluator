#!/usr/bin/env python3
"""Pre-registered analysis (ANALYSIS_PREREG + S4).

Default is watermarked PRELIMINARY output. --final is the only citable path
and refuses to run unless --sensitivities-declared-commit is passed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WATERMARK = "PRELIMINARY — not quotable"
CHOICE = {
    "winogrande",
    "arc_easy",
    "arc_challenge",
    "hellaswag",
    "piqa",
}
MATH = {"gsm8k", "math"}
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20260820

SINGLE_FEATURES = (
    "delta_pilot",
    "base_pass1",
    "headroom",
    "pilot_loss.steps_to_0_01",
    "gen_len.full.median",
)


@dataclass
class Row:
    task_id: str
    run_dir: Path
    status: str
    go: int
    delta_pilot: float
    delta_full: float
    base_pass1: float
    full_pass1: float
    features: dict[str, float | None]
    text: dict[str, float]
    source: str | None
    dry_run: bool


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(float(value)):
            return None
        return float(value)
    return None


def _delta(block: Any, key: str) -> float | None:
    if isinstance(block, dict):
        return _as_float(block.get(key, block.get("pass1")))
    return _as_float(block)


def format_compliance_scalar(task_id: str, block: dict[str, Any] | None) -> float:
    if not block:
        return 0.0
    base = block.get("base") if "base" in block else block
    if not isinstance(base, dict):
        return 0.0
    n = int(base.get("n") or 0)
    if n <= 0:
        return 0.0
    if task_id == "gsm8k":
        return float(base.get("hash") or 0) / n
    unp = float(base.get("unparseable") or 0)
    return 1.0 - unp / n


def _nested(src: dict[str, Any], dotted: str) -> float | None:
    cur: Any = src
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return _as_float(cur)


def _status_of(run_dir: Path) -> str:
    path = run_dir / "STATUS"
    if not path.is_file():
        return "ok"
    raw = path.read_text(encoding="utf-8").strip()
    try:
        payload = json.loads(raw)
        return str(payload.get("status") or "ok")
    except json.JSONDecodeError:
        return raw.splitlines()[0]


def _load_superni_source() -> dict[str, str]:
    path = ROOT / "docs" / "prod_lists" / "superni_50.json"
    if not path.is_file():
        return {}
    blob = json.loads(path.read_text(encoding="utf-8"))
    return {row["task_id"]: str(row.get("source") or "") for row in blob.get("tasks", [])}


def _text_features(task_id: str) -> dict[str, float]:
    task_path = ROOT / "tasks" / task_id / "task.json"
    if not task_path.is_file():
        return {
            "splits.train_n": 0.0,
            "max_new_tokens": 0.0,
            "len(prompt_style)": 0.0,
            "eval_n": 0.0,
        }
    task = json.loads(task_path.read_text(encoding="utf-8"))
    splits = task.get("splits") or {}
    return {
        "splits.train_n": float(splits.get("train_n") or 0),
        "max_new_tokens": float(task.get("max_new_tokens") or 0),
        "len(prompt_style)": float(len(str(task.get("prompt_style") or ""))),
        "eval_n": float(splits.get("eval_n") or 0),
    }


def load_row(metrics_path: Path, sources: dict[str, str]) -> Row | None:
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics.get("dry_run"):
        return None
    run_dir = metrics_path.parent
    task_id = str(metrics["task_id"])
    signals = metrics.get("signals") or {}
    delta_full = _delta(metrics.get("delta_full"), "delta_full")
    delta_pilot = _delta(metrics.get("delta_pilot"), "delta_pilot")
    if delta_full is None or delta_pilot is None:
        return None
    base = metrics.get("base") or {}
    full = metrics.get("full") or {}
    base_pass1 = _as_float(base.get("pass1"))
    full_pass1 = _as_float(full.get("pass1"))
    if base_pass1 is None or full_pass1 is None:
        return None
    fc = format_compliance_scalar(task_id, metrics.get("format_compliance") or signals.get("format_compliance"))
    steps = _nested(signals, "pilot_loss.steps_to_0_01")
    features = {
        "delta_pilot": delta_pilot,
        "base_pass1": _as_float(signals.get("base_pass1")) or base_pass1,
        "base_pass8": _as_float(signals.get("base_pass8")),
        "headroom": _as_float(signals.get("headroom")),
        "train_n": _as_float(signals.get("train_n")),
        "full_n": _as_float(signals.get("full_n")),
        "pilot_loss.start": _nested(signals, "pilot_loss.start"),
        "pilot_loss.end": _nested(signals, "pilot_loss.end"),
        "pilot_loss.steps_to_0_01": steps,
        "pilot_loss.steps_to_0_01_missing": 1.0 if steps is None else 0.0,
        "format_compliance": fc,
        "gen_len.full.median": _nested(signals, "gen_len.full.median"),
    }
    return Row(
        task_id=task_id,
        run_dir=run_dir,
        status=_status_of(run_dir),
        go=int(delta_full > 0),
        delta_pilot=delta_pilot,
        delta_full=delta_full,
        base_pass1=base_pass1,
        full_pass1=full_pass1,
        features=features,
        text=_text_features(task_id),
        source=sources.get(task_id),
        dry_run=False,
    )


def collect_rows(roots: list[Path], *, ok_only: bool) -> list[Row]:
    sources = _load_superni_source()
    found: dict[str, Row] = {}
    for root in roots:
        for path in sorted(root.rglob("metrics.json")):
            if "adapters" in path.parts or "_isolated" in path.parts:
                continue
            row = load_row(path, sources)
            if row is None:
                continue
            if ok_only and row.status != "ok":
                continue
            prev = found.get(row.task_id)
            if prev is None or str(row.run_dir) > str(prev.run_dir):
                found[row.task_id] = row
    return [found[k] for k in sorted(found)]


def _matrix(rows: list[Row], names: list[str], lookup) -> np.ndarray:
    data = []
    for row in rows:
        data.append([lookup(row, name) for name in names])
    return np.asarray(data, dtype=float)  # (n,f)


def _lookup_feat(row: Row, name: str) -> float:
    val = row.features.get(name)
    return float("nan") if val is None else float(val)


def _lookup_text(row: Row, name: str) -> float:
    return float(row.text.get(name) or 0.0)


def _impute_train(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # train:(ntr,f) test:(nte,f)
    filled_tr = train.copy()
    filled_te = test.copy()
    for j in range(train.shape[1]):
        col = train[:, j]  # (ntr,)
        finite = col[np.isfinite(col)]  # (k,)
        fill = float(np.median(finite)) if finite.size else 0.0
        tr_nan = ~np.isfinite(filled_tr[:, j])
        te_nan = ~np.isfinite(filled_te[:, j])
        filled_tr[tr_nan, j] = fill
        filled_te[te_nan, j] = fill
    return filled_tr, filled_te


def _zscore(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = train.mean(axis=0)  # (f,)
    std = train.std(axis=0)  # (f,)
    std = np.where(std < 1e-12, 1.0, std)  # (f,)
    ztr = (train - mean) / std  # (ntr,f)
    zte = (test - mean) / std  # (nte,f)
    return ztr, zte


def _fit_predict(xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray) -> np.ndarray:
    from sklearn.linear_model import LogisticRegression

    if len(set(ytr.tolist())) < 2:
        return np.full(xte.shape[0], float(ytr.mean()), dtype=float)  # (nte,)
    clf = LogisticRegression(max_iter=2000, solver="lbfgs")
    clf.fit(xtr, ytr)  # xtr:(ntr,f) ytr:(ntr,)
    proba = clf.predict_proba(xte)  # (nte,2)
    classes = list(clf.classes_)
    if 1 in classes:
        return proba[:, classes.index(1)]  # (nte,)
    return np.zeros(xte.shape[0], dtype=float)


def loto_probs(rows: list[Row], names: list[str], lookup) -> np.ndarray:
    n = len(rows)
    X = _matrix(rows, names, lookup)  # (n,f)
    y = np.asarray([row.go for row in rows], dtype=float)  # (n,)
    preds = np.zeros(n, dtype=float)
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        xtr, xte = _impute_train(X[mask], X[i : i + 1])
        ztr, zte = _zscore(xtr, xte)
        preds[i] = float(_fit_predict(ztr, y[mask], zte)[0])
    return preds


def auc_score(y: np.ndarray, p: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    if len(set(y.tolist())) < 2:
        return float("nan")
    return float(roc_auc_score(y, p))


def bootstrap_auc(y: np.ndarray, p: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    n = y.shape[0]
    stats: list[float] = []
    for _ in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, size=n)  # (n,)
        stats.append(auc_score(y[idx], p[idx]))
    arr = np.asarray(stats, dtype=float)  # (B,)
    arr = arr[np.isfinite(arr)]
    point = auc_score(y, p)
    if arr.size == 0:
        return point, float("nan"), float("nan")
    lo, hi = np.quantile(arr, [0.025, 0.975])  # → 标量
    return point, float(lo), float(hi)


def spearman_ci(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    from scipy.stats import spearmanr

    rho = float(spearmanr(x, y).statistic)
    n = x.shape[0]
    stats: list[float] = []
    for _ in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, size=n)
        stats.append(float(spearmanr(x[idx], y[idx]).statistic))
    arr = np.asarray(stats, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return rho, float("nan"), float("nan")
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return rho, float(lo), float(hi)


def metric_floor(row: Row) -> bool:
    return row.base_pass1 == 0.0 and row.full_pass1 == 0.0


def subset(rows: list[Row], pred) -> list[Row]:
    return [row for row in rows if pred(row)]


def run_bundle(rows: list[Row], rng: np.random.Generator) -> dict[str, Any]:
    if len(rows) < 3:
        return {"n": len(rows), "skipped": "n<3"}
    y = np.asarray([row.go for row in rows], dtype=float)
    feat_names = [
        "delta_pilot",
        "base_pass1",
        "base_pass8",
        "headroom",
        "train_n",
        "full_n",
        "pilot_loss.start",
        "pilot_loss.end",
        "pilot_loss.steps_to_0_01",
        "pilot_loss.steps_to_0_01_missing",
        "format_compliance",
        "gen_len.full.median",
    ]
    p_main = loto_probs(rows, feat_names, _lookup_feat)
    auc, lo, hi = bootstrap_auc(y, p_main, rng)
    dp = np.asarray([row.delta_pilot for row in rows], dtype=float)
    df = np.asarray([row.delta_full for row in rows], dtype=float)
    rho, rlo, rhi = spearman_ci(dp, df, rng)
    singles = {}
    for name in SINGLE_FEATURES:
        p = loto_probs(rows, [name], _lookup_feat)
        s_auc, s_lo, s_hi = bootstrap_auc(y, p, rng)
        singles[name] = {"auc": s_auc, "ci95": [s_lo, s_hi]}
    text_names = list(rows[0].text.keys())
    p_text = loto_probs(rows, text_names, _lookup_text)
    t_auc, t_lo, t_hi = bootstrap_auc(y, p_text, rng)
    return {
        "n": len(rows),
        "n_go": int(y.sum()),
        "main": {"auc": auc, "ci95": [lo, hi], "covers_0.5": bool(lo <= 0.5 <= hi) if math.isfinite(lo) else None},
        "spearman": {"rho": rho, "ci95": [rlo, rhi]},
        "single_feature": singles,
        "text_only": {"auc": t_auc, "ci95": [t_lo, t_hi]},
        "task_ids": [row.task_id for row in rows],
        "y": y.tolist(),
        "p_main": p_main.tolist(),
        "delta_pilot": dp.tolist(),
        "delta_full": df.tolist(),
    }


def _stamp_fig(fig, watermark: str | None) -> None:
    if not watermark:
        return
    fig.text(0.5, 0.02, watermark, ha="center", va="bottom", fontsize=9, color="red")


def write_plots(bundle: dict[str, Any], out_dir: Path, watermark: str | None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dp = np.asarray(bundle["delta_pilot"], dtype=float)
    df = np.asarray(bundle["delta_full"], dtype=float)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(dp, df, c=["#1f77b4" if g else "#d62728" for g in bundle["y"]])
    lim = max(0.05, float(np.nanmax(np.abs(np.concatenate([dp, df])))) * 1.1)
    ax.plot([-lim, lim], [-lim, lim], color="gray", lw=1)
    ax.axhline(0, color="black", lw=0.5)
    ax.axvline(0, color="black", lw=0.5)
    ax.set_xlabel("delta_pilot")
    ax.set_ylabel("delta_full")
    ax.set_title("calibration")
    _stamp_fig(fig, watermark)
    fig.tight_layout()
    fig.savefig(out_dir / "calibration_scatter.png", dpi=120)
    plt.close(fig)

    from sklearn.metrics import roc_curve

    y = np.asarray(bundle["y"], dtype=float)
    p = np.asarray(bundle["p_main"], dtype=float)
    if len(set(y.tolist())) < 2:
        return
    fpr, tpr, _ = roc_curve(y, p)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(fpr, tpr)
    ax.plot([0, 1], [0, 1], color="gray", lw=1)
    ax.set_xlabel("FPR")
    ax.set_ylabel("TPR")
    ax.set_title("ROC LOTO main")
    _stamp_fig(fig, watermark)
    fig.tight_layout()
    fig.savefig(out_dir / "roc.png", dpi=120)
    plt.close(fig)


def write_report(payload: dict[str, Any], path: Path, watermark: str | None) -> None:
    lines = [
        f"# {'PRELIMINARY analysis (not quotable)' if watermark else 'Analysis (citable)'}",
        "",
        f"- 时间 (UTC): {payload['ts']}",
        f"- git HEAD: `{payload['git_head']}`",
        f"- 协议: protocol_v2 / pv2",
        f"- 数据包: tv3 leftover + tv4/tv5 metrics",
        f"- n: {payload['main_bundle']['n']}",
        "",
    ]
    if watermark:
        lines += [f"**{watermark}**", ""]
        lines += ["本文件数字不可引用。最终可引用报告只来自 `--final`。", ""]
    else:
        main = payload["main_bundle"]
        lines += [
            "本文件数字可引用。主分析按 ANALYSIS_PREREG + S4。",
            "",
            f"- main LOTO AUC: {main.get('main')}",
            f"- Spearman: {main.get('spearman')}",
            f"- text-only: {main.get('text_only')}",
            f"- sensitivities keys: {sorted((payload.get('sensitivities') or {}).keys())}",
            "",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # numeric payload is json beside the md so prelim numbers stay in the out dir
    (path.with_suffix(".json")).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def _git_head() -> str:
    head = ROOT / ".git" / "HEAD"
    if not head.is_file():
        return "unknown"
    ref = head.read_text(encoding="utf-8").strip()
    if ref.startswith("ref:"):
        ref_path = ROOT / ".git" / ref.split(" ", 1)[1]
        if ref_path.is_file():
            return ref_path.read_text(encoding="utf-8").strip()[:12]
    return ref[:12]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-root", action="append", dest="roots", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--ok-only", action="store_true")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--sensitivities-declared-commit", default="")
    parser.add_argument("--include-partial-with-metrics", action="store_true")
    args = parser.parse_args()
    if args.final and not args.sensitivities_declared_commit:
        raise SystemExit("--final requires --sensitivities-declared-commit (S4 sha)")
    watermark = None if args.final else WATERMARK
    ok_only = bool(args.ok_only or not args.final)
    if args.final:
        ok_only = False
    rows = collect_rows([Path(p) for p in args.roots], ok_only=ok_only)
    if args.final:
        rows = [row for row in rows if row.status == "ok" or (row.status == "PARTIAL" and True)]
        # PARTIAL with metrics kept; over_budget without metrics already dropped
        rows = [row for row in rows if row.status != "over_budget"]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    main_bundle = run_bundle(rows, rng)
    payload: dict[str, Any] = {
        "ts": _now(),
        "git_head": _git_head(),
        "watermark": watermark,
        "ok_only": ok_only,
        "main_bundle": {k: v for k, v in main_bundle.items() if k not in {"y", "p_main"}},
        "sensitivities": {},
    }
    if args.final:
        a_rows = [row for row in rows if row.task_id != "arc_easy"]
        b_rows = [row for row in rows if not metric_floor(row)]
        payload["sensitivities"]["a_drop_arc_easy"] = {
            k: v for k, v in run_bundle(a_rows, rng).items() if k not in {"y", "p_main", "delta_pilot", "delta_full"}
        }
        payload["sensitivities"]["b_drop_metric_floor"] = {
            k: v
            for k, v in run_bundle(b_rows, rng).items()
            if k not in {"y", "p_main", "delta_pilot", "delta_full"}
        }
        payload["sensitivities"]["b_floor_ids"] = [row.task_id for row in rows if metric_floor(row)]
        choice_rows = [row for row in rows if row.task_id in CHOICE]
        math_rows = [row for row in rows if row.task_id in MATH]
        by_source: dict[str, list[Row]] = {}
        for row in rows:
            if row.source:
                by_source.setdefault(row.source, []).append(row)
        payload["sensitivities"]["c_choice"] = {
            k: v for k, v in run_bundle(choice_rows, rng).items() if k not in {"y", "p_main", "delta_pilot", "delta_full"}
        }
        payload["sensitivities"]["c_math"] = {
            k: v for k, v in run_bundle(math_rows, rng).items() if k not in {"y", "p_main", "delta_pilot", "delta_full"}
        }
        payload["sensitivities"]["c_superni_source"] = {
            src: {
                k: v
                for k, v in run_bundle(group, rng).items()
                if k not in {"y", "p_main", "delta_pilot", "delta_full"}
            }
            for src, group in sorted(by_source.items())
        }
    write_plots(main_bundle, out_dir, watermark)
    report_name = "ANALYSIS_PRELIMINARY.md" if watermark else "ANALYSIS_RESULTS.md"
    write_report(payload, out_dir / report_name, watermark)
    # stdout: counts only (no AUC)
    print(
        f"wrote n={len(rows)} status_ok={sum(r.status=='ok' for r in rows)} "
        f"out={out_dir} watermark={watermark or 'none'}",
        flush=True,
    )


if __name__ == "__main__":
    main()
