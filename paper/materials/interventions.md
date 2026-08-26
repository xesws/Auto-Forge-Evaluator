# Part 2 material: intervention-point checklist

Operator-owned prose. Each item is a human decision or halt, not a new analysis.
Anonymous wording is in `paper/part2.tex`. Do not put usernames, repo names, or hostnames in the PDF.

| # | When (UTC, from ledger) | What happened | Decision | In PDF? |
|---|-------------------------|---------------|----------|---------|
| 1 | 2026-08-22 | Protocol v3 temptation (pilot 10×100 recitation) | Freeze `protocol_v2`; no v3; pilot is the probe | yes, item 1 |
| 2 | 2026-08-22 | 46 pool rows misread as 46 tasks | Literature 13 + SuperNI 50 = 63 intended | yes, item 2 |
| 3 | 2026-08-22 | Second worker cancelled | Single serial queue of 60 | yes, item 3 |
| 4 | 2026-08-22 | BIRD download box vs Mini-Dev | Pack bird later as v5; never Mini-Dev | yes, item 4 |
| 5 | 2026-08-22 | False "cannot SSH" | Tool-layer rejection, not host failure; production started after correction | yes, item 5 (anonymized) |
| 6 | 2026-08-22 / S4 | APPS 3h over_budget, no metrics | 8h ops fence declared before any APPS label | yes, item 6 |
| 7 | 2026-08-24 / S4 | BIRD S0 `KeyError: sha256` | Dual zip-sha checker; isolate failed dir | yes, items 7–8 |
| 8 | S4 wrap-up | TyDiQA / task419 S4 CUDA OOM | OOM fallback 1×16, effective batch 16, yaml untouched | yes, item 9 |
| 9 | 2026-08-25 | Wave-1 bird S2 OOM; apps S4 OOM after 8h S1 0.0/0.005 | Campaign close n=61; logistics exclude before any label | yes, item 10 |

Sources: `docs/ledger.md`, `docs/ANALYSIS_PREREG_SUPPLEMENT.md` S3–S5.
