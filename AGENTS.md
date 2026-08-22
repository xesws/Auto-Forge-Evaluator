# AGENTS.md — Auto-Forge-Evaluator 工作规则
rev: 1 (2026-08-22)

本文件对在本仓库工作的所有 agent 生效。与任务 prompt 冲突时,先停下来问 operator,不许自行取舍。

## 1. Git 规则

- **最小提交单元 = 一个小任务。** 每完成一个可独立描述的更改(一个脚本、一个任务包、一处修复),立即 `commit` 并 `push`。禁止把多个不相关更改攒进一个 commit,禁止本地堆积未推送的提交——**做完就推,推完再做下一件**。
- Commit message 格式:`[phase-N] 动词开头的一句话`,例如 `[phase-2] add gsm8k verifier + mutation tests`。修复类用 `[fix]`,文档类用 `[docs]`,与 Phase 无关的杂项用 `[chore]`。
- 一律直接在 `main` 上工作(单人仓,无 PR 流程),因此更要小步:**每个 commit 必须让仓库处于可运行状态**——测试通不过就不许 commit。
- 禁止 `git push --force`。禁止改写已推送的历史。写错了就再提交一个 `[fix]`。
- 大文件不进 Git:`runs/`、`data_cache/`、`*.tar.gz`、模型权重、数据库文件全部走 `.gitignore`。数据靠哈希清单(MANIFEST)追踪,不靠 Git 存储。
- 每个 Phase 结束的最后一个 commit,message 加后缀 `[phase-N-done]`,方便回溯每个停点的仓库状态。

## 2. 版本命名规则

三类对象各有版本序列,互不混用:

- **协议**:`protocol_v{N}.yaml`(整数递增:v1, v2, …)。协议文件**只增不改**——任何参数变更 = 复制出新版本号的新文件 + 台账记录变更理由 + operator 确认。旧版本文件永久保留,run 产物里引用的协议版本必须真实存在于仓库中。
- **数据包**:`tasks_v{N}.tar.gz`(整数递增)。同名包内容**永不覆盖**:切片变了、任务增删了、verifier 改了,都出新版本号。每个包带顶层 `MANIFEST.sha256`,包版本与哈希一一对应。
- **运行产物**:`runs/{task_id}__{protocol_ver}__{tasks_ver}__{YYYYMMDD-HHmm}/`,例如 `runs/gsm8k__pv1__tv1__20260821-0230/`。目录名即完整可追溯坐标:看名字就知道这次 run 用的哪版协议、哪版数据。
- 文档修订(手册、本文件)在文件头部维护一行 `rev: N (YYYY-MM-DD)`,正文重大变更时 +1。

## 3. 台账

`docs/ledger.md`,append-only:每个决定、每个意外、每处对手册或本规则的偏离(偏离必须先问),各记一行,带日期。禁止编辑或删除已有行。

## 4. 一票否决项

- 静默调参(改协议不升版本号)
- 未推送就开始下一个任务
- 测试红着 commit
- 覆盖任何已发布的数据包或协议文件

## 5. 远程长任务必须自监督

tmux / SSH 上的训练与评测**不会**在结束时叫醒本会话。agent 不得等 operator 来问「跑完没有」才去看。

启动任何预计超过数分钟的远程作业时,必须同时挂上自己的监督(cron、session monitor、或等价的定时探活):轮询 journal/`metrics.json`/进程是否还在,完成后**主动回报**,失败也主动报。监督挂了要自己补挂。禁止把「等你问我」当成状态机。