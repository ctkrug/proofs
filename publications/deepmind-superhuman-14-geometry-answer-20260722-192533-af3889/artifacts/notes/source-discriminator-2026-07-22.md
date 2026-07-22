# Source-discriminator reconnaissance (2026-07-22)

## Sourced facts

* GitHub issue [google-deepmind/superhuman#14](https://github.com/google-deepmind/superhuman/issues/14) is open (created and last updated 2026-04-23; zero comments), titled "[BUG] Answerbench_v2--Answer check：geometry-004, number_theory-048".  Its body reports geometry-004 as `45752` and says the original is `4 and 5`; it also questions the direction of the number-theory-048 inequality.
* At upstream `main` commit `96fa6c4cc3a9bb7450ee7b6773b659d3a030dace` (2026-06-04), `imobench/answerbench_v2.csv` SHA-256 is `275877a9d988d85278fad3a5f8a41d7f83393a60bf259531ec0a5161e6b21cf9`.  RFC-style parsing gives a six-column header and 400 records.  Geometry-004 has six fields and Short Answer `45752`; number_theory-048 has ` $\\left\\{ (a,b):ab\\leq e^{3}\\right\\}$`.  One pre-existing unrelated record (`imo-bench-algebra-036`) parses to five fields, so a safe narrow correction must preserve that anomaly rather than silently normalize the file.
* Deprecated `imobench/answerbench.csv` (SHA-256 `37aeca686ce677f93580821cfe16a0c0e45872479a502df43272e099da37d8fa`) parses geometry-004 as `4, 5` and number_theory-048 as a different, old answer.  The v2 file was introduced in commit `ea72dda6e4aa` and already had `45752`; the later v2-only change `955558ad67ef` did not alter it.
* Upstream `CONTRIBUTING.md` requires a CLA and GitHub pull-request review for every submission.  No project-local test suite is advertised for this dataset.

## Proposed discriminator

Use `checkers/verify_answerbench_geometry_004.py` with the current raw v2 file as baseline and an edited candidate.  It CSV-parses both files, validates the literal six-column header, preserves each baseline record's field count, IDs, and record count, asserts the geometry edit is exactly `45752` to `4, 5`, asserts number_theory-048 remains exactly as v2, and rejects every other semantic cell change.  Cost is under one second and linear in 400 rows.

Canonical replay:

```bash
git fetch https://github.com/google-deepmind/superhuman.git 96fa6c4cc3a9bb7450ee7b6773b659d3a030dace
git show FETCH_HEAD:imobench/answerbench_v2.csv > baseline.csv
python checkers/verify_answerbench_geometry_004.py baseline.csv candidate.csv
```

The final external acceptance path is a narrowly scoped upstream PR, passing this independent check, with an explicit note that the issue's number-theory suggestion was intentionally not adopted; it remains subject to Google CLA and maintainer review.

## Limits and stop condition

This is provenance plus file-integrity evidence, not an independent geometry proof.  Stop after the checker passes and a diff confirms the one cell: further search/proof work is dominated by upstream PR review.  Reject any candidate that normalizes formatting, alters quoted problem text, or changes number_theory-048.  The principal should independently re-fetch the pinned source/hash immediately before opening a PR, then decide whether the v1 provenance plus issue report is sufficient or whether to attach a short independent derivation of the geometry answer.
