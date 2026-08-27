# Analysis v2 · ADDENDUM — attribution of the pre-decision AUC

- 时间 (UTC): 2026-08-27T01:59:32Z
- git HEAD: `bb956585c5a2`
- n = 61；协议未改，go 阈值未改，无 GPU 重跑
- 生成脚本: `scripts/analysis_v2_addendum.py`（CPU，纯重分析）

**身份: 修订期新增分析的更正件。** `ANALYSIS_RESULTS_v2.md` 的主表数字本身可复现，
但它对 0.755 → 0.844 的**归因是错的**。本文件给出正确分解，并作为论文引用真源。

## 1. 未申报的特征定义变更

位置: `scripts/analysis_v2.py::format_compliance_base`，分支 `task_id == 'math' -> base['boxed'] / n`。
在 `ANALYSIS_PREREG_V2.md` 八条新增项中**未申报**（见该文件 R1-9 补申报条）。

v1 公式 `1 - unparseable/n` 对没有 `unparseable` 键的任务恒返回 1.0。全样本只有两个这样的任务：

| task | base 块标量键 | v1 值 | v2 值 |
|---|---|---:|---:|
| `gsm8k` | `diverge`, `hash`, `last_only`, `n`, `none` | 0.290 | 0.290 |
| `math` | `boxed`, `diverge`, `last_only`, `n`, `none` | 1.000 | 0.550 |

v1 特判了 `gsm8k`、漏了 `math`。**该分支是正当的 bug 修复，不是挑任务**；
但它改变的任务是 ['math']，其中 `math` 是全样本仅有的两个实质负例之一。

## 2. 归因分解（同一 pipeline，只翻转 `format_compliance_base`）

| 模型 | fc v2（含 math 修复） | fc v1（仅去泄漏） | 差 |
|---|---:|---:|---:|
| `registered_leaked_12` | 0.7547 | 0.7547 | +0.0000 |
| `pre_decision_10` | 0.8443 | 0.6627 | +0.1816 |
| `l2cv_pre_decision` | 0.8750 | 0.7217 | +0.1533 |
| `no_pass8` | 0.8373 | 0.6745 | +0.1627 |
| `trio_3feat` | 0.7665 | 0.7665 | +0.0000 |

**分解:**

```
去掉泄漏特征 (12->10, fc 固定 v1) : 0.7547 -> 0.6627  = -0.0920
math fc 分支 (一个格子, 特征固定) : 0.6627 -> 0.8443  = +0.1816
```

**去泄漏使 AUC 下降。** 涨幅全部来自那一个格子。
`registered_leaked_12` 与 `trio_3feat` 对该分支免疫（差 = 0）。

## 3. 三个候选主行（bootstrap CI + 标签置换，每次置换重跑全 LOTO）

| 主行 | AUC | 95% CI | 覆盖 0.5 | 置换 p |
|---|---:|---|---|---:|
| pre-decision，仅去泄漏 | 0.6627 | [0.433, 0.839] | 是 | 0.0569 |
| pre-decision，去泄漏 + math 修复 | 0.8443 | [0.733, 0.943] | 否 | 0.0020 |
| **3 特征（对两者都免疫）** | 0.7665 | [0.646, 0.879] | 否 | 0.0040 |

置换 p 用 `(1 + #{perm >= obs}) / (1 + N)`，N = 1000。
`ANALYSIS_RESULTS_v2.md` 报的 0.0010 是 `#/N` 的朴素写法（命中 1 次），应读作 0.0020。

## 4. 稳定性: drop-one-negative jackknife（fc v2 的 pre-decision 模型）

全样本 AUC = 0.8443

| 丢弃的 no-go | AUC | 变化 |
|---|---:|---:|
| `math` | 0.6846 | -0.1597 |
| `gsm8k` | 0.7143 | -0.1301 |
| `task014_mctaco_wrong_answer_generation_absolute_timepoint` | 0.8329 | -0.0115 |
| `task236_iirc_question_from_passage_answer_generation` | 0.8437 | -0.0007 |
| `task1553_cnn_dailymail_summarization` | 0.8464 | +0.0020 |
| `mbpp` | 0.8544 | +0.0101 |
| `task071_abductivenli_answer_generation` | 0.8652 | +0.0209 |
| `task455_swag_context_generation` | 0.8706 | +0.0263 |

区间 [0.685, 0.871]。丢掉任一实质负例（`math` / `gsm8k`）AUC 掉 0.13–0.16。
8 个负例（实质负例 2 个）撑不住第二位小数。

## 5. 论文应当采用的读法

1. 注册主行（12 特征，含 post-decision `gen_len.full.median`）AUC 0.755，CI 覆盖 0.5，**照发阴性**。
2. 单纯移除该 post-decision 特征**不能**挽救它。
3. 把维度降到 3 个 pre-decision 特征才显著 —— 注册阴性的机制是**过参数化**（12 特征 / 8 负例），不是「没有信号」。
4. `math` format-compliance 的 bug 修复单独申报、单独报效应量，**不并入「去泄漏」**。
5. 门本来就不值钱（完美门效用上限 0.024），门显不显著都不该是头条。

