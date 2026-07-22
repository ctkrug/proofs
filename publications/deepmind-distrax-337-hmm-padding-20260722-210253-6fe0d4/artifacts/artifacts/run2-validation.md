# Run 2 validation record: Distrax issue #337

Recorded 2026-07-22 by the GPT-5.6 Sol principal. The injected GPT-5.6
Terra source-discriminator memo was treated as an advisory lead; every claim
used below was rechecked against the pinned checkout, GitHub, or a deterministic
artifact in this workspace.

## Current source and scope

- GitHub's issue API reported issue #337 open with zero comments at the time of
  this run: <https://github.com/google-deepmind/distrax/issues/337>.
- `git ls-remote` reported upstream `main` at
  `6701435c2b0796ec2d6dddf11bae0df615a62017`.
- GitHub's repository-scoped pull-request search for `337` returned zero
  results, and the issue events API returned no events.
- The checked scope is valid-prefix equality only. No claim is made about the
  values returned at padded positions.

## Patch identity

`patches/0001-preserve-hmm-backward-carry.patch` has SHA-256
`f115729ba1da41a10b3266f7621dc5d048797d6d39696820eaa83e48c7b12733`.
It changes the `t > length` branch in `HMM.backward` from
`jnp.zeros_like(beta_prev)` to `beta_prev` and adds a regression for valid
lengths 1, 3, and 5. On this run, `git diff --check`, byte comparison with the
pinned checkout's complete diff, and `git apply --check --reverse` all passed.

## Decisive evidence

1. Baseline experiment `.proof-experiments/20260722-203956-645239` failed at
   the first beta assertion as predeclared: all six padded valid-prefix beta
   entries were zero, while sliced-prefix entries were nonzero. The experiment
   record and stderr hashes are respectively
   `641e1d8bce9b32f3fef74a2e696709775bb4ab646339cc8c2070acafef352bfa`
   and `3e04d110032a3190ca5579ec265d0acd5a21918984f72d0ddf2c090163682277`.
2. The earlier complete focused selection
   `.proof-experiments/20260722-204153-3f9ac4` passed 45 tests and 180
   subtests, with 15 multi-device pmap variants skipped on the one-device host.
   Its record and stdout hashes are
   `f25b6e6b927cd690dd85def0328e60ab45745e518931d8ed86534a55ab4b4d43`
   and `773689c2af5917b926aad2a31a2a3e219f37028999274a591c68ca2640f7a803`.
3. Repaired-environment issue replay
   `.proof-experiments/20260722-205707-35db0b` exited 0. Its experiment record
   hash is
   `8e9d44f7ba0335a3447197c07b19519c2ab8152a72cad3fd09b5e71558d0ea54`.
4. Repaired-environment independent NumPy/JIT replay
   `.proof-experiments/20260722-205707-d2f290` passed all six combinations of
   two HMMs and lengths 1, 3, and 5. It compared alpha, beta, posterior, and
   log-likelihood against both sliced Distrax inference and a separately
   implemented NumPy recurrence. The maximum reported absolute discrepancy was
   `2.2203126377462468e-06` for a log-likelihood, within the declared tolerance.
   The record and stdout hashes are
   `2c4e18f28b82c90fa75a3b1f9e31eb38e9f8f7e80a83f86af231a9ac23859fcf`
   and `082a69209a5a41ba3c37c90e757f7ad9ef4fa07911bb31bde49292779ace3dc3`.
5. Repaired-environment regression-only replay
   `.proof-experiments/20260722-205741-bec817` passed 9 tests, with 3
   unavailable pmap variants skipped. The record and stdout hashes are
   `f713d5cfdb33e4cbb09aeeb525a65ea45f4968ecec6bb3e7155ba7a3e2a98cca`
   and `2bb8af8386efb9aab251e52b43140f6a1b7a3a348446ecee8ba9deb4e85b7d70`.

The repaired environment is outside the workspace at
`/tmp/distrax-337-evidence-venv-20260722T2054Z`; therefore its internal symlinks
are not workspace evidence. Dependencies are pinned in
`artifacts/requirements-lock.txt`. The previous evidence receipt's only errors
were four symlink paths under the removed workspace-local `.venv`; the decisive
artifact hashes themselves matched.

## Conclusion and limits

This is a review-ready local candidate for issue #337. It is not an accepted
upstream fix. Full repository CI, the skipped multi-device variants, human
review, and maintainer acceptance remain external validation steps. The next
session should not repeat mechanism discovery unless upstream changes, CI
fails, or a reviewer supplies a counterexample; its first action should be
isolated human review of the patch and this validation record.

