# S2–S7 delivery (one STOP)

- Time (UTC): 2026-08-26T18:15Z
- Parent HEAD at start: `d1d8523` `[paper-1]`
- Protocol: protocol_v2 / pv2 (yaml never edited)
- Citable numbers: `docs/ANALYSIS_RESULTS.md` only (no new AUC)
- PDFs: `paper/main.pdf` (9 pp), `paper/supp.pdf` (2 pp)

## Page budget 4 / 4 / 1

`\clearpage` between parts (CFP pages are not reallocatable).

| Block | Pages in `main.pdf` | Budget | Status |
|---|---|---|---|
| Part 1 Autonomous research result | 1–4 (4) | 4 | on budget |
| Part 1 Setup | p.1 + p.2 through §1.1 | ~1.3 | ~1p target |
| Part 1 Results | p.2 §1.2 + p.3 figures/tables | ~1.5 | ~1.5p target |
| Part 1 Discussion + related-lite | p.3 §1.3 + p.4 | ~1.2 | ~1.5p target; content complete |
| Part 2 System Design | 5–6 (2) | 4 | under; **prose not written** |
| Part 3 Broader Impact | 7 (1) | 1 | on budget; **prose not written** |
| Appendix + References | 8–9 (2) | unspecified | see uncertainty |

Part 2/3 contain only `\texttt{[OPERATOR PROSE HERE]}` plus material lists/figure. That is the CFP line: no human narrative was drafted.

## Engine / template ledger

| Item | Official zip | This tree | Ruling |
|---|---|---|---|
| `\workshoptitle` | `Workshop for Autonomous ML Research ` (short, trailing space) | `Workshop for Autonomous Machine Learning Research` (frozen in `[paper-1]`) | both acceptable |
| Build | Overleaf latexmk/pdflatex | **tectonic 0.16.9** (`latexmk`/`pdflatex` absent on this Mac) | both acceptable |
| Style | `neurips_2026.sty` from zip | byte-used; `dblblindworkshop` | match |
| Template zip | operator drop | `docs/paper/NeurIPS_Workshop_Template.zip` added to git | `[paper-7]` |

## S7 mechanical checks

| Check | Result |
|---|---|
| Anonymous grep (`tangyiq`, `xesws`, `Auto-Forge-Evaluator`, `forge-or-not`, `RunPod`, `194.68`, `github.com/xesws`) on `paper/` tex/md/bib + both PDFs | **zero hits** |
| bib × arXiv API `export.arxiv.org` 2026-08-26 | 18/18 used-or-kept IDs resolve; **1709.07822 skipped** (unrelated planar-graph paper); **1809.08887 Spider now resolves** (empty XML in a prior turn) |
| Figure/table cites | Fig.1 base-rate, Fig.2 scatter, Table 1 AUC, Table 2 literature, Fig.3 architecture — all `\label`+`\ref` |
| ROC figure | not in main (by plan) |
| Supplementary 61-row table | 61 rows, 53 go / 8 no-go |
| Protocol + pre-reg packed | `paper/supplementary/protocol_v2.yaml`, `ANALYSIS_PREREG.md`, `ANALYSIS_PREREG_SUPPLEMENT.md` |
| Undefined/overfull in final `main.log`/`supp.log` | none |

## Number provenance (every Part 1 quantity)

Abstract wording is frozen from `[paper-1]`; body uses AR.md display rounding. Do not “fix” the abstract.

