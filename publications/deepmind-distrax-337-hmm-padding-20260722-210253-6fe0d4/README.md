# Preserve valid HMM marginals for padded sequences in Distrax

> Status: Charlie-approved public research note. This is not peer-reviewed, journal-accepted, or
> independently expert-confirmed unless a later record explicitly says so.

## Contribution

Type: research software correctness

- At upstream commit 6701435c2b0796ec2d6dddf11bae0df615a62017, the issue witness returns zero beta values for all six valid state-time entries.
- With the one-line carry patch, padded and sliced forward_backward results agree within declared tolerances for valid alpha, beta, posterior, and log-likelihood at L=1, 3, and 5 in two fixed HMM parameterizations.
- The complete focused forward-backward selection passed 45 tests and 180 subtests, with 15 multi-device pmap variants skipped on the one-device host.
- The patch is byte-identical to the pinned checkout diff, passes git diff --check, and is reverse-applicable.
- This is a local candidate for human review, not an accepted upstream fix.

## Evidence

- Baseline experiment 20260722-203956-645239 returned 1 at the beta equality assertion with all six padded valid-prefix beta entries zero.
- Focused suite 20260722-204153-3f9ac4 returned 0: 45 passed, 15 skipped, 180 subtests passed.
- Patched issue replay 20260722-205707-35db0b returned 0.
- Independent replay 20260722-205707-d2f290 returned 0 with six machine-readable profile results.
- Regression-only replay 20260722-205741-bec817 returned 0: 9 passed and 3 unavailable pmap variants skipped.
- sha256sum -c artifacts/run2-evidence.sha256 validated every listed artifact.

Reproducible source artifacts are bundled under `artifacts/`. Their SHA-256 hashes are in
`MANIFEST.sha256` and `metadata.json`.

Independent checker: artifacts/check_hmm_padding_numpy.py separately implements normalized forward and backward recurrences in NumPy, then compares them with JIT-compiled padded and sliced Distrax inference for two HMMs and lengths 1, 3, and 5.

## Scope and limitations

A review-ready patch changes padded HMM backward steps from a zero carry to beta_prev and adds a regression comparing padded and sliced alpha, beta, posterior, and log-likelihood for L=1, 3, and 5. The pristine baseline failed as predicted; the patched issue reproduction, focused suite, repository regression, and independent NumPy/JIT checker passed. Evidence was repackaged without workspace virtualenv symlinks and bound by a checksum manifest.

The source line has a direct causal role: reverse scanning encounters padded steps before valid steps, so substituting zero destroys the carry. A failing-before/passing-after witness isolates that mechanism, while the separate recurrence and existing focused tests guard against accidental agreement or regression.

## Human approval

- Reviewer: Charlie Krug
- Reviewed: 2026-07-22T21:09:32.223084+00:00
- Note: I reviewed the evidence packet and approve this candidate for the next external contribution step.

Approval authorizes release of this research note; it does not substitute for independent review.

## Sources and novelty trail

- https://github.com/google-deepmind/distrax/issues/337
- https://github.com/google-deepmind/distrax/blob/6701435c2b0796ec2d6dddf11bae0df615a62017/distrax/_src/utils/hmm.py#L226-L237
- https://github.com/google-deepmind/distrax/blob/6701435c2b0796ec2d6dddf11bae0df615a62017/distrax/_src/utils/hmm_test.py
- https://github.com/google-deepmind/distrax/pulls?q=is%3Apr+337

## Methods and disclosure

- Research mode: hybrid
- Techniques: failing-before/passing-after regression, JAX reverse-scan carry analysis, Chex eager/JIT/device variants, independent NumPy forward-backward recurrence, boundary-length controls, hash-recorded deterministic experiments, content-addressed evidence manifest
- Tools: GPT-5.6 Sol acted as principal, auditing rather than voting with the advisory GPT-5.6 Terra source-discriminator delegate memo. Deterministic tools used were Git, curl and the GitHub API, Python 3.12.3, NumPy 2.5.1, JAX/JAXLIB 0.11.0, Distrax at 6701435c, Chex 0.1.92, TensorFlow Probability nightly 0.26.0.dev20260722, pytest 9.1.1, sha256sum, and the computational-researcher experiment recorder. No model output was treated as independent validation.; orchestration: gpt-5.6-sol principal with gpt-5.6-terra delegates.

## Reproduce and challenge

Inspect the source, run the recorded experiment commands, compare hashes, and try to falsify the
claim with an independent implementation. Corrections are welcome through the repository issue
tracker. External acceptance or expert review is recorded separately from this release.
