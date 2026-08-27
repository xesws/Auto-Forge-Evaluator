# 分析预注册 · 修订期 v2

本页是 **2026-08-26 修订战役** 的新增分析合同，不改 `ANALYSIS_PREREG.md` 原文。
v1 注册主行（含 `gen_len.full.median` / `full_n` 的 12 特征 LOTO）仍作为**注册主行**照报。
本页产出写入 `docs/ANALYSIS_RESULTS_v2.md` / `.json`。身份 = 修订期新增分析。

诚实条款不变：AUC 不显著 = 负结果照发。

## 不做

改协议；改 go 阈值 Δ_full>0（注册标签）；丢掉负 Δ 任务；GPU 重跑；把敏感性 b 的宽 CI 当佐证。

## 新增项（R1）

1. **去泄漏主表.** 主特征向量只含 pre-decision：
   `delta_pilot`, `base_pass1`, `base_pass8`, `headroom`,
   `pilot_loss.{start,end,steps_to_0_01,steps_to_0_01_missing}`,
   `format_compliance(base)`, `train_n`。
   `gen_len.full.median` 单列 post-hoc oracle 上界，不可用于决策。
   新主 LOTO AUC+CI 为论文新主数。
2. **标签置换.** 每次置换 y 重跑完整 LOTO，N=1000，报 p，与 bootstrap CI 并排。
3. **语义对照.** instruction 句向量（all-MiniLM-L6-v2, CPU）+ SuperNI Categories/Source；
   原 4 标量对照降为「元数据对照」。
4. **单特征 5 行全报.** 含 `steps_to_0_01`；脚注：多重比较未校正。
   partial Spearman ρ(Δ_pilot, Δ_full | base_pass1)。
5. **正则化.** L2-CV LOTO 与 3 特征版（delta_pilot, base_pass1, headroom）并列。
6. **McNemar 三分类.** 从 eval jsonl 配对；go / no-go / undetermined；α=0.05 双侧精确。
   注册标签仍为 Δ_full>0。
7. **成本.** journal 阶段墙钟；(S2+S3)/(S4+S5) 与 含 S1 版；pass@8 = 200×8=1600 次生成；
   无 pass@8 特征集变体。
8. **预算模拟.** K∈{5,10,20,30}；Δ_pilot 排序 vs 随机 vs oracle；
   门效用上限 = |Σ 负Δ| / Σ 正Δ；|Δ_pilot|≤0.02 占比。

种子：置换 20260826；bootstrap 仍 20260820 以便与 v1 区间方法对齐。

## 补申报 (R1-9) — 修订期发现的 bug 修复，晚于本合同

**发现时间晚于本页写定。** 按本项目「不改就是不改，改了就写下来」的规则补申报，不回填、不改上文。

`scripts/analysis_v2.py::format_compliance_base` 相对 v1 的
`scripts/analysis.py::format_compliance_scalar` 增加了一个分支：

```python
if task_id == "math":
    return float(base.get("boxed") or 0) / n      # 110/200 = 0.55
```

理由：v1 公式 `1 - unparseable/n` 对 `format_compliance.base` 块中没有 `unparseable`
键的任务恒返回 1.0。全样本 61 个任务里只有 **gsm8k** 和 **math** 是这种块形状
（gsm8k 用 `hash`、math 用 `boxed`）。v1 特判了 gsm8k、漏了 math。
所以这是**修 bug**，不是按任务挑值。

**但它必须单独申报，因为：**

1. 它不在本页 R1 的 8 条新增项内；
2. 它改变的唯一任务 `math` 是全样本仅有的两个实质负例之一（另一个是 gsm8k）；
3. 它的效应量是 **+0.182 AUC**（pre-decision 10 特征：0.663 → 0.844），
   **大于**去泄漏本身的效应（去泄漏是 −0.092：0.755 → 0.663）。

**约束（本条即刻生效）：**

- 任何含 `format_compliance` 项的模型，**必须同时报**修复前/修复后两个值。
- **禁止**把该修复的涨幅归入「去泄漏」叙事。
- 论文主张优先采用对该修复免疫的行（3 特征模型，不含 compliance 项）。
- 分解、bootstrap CI、置换 p、jackknife 写入
  `docs/ANALYSIS_RESULTS_v2_ADDENDUM.md`（脚本 `scripts/analysis_v2_addendum.py`）。
- 置换 p 一律用 `(1 + #{perm ≥ obs}) / (1 + N)`；`ANALYSIS_RESULTS_v2.md` 的 `#/N` 写法作废。

诚实条款不变：注册主行（12 特征）AUC 0.755 CI [0.500, 0.929] 覆盖 0.5，**阴性照发**。
