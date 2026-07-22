# Correct the transformer-block LayerNorm parameter count in DeepMind AI Foundations

> Status: Charlie-approved public research note. This is not peer-reviewed, journal-accepted, or
> independently expert-confirmed unless a later record explicitly says so.

## Contribution

Type: academic courseware correction

- At upstream e37bc994, both unmodified transformer-block references produce 460928 instead of 461440 for embedding_dim=256 and mlp_dim=384.
- The run-2 patch changes both references to count two complete LayerNorm components.
- The run-2 patch passes the focused two-copy regression at embedding dimensions 1, 128, and 256.
- The separate checker passes fixed totals 461440 and 198272.

## Evidence

- python3 scripts/audit_upstream_status.py returned 0 with issue state open, main e37bc994, and two zero-result PR searches.
- python3 scripts/replay_current_head.py --expected-commit e37bc99485767ebe68d8ff4db438721daa7ab966 --patch patches/issue-37-layernorm-count-run2.patch --checker checkers/layernorm_count_discriminator.py returned 0.
- The replayed diff SHA-256 equaled the saved patch SHA-256 e1d238c6fc02230734bd8161209b8b5afeb0954d93e66acf6fe74dab8ef94891.
- The repository unittest and independent checker both returned 0.

Reproducible source artifacts are bundled under `artifacts/`. Their SHA-256 hashes are in
`MANIFEST.sha256` and `metadata.json`.

Independent checker: checkers/layernorm_count_discriminator.py independently extracts both references and checks fixed totals 461440 and 198272; experiment 20260722-184123-54410d reports PASS.

## Scope and limitations

Prepared a current-head-validated, style-hardened candidate patch correcting both LayerNorm-count references and adding a focused regression. The issue remained open and no matching PR was found. Nothing was published or submitted.

The unpatched negative control fails both references by exactly 2 * embedding_dim. The final patch applies byte-for-byte to current main and passes both a repository regression and a separate fixed-oracle checker, satisfying the stated verification contract.

## Human approval

- Reviewer: Charlie Krug
- Reviewed: 2026-07-22T18:50:31.485332+00:00
- Note: Charlie reviewed the current-head patch, two-copy regression, independent checker, baseline controls, and novelty searches and approves this candidate for the next external contribution step.

Approval authorizes release of this research note; it does not substitute for independent review.

## Sources and novelty trail

- https://github.com/google-deepmind/ai-foundations/issues/37
- https://github.com/google-deepmind/ai-foundations/commit/e37bc99485767ebe68d8ff4db438721daa7ab966
- https://github.com/google-deepmind/ai-foundations/pulls?q=is%3Apr+37
- https://github.com/google-deepmind/ai-foundations/pulls?q=is%3Apr+parameter_count_layer_norm

## Methods and disclosure

- Research mode: hybrid
- Techniques: exact parameter accounting, Jupyter notebook AST extraction, fixed numeric oracles, compositional regression testing, clean Git patch replay, negative controls, SHA-256 artifact binding
- Tools: GPT-5 Codex acted as Sol principal. The supplied GPT-5.6 Terra source-discriminator memo was advisory only and its status claims were independently rechecked. Python 3.12.3, unittest, ast, json, urllib, Git 2.43.0, SHA-256, curl, and the Proof Factory experiment harness were used. No CAS, solver, proof assistant, external publishing, credential change, system package installation, or host modification was used.; orchestration: gpt-5.6-sol principal with gpt-5.6-terra delegates.

## Reproduce and challenge

Inspect the source, run the recorded experiment commands, compare hashes, and try to falsify the
claim with an independent implementation. Corrections are welcome through the repository issue
tracker. External acceptance or expert review is recorded separately from this release.
