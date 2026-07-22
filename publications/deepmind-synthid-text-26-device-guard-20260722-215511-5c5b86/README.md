# Fix SynthID Text's inverted GPU training guard

> Status: Charlie-approved public research note. This is not peer-reviewed, journal-accepted, or
> independently expert-confirmed unless a later record explicitly says so.

## Contribution

Type: research software correctness

- Pristine addb4a158143c7c6851a1308f78b89fceed59683 accepts cpu and rejects cuda and tpu at the initial train_best_detector guard.
- Patch SHA-256 df1d9a580a0286cbb8e85e06fbb534721cc7c8beaedd1bfb047e1ded6c1caefd makes cpu raise before processing while cuda and tpu reach mocked downstream training.
- The patch applies cleanly to the pristine addb4a1 index and its focused exact-method suite passes 3/3 without accelerator hardware.
- At 2026-07-22T21:48:46Z issue #26 was open, main was addb4a1, and three repository PR searches returned zero results.

## Evidence

- Experiment 20260722-214820-16d426: pristine inverse behavior PASS.
- Experiment 20260722-214820-984369: cuda, tpu, and cpu focused tests all PASS.
- Experiment 20260722-214820-54a4cb: independent exact guard and regression checker PASS.
- Experiment 20260722-214820-01af65: patch hash and pinned-index application PASS.
- artifacts/source-status-20260722T214846Z.json: live status and three novelty searches.

Reproducible source artifacts are bundled under `artifacts/`. Their SHA-256 hashes are in
`MANIFEST.sha256` and `metadata.json`.

Independent checker: tools/check_issue_26_patch.py is a separately written dependency-free AST/evaluation encoding; experiment 20260722-214820-54a4cb returned PASS.

## Scope and limitations

Against live upstream main addb4a1, patch df1d9a58...c1caefd changes `in` to `not in` and adds CPU rejection plus CUDA/TPU acceptance regressions. Run 3 confirmed the pristine inverse bug, passed all three patched cases, passed a separate AST checker, and verified clean index application. No full-package, hardware, training-numerics, CI, or maintainer claim is made.

The error message explicitly declares CPU unsupported, the guard is the first executable statement, pristine behavior is exactly inverse, and independent dynamic and structural checks agree on all guard-equivalence classes.

## Human approval

- Reviewer: Charlie Krug
- Reviewed: 2026-07-22T22:06:56.494657+00:00
- Note: I reviewed the evidence packet and approve this candidate for the next external contribution step.

Approval authorizes release of this research note; it does not substitute for independent review.

## Sources and novelty trail

- https://github.com/google-deepmind/synthid-text/issues/26
- https://github.com/google-deepmind/synthid-text/commit/addb4a158143c7c6851a1308f78b89fceed59683
- https://github.com/google-deepmind/synthid-text/blob/addb4a158143c7c6851a1308f78b89fceed59683/src/synthid_text/detector_bayesian.py#L1031-L1036
- https://github.com/google-deepmind/synthid-text/blob/addb4a158143c7c6851a1308f78b89fceed59683/.github/workflows/ci.yaml

## Methods and disclosure

- Research mode: computational
- Techniques: Python AST extraction, mocked branch regression testing, mutation control against a pinned Git object, independent AST truth-table evaluation, hash-bound patch apply checking, live GitHub API prior-art search
- Tools: GPT-5.6 Sol acted as principal investigator. A prior GPT-5.6 Terra source-discriminator memo was advisory and every relied-on claim was independently rechecked. Deterministic work used Python 3.12.3, stdlib ast/unittest, absl-py 2.3.1, mock 5.2.0, git, GitHub REST API, and the Proof Factory experiment runner. No CAS, solver, proof assistant, accelerator, or full ML training stack was used.; orchestration: gpt-5.6-sol principal with gpt-5.6-terra delegates.

## Reproduce and challenge

Inspect the source, run the recorded experiment commands, compare hashes, and try to falsify the
claim with an independent implementation. Corrections are welcome through the repository issue
tracker. External acceptance or expert review is recorded separately from this release.
