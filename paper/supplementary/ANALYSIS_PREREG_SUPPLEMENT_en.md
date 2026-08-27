# Pre-registration supplement (English) — Phase 4, commits S1–S5

English rendering of `docs/ANALYSIS_PREREG_SUPPLEMENT.md`. The Chinese original
is the source document; if the two disagree, the Chinese wins. Prepared
2026-08-27 for the anonymous supplementary archive. Not a new analysis.

This page supplements `ANALYSIS_PREREG` without editing it. Protocol remains
`protocol_v2` (no v3). Honesty clause unchanged: **a non-significant AUC is
published as a negative.**

Commit S1 froze specifications and algorithms only; the 50 SuperNI task ids,
the clone SHA and the run lists were written in Commit S2. **No non-`--dry-run`
production run was permitted before S2 was on `origin/main`.**

## Sample-frame correction

The original page's "n = 46 / 43 remaining" mistook retestable *pool rows* for
tasks. After de-duplication the literature layer is 13 tasks (GSM8K, WinoGrande
and Spider already sealed). This phase: 10 more literature packages plus 50
stratified SuperNI packages. Intended analysis sample n = 63 (3 historical + 60
new); LOTO is 63-fold once sealed. No change to the go threshold, no new main
features, no protocol edit. The 3 sealed runs count as production data and are
not rerun, so 60 new GPU runs.

## Near-duplicate folding

- MATH500 → MATH: only one task, `math` (Hendrycks competition MATH). MATH-500
  is not packed.
- MBPP+ → MBPP: only one task, `mbpp` (official 3 assertions). EvalPlus /
  MBPP+ are not packed.

## Task clusters (cluster robustness during analysis; not new main features)

| cluster | task ids |
|---|---|
| choice | winogrande, arc_easy, arc_challenge, hellaswag, piqa |
| math | gsm8k, math |
| sql | spider, bird |
| code | mbpp, apps |
| reading | drop, tydiqa |
| superni | the 50 from Commit S2; sub-label = SuperNI `Categories[0]` |

Cluster robustness = recompute the main LOTO AUC holding out an entire cluster.
Pre-declared, not mined after seeing results.

## Gates and budget caps

`gate_check.py` runs automatically after S6. Failure does not block the queue.

- unparseable (`parsed is None` or `note.unparseable`) on `eval_base_greedy.jsonl` **< 5%**
- pilot loss must fall: `signals.pilot_loss.end < start`; a missing source fails this item
- `systems` block complete: torch, transformers, cuda, driver, gpu_name, base_revision, seeds, `dry_run=false`
- determinism: reload the **base** (no LoRA) and re-evaluate greedily. Full 200 rows for list item 1 and every tenth task; otherwise 30 sampled rows (seed 20260820). Any per-id `pass` mismatch fails the gate.
- gate failure → `run_dir/STATUS` = `PARTIAL`
- per-task wall clock **3 h**; exceeded → `STATUS` = `over_budget`. APPS / BIRD were the flagged risks.

## `max_new_tokens` (protocol field stays per-task)

| tasks | max_new_tokens |
|---|---|
| arc_easy, arc_challenge, hellaswag, piqa | 16 |
| math | 512 |
| drop, tydiqa | 128 |
| mbpp, apps | 512 |
| bird | 256 |
| every SuperNI task | 128 |

## Code sandbox caps

Subprocess; 10 s; no network; dedicated temporary directory; `ulimit -v`
**2097152** KB (2 GiB).

## SuperNI filter specification v0 (frozen before execution)

1. Clone `https://github.com/allenai/natural-instructions.git` into the
   gitignored `data_cache/natural-instructions/`. The HEAD SHA is recorded in
   Commit S2.
2. Scope: both `Input_language` and `Output_language` lists must contain
   `English`. Either track (train/test) is eligible — this is not an
   instruction-generalisation evaluation; each task stands alone.
3. Size: enough instances for **eval 200 + train ≥ 10**, with disjoint
   train/eval ids. If the English-plus-size survivor set is < 50, **stop and
   report**; do not relax the constraint.
4. Sampling: strata = `Categories[0]`; quotas proportional to the number of
   tasks in each stratum; seed **20260822**; draw 50; at most 3 per
   `Source[0]`. A draw that violates the Source cap is skipped and sampling
   continues inside that stratum; an unfillable stratum returns its quota for
   reallocation. The implementation must match this paragraph:
   `scripts/sample_superni.py`. The 50 drawn task ids are **committed in S2
   before** any production run and before packaging.
5. Packaging: one loader; exact match normalised to `pass`, token-F1 only in
   `note`; `max_new_tokens=128`. The row-sampling seed remains the protocol's
   `20260820`, separate from the task-sampling seed 20260822.

