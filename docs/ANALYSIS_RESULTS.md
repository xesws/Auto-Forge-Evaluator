# Analysis (citable)

- 时间 (UTC): 2026-08-25T13:38Z
- git HEAD (run): `781b172`; S4 声明: `2fb2db2`
- 协议: protocol_v2 / pv2（yaml 未改）
- 数据包: tv3 leftover + tv4 + tv5 metrics
- 相关 runs: `runs/harvest/forge_incr_{1-7}.tar.gz` + 本机 tv3；全量归档 `runs/harvest/forge_runs_full.tar.gz` sha `71309f7c…f4028f7d`

本文件数字可引用。主分析按 `docs/ANALYSIS_PREREG.md` + S4。诚实条款：**AUC 不显著 = 负结果照发**。

图: `docs/calibration_scatter.png`, `docs/roc.png`。机器可读: `docs/ANALYSIS_RESULTS.json`。

## 样本

n = **61**（53 go / 8 no-go）。`go` ⇔ Δ_full > 0。

- 60 个 `STATUS=ok`（55 原 tv4 ok − 无 + Wave-1 tydiqa/task419 + 3 tv3）
- 外加 **arc_easy** PARTIAL（有 metrics.json）
- **不进 AUC**: apps（PARTIAL, S4 OOM, 无 metrics）、bird（PARTIAL, S2 OOM, 无 metrics）

## 主表

| 模型 | AUC | 95% CI (task bootstrap) | CI 覆盖 0.5? |
|---|---:|---|---|
| 主模型 LOTO logistic (`metrics.signals`) | 0.755 | [0.500, 0.929] | **是 → 不显著** |
| 单特征 Δ_pilot | 0.663 | [0.480, 0.825] | 是 |
| 单特征 base_pass1 | 0.441 | [0.255, 0.615] | 是 |
| 单特征 headroom | 0.481 | [0.285, 0.673] | 是 |
| 单特征 pilot_loss.steps_to_0_01 | 0.748 | [0.585, 0.894] | 否 |
| 单特征 gen_len.full.median | 0.818 | [0.505, 0.986] | 是（贴边） |
| 纯任务描述对照 | 0.309 | [0.045, 0.622] | 是（弱于随机） |

| 副终点 | ρ | 95% CI |
|---|---:|---|
| Spearman(Δ_pilot, Δ_full) | **0.755** | **[0.595, 0.864]**（不含 0） |

**结论（主终点）:** 主模型 LOTO AUC 的 bootstrap 95% CI 覆盖 0.5。按预注册诚实条款，这是**阴性结果**：10-shot LoRA 信号向量**不能**在任务级显著预测 go/no-go。负结果照发。不准事后加特征或改阈值。

**副终点:** Δ_pilot 与 Δ_full 的秩相关显著（ρ≈0.76）。pilot 能排序全量增益，但过不了「Δ_full>0」分类门（正类 53/61，门很松、负类少）。

## 敏感性（S4 预先声明）

### a. 剔除 arc_easy

n=60, AUC 0.748 [0.487, 0.920]，仍覆盖 0.5。Spearman 0.756 [0.594, 0.873]。与主分析同向。

### b. 剔除指标地板（base.pass1=0 ∧ full.pass1=0）

剔除 4 行: `task071_abductivenli_answer_generation`, `task1553_cnn_dailymail_summarization`, `task236_iirc_question_from_passage_answer_generation`, `task455_swag_context_generation`。

n=57, AUC 0.778 [0.411, 0.985]，**仍覆盖 0.5**。Spearman 0.771 [0.608, 0.878]。

这 4 个 no-go 是 EM 地板（生成/摘要抽不出匹配），经济标签可以是真 no-go，机制不是「模型完全没学」。主结论不依赖它们。

### c. 分组报告

| 簇 | n | 注 |
|---|---:|---|
| 选择题 {winogrande, arc_easy, arc_challenge, hellaswag, piqa} | 5 | 全是 go → AUC 无定义 |
| 数学 {gsm8k, math} | 2 | n<3，跳过 AUC |
| SuperNI 同源 | 多数 source n=1 | 跳过；mctaco n=3 不稳（AUC 0，CI 退化）；synthetic n=3 全 go |

簇级 AUC 没有可引用的稳定估计。S1「留出整个簇」在主模型 LOTO 里已通过任务持出体现，不再另报一个过拟合的簇门。

## 失败模式（段落素材）

1. **格式覆盖（gsm8k）:** Δ_full −0.230。base 已会 `####`；全量把格式学满、推理退化。不是 EOS 崩。math 同类负 Δ。
2. **EM 地板:** CNN / IIRC / SWAG / task071 的 Δ_full=0 来自 exact-match 抽不中，不是训练没跑。与 gsm8k「真学坏」要分开写。
3. **分类门太松:** 61 里 53 个 Δ_full>0。AUC 对「会不会涨」几乎没有难负例；Spearman 才打到连续增益。
4. **OOM:** tydiqa / task419 用 1×16 fallback 后拿到数字（Δ_full +0.530 / +0.505），有效 batch 仍 16。bird S2 OOM、apps S4 OOM **没有**数字，未进样本。apps 的 8h 帽让 S1 跑完（0.0 / 0.005），全量仍炸。
5. **描述特征对照弱于随机**（AUC 0.31）: 规模/prompt 长度解释不了 go；主模型即使不显著，也不是被这些静态特征带起来的。

## 不在样本里

- apps: PARTIAL，无 `metrics.json`
- bird: PARTIAL，无 `metrics.json`（S0 打包 bug 已修；S2 显存是新失败）
