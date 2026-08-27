#!/usr/bin/env python3
"""Revision-period analysis (ANALYSIS_PREREG_V2). CPU only. No GPU.

Writes docs/ANALYSIS_RESULTS_v2.md and .json. Does not edit protocol_v2
or ANALYSIS_RESULTS.md (v1 remains the registered citable row).
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import analysis as av1  # type: ignore  # noqa: E402

PRE_DECISION = [
    "delta_pilot",
    "base_pass1",
    "base_pass8",
    "headroom",
    "pilot_loss.start",
    "pilot_loss.end",
    "pilot_loss.steps_to_0_01",
    "pilot_loss.steps_to_0_01_missing",
    "format_compliance_base",
    "train_n",
]
NO_PASS8 = [n for n in PRE_DECISION if n not in {"base_pass8", "headroom"}]
TRIO = ["delta_pilot", "base_pass1", "headroom"]
LEAKED_12 = [
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
SINGLE_5 = [
    "delta_pilot",
    "base_pass1",
    "headroom",
    "pilot_loss.steps_to_0_01",
    "gen_len.full.median",
]
META_TEXT = ["splits.train_n", "max_new_tokens", "len(prompt_style)", "eval_n"]
PERM_N = 1000
PERM_SEED = 20260826
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20260820
MCNEMAR_ALPHA = 0.05
DUMB_PROBE = 0.02
K_BUDGET = (5, 10, 20, 30)
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
NI_TASKS = ROOT / "data_cache" / "natural-instructions" / "tasks"


@dataclass
class V2Row:
    task_id: str
    run_dir: Path
    status: str
    go_registered: int
    delta_pilot: float
    delta_full: float
    base_pass1: float
    full_pass1: float
    features: dict[str, float | None]
    text: dict[str, float]
    instruction: str
    stratum: str
    source: str
    n01: int = 0
    n10: int = 0
    mcnemar_p: float = 1.0
    label3: str = "undetermined"
    cost: dict[str, float | None] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_head() -> str:
    return av1._git_head()


def _parse_ts(raw: str) -> datetime | None:
    raw = (raw or "").strip().replace("Z", "")
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def journal_stage_seconds(run_dir: Path) -> dict[str, float | None]:
    path = run_dir / "journal.jsonl"
    out: dict[str, float | None] = {f"S{i}": None for i in range(7)}
    if not path.is_file():
        return out
    starts: dict[str, datetime] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        stage = str(rec.get("stage") or "")
        event = str(rec.get("event") or "")
        ts = _parse_ts(str(rec.get("ts") or ""))
        if not stage or ts is None:
            continue
        if event == "start":
            starts[stage] = ts
        elif event == "done" and stage in starts:
            out[stage] = (ts - starts[stage]).total_seconds()
    return out


def format_compliance_base(task_id: str, block: Any) -> float:
    if not isinstance(block, dict):
        return 0.0
    base = block.get("base") if isinstance(block.get("base"), dict) else block
    if not isinstance(base, dict):
        return 0.0
    n = int(base.get("n") or 0)
    if n <= 0:
        return 0.0
    if task_id == "gsm8k":
        return float(base.get("hash") or 0) / n
    if task_id == "math":
        return float(base.get("boxed") or 0) / n
    unp = float(base.get("unparseable") or 0)
    return 1.0 - unp / n


def _instruction_text(task_id: str) -> tuple[str, str, str]:
    ni = NI_TASKS / f"{task_id}.json"
    if ni.is_file():
        blob = json.loads(ni.read_text(encoding="utf-8"))
        definition = blob.get("Definition") or []
        if isinstance(definition, list):
            text = " ".join(str(x) for x in definition)
        else:
            text = str(definition)
        cats = blob.get("Categories") or []
        src = blob.get("Source") or []
        stratum = str(cats[0]) if cats else "superni"
        source = str(src[0]) if src else "superni"
        return text.strip(), stratum, source
    task_path = ROOT / "tasks" / task_id / "task.json"
    if task_path.is_file():
        task = json.loads(task_path.read_text(encoding="utf-8"))
        return str(task.get("prompt_style") or task_id), "literature", task_id
    return task_id, "unknown", task_id


def mcnemar_from_jsonl(run_dir: Path) -> tuple[int, int, float, str]:
    from scipy.stats import binomtest

    base_path = run_dir / "eval_base_greedy.jsonl"
    full_path = run_dir / "eval_full_greedy.jsonl"
    if not base_path.is_file() or not full_path.is_file():
        return 0, 0, 1.0, "undetermined"

    def load_pass(path: Path) -> dict[str, bool]:
        out: dict[str, bool] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            samples = rec.get("samples") or []
            flag = bool(samples[0].get("pass")) if samples else False
            out[str(rec.get("id"))] = flag
        return out

    base = load_pass(base_path)
    full = load_pass(full_path)
    ids = sorted(set(base) & set(full))
    n01 = n10 = 0
    for i in ids:
        b, f = base[i], full[i]
        if (not b) and f:
            n01 += 1
        elif b and (not f):
            n10 += 1
    n_disc = n01 + n10
    if n_disc == 0:
        p = 1.0
    else:
        p = float(binomtest(n01, n=n_disc, p=0.5, alternative="two-sided").pvalue)
    if p < MCNEMAR_ALPHA and n01 > n10:
        lab = "go"
    elif p < MCNEMAR_ALPHA and n10 > n01:
        lab = "no-go"
    else:
        lab = "undetermined"
    return n01, n10, p, lab


def load_v2_rows(roots: list[Path]) -> list[V2Row]:
    sources = av1._load_superni_source()
    found: dict[str, av1.Row] = {}
    for root in roots:
        for path in sorted(root.rglob("metrics.json")):
            if "adapters" in path.parts or "_isolated" in path.parts:
                continue
            row = av1.load_row(path, sources)
            if row is None:
                continue
            prev = found.get(row.task_id)
            if prev is None or str(row.run_dir) > str(prev.run_dir):
                found[row.task_id] = row
    sealed = json.loads((ROOT / "docs" / "ANALYSIS_RESULTS.json").read_text(encoding="utf-8"))
    keep = set(sealed["main_bundle"]["task_ids"])
    out: list[V2Row] = []
    for tid in sorted(keep):
        row = found[tid]
        metrics = json.loads((row.run_dir / "metrics.json").read_text(encoding="utf-8"))
        fc_block = metrics.get("format_compliance") or (metrics.get("signals") or {}).get("format_compliance")
        feats = dict(row.features)
        feats["format_compliance_base"] = format_compliance_base(tid, fc_block)
        instr, stratum, source = _instruction_text(tid)
        if tid.startswith("task") and sources.get(tid):
            source = sources[tid]
        n01, n10, p, lab3 = mcnemar_from_jsonl(row.run_dir)
        stage = journal_stage_seconds(row.run_dir)
        s1, s2, s3 = stage.get("S1"), stage.get("S2"), stage.get("S3")
        s4, s5 = stage.get("S4"), stage.get("S5")

        def _sum(*xs: float | None) -> float | None:
            vals = [x for x in xs if x is not None]
            return float(sum(vals)) if len(vals) == len(xs) else None

        probe = _sum(s2, s3)
        full = _sum(s4, s5)
        probe_s1 = _sum(s1, s2, s3)
        cost = {
            "S1": s1,
            "S2": s2,
            "S3": s3,
            "S4": s4,
            "S5": s5,
            "probe_s2s3": probe,
            "full_s4s5": full,
            "probe_with_s1": probe_s1,
            "ratio_s2s3_over_s4s5": (probe / full) if probe is not None and full and full > 0 else None,
            "ratio_with_s1_over_s4s5": (probe_s1 / full) if probe_s1 is not None and full and full > 0 else None,
        }
        out.append(
            V2Row(
                task_id=tid,
                run_dir=row.run_dir,
                status=row.status,
                go_registered=row.go,
                delta_pilot=row.delta_pilot,
                delta_full=row.delta_full,
                base_pass1=row.base_pass1,
                full_pass1=row.full_pass1,
                features=feats,
                text=row.text,
                instruction=instr,
                stratum=stratum,
                source=source,
                n01=n01,
                n10=n10,
                mcnemar_p=p,
                label3=lab3,
                cost=cost,
            )
        )
    return out


def _lookup(row: V2Row, name: str) -> float:
    if name in row.features:
        val = row.features.get(name)
        return float("nan") if val is None else float(val)
    return float(row.text.get(name) or 0.0)


def loto_probs(rows: list[V2Row], names: list[str]) -> np.ndarray:
    n = len(rows)
    X = np.asarray([[_lookup(r, name) for name in names] for r in rows], dtype=float)  # (n,f)
    y = np.asarray([r.go_registered for r in rows], dtype=float)  # (n,)
    preds = np.zeros(n, dtype=float)
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        xtr, xte = av1._impute_train(X[mask], X[i : i + 1])
        ztr, zte = av1._zscore(xtr, xte)
        preds[i] = float(av1._fit_predict(ztr, y[mask], zte)[0])
    return preds


def loto_l2cv(rows: list[V2Row], names: list[str]) -> np.ndarray:
    from sklearn.linear_model import LogisticRegressionCV

    n = len(rows)
    X = np.asarray([[_lookup(r, name) for name in names] for r in rows], dtype=float)  # (n,f)
    y = np.asarray([r.go_registered for r in rows], dtype=float)  # (n,)
    preds = np.zeros(n, dtype=float)
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        xtr, xte = av1._impute_train(X[mask], X[i : i + 1])
        ztr, zte = av1._zscore(xtr, xte)
        ytr = y[mask]
        if len(set(ytr.tolist())) < 2:
            preds[i] = float(ytr.mean())
            continue
        n_tr = int(ztr.shape[0])
        cv = min(5, max(2, int(ytr.sum()), int((1 - ytr).sum())))
        cv = min(cv, n_tr)
        if cv < 2:
            preds[i] = float(av1._fit_predict(ztr, ytr, zte)[0])
            continue
        clf = LogisticRegressionCV(
            Cs=8,
            cv=cv,
            scoring="roc_auc",
            max_iter=4000,
            solver="lbfgs",
            n_jobs=1,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(ztr, ytr)  # ztr:(ntr,f) ytr:(ntr,)
        proba = clf.predict_proba(zte)  # (1,2)
        classes = list(clf.classes_)
        preds[i] = float(proba[0, classes.index(1)]) if 1 in classes else 0.0
    return preds


def bundle_auc(rows: list[V2Row], names: list[str], rng: np.random.Generator, y: np.ndarray | None = None) -> dict[str, Any]:
    if y is None:
        y = np.asarray([r.go_registered for r in rows], dtype=float)  # (n,)
    p = loto_probs(rows, names)
    auc, lo, hi = av1.bootstrap_auc(y, p, rng)
    return {
        "n": int(y.shape[0]),
        "n_go": int(y.sum()),
        "auc": auc,
        "ci95": [lo, hi],
        "covers_0.5": bool(lo <= 0.5 <= hi) if math.isfinite(lo) else None,
        "p": p.tolist(),
        "features": names,
    }


def permutation_p(rows: list[V2Row], names: list[str], observed: float, y: np.ndarray) -> dict[str, Any]:
    rng = np.random.default_rng(PERM_SEED)
    stats: list[float] = []
    y_work = y.copy()
    for k in range(PERM_N):
        rng.shuffle(y_work)
        # temporarily overwrite go for LOTO
        saved = [r.go_registered for r in rows]
        for r, g in zip(rows, y_work):
            r.go_registered = int(g)
        p = loto_probs(rows, names)
        stats.append(av1.auc_score(y_work, p))
        for r, g in zip(rows, saved):
            r.go_registered = g
        if (k + 1) % 100 == 0:
            print(f"perm {k+1}/{PERM_N}", flush=True)
    arr = np.asarray(stats, dtype=float)  # (PERM_N,)
    arr = arr[np.isfinite(arr)]
    p_right = float(np.mean(arr >= observed)) if arr.size else float("nan")
    return {
        "n_perm": PERM_N,
        "seed": PERM_SEED,
        "observed_auc": observed,
        "p_ge_observed": p_right,
        "perm_mean": float(arr.mean()) if arr.size else float("nan"),
        "perm_ci95": np.quantile(arr, [0.025, 0.975]).tolist() if arr.size else [None, None],
    }


def partial_spearman(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    from scipy.stats import spearmanr

    zc = np.column_stack([np.ones(z.shape[0]), z])  # (n,2)
    bx, *_ = np.linalg.lstsq(zc, x, rcond=None)  # zc:(n,2) x:(n,) → bx:(2,)
    by, *_ = np.linalg.lstsq(zc, y, rcond=None)
    rx = x - zc @ bx  # (n,2)@(2,) → (n,)
    ry = y - zc @ by
    return float(spearmanr(rx, ry).statistic)


def embed_instructions(rows: list[V2Row]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL, device="cpu")
    texts = [r.instruction or r.task_id for r in rows]
    vec = model.encode(texts, batch_size=16, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(vec, dtype=float)  # (n,d)


def loto_embed(rows: list[V2Row], E: np.ndarray) -> np.ndarray:
    """Embedding + fold-wise one-hot stratum/source, L2 logistic."""
    from sklearn.linear_model import LogisticRegression

    n = len(rows)
    y = np.asarray([r.go_registered for r in rows], dtype=float)  # (n,)
    strata = [r.stratum for r in rows]
    sources = [r.source for r in rows]
    preds = np.zeros(n, dtype=float)
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        s_tr = sorted(set(strata[j] for j in range(n) if mask[j]))
        o_tr = sorted(set(sources[j] for j in range(n) if mask[j]))

        def oh(idx: int) -> np.ndarray:
            a = np.zeros(len(s_tr) + len(o_tr), dtype=float)
            if strata[idx] in s_tr:
                a[s_tr.index(strata[idx])] = 1.0
            if sources[idx] in o_tr:
                a[len(s_tr) + o_tr.index(sources[idx])] = 1.0
            return a

        xtr = np.stack([np.concatenate([E[j], oh(j)]) for j in range(n) if mask[j]])  # (ntr, d+k)
        xte = np.concatenate([E[i], oh(i)])[None, :]  # (1, d+k)
        ztr, zte = av1._zscore(xtr, xte)
        ytr = y[mask]
        if len(set(ytr.tolist())) < 2:
            preds[i] = float(ytr.mean())
            continue
        clf = LogisticRegression(max_iter=4000, solver="lbfgs", C=1.0)
        clf.fit(ztr, ytr)
        proba = clf.predict_proba(zte)
        classes = list(clf.classes_)
        preds[i] = float(proba[0, classes.index(1)]) if 1 in classes else 0.0
    return preds


def budget_sim(rows: list[V2Row], rng: np.random.Generator) -> dict[str, Any]:
    df = np.asarray([r.delta_full for r in rows], dtype=float)  # (n,)
    dp = np.asarray([r.delta_pilot for r in rows], dtype=float)  # (n,)
    pos = np.clip(df, 0, None)  # (n,)
    G = float(pos.sum())
    neg_sum = float(df[df < 0].sum())
    order_pilot = np.argsort(-dp)  # (n,)
    order_oracle = np.argsort(-df)
    out: dict[str, Any] = {
        "G_positive_sum": G,
        "neg_delta_sum": neg_sum,
        "gate_utility_upper": (abs(neg_sum) / G) if G > 0 else None,
        "always_forge_net": float(df.sum()),
        "oracle_net": G,
        "dumb_probe_frac_abs_le_0.02": float(np.mean(np.abs(dp) <= DUMB_PROBE)),
        "K": {},
    }
    n = len(rows)
    for k in K_BUDGET:
        k = min(k, n)
        cap_p = float(pos[order_pilot[:k]].sum() / G) if G else 0.0
        cap_o = float(pos[order_oracle[:k]].sum() / G) if G else 0.0
        rand_caps = []
        for _ in range(BOOTSTRAP_N):
            pick = rng.choice(n, size=k, replace=False)
            rand_caps.append(float(pos[pick].sum() / G) if G else 0.0)
        rc = np.asarray(rand_caps, dtype=float)
        out["K"][str(k)] = {
            "k": k,
            "pilot_capture": cap_p,
            "oracle_capture": cap_o,
            "random_capture_mean": float(rc.mean()),
            "random_capture_ci95": np.quantile(rc, [0.025, 0.975]).tolist(),
        }
    return out


def write_md(payload: dict[str, Any], path: Path) -> None:
    m = payload["main_predecision"]
    leaked = payload["registered_leaked_12"]
    perm = payload["permutation"]
    lines = [
        "# Analysis v2 (revision-period, citable for the rewrite)",
        "",
        f"- 时间 (UTC): {payload['ts']}",
        f"- git HEAD: `{payload['git_head']}`",
        "- 协议: protocol_v2 / pv2（yaml 未改）",
        "- 合同: `docs/ANALYSIS_PREREG_V2.md`（v1 注册主行仍照报）",
        f"- n = **{payload['n']}**（{payload['n_go_registered']} go under registered label Δ_full>0）",
        "",
        "**身份: 修订期新增分析。** v1 `ANALYSIS_RESULTS.md` 仍是注册主行真源。",
        "本文件是去泄漏后的论文新主数真源。",
        "",
        "## 主表（pre-decision LOTO）",
        "",
        f"- 新主 LOTO AUC = **{m['auc']:.3f}**, 95% CI [{m['ci95'][0]:.3f}, {m['ci95'][1]:.3f}], "
        f"覆盖 0.5? **{'是' if m['covers_0.5'] else '否'}**",
        f"- 标签置换 p (N={perm['n_perm']}, P(AUC_perm ≥ AUC_obs)) = **{perm['p_ge_observed']:.4f}**",
        f"- 置换与 bootstrap 同向（均不显著 / 均显著）: **{payload['perm_agrees_with_ci']}**",
        f"- 注册泄漏 12 特征 LOTO（对照，不可用于决策）AUC = {leaked['auc']:.3f} "
        f"[{leaked['ci95'][0]:.3f}, {leaked['ci95'][1]:.3f}]",
        f"- post-hoc oracle `gen_len.full.median` AUC = {payload['posthoc_oracle']['auc']:.3f} "
        f"[{payload['posthoc_oracle']['ci95'][0]:.3f}, {payload['posthoc_oracle']['ci95'][1]:.3f}]",
        f"- L2-CV LOTO AUC = {payload['l2cv']['auc']:.3f} "
        f"[{payload['l2cv']['ci95'][0]:.3f}, {payload['l2cv']['ci95'][1]:.3f}]",
        f"- 3-feat (Δ_pilot, base_pass1, headroom) AUC = {payload['trio']['auc']:.3f} "
        f"[{payload['trio']['ci95'][0]:.3f}, {payload['trio']['ci95'][1]:.3f}]",
        f"- 无 pass@8 特征集 AUC = {payload['no_pass8']['auc']:.3f} "
        f"[{payload['no_pass8']['ci95'][0]:.3f}, {payload['no_pass8']['ci95'][1]:.3f}]",
        "",
        "## Spearman",
        "",
        f"- ρ(Δ_pilot, Δ_full) = {payload['spearman']['rho']:.3f} "
        f"[{payload['spearman']['ci95'][0]:.3f}, {payload['spearman']['ci95'][1]:.3f}]",
        f"- partial ρ | base_pass1 = {payload['partial_spearman_base']:.3f}",
        "",
        "## 单特征（5 行；多重比较未校正）",
        "",
        "| 特征 | AUC | 95% CI | 覆盖 0.5? | 决策可用 |",
        "|---|---:|---|---|---|",
    ]
    for name, blk in payload["single_feature"].items():
        usable = "否（post-hoc）" if name == "gen_len.full.median" else "是（pre-decision）"
        cov = "是" if blk["covers_0.5"] else "否"
        lines.append(
            f"| `{name}` | {blk['auc']:.3f} | [{blk['ci95'][0]:.3f}, {blk['ci95'][1]:.3f}] | {cov} | {usable} |"
        )
    sem = payload["semantic"]
    meta = payload["metadata_control"]
    lines += [
        "",
        "## 对照",
        "",
        f"- 元数据对照（4 标量）AUC = {meta['auc']:.3f} [{meta['ci95'][0]:.3f}, {meta['ci95'][1]:.3f}] "
        f"（eval_n 唯一值 = {payload['eval_n_unique']}）",
        f"- 语义对照（MiniLM instruction + Categories/Source）AUC = {sem['auc']:.3f} "
        f"[{sem['ci95'][0]:.3f}, {sem['ci95'][1]:.3f}]",
        "",
        "## McNemar 三分类（修订期新增；α=0.05 双侧精确，未校正）",
        "",
        f"- go / no-go / undetermined = {payload['mcnemar']['n_go']} / "
        f"{payload['mcnemar']['n_nogo']} / {payload['mcnemar']['n_undetermined']}",
        f"- LOTO AUC on determined-only = {payload['mcnemar']['auc_determined']}",
        f"- LOTO AUC treating undetermined as no-go = {payload['mcnemar']['auc_undet_as_nogo']}",
        "",
        "## 成本与预算",
        "",
        f"- median (S2+S3)/(S4+S5) = {payload['cost']['ratio_s2s3_over_s4s5_median']}",
        f"- median (S1+S2+S3)/(S4+S5) = {payload['cost']['ratio_with_s1_over_s4s5_median']}",
        f"- pass@8 generations per task = 200×8 = **1600** (protocol; not a new measurement)",
        f"- |Δ_pilot|≤0.02 占比 = {payload['budget']['dumb_probe_frac_abs_le_0.02']:.3f}",
        f"- 门效用上限 |Σ负Δ| / Σ正Δ = {payload['budget']['gate_utility_upper']}",
        f"- base_pass1==0 : {payload['n_base0']}/{payload['n']}",
        "",
        "Budget capture (positive-gain mass):",
        "",
        "| K | Δ_pilot | random mean | oracle |",
        "|---:|---:|---:|---:|",
    ]
    for k, blk in payload["budget"]["K"].items():
        lines.append(
            f"| {blk['k']} | {blk['pilot_capture']:.3f} | {blk['random_capture_mean']:.3f} | {blk['oracle_capture']:.3f} |"
        )
    lines += [
        "",
        "敏感性 a（去 arc_easy）仍计算；敏感性 b 的宽 CI **不作为佐证**（见 json）。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    roots = [ROOT / "runs", ROOT / "runs" / "harvest" / "extracted"]
    print("loading rows", flush=True)
    rows = load_v2_rows(roots)
    n = len(rows)
    if n != 61:
        raise SystemExit(f"expected n=61, got {n}")
    y = np.asarray([r.go_registered for r in rows], dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)

    print("main pre-decision LOTO", flush=True)
    main_pd = bundle_auc(rows, PRE_DECISION, rng)
    print("registered leaked 12", flush=True)
    leaked = bundle_auc(rows, LEAKED_12, rng)
    print("posthoc oracle", flush=True)
    oracle = bundle_auc(rows, ["gen_len.full.median"], rng)
    print("trio", flush=True)
    trio = bundle_auc(rows, TRIO, rng)
    print("no pass8", flush=True)
    nop8 = bundle_auc(rows, NO_PASS8, rng)
    print("L2-CV", flush=True)
    p_l2 = loto_l2cv(rows, PRE_DECISION)
    l2_auc, l2_lo, l2_hi = av1.bootstrap_auc(y, p_l2, rng)
    l2 = {"auc" : l2_auc, "ci95": [l2_lo, l2_hi], "covers_0.5": bool(l2_lo <= 0.5 <= l2_hi), "p": p_l2.tolist()}

    singles = {}
    for name in SINGLE_5:
        print("single", name, flush=True)
        blk = bundle_auc(rows, [name], rng)
        singles[name] = {k: blk[k] for k in ("auc", "ci95", "covers_0.5")}

    print("metadata control", flush=True)
    meta = bundle_auc(rows, META_TEXT, rng)
    eval_ns = sorted({row.text.get("eval_n") for row in rows})

    print("embeddings", flush=True)
    E = embed_instructions(rows)
    p_sem = loto_embed(rows, E)
    s_auc, s_lo, s_hi = av1.bootstrap_auc(y, p_sem, rng)
    semantic = {
        "auc": s_auc,
        "ci95": [s_lo, s_hi],
        "covers_0.5": bool(s_lo <= 0.5 <= s_hi),
        "model": EMBED_MODEL,
        "p": p_sem.tolist(),
    }

    dp = np.asarray([r.delta_pilot for r in rows], dtype=float)
    df = np.asarray([r.delta_full for r in rows], dtype=float)
    bp = np.asarray([r.base_pass1 for r in rows], dtype=float)
    rho, rlo, rhi = av1.spearman_ci(dp, df, rng)
    part = partial_spearman(dp, df, bp)

    print("permutation 1000", flush=True)
    perm = permutation_p(rows, PRE_DECISION, float(main_pd["auc"]), y)
    agrees = bool(main_pd["covers_0.5"]) == (perm["p_ge_observed"] >= 0.05)

    # McNemar AUC variants
    y_det_idx = [i for i, r in enumerate(rows) if r.label3 != "undetermined"]
    y_det = np.asarray([1 if rows[i].label3 == "go" else 0 for i in y_det_idx], dtype=float)
    auc_det: Any = None
    if len(set(y_det.tolist())) == 2 and len(y_det) >= 8:
        sub = [rows[i] for i in y_det_idx]
        saved = [r.go_registered for r in sub]
        for r, g in zip(sub, y_det):
            r.go_registered = int(g)
        blk = bundle_auc(sub, PRE_DECISION, rng)
        auc_det = {"auc": blk["auc"], "ci95": blk["ci95"], "n": blk["n"], "n_go": blk["n_go"]}
        for r, g in zip(sub, saved):
            r.go_registered = g
    y_u = np.asarray([1 if r.label3 == "go" else 0 for r in rows], dtype=float)
    saved = [r.go_registered for r in rows]
    for r, g in zip(rows, y_u):
        r.go_registered = int(g)
    blk_u = bundle_auc(rows, PRE_DECISION, rng)
    for r, g in zip(rows, saved):
        r.go_registered = g

    n_go3 = sum(r.label3 == "go" for r in rows)
    n_no3 = sum(r.label3 == "no-go" for r in rows)
    n_un3 = sum(r.label3 == "undetermined" for r in rows)

    ratios = [r.cost.get("ratio_s2s3_over_s4s5") for r in rows]
    ratios_s1 = [r.cost.get("ratio_with_s1_over_s4s5") for r in rows]

    def _med(xs: list[float | None]) -> float | None:
        v = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
        return float(np.median(v)) if v else None

    cost = {
        "ratio_s2s3_over_s4s5_median": _med(ratios),
        "ratio_s2s3_over_s4s5_iqr": (
            None
            if not [x for x in ratios if x is not None]
            else np.quantile([float(x) for x in ratios if x is not None], [0.25, 0.75]).tolist()
        ),
        "ratio_with_s1_over_s4s5_median": _med(ratios_s1),
        "ratio_with_s1_over_s4s5_iqr": (
            None
            if not [x for x in ratios_s1 if x is not None]
            else np.quantile([float(x) for x in ratios_s1 if x is not None], [0.25, 0.75]).tolist()
        ),
        "n_with_journal": sum(r.cost.get("S2") is not None for r in rows),
        "pass8_generations": 1600,
        "per_task": [
            {
                "task_id": r.task_id,
                **{k: r.cost.get(k) for k in ("S1", "S2", "S3", "S4", "S5", "ratio_s2s3_over_s4s5", "ratio_with_s1_over_s4s5")},
            }
            for r in rows
        ],
    }

    print("budget sim", flush=True)
    budget = budget_sim(rows, rng)

    a_rows = [r for r in rows if r.task_id != "arc_easy"]
    sens_a = bundle_auc(a_rows, PRE_DECISION, rng)
    b_rows = [r for r in rows if not (r.base_pass1 == 0.0 and r.full_pass1 == 0.0)]
    sens_b = bundle_auc(b_rows, PRE_DECISION, rng)

    payload = {
        "ts": _now(),
        "git_head": _git_head(),
        "identity": "revision-period ANALYSIS_PREREG_V2",
        "n": n,
        "n_go_registered": int(y.sum()),
        "n_base0": int(sum(r.base_pass1 == 0.0 for r in rows)),
        "task_ids": [r.task_id for r in rows],
        "delta_pilot": dp.tolist(),
        "delta_full": df.tolist(),
        "base_pass1": bp.tolist(),
        "y_registered": y.tolist(),
        "label3": [r.label3 for r in rows],
        "main_predecision": {k: main_pd[k] for k in main_pd if k != "p"},
        "main_predecision_p": main_pd["p"],
        "registered_leaked_12": {k: leaked[k] for k in leaked if k != "p"},
        "posthoc_oracle": {k: oracle[k] for k in oracle if k != "p"},
        "trio": {k: trio[k] for k in trio if k != "p"},
        "no_pass8": {k: nop8[k] for k in nop8 if k != "p"},
        "l2cv": {k: l2[k] for k in l2 if k != "p"},
        "single_feature": singles,
        "metadata_control": {k: meta[k] for k in meta if k != "p"},
        "eval_n_unique": eval_ns,
        "semantic": {k: semantic[k] for k in semantic if k != "p"},
        "spearman": {"rho": rho, "ci95": [rlo, rhi]},
        "partial_spearman_base": part,
        "permutation": perm,
        "perm_agrees_with_ci": agrees,
        "mcnemar": {
            "alpha": MCNEMAR_ALPHA,
            "n_go": n_go3,
            "n_nogo": n_no3,
            "n_undetermined": n_un3,
            "auc_determined": auc_det,
            "auc_undet_as_nogo": {k: blk_u[k] for k in ("auc", "ci95", "n", "n_go") if k in blk_u},
            "per_task": [
                {"task_id": r.task_id, "n01": r.n01, "n10": r.n10, "p": r.mcnemar_p, "label3": r.label3}
                for r in rows
            ],
        },
        "cost": cost,
        "budget": budget,
        "sensitivity_a_drop_arc_easy": {k: sens_a[k] for k in sens_a if k != "p"},
        "sensitivity_b_drop_floor_NOT_AS_EVIDENCE": {k: sens_b[k] for k in sens_b if k != "p"},
        "run_dirs": [str(r.run_dir) for r in rows],
    }

    out_md = ROOT / "docs" / "ANALYSIS_RESULTS_v2.md"
    out_json = ROOT / "docs" / "ANALYSIS_RESULTS_v2.json"
    write_md(payload, out_md)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote n={n} {out_md}", flush=True)


if __name__ == "__main__":
    main()
