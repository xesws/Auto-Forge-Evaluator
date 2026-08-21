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

