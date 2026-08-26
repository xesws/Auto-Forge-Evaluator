# Discussion (draft)

Source: `docs/ANALYSIS_RESULTS.md`. No new numbers.

The honest reading is split. If the operational question is *whether* to run full FT (go/no-go), a 10-shot LoRA probe on Qwen2.5-1.5B-Instruct is not a significant classifier. That is the paper’s primary, pre-registered claim, and it is negative. If the question is *how large* the full-FT gain will be, the same probe ranks tasks (Spearman 0.76). Those two sentences should not be collapsed.

The 87% base rate is not a nuisance to hide. On this protocol most tasks have Δ_full > 0, so a classifier that predicts “always go” is already strong in accuracy and useless in AUC. Missing negatives make the gate easy and the ROC noisy. Limitations should say so explicitly, including the apps footnote: introductory APPS reached base 0.0 / pass@8 0.005 before S4 OOM, i.e. a potential hard negative that never received a Δ_full. bird likewise never received a label. Both are closed with the logistics sentence, not as “models cannot learn SQL/code.”

Failure modes that *are* in the sample should be named without turning them into extra endpoints:

- gsm8k/math: format overwrite, not an EOS bug. Negative deltas, labeled on the scatter.
- CNN/IIRC/SWAG/task071: exact-match floor. Sensitivity b drops them; the negative gate remains.
- Long-context OOM: tydiqa and Persent (task419) are in-sample only because of a disclosed 1×16 fallback with the same effective batch as 2×8.

The text-only reverse result blocks a cheap alternative story (“you could have skipped the GPU and used dataset size”). Whatever the probe is doing, it is not reconstructing train_n.

We do not add features, change the go threshold, or reopen bird/apps. Cluster AUCs stay in the appendix as “not estimable,” not as a third main table.