| Quantity | Paper location | Source |
|---|---|---|
| n=61 | abstract, Setup, table | AR.md L22–24 |
| 53 go / 8 no-go | abstract, Setup, F1, Discussion | AR.md L24 |
| 87% / 86.9% / 53/61 | abstract 87%; body 86.9% and 87% | AR.md L18, L24 |
| Spearman 0.755 [0.595, 0.864] | F2; abstract CI rounded [0.60, 0.86] | AR.md L16, L48 |
| Spearman a 0.756 [0.594, 0.873] | F2 | AR.md L49 |
| Spearman b 0.771 [0.608, 0.878] | F2 | AR.md L50 |
| LOTO AUC 0.755 [0.500, 0.929] covers 0.5 | F3, Table 1; abstract CI [0.50, 0.93] | AR.md L15, L36 |
| a n=60 AUC 0.748 [0.487, 0.920] | F3, Table 1 | AR.md L37 |
| b n=57 AUC 0.778 [0.411, 0.985] | F3, Table 1 | AR.md L38 |
| single-feature Δ_pilot 0.663 [0.480, 0.825] | F3 | AR.md L39 |
| gen_len.full.median 0.818 [0.505, 0.986] | F3 | AR.md L43 |
| text-only 0.309 [0.045, 0.622] | F4, Table 1; abstract 0.31 | AR.md L17, L44 |
| gsm8k Δ_full −0.230 | F2/Discussion; abstract −0.23 | AR.md L58 |
| tydiqa / task419 Δ_full +0.530 / +0.505 | Setup, archive | AR.md L61 |
| ARC-Easy PARTIAL in-sample | Setup | AR.md L26 |
| bird/apps logistics exclude | Setup, Discussion | AR.md L27–30 |
| EM-floor ids (task071/1553/236/455) | Discussion | AR.md L52 |
| cluster AUC not estimable; math n=2 | Discussion | AR.md L54 |
| go ⇔ Δ_full > 0 | Setup | AR.md L24; ANALYSIS_PREREG.md L8–9 |
| LoRA r16 α32, seq 4096, 2×8=16, pilot 10×100, cap 8000 ep3, eval 200 greedy | Setup | protocol_v2.yaml L1–44 (not AR.md) |
| SuperNI seed 20260822, n=50, Source cap 3 | Setup | ANALYSIS_PREREG_SUPPLEMENT.md L67–108 |
| Literature table bases/Δs | Table 2 | GATE_REPORT L11–13; REPORT_20260824T0024Z L56–63, L120–122; REPORT_20260825T0851Z L16–18; JSON companion `delta_*` |
| APPS base 0.0 / pass@8 0.005 | Discussion footnote | AR.md L30 (not a Δ_full) |
| winogrande Δ_full +0.190 | Discussion | GATE_REPORT L12; REPORT_20260824T0024Z L121 |
| math Δ_pilot −0.155, Δ_full −0.160 | Discussion | REPORT_20260824T0024Z L56 |

## Uncertainty list

1. Abstract freeze rounding differs from AR.md (0.31 vs 0.309; −0.23 vs −0.230; CIs [0.50, 0.93] / [0.60, 0.86]). Body keeps AR.md. Do not edit the abstract without operator.
2. “11 literature-layer tasks” is 13 intended minus bird/apps, not an AR.md integer.
3. SuperNI filter/seed/SHA live in the pre-reg supplement, not AR.md.
4. Protocol hyperparameters live in `protocol_v2.yaml`, not AR.md.
5. Table 2 cell values are report display-rounding; sealed companion is `ANALYSIS_RESULTS.json` `delta_*`. No new analysis.
6. APPS 0.0 / 0.005 is a limitations footnote, not an analysis row.
7. Campaign GPU-hours were **not** computed; Part 2 archive says so.
8. Whether appendix + references count against 4+4+1 is not stated in the sty. They sit after Part 3 on pages 8–9.
9. Part 2/3 have no operator prose. A desk reject for empty human sections is possible until those slots are filled.
10. `\workshoptitle` expanded name vs zip short name: ledgered, not changed.
11. Build is tectonic, not latexmk: ledgered.
12. arXiv 1809.08887 (Spider) resolved this turn after a prior empty API; it is in `refs.bib`.
13. arXiv 1709.07822 is **not** cited (wrong paper).
14. Unused verified bib keys: `simplerlzoo`, `smollm2`, `shadowft` (in `refs.bib`, not `\cite`d).
15. Sty prints “Affiliation / Address / email” under Anonymous Author(s); inherited from `[paper-1]`.
16. Supplementary PDF typesets the 61-row table; protocol yaml and pre-reg markdown are **files in the pack**, not listings in `supp.pdf`.
17. Figure “13.1% (8)” is drawn by `plot_citable_figures.py` from 8/61; prose does not restate 13.1%.
18. Page 3 is Results floats then Discussion start (order preserved via `[H]` + `\FloatBarrier`).
19. Part 2 material mentions “Mini-Dev never used” (negative fact, not a dataset in the sample).
20. Disclosure checkboxes are unchecked; operator must tick after human curation.

## What was not done

- No Part 2/3 narrative.
- No new AUC, no bird/apps rescue, no Mini-Dev, no protocol edit, no pod kill.
- Git push is batch (operator approval), not per-section live review.
