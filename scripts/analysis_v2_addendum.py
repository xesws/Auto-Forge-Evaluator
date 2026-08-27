#!/usr/bin/env python3
"""Addendum to ANALYSIS_RESULTS_v2: attribution of the pre-decision AUC.

Why this file exists
--------------------
`ANALYSIS_RESULTS_v2.md` reports the pre-decision LOTO AUC as 0.844 and reads
the v1 registered negative as "leakage plus estimator".  That attribution is
wrong.  `analysis_v2.format_compliance_base` added a `math -> boxed/n` branch
that `analysis.format_compliance_scalar` (v1) did not have.  That branch is a
genuine bug fix -- the v1 formula `1 - unparseable/n` silently returns 1.0 for
any task whose format-compliance block has no `unparseable` key, and gsm8k /
math are the only two such tasks (v1 special-cased gsm8k and missed math) --
but it was introduced during the revision period and is NOT listed in
`ANALYSIS_PREREG_V2.md`.  It lands on one of only two substantive negatives.

This script separates the two effects and writes the numbers the paper must
report.  It runs on CPU, touches no protocol, no go threshold, no GPU.

Outputs: docs/ANALYSIS_RESULTS_v2_ADDENDUM.md and .json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import analysis as av1  # noqa: E402
import analysis_v2 as v2  # noqa: E402

BOOT_N = 2000
BOOT_SEED = 20260820  # aligned with v1/v2 interval method
PERM_N = 1000
PERM_SEED = 20260826  # aligned with v2


def _fc_v1_value(row: v2.V2Row) -> float:
    """The value `format_compliance_base` would take under the v1 formula."""
    metrics = json.loads((row.run_dir / "metrics.json").read_text(encoding="utf-8"))
    block = metrics.get("format_compliance") or (metrics.get("signals") or {}).get("format_compliance")
    return av1.format_compliance_scalar(row.task_id, block)


def _set_fc(rows: list[v2.V2Row], values: dict[str, float]) -> None:
    for row in rows:
        row.features["format_compliance_base"] = values[row.task_id]


def _auc(rows: list[v2.V2Row], names: list[str]) -> float:
    y = np.asarray([r.go_registered for r in rows], dtype=float)  # (n,)
    p = v2.loto_probs(rows, names)  # (n,)
    return float(av1.auc_score(y, p))


def _boot_ci(rows: list[v2.V2Row], names: list[str]) -> tuple[float, float, float]:
    y = np.asarray([r.go_registered for r in rows], dtype=float)  # (n,)
    p = v2.loto_probs(rows, names)  # (n,)
    point = float(av1.auc_score(y, p))
    rng = np.random.default_rng(BOOT_SEED)
    n = y.shape[0]
    stats: list[float] = []
    for _ in range(BOOT_N):
        idx = rng.integers(0, n, size=n)  # (n,)
        val = av1.auc_score(y[idx], p[idx])
        if np.isfinite(val):
            stats.append(val)
    arr = np.asarray(stats, dtype=float)  # (B,)
    lo, hi = np.quantile(arr, [0.025, 0.975])  # -> scalars
    return point, float(lo), float(hi)


def _perm_p(rows: list[v2.V2Row], names: list[str], observed: float) -> dict[str, Any]:
    """Label permutation with a full LOTO refit inside every permutation.

    Reported as (1 + #{perm >= obs}) / (1 + N), the unbiased convention; the
    v2 file used #{...}/N, which cannot go below 1/N and printed 0.001 for a
    single hit.
    """
    y = np.asarray([r.go_registered for r in rows], dtype=float)  # (n,)
    rng = np.random.default_rng(PERM_SEED)
    work = y.copy()
    saved = [r.go_registered for r in rows]
    ge = 0
    stats: list[float] = []
    for k in range(PERM_N):
        rng.shuffle(work)
        for row, g in zip(rows, work):
            row.go_registered = int(g)
        val = av1.auc_score(work, v2.loto_probs(rows, names))
        stats.append(val)
        if np.isfinite(val) and val >= observed:
            ge += 1
        if (k + 1) % 200 == 0:
            print(f"    perm {k+1}/{PERM_N}", flush=True)
    for row, g in zip(rows, saved):
        row.go_registered = g
    arr = np.asarray(stats, dtype=float)  # (PERM_N,)
    arr = arr[np.isfinite(arr)]
    return {
        "n_perm": PERM_N,
        "seed": PERM_SEED,
        "n_ge_observed": ge,
        "p_unbiased": (ge + 1) / (PERM_N + 1),
        "p_naive_v2_convention": ge / PERM_N,
        "perm_mean": float(arr.mean()),
    }


def fc_key_audit(rows: list[v2.V2Row]) -> list[dict[str, Any]]:
    """Which tasks have no `unparseable` key, i.e. where the v1 formula is blind."""
    out = []
    for row in rows:
        metrics = json.loads((row.run_dir / "metrics.json").read_text(encoding="utf-8"))
        block = metrics.get("format_compliance") or (metrics.get("signals") or {}).get("format_compliance") or {}
        base = block.get("base") if isinstance(block.get("base"), dict) else block
        if isinstance(base, dict) and base and "unparseable" not in base:
            out.append(
                {
                    "task_id": row.task_id,
                    "scalar_keys": sorted(k for k, v in base.items() if not isinstance(v, dict)),
                    "v1_value": _fc_v1_value(row),
                    "v2_value": row.features["format_compliance_base"],
                }
            )
    return out


def main() -> None:
    rows = v2.load_v2_rows([ROOT / "runs", ROOT / "runs" / "harvest" / "extracted"])
    print(f"rows = {len(rows)}", flush=True)
    fc_v2 = {r.task_id: float(r.features["format_compliance_base"]) for r in rows}
    fc_v1 = {r.task_id: float(_fc_v1_value(r)) for r in rows}
    differing = sorted(t for t in fc_v2 if abs(fc_v2[t] - fc_v1[t]) > 1e-12)
    audit = fc_key_audit(rows)

    variants = {
        "pre_decision_10": v2.PRE_DECISION,
        "l2cv_note": v2.PRE_DECISION,  # placeholder, handled separately
        "no_pass8": v2.NO_PASS8,
        "trio_3feat": v2.TRIO,
        "registered_leaked_12": v2.LEAKED_12,
    }

    # --- decomposition: every variant under both fc definitions -------------
    decomposition: dict[str, dict[str, float]] = {}
    for name, feats in variants.items():
        if name == "l2cv_note":
            continue
        _set_fc(rows, fc_v2)
        a_v2 = _auc(rows, feats)
        _set_fc(rows, fc_v1)
        a_v1 = _auc(rows, feats)
        decomposition[name] = {"fc_v2": a_v2, "fc_v1": a_v1, "delta": a_v2 - a_v1}
        print(f"  {name:24s} fc_v2={a_v2:.4f} fc_v1={a_v1:.4f} d={a_v2-a_v1:+.4f}", flush=True)

    _set_fc(rows, fc_v2)
    l2_v2 = float(av1.auc_score(np.asarray([r.go_registered for r in rows], dtype=float), v2.loto_l2cv(rows, v2.PRE_DECISION)))
    _set_fc(rows, fc_v1)
    l2_v1 = float(av1.auc_score(np.asarray([r.go_registered for r in rows], dtype=float), v2.loto_l2cv(rows, v2.PRE_DECISION)))
    decomposition["l2cv_pre_decision"] = {"fc_v2": l2_v2, "fc_v1": l2_v1, "delta": l2_v2 - l2_v1}
    decomposition.pop("l2cv_note", None)
    print(f"  l2cv_pre_decision        fc_v2={l2_v2:.4f} fc_v1={l2_v1:.4f} d={l2_v2-l2_v1:+.4f}", flush=True)

    # --- the three candidate main rows, with CI and permutation -------------
    rows_out: dict[str, Any] = {}
    for key, feats, fc in [
        ("pre_decision_fc_v1_deleak_only", v2.PRE_DECISION, fc_v1),
        ("pre_decision_fc_v2_deleak_plus_mathfix", v2.PRE_DECISION, fc_v2),
        ("trio_3feat_fc_invariant", v2.TRIO, fc_v2),
    ]:
        _set_fc(rows, fc)
        auc, lo, hi = _boot_ci(rows, feats)
        print(f"  {key}: AUC={auc:.4f} CI=[{lo:.3f},{hi:.3f}] -> permutation", flush=True)
        perm = _perm_p(rows, feats, auc)
        rows_out[key] = {"auc": auc, "ci95": [lo, hi], "covers_0.5": bool(lo <= 0.5 <= hi), "permutation": perm}

    # --- jackknife: drop one negative, refit the 0.844 model ----------------
    _set_fc(rows, fc_v2)
    full = _auc(rows, v2.PRE_DECISION)
    jack = []
    for row in rows:
        if row.go_registered != 0:
            continue
        sub = [r for r in rows if r is not row]
        jack.append({"dropped": row.task_id, "auc": _auc(sub, v2.PRE_DECISION), "delta": None})
    for item in jack:
        item["delta"] = item["auc"] - full
    jack.sort(key=lambda d: d["auc"])

    payload = {
        "identity": "revision-period addendum to ANALYSIS_RESULTS_v2; no protocol / no go-threshold / no GPU change",
        "ts": v2._now(),
        "git_head": v2._git_head(),
        "n": len(rows),
        "fc_definition_change": {
            "where": "scripts/analysis_v2.py::format_compliance_base",
            "branch": "task_id == 'math' -> base['boxed'] / n",
            "declared_in_prereg_v2": False,
            "tasks_with_different_value": differing,
            "v1_blind_tasks": audit,
        },
        "decomposition": decomposition,
        "candidate_main_rows": rows_out,
        "jackknife_drop_one_negative_on_fc_v2_pre_decision": {
            "full_sample_auc": full,
            "rows": jack,
            "range": [min(j["auc"] for j in jack), max(j["auc"] for j in jack)],
        },
    }

    (ROOT / "docs" / "ANALYSIS_RESULTS_v2_ADDENDUM.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    write_md(payload, ROOT / "docs" / "ANALYSIS_RESULTS_v2_ADDENDUM.md")
    print("wrote docs/ANALYSIS_RESULTS_v2_ADDENDUM.{md,json}")


def write_md(p: dict[str, Any], path: Path) -> None:
    d = p["decomposition"]
    c = p["candidate_main_rows"]
    j = p["jackknife_drop_one_negative_on_fc_v2_pre_decision"]
    fc = p["fc_definition_change"]
    L: list[str] = []
    L.append("# Analysis v2 · ADDENDUM — attribution of the pre-decision AUC")
    L.append("")
    L.append(f"- 时间 (UTC): {p['ts']}")
    L.append(f"- git HEAD: `{p['git_head']}`")
    L.append(f"- n = {p['n']}；协议未改，go 阈值未改，无 GPU 重跑")
    L.append("- 生成脚本: `scripts/analysis_v2_addendum.py`（CPU，纯重分析）")
    L.append("")
    L.append("**身份: 修订期新增分析的更正件。** `ANALYSIS_RESULTS_v2.md` 的主表数字本身可复现，")
    L.append("但它对 0.755 → 0.844 的**归因是错的**。本文件给出正确分解，并作为论文引用真源。")
    L.append("")
    L.append("## 1. 未申报的特征定义变更")
    L.append("")
    L.append(f"位置: `{fc['where']}`，分支 `{fc['branch']}`。")
    L.append(f"在 `ANALYSIS_PREREG_V2.md` 八条新增项中**未申报**（见该文件 R1-9 补申报条）。")
    L.append("")
    L.append("v1 公式 `1 - unparseable/n` 对没有 `unparseable` 键的任务恒返回 1.0。全样本只有两个这样的任务：")
    L.append("")
    L.append("| task | base 块标量键 | v1 值 | v2 值 |")
    L.append("|---|---|---:|---:|")
    for a in fc["v1_blind_tasks"]:
        L.append(f"| `{a['task_id']}` | {', '.join('`'+k+'`' for k in a['scalar_keys'])} | {a['v1_value']:.3f} | {a['v2_value']:.3f} |")
    L.append("")
    L.append("v1 特判了 `gsm8k`、漏了 `math`。**该分支是正当的 bug 修复，不是挑任务**；")
    L.append(f"但它改变的任务是 {fc['tasks_with_different_value']}，其中 `math` 是全样本仅有的两个实质负例之一。")
    L.append("")
    L.append("## 2. 归因分解（同一 pipeline，只翻转 `format_compliance_base`）")
    L.append("")
    L.append("| 模型 | fc v2（含 math 修复） | fc v1（仅去泄漏） | 差 |")
    L.append("|---|---:|---:|---:|")
    order = ["registered_leaked_12", "pre_decision_10", "l2cv_pre_decision", "no_pass8", "trio_3feat"]
    for k in order:
        if k in d:
            L.append(f"| `{k}` | {d[k]['fc_v2']:.4f} | {d[k]['fc_v1']:.4f} | {d[k]['delta']:+.4f} |")
    L.append("")
    pd = d["pre_decision_10"]
    reg = d["registered_leaked_12"]
    L.append("**分解:**")
    L.append("")
    L.append("```")
    L.append(f"去掉泄漏特征 (12->10, fc 固定 v1) : {reg['fc_v1']:.4f} -> {pd['fc_v1']:.4f}  = {pd['fc_v1']-reg['fc_v1']:+.4f}")
    L.append(f"math fc 分支 (一个格子, 特征固定) : {pd['fc_v1']:.4f} -> {pd['fc_v2']:.4f}  = {pd['delta']:+.4f}")
    L.append("```")
    L.append("")
    L.append("**去泄漏使 AUC 下降。** 涨幅全部来自那一个格子。")
    L.append("`registered_leaked_12` 与 `trio_3feat` 对该分支免疫（差 = 0）。")
    L.append("")
    L.append("## 3. 三个候选主行（bootstrap CI + 标签置换，每次置换重跑全 LOTO）")
    L.append("")
    L.append("| 主行 | AUC | 95% CI | 覆盖 0.5 | 置换 p |")
    L.append("|---|---:|---|---|---:|")
    label = {
        "pre_decision_fc_v1_deleak_only": "pre-decision，仅去泄漏",
        "pre_decision_fc_v2_deleak_plus_mathfix": "pre-decision，去泄漏 + math 修复",
        "trio_3feat_fc_invariant": "**3 特征（对两者都免疫）**",
    }
    for k, v in c.items():
        pm = v["permutation"]
        L.append(
            f"| {label[k]} | {v['auc']:.4f} | [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}] | "
            f"{'是' if v['covers_0.5'] else '否'} | {pm['p_unbiased']:.4f} |"
        )
    L.append("")
    L.append(f"置换 p 用 `(1 + #{{perm >= obs}}) / (1 + N)`，N = {PERM_N}。")
    L.append("`ANALYSIS_RESULTS_v2.md` 报的 0.0010 是 `#/N` 的朴素写法（命中 1 次），应读作 "
             f"{c['pre_decision_fc_v2_deleak_plus_mathfix']['permutation']['p_unbiased']:.4f}。")
    L.append("")
    L.append("## 4. 稳定性: drop-one-negative jackknife（fc v2 的 pre-decision 模型）")
    L.append("")
    L.append(f"全样本 AUC = {j['full_sample_auc']:.4f}")
    L.append("")
    L.append("| 丢弃的 no-go | AUC | 变化 |")
    L.append("|---|---:|---:|")
    for it in j["rows"]:
        L.append(f"| `{it['dropped']}` | {it['auc']:.4f} | {it['delta']:+.4f} |")
    L.append("")
    L.append(f"区间 [{j['range'][0]:.3f}, {j['range'][1]:.3f}]。丢掉任一实质负例（`math` / `gsm8k`）AUC 掉 0.13–0.16。")
    L.append("8 个负例（实质负例 2 个）撑不住第二位小数。")
    L.append("")
    L.append("## 5. 论文应当采用的读法")
    L.append("")
    L.append("1. 注册主行（12 特征，含 post-decision `gen_len.full.median`）AUC 0.755，CI 覆盖 0.5，**照发阴性**。")
    L.append("2. 单纯移除该 post-decision 特征**不能**挽救它。")
    L.append("3. 把维度降到 3 个 pre-decision 特征才显著 —— 注册阴性的机制是**过参数化**（12 特征 / 8 负例），不是「没有信号」。")
    L.append("4. `math` format-compliance 的 bug 修复单独申报、单独报效应量，**不并入「去泄漏」**。")
    L.append("5. 门本来就不值钱（完美门效用上限 0.024），门显不显著都不该是头条。")
    L.append("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
