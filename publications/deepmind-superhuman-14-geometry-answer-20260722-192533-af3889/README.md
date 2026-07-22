# Correct the corrupted short answer for IMO AnswerBench geometry problem 004

> Status: Charlie-approved public research note. This is not peer-reviewed, journal-accepted, or
> independently expert-confirmed unless a later record explicitly says so.

## Contribution

Type: dataset correction

- Against upstream commit 96fa6c4cc3a9bb7450ee7b6773b659d3a030dace, the candidate changes exactly imo-bench-geometry-004 column 3 from 45752 to 4, 5.
- The corrected geometry-004 record parses into exactly six fields.
- imo-bench-number_theory-048 and all other records are unchanged.
- The candidate SHA-256 is a56cee7c31412a6d851af03263d305b65baa173f455bd092837c476c5a975cdc.
- The review patch applies cleanly to the pinned upstream commit and produces the same candidate hash.

## Evidence

- python3 checkers/verify_answerbench_geometry_004.py V1.csv BASELINE_V2.csv imobench/answerbench_v2.csv: PASS
- python3 checkers/check_exact_geometry_004_patch_bytes.py BASELINE_V2.csv imobench/answerbench_v2.csv: PASS
- python3 checkers/test_geometry_004_checkers.py V1.csv BASELINE_V2.csv imobench/answerbench_v2.csv: candidate accepted and four adversarial controls rejected
- git apply --check artifacts/answerbench-v2-geometry-004.patch in a clean upstream checkout: PASS
- Clean-checkout application produced a one-file, one-insertion/one-deletion diff and candidate SHA-256 a56cee7c31412a6d851af03263d305b65baa173f455bd092837c476c5a975cdc.

Reproducible source artifacts are bundled under `artifacts/`. Their SHA-256 hashes are in
`MANIFEST.sha256` and `metadata.json`.

Independent checker: checkers/check_exact_geometry_004_patch_bytes.py is a separately written, parser-independent encoding. It requires exact full-file byte equality after one unique context-bound replacement and passed against the pinned baseline.

## Scope and limitations

Corrected imo-bench-geometry-004 from 45752 to the quoted CSV field 4, 5. Pinned v1, the official Sharygin solution, a complete semantic comparison, a separate byte checker, four negative controls, and a clean-upstream patch replay all agree. number_theory-048 and every unrelated byte remain unchanged.

The official solution explicitly gives n=4 or n=5. The candidate has exactly one semantic-cell delta and is byte-for-byte the pinned baseline after that unique replacement. Independent encodings and adversarial controls make the result eligible for isolated human review.

## Human approval

- Reviewer: Charlie Krug
- Reviewed: 2026-07-22T20:31:45.793933+00:00
- Note: I reviewed the evidence packet and approve this candidate for the next external contribution step.

Approval authorizes release of this research note; it does not substitute for independent review.

## Sources and novelty trail

- https://github.com/google-deepmind/superhuman/issues/14
- https://geometry.ru/olimp/2009/finseng.pdf
- https://github.com/google-deepmind/superhuman/commit/96fa6c4cc3a9bb7450ee7b6773b659d3a030dace
- https://raw.githubusercontent.com/google-deepmind/superhuman/96fa6c4cc3a9bb7450ee7b6773b659d3a030dace/imobench/answerbench.csv
- https://raw.githubusercontent.com/google-deepmind/superhuman/96fa6c4cc3a9bb7450ee7b6773b659d3a030dace/imobench/answerbench_v2.csv

## Methods and disclosure

- Research mode: computational
- Techniques: standards-compliant CSV parsing, complete semantic-cell comparison, context-bound byte replacement, hash-pinned source verification, negative-control testing, clean-checkout patch replay
- Tools: GPT-5.6 Sol served as principal investigator. A GPT-5.6 Terra delegate supplied bounded source reconnaissance; Sol independently rechecked every relied-on claim against the live issue, pinned Git object, and official olympiad solution. Python 3.12.3 standard-library CSV parsing, Git 2.43.0, deterministic Python checkers, curl, and the Proof Factory experiment recorder were used. No CAS, solver, proof assistant, lab compute, system-package installation, external publication, or repository-remote change was used.; orchestration: gpt-5.6-sol principal with gpt-5.6-terra delegates.

## Reproduce and challenge

Inspect the source, run the recorded experiment commands, compare hashes, and try to falsify the
claim with an independent implementation. Corrections are welcome through the repository issue
tracker. External acceptance or expert review is recorded separately from this release.
