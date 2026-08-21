# docs/ledger.md

append-only. One dated line per decision, incident, or spec deviation.

- 2026-08-21: Phase 1 start. Copied operator file `开发手册v1.md` verbatim to `docs/MANUAL_v1.md` (sha256:153a003fd3da0615439b714404aa8e89eeedd5a8a62491173f0688d082c1c211, 5207 bytes, no trailing newline). `docs/MANUAL_v1.md` is the spec source.
- 2026-08-21: Added `configs/protocol_v1.yaml` with only MANUAL §2 keys/values (block YAML, no extra keys). `max_new_tokens` kept as the literal string `per-task(见 §5)`; per-task ints live in task.json in Phase 2. `base_revision` kept as `PIN_AT_ENV_SETUP` until Phase 3 pin.
