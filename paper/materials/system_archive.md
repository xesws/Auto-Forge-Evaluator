# Part 2 material: system-number archive

Do not invent GPU-hours. Do not recompute AUC.

## Sealed analysis (citable)

| quantity | value | source |
|---|---|---|
| n | 61 | ANALYSIS_RESULTS.md L24 |
| go / no-go | 53 / 8 | L24 |
| base rate | 53/61 ≈ 86.9% (paper 87%) | L18, L24 |
| main LOTO AUC | 0.755 [0.500, 0.929] covers 0.5 | L15, L36 |
| Spearman | 0.755 [0.595, 0.864] excludes 0 | L16, L48 |
| text-only AUC | 0.309 [0.045, 0.622] | L17, L44 |
| gsm8k Δ_full | −0.230 | L58 |
| tydiqa / task419 Δ_full | +0.530 / +0.505 | L61 |
| bird, apps | excluded for logistics, before any label existed | L27–30 |

## Run logistics (not citable as analysis)

| quantity | value | source |
|---|---|---|
| serial queue | 60/60 drained | REPORT_20260824T0024Z; ledger 2026-08-24 |
| tv4 STATUS=ok | 55 | ledger 2026-08-24 task896 line |
| tv3 leftover | gsm8k, winogrande, spider (in n=61) | GATE_REPORT; AR.md |
| isolated failed dirs | kept, not deleted | S4 wrap-up |
| protocol yaml | never edited after freeze | AR.md header; protocol_v2.yaml |
| full tar sha256 | `71309f7c73eee3f4bc0c9781ef5655d560ae976b5ee00a86110a8aebf4028f7d` | ledger 2026-08-25 |
| gsm8k wall (Gate 0) | ≈ 2.16 h | GATE_REPORT L38 |
| winogrande wall | ≈ 0.51 h | GATE_REPORT L39 |
| spider effective GPU | ≈ 2.22 h | GATE_REPORT L40 |
| **campaign GPU-hours** | **not computed** | do not invent |

## Hardware (anonymous)

Single 48GB-class GPU worker, one serial queue. Do not name the vendor, hostname, or region in the PDF.
