# Analysis v2 (revision-period, citable for the rewrite)

- 时间 (UTC): 2026-08-27T01:32:00Z
- git HEAD: `9937332e03e7`
- 协议: protocol_v2 / pv2（yaml 未改）
- 合同: `docs/ANALYSIS_PREREG_V2.md`（v1 注册主行仍照报）
- n = **61**（53 go under registered label Δ_full>0）

**身份: 修订期新增分析。** v1 `ANALYSIS_RESULTS.md` 仍是注册主行真源。

> ⚠️ **归因部分已被更正。** 本文件把 0.755 → 0.844 归因为「去泄漏」，这是**错的**：
> 单纯去泄漏是 0.755 → **0.663**（下降）；+0.182 的涨幅全部来自 `analysis_v2.py`
> 里一个未申报的 `math` format-compliance bug 修复。
> 分解、修复前/后双值、置换 p 的正确写法、jackknife 见
> **`docs/ANALYSIS_RESULTS_v2_ADDENDUM.md`**（合同补条见 `ANALYSIS_PREREG_V2.md` R1-9）。
> 两文冲突处**以 ADDENDUM 为准**。本文件下列数字本身可复现，不改。

## 主表（pre-decision LOTO）

- 新主 LOTO AUC = **0.844**, 95% CI [0.736, 0.939], 覆盖 0.5? **否**
- 标签置换 p (N=1000, P(AUC_perm ≥ AUC_obs)) = **0.0010**
- 置换与 bootstrap 同向（均不显著 / 均显著）: **True**
- 注册泄漏 12 特征 LOTO（对照，不可用于决策）AUC = 0.755 [0.498, 0.930]
- post-hoc oracle `gen_len.full.median` AUC = 0.818 [0.528, 0.978]
- L2-CV LOTO AUC = 0.875 [0.763, 0.960]
- 3-feat (Δ_pilot, base_pass1, headroom) AUC = 0.767 [0.649, 0.870]
- 无 pass@8 特征集 AUC = 0.837 [0.721, 0.930]

## Spearman

- ρ(Δ_pilot, Δ_full) = 0.755 [0.596, 0.863]
- partial ρ | base_pass1 = 0.832

## 单特征（5 行；多重比较未校正）

| 特征 | AUC | 95% CI | 覆盖 0.5? | 决策可用 |
|---|---:|---|---|---|
| `delta_pilot` | 0.663 | [0.478, 0.827] | 是 | 是（pre-decision） |
| `base_pass1` | 0.441 | [0.265, 0.615] | 是 | 是（pre-decision） |
| `headroom` | 0.481 | [0.282, 0.667] | 是 | 是（pre-decision） |
| `pilot_loss.steps_to_0_01` | 0.748 | [0.585, 0.881] | 否 | 是（pre-decision） |
| `gen_len.full.median` | 0.818 | [0.537, 0.985] | 否 | 否（post-hoc） |

## 对照

- 元数据对照（4 标量）AUC = 0.309 [0.051, 0.675] （eval_n 唯一值 = [200.0]）
- 语义对照（MiniLM instruction + Categories/Source）AUC = 0.512 [0.255, 0.746]

## McNemar 三分类（修订期新增；α=0.05 双侧精确，未校正）

- go / no-go / undetermined = 45 / 2 / 14
- LOTO AUC on determined-only = {'auc': 1.0, 'ci95': [1.0, 1.0], 'n': 47, 'n_go': 45}
- LOTO AUC treating undetermined as no-go = {'auc': 0.8875, 'ci95': [0.7916276737967916, 0.9636426767676769], 'n': 61, 'n_go': 45}

## 成本与预算

- median (S2+S3)/(S4+S5) = 0.17369727047146402
- median (S1+S2+S3)/(S4+S5) = 0.5288985823336968
- pass@8 generations per task = 200×8 = **1600** (protocol; not a new measurement)
- |Δ_pilot|≤0.02 占比 = 0.377
- 门效用上限 |Σ负Δ| / Σ正Δ = 0.02352941176470588
- base_pass1==0 : 23/61

Budget capture (positive-gain mass):

| K | Δ_pilot | random mean | oracle |
|---:|---:|---:|---:|
| 5 | 0.220 | 0.080 | 0.261 |
| 10 | 0.423 | 0.164 | 0.446 |
| 20 | 0.718 | 0.326 | 0.740 |
| 30 | 0.833 | 0.491 | 0.904 |

敏感性 a（去 arc_easy）仍计算；敏感性 b 的宽 CI **不作为佐证**（见 json）。

