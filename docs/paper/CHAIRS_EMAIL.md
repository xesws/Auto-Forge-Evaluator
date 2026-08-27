# Draft email to AutoMLR chairs (operator sends)

Subject: AutoMLR 2026 — page budget, checklist, and disclosure (submission TBD)

Dear AutoMLR chairs,

We are preparing a double-blind submission and want to confirm three
formatting points against the CFP (automlr.com, “Length and structure”).

1. Page budget. We interpret the CFP as: Part 1 ≤ 4 pages, Part 2 ≤ 4
   pages, Part 3 ≤ 1 page, not reallocatable; “the total limit is nine
   pages, excluding references.” Our PDF uses pages 1–9 for the three
   parts, then Disclosure, then References. The NeurIPS paper checklist
   is appended after References.

2. Checklist. The AutoMLR CFP does not mention the NeurIPS Paper
   Checklist. The official workshop TeX template ships `checklist.tex`.
   Under the stricter reading we \input it after the bibliography. If
   the workshop does not want it, we will drop it on request.

3. Appendix. Reproducibility details (protocol, 61-row table,
   analysis code, eval jsonl) are in a separate supplementary archive
   rather than inside the 9-page body.

4. Disclosure boxes. The two human-attestation checkboxes will be
   ticked only after a human author has line-checked every claim. They
   are unchecked in any draft we circulate before that.

5. Post-registration correction, disclosed. During a CPU-only
   revision we found that our analysis code had changed one feature
   *definition* outside the revision's own written contract: the
   format-compliance scalar `1 - unparseable/n` silently returns 1.0
   for tasks whose compliance block has no `unparseable` key, and we
   had special-cased only one of the two such tasks. Fixing the second
   is correct on the merits, but it moves one cell of the design
   matrix and is worth +0.182 AUC on the affected model — more than
   the leakage removal it was reported alongside. We have (a) filed it
   as a late declaration in the revision contract, (b) published the
   full before/after decomposition, permutation tests and a
   drop-one-negative jackknife in an addendum, and (c) rewritten the
   paper's claim to rest on a model that is invariant to the fix. The
   pre-registered primary endpoint remains negative and is published
   as such. We flag this proactively rather than have a reviewer find
   it; if the chairs would prefer a different treatment, tell us.

Please tell us if (2) should be omitted.

Anonymously,
The authors
