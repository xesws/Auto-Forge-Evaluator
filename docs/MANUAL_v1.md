═══ §1 目的与总架构 ═══
研究:十样本试点微调能否预测全量微调收益(go/no-go 的 AUC)。
本仓库承载:任务包物化 → (pilot → full → eval) 单任务管线 →
多任务队列执行。原则:协议单一真源、数据冻结包、一切可复算、
台账 append-only。

═══ §2 冻结协议 configs/protocol_v1.yaml(逐字段)═══
base_model: Qwen/Qwen2.5-1.5B-Instruct
base_revision: "PIN_AT_ENV_SETUP"   # Phase 3 首次拉权重时钉为
                                    # 具体 commit sha 并记台账
dtype: bfloat16
quantization: none                  # 16GB 下 LoRA 不量化,禁 QLoRA
lora: {r: 16, alpha: 32, dropout: 0.05,
       target_modules: [q_proj,k_proj,v_proj,o_proj,
                        gate_proj,up_proj,down_proj]}
train: {lr: 1.0e-4, schedule: cosine, warmup_ratio: 0.03,
        per_device_batch: 4, grad_accum: 4,
        loss: completion_only,      # prompt 部分 mask
        template: chat}             # 训练评测同用 chat template
pilot: {n: 10, steps: 100, sample_seed: 20260820}
full:  {cap: 8000, epochs: 3, sample_seed: 20260820}
eval:  {slice_n: 200, slice_seed: 20260820,
        decoding: greedy, temperature: 0.0}
signals:
  pass1: greedy
  pass8: {k: 8, temperature: 1.0, top_p: 0.95}   # 仅作信号,
                                                  # 标签永远 greedy
seeds: {train_seed: 42}
max_new_tokens: per-task(见 §5)

═══ §3 仓库骨架 ═══
configs/protocol_v1.yaml
tasks/<task_id>/{task.json, train.jsonl, eval.jsonl,
                 verifier.py, MANIFEST.sha256}
src/{data.py, train_lora.py, eval_greedy.py, signals.py}
scripts/{make_task_package.py, run_task.py, worker.py(占位)}
tests/(verifier 单元测试)
docs/{MANUAL_v1.md, ledger.md}
runs/(.gitignore)  data_cache/(.gitignore)

═══ §4 任务包格式 ═══
task.json:
  {task_id, source: {dataset, hf_path, config, revision},
   prior_label, pool_ref(池子行号或 task_name+paper),
   splits: {train_n, eval_n, seeds}, max_new_tokens,
   prompt_style: 说明字段}
train.jsonl / eval.jsonl 每行:
  {id, messages: [{role:user, content:...}], reference: {...}}
  # reference 结构由各 verifier 定义
verifier.py 统一接口:
  def verify(output: str, reference: dict) -> dict:
      return {"pass": bool, "parsed": str|None, "note": str}
  # unparseable 必须以 parsed=None 显式区分,禁止静默判错
MANIFEST.sha256:目录内全部文件的哈希清单。
打包:tasks_v1.tar.gz + 顶层 MANIFEST,版本只增不改。

═══ §5 三个冒烟任务 ═══
[gsm8k]  源:HF openai/gsm8k, config "main"
  train:官方 train 全量 7,473;eval:test 固定种子抽 200
  max_new_tokens: 512
  verifier:优先取 "#### " 后数值;兜底取输出中最后一个数;
  规范化(去逗号/空格,float 容差 1e-6)后精确匹配。
  两种抽取都写进 note,分歧样本 id 落 runs/<run>/extract_div.jsonl
[winogrande]  源:HF allenai/winogrande, config "winogrande_xl"
  train:40,398 固定种子降采样 8,000;eval:validation 抽 200
  prompt:句子 + 选项 A/B,要求只答字母
  max_new_tokens: 16
  verifier:解析输出首个 A/B(容忍 "A."、"答案:A" 等模式);
  解析失败 → pass=False, parsed=None,unparseable 计数单列
[spider]  源:HF xlangai/spider(题目);数据库文件为独立下载
  (~100MB,触发 prompt 里的报告条款;记录实际来源与 sha)
  train:官方 8,659;eval:dev 抽 200
  prompt:含目标库 schema(CREATE TABLE 摘要)+ 问题
  max_new_tokens: 256
  verifier:sqlite 执行生成 SQL 与金标 SQL,结果集比对
  (行序无关、多重集比较);执行异常/超时(30s)= fail,
  note 记异常类型
单元测试(Phase 2 必做,变异测试):每个 verifier 喂
  ①金标答案(必 pass)②已知错误答案(必 fail)
  ③格式变体的正确答案(数值加逗号/字母带句号:必 pass)
  ④乱码(必 parsed=None)
  每类 ≥3 例,tests/ 里固化。

═══ §6 单任务管线 scripts/run_task.py ═══
阶段序(journal 逐阶段落行,断点从阶段边界续):
  S0 load(task 包哈希校验)
  S1 eval_base:eval 切片 greedy pass@1 + pass@8   → base 信号
  S2 pilot_train(10 样本 ×100 步)
  S3 eval_pilot:同切片 greedy                     → Δ_pilot
  S4 full_train(cap 8000 ×3ep)
  S5 eval_full:同切片 greedy                      → Δ_full
  S6 seal:metrics.json(含 systems 块:torch/transformers/
     CUDA/driver 版本、base_revision、全部种子)+ 全产物哈希
--dry-run:以 HF 上一个 <100M 参数的随机初始化小模型替换基座、
  各阶段步数=2、eval 切 5 条,验证控制流/落盘/journal/续跑,
  不验证数值。Mac CPU 可跑,这是你的自测通道。
GPU 交付:输出 Gate 0 命令,形如
  python scripts/run_task.py --task gsm8k --protocol configs/protocol_v1.yaml

═══ §7 存储层 ═══
默认全部落本地 runs/。抽象一个 Storage 接口(put/get/list),
本地实现先行;S3 实现留 stub,凭证走环境变量,本 Phase 不配。

═══ §8 纪律 ═══
协议改动 = 版本号 +1 + 台账一行 + operator 确认,禁止静默调参;
数字必须可从落盘产物复算;不确定就问。