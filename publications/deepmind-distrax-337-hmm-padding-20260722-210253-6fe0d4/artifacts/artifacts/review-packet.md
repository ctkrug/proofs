# Review packet: Distrax issue #337

Prepared 2026-07-22 by the GPT-5.6 Sol principal after independently auditing
the advisory GPT-5.6 Terra source-discriminator memo.

## Claim and source status

At upstream Distrax commit
`6701435c2b0796ec2d6dddf11bae0df615a62017`, `HMM.backward` replaces its
reverse-scan carry with zeros for `t > length`. The issue reporter's example
therefore returns zero beta and posterior values throughout the valid prefix.
The proposed one-line fix preserves `beta_prev` on those suffix steps.

As checked through the GitHub API on 2026-07-22, issue #337 was open, had zero
comments and no events, and a repository-scoped pull-request search for `337`
returned zero matches. Direct sources:

* <https://github.com/google-deepmind/distrax/issues/337>
* <https://github.com/google-deepmind/distrax/blob/6701435c2b0796ec2d6dddf11bae0df615a62017/distrax/_src/utils/hmm.py#L226-L237>
* <https://github.com/google-deepmind/distrax/pulls?q=is%3Apr+337>

## Reviewable change

`patches/0001-preserve-hmm-backward-carry.patch` changes one source line and adds
a 21-line regression. The regression compares padded and sliced-prefix alpha,
beta, posterior, and log-likelihood for valid lengths 1, 3, and 5 under the
repository's Chex variant harness. It deliberately does not assert semantics
for padded output positions.

The patch is byte-for-byte equal to `git diff` from the pinned checkout,
passes `git diff --check`, and passes `git apply --check --reverse` against the
patched checkout. Patch SHA-256:
`f115729ba1da41a10b3266f7621dc5d048797d6d39696820eaa83e48c7b12733`.

## Reproduction and validation

All runs used Python 3.12.3, seed 0, explicit time/memory limits, the dependency
versions in `artifacts/requirements-lock.txt`, and the experiment recorder.

1. Baseline, `.proof-experiments/20260722-203956-645239`: the issue
   discriminator failed as predicted. All 6 valid beta entries were zero;
   the sliced-prefix beta entries were nonzero. Return code 1.
2. Focused patched suite, `.proof-experiments/20260722-204153-3f9ac4`:
   `pytest -q .../hmm_test.py -k forward_backward` reported 45 passed, 15
   skipped, 100 deselected, and 180 passed subtests. The skips were the pmap
   variants on a one-device host. Return code 0.
3. Independent checker, `.proof-experiments/20260722-204731-1095a2`:
   a separately implemented NumPy forward-backward recurrence matched the
   patched JIT-compiled Distrax outputs for two parameterizations and valid
   lengths 1, 3, and full length. Across the six checks, the largest observed
   absolute discrepancy was `2.2203126377462468e-06` for a log-likelihood;
   all declared comparisons passed. Return code 0.
4. Original issue discriminator after patch,
   `.proof-experiments/20260722-204752-5acfc8`: return code 0.

## Adversarial controls and limits

The first two NumPy-checker attempts are preserved as negative results. The
initial three-state full-length control used extreme values `42` and `-42`,
which exposed float32-vs-float64 emission underflow rather than a padding
failure. Replacing them with finite non-neutral `8` and `-6` still exposed the
library's intentional `1e-15` normalization floor. The final independent
oracle applies that same numerical-floor contract while retaining a separate
NumPy recurrence. These corrections were checker fixes; padded-vs-sliced
Distrax comparisons passed in the failed runs.

This packet establishes a locally reproducible candidate patch, not upstream
acceptance. The entire repository test suite was not run; the completed scope
is every forward-backward test and variant available on the single-CPU-device
host. External maintainer review and repository CI remain required.

## Tool disclosure

GPT-5.6 Sol designed and executed the patch, tests, independent oracle, and
review packet. A GPT-5.6 Terra delegate performed earlier bounded source
reconnaissance; Sol rechecked the claims against the official issue, GitHub
API, pinned source, and deterministic runs. Tools used: Git, curl/GitHub API,
Python, NumPy, JAX/JAXLIB, Distrax, Chex, TensorFlow Probability nightly,
pytest, and the computational-researcher experiment recorder. No model output
was treated as independent validation.
