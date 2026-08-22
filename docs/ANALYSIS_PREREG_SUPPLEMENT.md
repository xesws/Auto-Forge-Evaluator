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

---

## Commit S2 冻结值(抽样之后写入)

- clone: `https://github.com/allenai/natural-instructions.git` (depth 1)
- HEAD SHA: `55a365637381ce7f3748fa2eac7aef1a113bbb82`
- English+规模 存活集: **890** (≥50)
- 种子 20260822, n=50, `Source[0]` ≤3: 名单 `docs/prod_lists/superni_50.json`
- 静态名单(S2 当时): `docs/prod_lists/pod_a.txt` + `pod_b.txt`。
  **S3 起作废双仓**,见下。

50 个 task id(按 id 排序,与抽样脚本输出一致):

task010_mctaco_answer_generation_event_ordering
task014_mctaco_wrong_answer_generation_absolute_timepoint
task016_mctaco_answer_generation_frequency
task026_drop_question_generation
task037_qasc_generate_related_fact
task071_abductivenli_answer_generation
task076_splash_correcting_sql_mistake
task094_conala_calculate_mean
task113_count_frequency_of_letter
task1202_atomic_classification_xneed
task1283_hrngo_quality_classification
task1287_glue_qqp_paraphrasing
task1295_adversarial_qa_question_answering
task1313_amazonreview_polarity_classification
task1386_anli_r2_entailment
task1392_superglue_multirc_answer_verification
task1411_dart_subject_identification
task1419_mathqa_gain
task1420_mathqa_general
task1541_agnews_classification
task1553_cnn_dailymail_summarization
task1600_smcalflow_sentence_generation
task1622_disfl_qa_text_modication
task163_count_words_ending_with_letter
task1661_super_glue_classification
task1712_poki_classification
task196_sentiment140_answer_generation
task227_clariq_classification
task236_iirc_question_from_passage_answer_generation
task242_tweetqa_classification
task278_stereoset_sentence_generation_antistereotype
task286_olid_offense_judgment
task305_jeopardy_answer_generation_normal
task339_record_answer_generation
task345_hybridqa_answer_generation
task366_synthetic_return_primes
task383_matres_classification
task401_numeric_fused_head_reference
task404_grailqa_paraphrase_validation
task419_persent_answer_generation
task430_senteval_subject_count
task455_swag_context_generation
task568_circa_question_generation
task607_sbic_intentional_offense_binary_classification
task619_ohsumed_abstract_title_generation
task634_allegro_reviews_classification
task647_answer_generation
task649_race_blank_question_generation
task677_ollie_sentence_answer_generation
task896_miam_language_classification

---

## Commit S3 执行修订(operator: 单 pod 串行, pod B 取消)

闸门、3h 帽、PARTIAL、确定性节奏(名单第 1 个与每第 10 个全量 200,其余 30 条 seed 20260820) **零变更**。

- 运行名单: `docs/prod_lists/prod_serial.txt` = 文献(无 bird) → SuperNI(原 pod_a 25 再 pod_b 25) → `bird` 队尾。`pod_a.txt` / `pod_b.txt` 仅作历史。
- `tasks_v4.tar.gz` = **59 包**(9 文献 + 50 SuperNI)。不等 bird。v4 只增不改。bird 若物化成功另出 `tasks_v5` (仅 bird)。
- 分析 n = 63(含 bird)或 **62**。排除仅当 pod 上 bird 物化自启动起 2h 不绿、且当时尚无任何 bird `metrics.json`。排除句原文:
  excluded for logistics, before any bird number existed
- 中期报告: 9 个非 bird 文献 GPU 封盘后交(3 历史 + 9 = 12 行; bird 仍在队尾/并行物化)。13 行只出现在终表且仅当 bird 入样。
