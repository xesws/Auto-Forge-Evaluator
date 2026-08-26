# Reproducibility appendix material

Not an analysis. Points at sealed artifacts. Do not treat this file as citable metrics.

## Protocol

- File: `configs/protocol_v2.yaml` (never edited after freeze).
- Model: Qwen2.5-1.5B-Instruct revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`.
- LoRA r=16 α=32; max_seq_len 4096; train 2×8 (effective batch 16); pilot 10×100; full cap 8000 / 3 epochs; eval 200 greedy.
- Packages: `tasks_v4.tar.gz` (59) sha in `MANIFEST.sha256`; `tasks_v5.tar.gz` bird-only `cf25de9ca1c889e75e33a5ce484e0374c4881da422401dad7b01ffce5b338983`.
- Analysis pre-reg: `docs/ANALYSIS_PREREG.md` + supplement S1–S5.

## Disclosed run-level exceptions (not yaml edits)

**OOM fallback** (S4; only `tydiqa` and `task419_persent_answer_generation`):
- `per_device_batch=1`, `grad_accum=16` (effective batch still 16).
- Flag `oom_fallback: true` in STATUS and `metrics.json`.
- Both sealed STATUS=ok (Wave-1 tv5 dirs).

**Apps 8h wall** (S4): `WALL_SEC=28800` for `apps` only. First apps slot had been 3h `over_budget` with no `metrics.json`. The 8h rerun finished S1 then died S4 OOM — still no Δ_full.

## PARTIAL / over_budget ledger (all causes)

| task | status | cause | in n=61? |
|---|---|---|---|
| apps (tv4) | over_budget | 3h wall, S1 only | no |
| apps (tv5 rerun) | PARTIAL | S4 CUDA OOM step 22/495 after S1 0.0/0.005 | no (no Δ_full) |
| tydiqa (tv4) | PARTIAL | S4 CUDA OOM | no (replaced by tv5 ok) |
| tydiqa (tv5) | ok | oom_fallback | yes |
| arc_easy | PARTIAL | unparseable 10/200=5%; metrics exist | **yes** |
| task419 (tv4) | PARTIAL | S4 CUDA OOM step 11 | no (replaced by tv5 ok) |
| task419 (tv5) | ok | oom_fallback | yes |
| bird (tv4) | PARTIAL | S0 KeyError sha256 (checker vs dual zip fields) | no |
| bird (tv5) | PARTIAL | S2 CUDA OOM; S1 0.085/0.23; no metrics.json | no |

Closed exclusion (S5), both tasks:

> excluded for logistics, before any label existed

Failed dirs kept under `runs/_isolated/` in the full tar (`forge_runs_full.tar.gz` sha `71309f7c…`).

## How to redraw figures

```
python scripts/plot_citable_figures.py
```

Reads `docs/figures/plot_data.json` (n=61, 53 go). Does not modify `ANALYSIS_RESULTS.md`. `--refresh-data` rebuilds the JSON from the sealed results file plus LOTO scores; do not use it to invent new tables.
