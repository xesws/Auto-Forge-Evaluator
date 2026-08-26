# Operator 必改清单（Part 2 / 3 / Disclosure）

Drafted 2026-08-26T18:40Z from `paper/part2.tex`, `part3.tex`, `main.tex` Disclosure.
CFP: Part 2 is expected to be **human-written**. This file is the navigation for that rewrite.
Boxes in Disclosure are **unchecked** until you actually line-check.

Legend: **F** = factual (ledger/report); **V** = view/rhetoric; **C** = confirm you agree; **R** = likely rewrite.

## Part 2

| § | First words | F / V | What you should do |
|---|---|---|---|
| 2.1 p1 | We ran the study with two coupled pieces | F | **C** naming: “LLM coding agent” + harness. Add the agent model name in the chairs-only disclosure if you want it in the PDF. |
| 2.1 p2 | The experimental model … omitted here | F+policy | **C** omit-for-blind vs name Grok/other in the PDF. |
| 2.1 p3 | The harness is a single-task state machine S0–S6 | F | Keep unless S0–S6 wording is wrong. |
| 2.1 p4 | Figure 3 is the loop | F | Caption is factual. **R** if you want a less schematic figure. |
| 2.2 p1 | Compute was one 48GB-class GPU | F | **C** “48GB-class” vs saying A40. Host/vendor omitted on purpose. |
| 2.2 p2 | Local tools were git … | F | Fine. |
| 2.2 p3 | Execution-based verifiers … | F | Fine. |
| 2.2 p4 | GSM8K accepts `#### 1,000` … bare article “a” | F (tests) | Fine. |
| 2.2 p5 | The factory pins source revisions … SuperNI 890 / seed | F | Fine. |
| 2.2 p6 | Code execution is a subprocess 10s / 2 GiB | F | Fine. |
| 2.3 p1 | The loop was not an open-ended search | F | **V-lite** “not NAS”. **C**. |
| 2.3 p2 | Protocol freeze came first … recitation is the probe | F | Operator freeze 2026-08-22. Keep. |
| 2.3 p3 | Sample-frame correction … Mini-Dev never used | F | **C** Mini-Dev named as a negative fact. |
| 2.3 p4 | serial queue … ~39 h wall | F | Timestamps 09:34Z→00:22Z. **C** the ~39 h arithmetic. |
| 2.3 p5 | 55 STATUS=ok … smoke three count as production | F | Fine. |
| 2.3 p6 | 3 h wall … incr every tenth | F | Fine. |
| 2.3 p7 | four-task rerun wave … no AUC until script | F | Fine. |
| 2.4 intro | Human interventions were discrete | F | Fine. |
| 2.4 SSH | The agent reported … unreachable | F | **C** anonymized wording. **R** if you want this incident out. |
| 2.4 slip | Gate 1 started before Gate 0 | F | **V** “The STOP did what a comment in chat cannot”. **R** that sentence if too cute. |
| 2.4 EOS | Format overwrite, not EOS | F | Diagnosis from GATE five-eye, not a ledger line titled “EOS”. **C** that we may frame EOS as the ruled-out alternative. |
| 2.4 BIRD | KeyError sha256 … did not invent a SQL label | F | Last sentence is a rule, not a new fact. Keep. |
| 2.4 APPS | 3 h then 8 h … still no Δ_full | F | Fine. |
| 2.4 OOM | 1×16 only two ids | F | Fine. |
| 2.4 close | excluded for logistics… | F | Exact S5 sentence. Do not paraphrase if you want byte-match. |
| 2.4 owns | What the operator always owns | F list + **C** | Confirm the list is complete (kill pod, boxes, Mini-Dev, go threshold…). |
| 2.5 p1–p2 | Gates … five-eye all green | F | Fine. |
| 2.5 p3 | MANIFEST … full tar sha 71309f7c… | F | Truncated sha in PDF. Fine. |
| 2.5 p4 | analysis contract … boxes unchecked | F | **C** this admits Part 2 is agent-drafted. Required for honesty; **R** after you curate (then tick boxes and delete this sentence). |
| 2.6 p1 | qualifying result is a 61-row table | F | Repeats Part 1. **R** shorter if you want page 8 for something else. |
| 2.6 p2 | Small-model post-training spends real GPU | **V** | “usable for budget allocation”. **R** or keep as the only process-claim. |
| 2.6 p3 | The process claim … enough to publish | **V** | Paragraph-end view. **C**. |
| 2.7 p1 | append-only versioned | F | Fine. |
| 2.7 p2 | harvest two-tier | F | Fine. |
| 2.7 p3 | A sealed run directory is meant to be readable | F | Fine. |
| 2.8 p1 | one base, one recipe, 8 no-go | F | Fine. |
| 2.8 p2 | GPU-hours were not summed | F | Do not add a campaign total. Smoke 1.5 kWh is TDP×wall, not a meter. **C**. |
| 2.8 p3 | misreport and Gate 1-before-0 stay in the log | **V-lite** | “cleaner than it was”. **R** if you do not want that tone. |

## Part 3 (1 page — do not lengthen)

| ¶ | First words | F / V | What you should do |
|---|---|---|---|
| 1 | Guardrails earned their keep when they failed closed | F then **V** | Last sentence “A rail that invents a number…” is rhetoric. **R** or keep. |
| 2 | Pre-registration is what made the negative… publishable | F | Fine. **C** “sixty GPU slots” = the 60-queue, not 61 labelled rows. |
| 3 | STOP points were the human–agent interface | F then **V** | “chatbot apology” is rhetoric. **R**. |
| 4 | Diagnosis was split on purpose | F then **V** | Last sentence “We would like the field to copy…” is the only field-adaptation ask. **C** / **R**. |

## Disclosure (template slots)

| Slot | Draft status | What you should do |
|---|---|---|
| Agent(s)/model(s) used | Filled: harness + LLM agent drafted Parts 1–3; model omitted for blind | **C** name the coding model to chairs. **R** if you want the model in the PDF. |
| □ curated and verified every claim | **Unchecked** | Tick **only after** you line-check Part 2/3 and the number table. |
| □ full accountability | **Unchecked** | Tick with the first box. This draft cannot tick them for you. |
| Sentence “this text has not yet been line-checked” | Honest for this commit | **Delete** once you have ticked the boxes. |

## Page / CFP notes (not prose)

- Parts occupy **4 + 4 + 1** (PDF pp. 1–9). Appendix + refs are pp. 10–11. CFP total is “nine pages excluding references.” If chairs count the reproducibility/disclosure appendix against the 9, cut that appendix or fold it into 2.7.
- CFP: “We expect Part 2 to be human-written.” After you rewrite, say so in 2.5 p4.
- Do not add campaign GPU-hours.
- Do not name the repo, host, or username (S7 grep is currently clean).
