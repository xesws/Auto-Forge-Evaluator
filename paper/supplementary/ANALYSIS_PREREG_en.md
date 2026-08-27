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

## Late declaration R1-9 (found after the v2 contract was written)

The revision code changed one feature **definition** outside the v2 contract. The v1 format-compliance scalar `1 - unparseable/n` silently returns 1.0 for any task whose compliance block carries no `unparseable` key. Exactly two of the 61 tasks are shaped that way: GSM8K (key `hash`), which v1 special-cased, and MATH (key `boxed`), which it missed. `analysis_v2.py::format_compliance_base` adds the matching MATH branch (`boxed/n = 0.55`).

This is a bug fix on the merits, not a per-task choice. It is declared late because it was found late, and because:

1. it is not one of the eight declared v2 items;
2. the only task it changes, MATH, is one of only two substantive negatives in the sample (the other is GSM8K);
3. its effect is **+0.182 AUC** on the pre-decision model (0.663 → 0.844), larger than the effect of removing leakage itself (−0.092: 0.755 → 0.663).

Binding constraints from this declaration onward:

- Any model containing a `format_compliance` term must report both the pre-fix and post-fix value.
- The fix's gain may **not** be attributed to "removing leakage".
- Paper claims prefer rows that are invariant to the fix (the 3-feature model, which has no compliance term).
- Decomposition, bootstrap CIs, permutation tests and a drop-one-negative jackknife live in `ANALYSIS_RESULTS_v2_ADDENDUM` (script `analysis/analysis_v2_addendum.py`).
- Permutation p is reported as `(1 + #{perm >= obs}) / (1 + N)`. The `#/N` form printed in `ANALYSIS_RESULTS_v2.md` is withdrawn.

The honesty clause is unchanged: the registered 12-feature row is AUC 0.755, CI [0.500, 0.929], covers 0.5, published as a negative.
