#!/usr/bin/env python3
"""Citable figures from frozen plot_data.json. Does not rewrite ANALYSIS_RESULTS.

    python scripts/plot_citable_figures.py --refresh-data
    python scripts/plot_citable_figures.py

Quoted numbers live only in docs/ANALYSIS_RESULTS.md. This script redraws
scatter / ROC+band / base-rate bar from the frozen arrays.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIG = ROOT / "docs" / "figures"
DATA = FIG / "plot_data.json"
RESULTS = ROOT / "docs" / "ANALYSIS_RESULTS.json"
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20260820
FPR_GRID = np.linspace(0.0, 1.0, 101)  # (G,)

CHOICE = {"winogrande", "arc_easy", "arc_challenge", "hellaswag", "piqa"}
MATH = {"gsm8k", "math"}
SQL = {"spider"}
CODE = {"mbpp"}
READING = {"drop", "tydiqa"}
CLUSTER_COLOR = {
    "choice": "#1f77b4",
    "math": "#d62728",
    "reading": "#2ca02c",
    "code": "#ff7f0e",
    "sql": "#9467bd",
    "superni": "#7f7f7f",
}
ANNOTATE = {"gsm8k", "math"}


def cluster_of(task_id: str) -> str:
    if task_id in CHOICE:
        return "choice"
    if task_id in MATH:
        return "math"
    if task_id in SQL:
        return "sql"
    if task_id in CODE:
        return "code"
    if task_id in READING:
        return "reading"
    return "superni"


def _load_analysis():
    import importlib.util

    path = ROOT / "scripts" / "analysis.py"
    spec = importlib.util.spec_from_file_location("analysis_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _refresh_data() -> dict:
    """One-time export of frozen arrays. Does not write ANALYSIS_RESULTS.*."""
    an = _load_analysis()

    blob = json.loads(RESULTS.read_text(encoding="utf-8"))
    main = blob["main_bundle"]
    task_ids = list(main["task_ids"])
    dp = [float(x) for x in main["delta_pilot"]]
    df = [float(x) for x in main["delta_full"]]
    go = [int(x > 0) for x in df]
    if len(task_ids) != 61 or sum(go) != 53:
        raise SystemExit(
            f"frozen sample drift: n={len(task_ids)} n_go={sum(go)} (want 61/53)"
        )
    roots = [
        ROOT / "runs" / "harvest" / "extracted",
        ROOT / "runs",
    ]
    rows = an.collect_rows(roots, ok_only=False)
    by_id = {row.task_id: row for row in rows}
    ordered = []
    missing = []
    for tid in task_ids:
        if tid not in by_id:
            missing.append(tid)
        else:
            ordered.append(by_id[tid])
    if missing:
        raise SystemExit(f"cannot rebuild LOTO scores, missing metrics: {missing}")
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
    p_main = an.loto_probs(ordered, feat_names, an._lookup_feat).tolist()
    payload = {
        "source": "docs/ANALYSIS_RESULTS.json",
        "n": 61,
        "n_go": 53,
        "task_ids": task_ids,
        "delta_pilot": dp,
        "delta_full": df,
        "go": go,
        "cluster": [cluster_of(t) for t in task_ids],
        "p_main": p_main,
        "quoted": {
            "auc": 0.755,
            "auc_ci": [0.500, 0.929],
            "spearman": 0.755,
            "spearman_ci": [0.595, 0.864],
            "text_auc": 0.309,
            "base_rate": 53 / 61,
        },
    }
    FIG.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load_data(*, refresh: bool) -> dict:
    if refresh or not DATA.is_file():
        return _refresh_data()
    return json.loads(DATA.read_text(encoding="utf-8"))


def plot_scatter(data: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dp = np.asarray(data["delta_pilot"], dtype=float)
    df = np.asarray(data["delta_full"], dtype=float)
    clusters = data["cluster"]
    ids = data["task_ids"]
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    for name, color in CLUSTER_COLOR.items():
        idx = [i for i, c in enumerate(clusters) if c == name]
        if not idx:
            continue
        ax.scatter(
            dp[idx],
            df[idx],
            c=color,
            label=name,
            s=36,
            zorder=3,
            edgecolors="white",
            linewidths=0.4,
        )
    lim = max(1.05, float(np.nanmax(np.abs(np.concatenate([dp, df])))) * 1.08)
    ax.plot([-lim, lim], [-lim, lim], color="#bbbbbb", lw=1, zorder=1)
    ax.axhline(0, color="black", lw=0.6)
    ax.axvline(0, color="black", lw=0.6)
    for i, tid in enumerate(ids):
        if tid in ANNOTATE:
            ax.annotate(
                tid,
                (dp[i], df[i]),
                textcoords="offset points",
                xytext=(6, -10),
                fontsize=8,
                color=CLUSTER_COLOR["math"],
            )
    ax.set_xlabel(r"$\Delta_{\mathrm{pilot}}$")
    ax.set_ylabel(r"$\Delta_{\mathrm{full}}$")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def _roc_interp(y: np.ndarray, p: np.ndarray, grid: np.ndarray) -> np.ndarray:
    from sklearn.metrics import roc_curve

    if len(set(y.tolist())) < 2:
        return np.full(grid.shape, np.nan)
    fpr, tpr, _ = roc_curve(y, p)
    fpr = np.concatenate(([0.0], fpr, [1.0]))
    tpr = np.concatenate(([0.0], tpr, [1.0]))
    order = np.argsort(fpr)
    fpr, tpr = fpr[order], tpr[order]
    _, uniq = np.unique(fpr, return_index=True)
    return np.interp(grid, fpr[uniq], tpr[uniq])  # grid:(G,) fpr:(k,) tpr:(k,) → (G,)


def plot_roc(data: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    y = np.asarray(data["go"], dtype=float)
    p = np.asarray(data["p_main"], dtype=float)
    point = _roc_interp(y, p, FPR_GRID)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = y.shape[0]
    bands = []
    for _ in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, size=n)
        yi, pi = y[idx], p[idx]
        if len(set(yi.tolist())) < 2:
            continue
        bands.append(_roc_interp(yi, pi, FPR_GRID))
    band = np.vstack(bands)  # (B,G)
    lo = np.nanquantile(band, 0.025, axis=0)  # (G,)
    hi = np.nanquantile(band, 0.975, axis=0)  # (G,)
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    ax.fill_between(FPR_GRID, lo, hi, color="#1f77b4", alpha=0.22, label="bootstrap 95%")
    ax.plot(FPR_GRID, point, color="#1f77b4", lw=2, label="LOTO main")
    ax.plot([0, 1], [0, 1], color="#888888", lw=1, ls="--", label="chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_base_rate(data: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = int(data["n"])
    n_go = int(data["n_go"])
    n_nogo = n - n_go
    fig, ax = plt.subplots(figsize=(5.4, 4.2))
    xs = ["go\n" + r"($\Delta_{\mathrm{full}}>0$)", "no-go"]
    ys = [n_go / n, n_nogo / n]
    ax.bar(xs, ys, color=["#1f77b4", "#d62728"], width=0.55)
    ax.axhline(0.5, color="#888888", ls="--", lw=1, label="chance 50%")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("share of tasks")
    ax.set_title(f"label base rate  {n_go}/{n} = {n_go / n:.1%}")
    for x, y in zip(xs, ys):
        ax.text(x, y + 0.03, f"{y:.1%}\n({int(round(y * n))})", ha="center", va="bottom", fontsize=9)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="rebuild plot_data.json from ANALYSIS_RESULTS.json + LOTO scores",
    )
    args = parser.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    data = load_data(refresh=args.refresh_data)
    if int(data["n"]) != 61 or int(data["n_go"]) != 53:
        raise SystemExit("plot_data.json is not the sealed n=61 / 53-go table")
    plot_scatter(data, FIG / "calibration_scatter.png")
    plot_roc(data, FIG / "roc_bootstrap.png")
    plot_base_rate(data, FIG / "base_rate.png")
    print(f"wrote figures under {FIG} n={data['n']} n_go={data['n_go']}", flush=True)


if __name__ == "__main__":
    main()
