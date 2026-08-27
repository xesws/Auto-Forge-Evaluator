#!/usr/bin/env python3
"""Citable v2 figures from ANALYSIS_RESULTS_v2.json. No new analysis."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EM_FLOOR = {
    "task071_abductivenli_answer_generation",
    "task1553_cnn_dailymail_summarization",
    "task236_iirc_question_from_passage_answer_generation",
    "task455_swag_context_generation",
}


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve

    payload = json.loads((ROOT / "docs" / "ANALYSIS_RESULTS_v2.json").read_text(encoding="utf-8"))
    out = ROOT / "paper" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    docs_fig = ROOT / "docs" / "figures"
    docs_fig.mkdir(parents=True, exist_ok=True)

    dp = np.asarray(payload["delta_pilot"], dtype=float)
    df = np.asarray(payload["delta_full"], dtype=float)
    ids = payload["task_ids"]
    y = np.asarray(payload["y_registered"], dtype=float)
    p = np.asarray(payload["main_predecision_p"], dtype=float)

    # Fig 1: budget capture curve
    K = [int(k) for k in payload["budget"]["K"]]
    pilot = [payload["budget"]["K"][str(k)]["pilot_capture"] for k in K]
    rnd = [payload["budget"]["K"][str(k)]["random_capture_mean"] for k in K]
    rnd_lo = [payload["budget"]["K"][str(k)]["random_capture_ci95"][0] for k in K]
    rnd_hi = [payload["budget"]["K"][str(k)]["random_capture_ci95"][1] for k in K]
    ora = [payload["budget"]["K"][str(k)]["oracle_capture"] for k in K]
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.plot(K, pilot, "o-", color="#1f77b4", label=r"rank by $\Delta_{\mathrm{pilot}}$")
    ax.plot(K, ora, "s--", color="#2ca02c", label=r"oracle (rank by $\Delta_{\mathrm{full}}$)")
    ax.plot(K, rnd, "^-", color="#7f7f7f", label="random")
    ax.fill_between(K, rnd_lo, rnd_hi, color="#7f7f7f", alpha=0.2)
    ax.set_xlabel("budget $K$ (tasks fully fine-tuned)")
    ax.set_ylabel("fraction of positive-gain mass captured")
    ax.set_xticks(K)
    ax.set_ylim(0, 1.02)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "budget_capture.png", dpi=160)
    fig.savefig(docs_fig / "budget_capture.png", dpi=160)
    plt.close(fig)

    # Fig 2: cropped scatter + EM floor
    fig, ax = plt.subplots(figsize=(4.4, 4.4))
    em = np.array([tid in EM_FLOOR for tid in ids])
    ax.scatter(dp[~em], df[~em], c=["#1f77b4" if g else "#d62728" for g in y[~em]], s=22, zorder=2)
    ax.scatter(dp[em], df[em], c="#ff7f0e", s=36, marker="D", zorder=3, label="EM floor")
    ax.axhline(0, color="black", lw=0.6)
    ax.axvline(0, color="black", lw=0.6)
    ax.plot([-0.4, 1.0], [-0.4, 1.0], color="gray", lw=0.8)
    for tid, x, yy in zip(ids, dp, df):
        if tid in {"gsm8k", "math"}:
            ax.annotate(tid, (x, yy), textcoords="offset points", xytext=(4, -8), fontsize=7, color="#d62728")
    ax.set_xlim(-0.40, 1.02)
    ax.set_ylim(-0.28, 1.05)
    ax.set_xlabel(r"$\Delta_{\mathrm{pilot}}$")
    ax.set_ylabel(r"$\Delta_{\mathrm{full}}$")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "calibration_scatter.png", dpi=160)
    fig.savefig(docs_fig / "calibration_scatter_v2.png", dpi=160)
    plt.close(fig)

    # ROC of new main
    fpr, tpr, _ = roc_curve(y, p)
    fig, ax = plt.subplots(figsize=(4.0, 4.0))
    ax.plot(fpr, tpr, color="#1f77b4", lw=2)
    ax.plot([0, 1], [0, 1], color="gray", lw=1)
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_title("LOTO ROC (pre-decision features)")
    fig.tight_layout()
    fig.savefig(out / "roc_predecision.png", dpi=160)
    fig.savefig(docs_fig / "roc_predecision.png", dpi=160)
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    main()