## `prior_label`

The 60 new tasks carry `prior_label = null` (no invented strong-gain / weak
labels). The literature 10 use
`pool_ref = literature-layer Phase 4; folded MATH500→MATH, MBPP+→MBPP`;
SuperNI uses `pool_ref = superni stratified sample seed 20260822`. Control
predictors remain forbidden from using `prior_label` / `pool_ref`.

## APPS difficulty

Introductory only. Competitive problems are not packed (they would sit on a
zero-gain floor for a 1.5B model).

## BIRD download box

The official archive is ~33.4 GB. Time box 1 hour, size box 40 GB. Exceeding
either stops and reports; Mini-Dev is not substituted.

## Not done (frozen by this page)

Starting production before the S2 list exists; adding main-model features;
moving the go threshold; editing the protocol; packing MATH-500 or MBPP+;
filtering TyDiQA languages after seeing scores; promoting cluster robustness to
a primary endpoint.

---

## Commit S2 frozen values (written after sampling)

- clone: `https://github.com/allenai/natural-instructions.git` (depth 1)
- HEAD SHA: `55a365637381ce7f3748fa2eac7aef1a113bbb82`
- English + size survivor set: **890** (≥ 50)
- seed 20260822, n = 50, `Source[0]` ≤ 3; list in `docs/prod_lists/superni_50.json`

## Commit S3 execution revision (single pod, serial; pod B cancelled)

Gates, the 3 h cap, PARTIAL, and the determinism cadence are **unchanged**.

- Run list: literature (no bird) → SuperNI → `bird` at the tail.
- `tasks_v4.tar.gz` = **59 packages** (9 literature + 50 SuperNI); it does not
  wait for bird. v4 is append-only. If bird materialises, it ships as
  `tasks_v5` (bird only).

## Commit S4 wrap-up order (four reruns + pre-declared secondary sensitivities)

Written **before** any rerun GPU started and **before** any AUC was computed.
The protocol file remains `protocol_v2.yaml` (never edited, no v3). Effective
batch remains 16.

1. **bird**: the S0 `KeyError: sha256` was checker lag, not a logistics
   exclusion. `task.json` carries dual SHAs (`train_zip_sha256` /
   `dev_zip_sha256`); the checker is aligned to those fields. `tasks_v5.tar.gz`
   is not rebuilt (bytes unchanged). The failed directory is isolated in place
   under `runs/_isolated/`, never deleted. Mini-Dev is not substituted.
2. **apps 8 h**: the 3 h cap is an ops fence, not a measurement. `apps` alone
   gets `WALL_SEC=28800`. The first apps slot was `STATUS=over_budget` with no
   `metrics.json`, so **the adjustment happened before any apps number
   existed**.
3. **OOM fallback** (only `tydiqa` and `task419_persent_answer_generation`): a
   run-level override of `per_device_batch=1` × `grad_accum=16` (effective
   batch still 16, identical to the protocol's 2 × 8). `protocol_v2.yaml` is
   not edited. STATUS and `metrics.json` record `oom_fallback: true`. Any other
   task carrying that flag fails hard.
4. **arc_easy**: keep the existing PARTIAL numbers, do not rerun. It enters the
   main analysis; sensitivity (a) drops it.

Pre-declared secondary sensitivities, frozen at this point and computed in the
single main analysis run:

- **a.** Drop `arc_easy` (borderline gate sample) and recompute AUC / Spearman / LOTO.
- **b.** Drop metric-floor rows: rows with a `metrics.json` where
  `base.pass1 == 0` and `full.pass1 == 0`. The predicate is frozen; the list
  follows from the seal. An economic no-go can be real, but the mechanism here
  is an exact-match floor and must be reported separately from "the model
  genuinely cannot learn this".
- **c.** Grouped reporting (not a new main model) for the choice cluster, the
  math cluster, and SuperNI same-source clusters.

## Commit S5 campaign close (analysis sealed; bird/apps closed)

Written after `ANALYSIS_RESULTS.md` `--final` numbers landed. This block is
**not** a new analysis; no further AUC may be computed.

- The single citable source is `docs/ANALYSIS_RESULTS.md`.
- The analysis set is **sealed at n = 61**.
- **bird** and **apps** are closed. Neither has a go label (bird has no
  `metrics.json` at all; apps has no Δ_full and no `metrics.json`). The
  exclusion sentence, used once for each, reads exactly:
  `excluded for logistics, before any label existed`
- APPS's S1 base 0.0 / 0.005 goes into limitations only, as a footnote about
  the missing negative class. It is not an analysis row.
