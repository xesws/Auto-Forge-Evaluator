# Results (draft)

Source: `docs/ANALYSIS_RESULTS.md` (sealed). n=61 tasks with a go/no-go label. go ⇔ Δ_full > 0. bird and apps are out of the sample (`excluded for logistics, before any label existed`).

## Setup (one paragraph)

Each task is one row. The primary predictor is a leave-one-task-out logistic regression on the frozen `metrics.signals` vector (plus the pre-declared format-compliance scalar). Interval estimates are task-level bootstrap 95% CIs on the LOTO pairs. The secondary endpoint is Spearman ρ between Δ_pilot and Δ_full. A text-only logistic (train size, max_new_tokens, prompt-style length, eval_n) is the no-pilot control. Figures: `docs/figures/calibration_scatter.png`, `roc_bootstrap.png`, `base_rate.png`.

## Finding 1 — Negative primary gate

The main LOTO model has AUC 0.755 with CI [0.500, 0.929]. The interval covers 0.5. Under the pre-registered honesty clause this is a **negative result**: a 10-example LoRA probe does **not** significantly classify whether full fine-tuning will raise greedy pass@1.

The same verdict holds in the two pre-declared sensitivities, reported here next to the main row rather than as afterthoughts:

| sample | n | AUC | 95% CI | covers 0.5 |
|---|---:|---:|---|---|
| main | 61 | 0.755 | [0.500, 0.929] | yes |
| a. drop arc_easy | 60 | 0.748 | [0.487, 0.920] | yes |
| b. drop EM-floor rows | 57 | 0.778 | [0.411, 0.985] | yes |

Single-feature logistics are weaker or only borderline (Δ_pilot 0.663 [0.480, 0.825]; generation length 0.818 [0.505, 0.986]).

## Finding 2 — Significant ranking

Spearman ρ(Δ_pilot, Δ_full) = 0.755, CI [0.595, 0.864], excluding 0. The calibration scatter (`docs/figures/calibration_scatter.png`) is upward-sloping: the probe ranks *how much* full FT helps even though it cannot pass the binary gate. gsm8k and math sit in the third quadrant (both deltas negative) and are labeled.

Sensitivities a/b leave Spearman intact (0.756 and 0.771, CIs still exclude 0).

## Finding 3 — Description features run the wrong way

The text-only control, which never sees a probe or a run metric, has AUC 0.309 [0.045, 0.622] — below chance. Task size and prompt length do not explain go. The main model’s (non-significant) AUC is therefore not an artifact of static task descriptors.

## Finding 4 — 87% base rate

53 of 61 labeled tasks are go (86.9%). The bar in `docs/figures/base_rate.png` is the whole point: Δ_full > 0 is an easy event on this 1.5B protocol. The ROC (`docs/figures/roc_bootstrap.png`) has a wide bootstrap band that includes the diagonal, matching Finding 1. With eight negatives, AUC is under-powered for a hard gate; ranking still has signal (Finding 2).

## What is not in n=61

tydiqa and task419 entered after an OOM fallback that keeps effective batch 16 (Δ_full +0.530 and +0.505). bird and apps produced **no label** and stay out. Cluster-wise AUCs are not reported as estimates: the choice cluster is all-go; math has n=2.
