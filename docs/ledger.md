# docs/ledger.md

append-only. One dated line per decision, incident, or spec deviation.

- 2026-08-21: Phase 1 start. Copied operator file `开发手册v1.md` verbatim to `docs/MANUAL_v1.md` (sha256:153a003fd3da0615439b714404aa8e89eeedd5a8a62491173f0688d082c1c211, 5207 bytes, no trailing newline). `docs/MANUAL_v1.md` is the spec source.
- 2026-08-21: Added `configs/protocol_v1.yaml` with only MANUAL §2 keys/values (block YAML, no extra keys). `max_new_tokens` kept as the literal string `per-task(见 §5)`; per-task ints live in task.json in Phase 2. `base_revision` kept as `PIN_AT_ENV_SETUP` until Phase 3 pin.
- 2026-08-21: Phase 1 skeleton: `tasks/` `src/` `tests/` via `.gitkeep`; `scripts/worker.py` placeholder only (MANUAL §3 占位). Did not add `src/{data,train_lora,eval_greedy,signals}.py` or `scripts/{make_task_package,run_task}.py` — operator Phase split puts those in Phase 2/3.
- 2026-08-21: `runs/` and `data_cache/` exist locally and are gitignored. `.gitignore` also covers `*.tar.gz`, model weights, db files (AGENTS.md), plus standard Python/OS junk (`__pycache__`, `.venv`, `.DS_Store`).
- 2026-08-21: README is three lines (operator Phase 1 request; not listed in MANUAL §3).
- 2026-08-21: Committed pre-existing `AGENTS.md` (working rules already in the clone; not listed in MANUAL §3).
- 2026-08-21: Deleted root `开发手册v1.md` after the verbatim copy so the spec has a single path `docs/MANUAL_v1.md`.
- 2026-08-21: Phase 1 STOP. No downloads, no training, no invented protocol keys.
- 2026-08-21: Operator confirmed push. `git push -u origin main` created remote `main` at github.com/xesws/Auto-Forge-Evaluator (HEAD a512d97).
- 2026-08-21: Phase 2 start. GSM8K verifier: prefer `####` then last number; both extracts in JSON `note`; numeric compare after strip comma/space with abs tol 1e-6.
- 2026-08-21: WinoGrande verifier: first A/B; accepts `A.`, `答案:A`, `Answer: B`; parse fail → parsed=None. Bare English article `a` is not an answer.
- 2026-08-21: Spider verifier: extract SQL (fence or raw, must have SELECT/WITH/DML); sqlite ro exec vs gold; Counter/multiset row compare; 30s interrupt → TimeoutError in note. Fixture DBs only in tests so far.
- 2026-08-21: `scripts/make_task_package.py` pins HF revisions observed 2026-08-21: openai/gsm8k `740312add88f781978c0658806c59bc2815b9866`, allenai/winogrande `01e74176c63542e6b0bcb004dcdea22d94fb67b5`, xlangai/spider `0c350918f3f29ec754f1181c65cdce76cd6c133c`. Slice/sample seeds and eval_n/cap read from protocol_v1.yaml, not invented.
- 2026-08-21: `prior_label` and `pool_ref` in task.json set to JSON null — MANUAL lists the keys but gives no values. Not filled in.
- 2026-08-21: Materialized gsm8k: official train 7473, test sample 200 with eval.slice_seed 20260820. Gold self-check on 5 eval rows passed.
- 2026-08-21: Materialized winogrande_xl: pool 40398 downsampled to 8000 with full.sample_seed 20260820; validation sample 200. Gold letters mapped from HF answer field `1`/`2` → `A`/`B`.
- 2026-08-21: HF xlangai/spider train is 7000; MANUAL requires official 8659. Used official Yale zip (`train_spider.json` 7000 + `train_others.json` 1659). Recorded HF revision in task.json as named by §5, questions+DBs taken from the zip.
- 2026-08-21: Spider official zip from yale-lily.github.io GDrive id `1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J`, Drive name `spider_data.zip`, 205800266 bytes (~196MB, under 500MB abort), sha256 `00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b`. MANUAL said ~100MB; actual is larger. Kept in `data_cache/spider/` (gitignored).
- 2026-08-21: Materialized spider train 8659 / eval 200. Gold SQL execution on all 200 eval rows passed. db_path is relative under `data_cache/spider/extract/`.
- 2026-08-21: Packed `tasks_v1.tar.gz` (1654675 bytes, sha256 `2f12baddaf5bf2e6869f427dca8d660d27ae0945a25cc0be3fc1b78862d72380`) + top-level `MANIFEST.sha256`. tar.gz gitignored; MANIFEST tracked.
- 2026-08-21: Phase 2 STOP. Unresolved: prior_label/pool_ref are null; GSM8K prompt is question-only; Spider CREATE TABLE dump is full sqlite_master SQL not a hand-written 摘要.
- 2026-08-21: Operator filled prior_label/pool_ref from literature pool v0.2: gsm8k strong-gain; winogrande weak-or-no-gain; spider strong-gain. Values copied verbatim into task.json.
- 2026-08-21: Operator GSM8K prompt ruling: append one fixed instruction line `Reason step by step, then give the final answer on the last line in the form: #### <number>` to user content for train and eval. Reason: `####` is the dataset convention, not a model habit; without it eval_base extraction collapses to last-number fallback and injects parse noise.
- 2026-08-21: Operator Spider schema ruling: full sqlite_master DDL approved (determinism over hand-written 摘要). Guard: log (do not fail) if a prompt exceeds 4000 tokens, counted with Qwen/Qwen2.5-1.5B-Instruct tokenizer. Pack-time scan: max 2147 tokens (spider-train-3636), over-limit count 0.
- 2026-08-21: Operator pin: Spider consumers must pre-check source.sha256 `00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b` and source.yale_zip_gdrive_id `1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J`. source.train is `train_spider + train_others = 8659`. HF xlangai/spider train=7000 is not the frozen train set.
- 2026-08-21: Packed `tasks_v2.tar.gz` sha256 `794ec0ea78ae6a6a1b526b7682632d378d6bdd439b68e32680ebe00c2c457d48`. `tasks_v1.tar.gz` retained (sha256 `2f12badd…2380`). v1 superseded before use; no run consumed v1.
- 2026-08-21: Phase 3. Training completions are built from frozen `reference` (gsm8k `#### {gold}`; winogrande letter; spider SQL). Original GSM8K CoT is not in the package.
- 2026-08-21: MANUAL has no max_seq_len. Dry-run truncates at 512; non-dry-run at 2048 pending operator. Dry-run also caps gen `max_new_tokens` at 16 and uses grad_accum=1 so the 2 optimizer steps actually fire.
- 2026-08-21: Dry-run model is HF `yujiepan/qwen2-tiny-random` (2.43M, random Qwen2, all LoRA target_modules present), revision `b01b9c82aaf1efb4c26c94b6342d611b397245ff`. CPU float32. Protocol `base_revision` stays `PIN_AT_ENV_SETUP` in protocol_v1.yaml (only-add-never-edit); resolved sha goes to metrics.systems on load.
- 2026-08-21: Storage: LocalStorage in `src/data.py`; S3Storage stub raises, credentials env-only, not configured. Extra `src/storage.py` not added so src stays the four §3 scripts plus `__init__.py`.
- 2026-08-21: GSM8K CPU `--dry-run` S0–S6 green at `runs/gsm8k__pv1__tv2__20260821-0151`. Resume with `--run-dir` skips a sealed run. pass@8 returned 8 distinct samples. Values are not validated (tiny random model).
- 2026-08-21: Non-dry-run refuses to start without CUDA (Mac safety). Gate 0 command is `python scripts/run_task.py --task gsm8k --protocol configs/protocol_v1.yaml`.
- 2026-08-21: Operator Phase 3 harvest. `tasks_v2.tar.gz` superseded before use; file retained (sha256 `794ec0ea…7d48`).
- 2026-08-21: tasks_v3: GSM8K train `reference.solution` is official answer with `<<calc>>` stripped, steps and `#### N` kept. Mean length 247.5 chars. Packer asserts mean > 100. winogrande/spider jsonl unchanged.
- 2026-08-21: Packed `tasks_v3.tar.gz` sha256 `1deaedcb91d3c98a5c02688f0e83b3a3d124b58a8a5bded570ea2bd2b0f36db0`.
- 2026-08-21: `protocol_v1.yaml` superseded before use; file retained. `protocol_v2.yaml` born complete: max_seq_len 4096, per_device_batch 2, grad_accum 8 (effective batch 16, not per-GPU). Other fields match v1. base_revision pinned at birth to HF `Qwen/Qwen2.5-1.5B-Instruct` sha `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` via `model_info` (no weight download on this Mac). Never edit v2.
- 2026-08-21: CPU dry-run with `--protocol configs/protocol_v2.yaml` green at `runs/gsm8k__pv2__tv3__20260821-0204`. Gate 0: `python scripts/run_task.py --task gsm8k --protocol configs/protocol_v2.yaml`.
- 2026-08-21: Operator opened git-push permission. Pushed 8 local commits `ff9b731..a3d726b` to origin/main. Prior intercepts were the agent auto-mode safety layer (classified `git push` as publish), not GitHub/auth.
- 2026-08-21: RunPod A40 bring-up on `forge-or-not` (`e3d5f8e09a46`). Clone `/workspace/Auto-Forge-Evaluator` HEAD `8603380`. venv `/workspace/venv` (PEP 668 blocked system pip). torch 2.11.0+cu128, transformers 5.15.1, peft 0.20.0, CUDA 12.8, driver 570.195.03, gpu NVIDIA A40. Qwen pin `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` OK. Spider zip sha `00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b` OK, extracted to `data_cache/spider/extract/spider_data/database`. Snapshot `runs/env_snapshot.json`. Waiting for operator `go` before Gate 0.
- 2026-08-21: Operator `go`. Gate 0 started in tmux `gate0` on pod. Run dir `runs/gsm8k__pv2__tv3__20260821-1038`. S0 done, revision pin matches, dry_run=false, eval_n=200. S1 eval_base started ~10:38 UTC.

