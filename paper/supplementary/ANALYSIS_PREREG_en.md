# Analysis pre-registration (English translation)

This is an English rendering of `ANALYSIS_PREREG.md` (Chinese original kept as the source document) plus the revision-period contract `ANALYSIS_PREREG_V2.md`. If the two languages disagree, the Chinese original wins.

**Translation notice.** Prepared 2026-08-27 for the anonymous supplementary archive. Not a new analysis.

## Registered contract (v1)

- Protocol `protocol_v2` (never edit). Label: go iff Δ_full > 0. Zeros are no-go.
- Secondary: Spearman ρ(Δ_pilot, Δ_full) with task-level bootstrap CI. Not a gate.
- Main predictor: LOTO logistic on `metrics.signals` plus the pre-declared format-compliance scalar, `gen_len.full.median`, `pilot_loss.steps_to_0_01` and its missingness indicator.
- Single-feature logistics and a text-only control (train_n, max_new_tokens, len(prompt_style), eval_n). No `prior_label`, no `pool_ref`, no run metrics in the control.
- Task-level LOTO; bootstrap 95% CI on the LOTO pairs (resample tasks, do not nest LOTO inside the bootstrap).
- Honesty clause: AUC is non-significant iff that CI covers 0.5. Publish the negative. After this contract: no new features, no moved go threshold, no dropped negative-Δ tasks, no protocol edit.

## Revision-period contract (v2)

Identity: **revision-period new analysis**. The v1 registered row is still reported. New main number = LOTO on the **pre-decision** vector only (no `gen_len.full.median`, no `full_n`). `gen_len.full.median` is a post-hoc oracle row, not a decision feature. Permutation test N=1000. Semantic MiniLM control. McNemar three-way labels. Cost ratios from journal timestamps. Budget-capture curves. Sensitivity (b) CI is not used as supporting evidence.
