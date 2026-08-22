# 分析预注册 · 增补 (Phase 4)

本页是 `docs/ANALYSIS_PREREG.md` 的增补,不改原页正文。
协议仍为 `protocol_v2`(不出 v3)。诚实条款不变:

AUC 不显著 = 负结果照发

本增补 **Commit S1** 只冻结规格与算法,不含 SuperNI 50 个 task id。
50 个 id、clone SHA、两张 pod 名单写入 **Commit S2**。
**S2 未上 `origin/main` 之前,禁止任何非 `--dry-run` 的量产 run。**

## 样本框纠正

原页 n=46 /「剩 43」把 pool_v0.2 的可重测**行**数当成了任务数。
去重后文献层任务 = 13(已封 gsm8k / winogrande / spider)。
本阶段:文献层再 10 包 + SuperNI 分层抽 50 包。分析样本 n = **63 任务**
(3 历史 + 60 新)。LOTO 在全量封盘后为 63 折。不改 go 阈值、不加主模型特征、不改协议。

已封 3 个 run 计为量产数据,不重跑。本阶段 GPU 新 run = 60。

## 近重复折叠

- MATH500 → MATH: 只打一个任务 `math`(Hendrycks competition MATH)。不打 MATH-500。
- MBPP+ → MBPP: 只打一个任务 `mbpp`(官方 3 断言)。不打 EvalPlus / MBPP+。

## 任务簇(分析期做簇稳健性,不是新主特征)

| cluster | task_ids |
|---|---|
| choice | winogrande, arc_easy, arc_challenge, hellaswag, piqa |
| math | gsm8k, math |
| sql | spider, bird |
| code | mbpp, apps |
| reading | drop, tydiqa |
| superni | Commit S2 的 50 个;子标签 = SuperNI `Categories[0]` |

簇稳健性 = 主模型 LOTO AUC 在「留出整个簇」下重算。预声明,不是看到结果再挖。

## 闸门与预算帽

`scripts/gate_check.py` 在 S6 后自动跑。失败不堵队列。

- unparseable(`parsed is None` 或 `note.unparseable`) on `eval_base_greedy.jsonl` **< 5%**
- pilot loss 下降: `signals.pilot_loss.end < start`; source=missing → 该项失败
- `systems` 齐: torch, transformers, cuda, driver, gpu_name, base_revision, seeds, dry_run=false
- 确定性: 重载 **base**(无 LoRA) greedy。每 pod 名单第 1 个与每第 10 个任务全量 200;
  其余抽 30 条(seed 20260820)。per-id `pass` 任一不一致 → 闸门失败
- 闸门失败 → `run_dir/STATUS` = `PARTIAL`
- 单任务墙钟 **3 h**;超时 → `STATUS` = `over_budget`。APPS / BIRD 为风险户

## max_new_tokens(协议字段仍为 per-task)

| tasks | max_new_tokens |
|---|---|
| arc_easy, arc_challenge, hellaswag, piqa | 16 |
| math | 512 |
| drop, tydiqa | 128 |
| mbpp, apps | 512 |
| bird | 256 |
| 每个 SuperNI 任务 | 128 |

## 代码沙箱帽

子进程; 10 s; 无网络; 专用临时目录; `ulimit -v` **2097152** KB (2 GiB)。

## SuperNI 过滤器规格 v0(先入库,后执行)

1. Clone `https://github.com/allenai/natural-instructions.git` 到 gitignored
   `data_cache/natural-instructions/`。HEAD SHA 记入本增补 Commit S2。
2. 范围: `Input_language` 与 `Output_language` 列表均包含 `English`。
   train/test track 均可入(不做指令泛化评测;任务各自独立成立)。
3. 规模: 实例数足够 **eval 200 + train ≥ 10**,且 train/eval id 不重叠。
   English+规模 过滤后存活集 < 50 → **停,上报**,不放松约束。
4. 抽样: 层 = `Categories[0]`;按层内任务数比例分配名额;种子 **20260822**;
   抽 50;同一 `Source[0]` ≤ 3。层内抽到违规 Source 则跳过该任务、在该层继续;
   层填不满则按剩余层质量重新分配名额。实现必须与本段一致:
   `scripts/sample_superni.py`。抽出的 50 个 task id **先 commit 进本增补 S2**,
   后跑任何量产 run,后打 SuperNI 包。
5. 打包: 统一 loader; 规范化 EM 为 pass, token-F1 只进 `note`;
   `max_new_tokens=128`。行抽样种子仍为协议 `20260820`(与任务抽样种子 20260822 分开)。

## prior_label

60 个新任务 `prior_label` = JSON null(不编造 strong-gain / weak)。
文献 10 的 `pool_ref` = `literature-layer Phase 4; folded MATH500→MATH, MBPP+→MBPP`。
SuperNI 的 `pool_ref` = `superni stratified sample seed 20260822`。
对照预测器仍禁止使用 `prior_label` / `pool_ref`。

## APPS 难度

只取 introductory。competitive 不进包(避免 1.5B 贴零增益地板)。

## BIRD 下载盒

官方库约 33.4 GB。时间盒 1 小时,体积盒 40 GB。超盒停止上报,不改用 Mini-Dev。

## 不做

S2 名单出来之前开量产 run;加主模型特征;改 go 阈值;改协议;打 MATH-500 或 MBPP+;
因看到分数再滤 TyDiQA 语言;把簇稳健性变成主终点。
