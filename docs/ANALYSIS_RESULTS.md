# Analysis (citable) — **SEALED**

- 时间 (UTC): 2026-08-25T13:38Z（数字封于 `--final` 跑次；本稿 2026-08-25 关账）
- git HEAD (run): `781b172`; S4 声明: `2fb2db2`
- 协议: protocol_v2 / pv2（yaml 未改）
- 数据包: tv3 leftover + tv4 + tv5 metrics
- 相关 runs: `runs/harvest/forge_incr_{1-7}.tar.gz` + 本机 tv3；全量归档 `runs/harvest/forge_runs_full.tar.gz` sha `71309f7c…f4028f7d`
- 图: `docs/figures/`（`scripts/plot_citable_figures.py` 从冻结 `docs/figures/plot_data.json` 一键复算）
- 机器可读: `docs/ANALYSIS_RESULTS.json`

**本文件是唯一可引用真源。不再有任何补算。** 主分析按 `docs/ANALYSIS_PREREG.md` + S4。诚实条款：**AUC 不显著 = 负结果照发**。

## 四发现（论文叙事，封死）

1. **阴性主门.** 主模型任务级 LOTO logistic AUC = 0.755，bootstrap 95% CI [0.500, 0.929] **覆盖 0.5**。10-shot LoRA 信号向量不能显著预测 go/no-go。
2. **显著排序.** Spearman ρ(Δ_pilot, Δ_full) = 0.755，CI [0.595, 0.864] **不含 0**。pilot 能排序全量增益，过不了二分类门。
3. **描述反向.** 纯任务描述对照 AUC = 0.309，CI [0.045, 0.622]，弱于随机。规模/prompt 长度解释不了 go。
4. **87% 基率.** n=61 中 53 go（53/61 ≈ **86.9%**）。门 Δ_full>0 太松，负类缺席，AUC 难显著。

敏感性 **a**（去 arc_easy）与 **b**（去 EM 地板）与主表并列：AUC CI 仍覆盖 0.5。叙事不依赖这两刀。

## 样本（封死 n=61）

n = **61**（53 go / 8 no-go）。`go` ⇔ Δ_full > 0。

- 60 个 `STATUS=ok` + **arc_easy** PARTIAL（有 metrics.json）
- **bird**、**apps** 不进分析集。终裁原文:
  `excluded for logistics, before any label existed`
  - bird: 无任何 `metrics.json`（S0 字段 bug 已修；S2 CUDA OOM 无标签）
  - apps: 无 Δ_full / 无 `metrics.json`（8h 帽跑完 S1 base 0.0/0.005，S4 OOM）。base 地板写入 limitations，作为负类缺席的注脚，**不是**分析标签

## 主表（含预先声明的 a / b）

| 模型 | n | AUC | 95% CI | 覆盖 0.5? |
|---|---:|---:|---|---|
| 主模型 LOTO logistic | 61 | 0.755 | [0.500, 0.929] | **是 → 不显著** |
| **a.** 剔除 arc_easy | 60 | 0.748 | [0.487, 0.920] | **是** |
| **b.** 剔除指标地板 | 57 | 0.778 | [0.411, 0.985] | **是** |
| 单特征 Δ_pilot | 61 | 0.663 | [0.480, 0.825] | 是 |
| 单特征 base_pass1 | 61 | 0.441 | [0.255, 0.615] | 是 |
| 单特征 headroom | 61 | 0.481 | [0.285, 0.673] | 是 |
| 单特征 pilot_loss.steps_to_0_01 | 61 | 0.748 | [0.585, 0.894] | 否 |
| 单特征 gen_len.full.median | 61 | 0.818 | [0.505, 0.986] | 是（贴边） |
| 纯任务描述对照 | 61 | 0.309 | [0.045, 0.622] | 是（弱于随机） |

| 副终点 | n | ρ | 95% CI |
|---|---:|---:|---|
| Spearman(Δ_pilot, Δ_full) | 61 | **0.755** | **[0.595, 0.864]** |
| a. 去 arc_easy | 60 | 0.756 | [0.594, 0.873] |
| b. 去指标地板 | 57 | 0.771 | [0.608, 0.878] |

**b** 剔除: `task071_abductivenli_answer_generation`, `task1553_cnn_dailymail_summarization`, `task236_iirc_question_from_passage_answer_generation`, `task455_swag_context_generation`。

簇级 AUC（S4c）无稳定估计（选择题全 go；数学 n=2；SuperNI 同源大多 n=1）。不另开分析。

## 失败模式（封，不再扩展）

1. **格式覆盖（gsm8k / math）:** gsm8k Δ_full −0.230。base 已会 `####`；全量把格式学满、推理退化。
2. **EM 地板:** 上列 4 行 Δ_full=0 来自 exact-match 抽不中。
3. **分类门太松 / 87% 基率.**
4. **OOM 披露:** tydiqa / task419 走 1×16 fallback 后进样本（Δ_full +0.530 / +0.505）。bird / apps 无标签，已排除。
5. **描述对照弱于随机.**
