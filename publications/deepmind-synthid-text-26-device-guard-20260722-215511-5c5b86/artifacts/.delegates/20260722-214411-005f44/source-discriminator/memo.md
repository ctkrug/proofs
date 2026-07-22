Memo — source discriminator

- Exact source/status: issue [#26](https://github.com/google-deepmind/synthid-text/issues/26) is open (checked 2026-07-22). Upstream `main` remains [`addb4a1`](https://github.com/google-deepmind/synthid-text/commit/addb4a158143c7c6851a1308f78b89fceed59683); its pinned detector blob is `955424b…` (SHA-256 `8f917d…361`) and uses the inverted `in ("cuda", "tpu")` guard. Three independent GitHub PR searches for `train_best_detector`, `detector_bayesian`, and `torch_device.type` returned zero results.

- Best live route (score 88): apply/review the existing minimal patch, then obtain upstream PR CI and maintainer disposition. The local correctness uncertainty for the stated initial guard is exhausted; external acceptance is not.

- Cheapest executable discriminator: replay:
  1. pristine exact-method behavior (CPU accepted, CUDA/TPU rejected);
  2. patched structural allowlist check;
  3. focused mocked method tests for `cpu`, `cuda`, `tpu`;
  4. `git apply --check --cached` against `addb4a1`.
  
  This turn: 1, 2, and 4 passed; after repairing the missing two test-only dependencies in an external temporary environment, all 3 focused tests passed. No accelerator hardware was used or needed for this branch contract.

- Controls/reduction: source-declared supported values are two singleton classes (`cuda`, `tpu`); every other `torch_device.type` value is equivalent under the sole membership predicate, represented by `cpu`. This reduces an unbounded token domain to three exact branch cases, with no numerical-training claim.

- Reusable artifact: [patch](</root/proof-factory/research/deepmind-synthid-text-26-device-guard/workspace/patches/synthid-text-issue-26.patch>) SHA-256 `df1d9a58…c1caefd`, plus [structural checker](</root/proof-factory/research/deepmind-synthid-text-26-device-guard/workspace/tools/check_bayesian_device_guard.py>) and [focused runner](</root/proof-factory/research/deepmind-synthid-text-26-device-guard/workspace/tools/run_focused_device_guard_tests.py>).

- Outside acceptance path: the project requires reviewed GitHub pull requests, and its [CI workflow](https://github.com/google-deepmind/synthid-text/blob/main/.github/workflows/ci.yaml) installs `.[test]` and runs `pytest -v` on Python 3.9–3.11. A human-authorized fork/PR is therefore the first result that would materially advance acceptance.

- Failure/switch conditions: stop local implementation work if upstream moves the method/contract, CI finds package-level failure, or maintainers supersede/reject the patch. Reopen technical work only then; full ML integration has low marginal value now (challenger score 30.36).

Sol should independently verify the live ref, clean application, and that the submitted test is discovered by native `pytest`; reject any claim that mocked branch coverage validates accelerator training numerics or substitutes for upstream CI.
