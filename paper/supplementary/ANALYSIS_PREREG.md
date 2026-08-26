# 分析预注册

冻结于第一个剩余量产 run 之前。本页是分析合同,不是分析实现。
协议 `protocol_v2`(冻结,不出 v3)。数据包 `tasks_v3`。
样本:任务级,一任务一行;量产目标 n=46(已封 3,剩 43)。

## 标签

- 主终点: go ⇔ Δ_full > 0(严格大于)。Δ_full == 0 记 no-go。
- 连续副终点: Spearman ρ(标量 Δ_pilot, Δ_full)。报 ρ 与任务级 bootstrap CI。
  副终点不是 go/no-go 门。不用向量、不用 Pearson。

## 预测器族(任务级)

1. 主模型: logistic 回归,特征取 `metrics.signals` 数值字段。
   `format_compliance` 压成预声明标量: gsm8k 用 greedy `hash/n`;
   其余任务用 `1 - unparseable/n`(缺键当 0)。另加
   `gen_len.full.median`、`pilot_loss.steps_to_0_01` 及缺失指示
   (`steps_to_0_01 is null` → 指示=1,该数值填训练折中位数)。
2. 单特征 logistic 基线,各训一次:
   `delta_pilot`, `base_pass1`, `headroom`,
   `pilot_loss.steps_to_0_01`, `gen_len.full.median`。
3. 对照(不跑试点): 仅任务描述特征的 logistic。闭集:
   `splits.train_n`, `max_new_tokens`, `len(prompt_style)`, `eval_n`。
   禁止: `prior_label`, `pool_ref`, 任何 `signals.*`, 任何 run 指标。
   (`prior_label` 是文献结局,不是描述。)

每折:数值特征只在训练任务上 z-score,再套到持出任务。

## 验证与区间

- 任务级 leave-one-task-out(n=46 时 46 折)。持出任务不进 scaler、不进分类器。
- AUC 置信区间:对 n 个 LOTO 对 `(y_i, p_i)` 做任务级 bootstrap
  (有放回抽任务,重算 AUC,2.5/97.5 分位)。不在 bootstrap 内再套一层 LOTO。

## 诚实条款

AUC 不显著 = 负结果照发

主模型 LOTO AUC **不显著** 当且仅当该 bootstrap 95% CI 覆盖 0.5。
负结果照发。本 commit 之后不准加特征、改 go 阈值、改协议、丢掉负 Δ 任务。

## 不做(本页冻结)

见到剩余 43 再挖特征;把 Spearman 换成 Pearson;把 `prior_label` 当特征;
因 gsm8k Δ_full < 0 而剔除;把副终点当门。本页不实现 sklearn、不跑分析。
