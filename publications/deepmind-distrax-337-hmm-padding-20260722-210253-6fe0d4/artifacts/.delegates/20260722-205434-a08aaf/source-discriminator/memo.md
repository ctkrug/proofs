## Source-discriminator memo

**Best live route:** upstream-ready one-line carry preservation plus a committed padded-prefix regression.

**Sourced status (observed 2026-07-22):** issue [#337](https://github.com/google-deepmind/distrax/issues/337) is open, has no linked branches/PRs on its issue page, and upstream `main` is `6701435c2b0796ec2d6dddf11bae0df615a62017` (`git ls-remote`). The current raw source still uses `jnp.zeros_like(beta_prev)` for `t > length` in [`hmm.py`](https://github.com/google-deepmind/distrax/blob/6701435c2b0796ec2d6dddf11bae0df615a62017/distrax/_src/utils/hmm.py#L226-L237). GitHub’s API was rate-limited; public git, raw-source, and issue-HTML retrieval independently confirmed the relevant status.

**Rationale:** reverse scanning encounters padded `t=5,4` before valid `t=3,2` for a five-element sequence with `L=3`; replacing carry with zero makes zeros propagate into the valid prefix. Preserving `beta_prev` freezes the backward state through padding and restores the normal terminal-ones carry at `t=L`.

**Cheapest executable discriminator:** reuse [hmm_padding_discriminator.py](/root/proof-factory/research/deepmind-distrax-337-hmm-padding/workspace/artifacts/hmm_padding_discriminator.py). Against a clean checkout:

```sh
PYTHONPATH=/path/to/distrax python artifacts/hmm_padding_discriminator.py
```

It uses the issue’s two-state HMM, `obs=[.05,2.9,.1,99.,99.]`, `L=3`, and requires valid-prefix beta/posterior plus log-likelihood agreement with `obs[:3]` within `1e-6`. The non-neutral suffix prevents a vacuous pass. The earlier recorded baseline fails at beta; applying [0001-preserve-hmm-backward-carry.patch](/root/proof-factory/research/deepmind-distrax-337-hmm-padding/workspace/patches/0001-preserve-hmm-backward-carry.patch) is the direct A/B control.

For acceptance, retain the patch’s stronger repository regression: compare alpha, beta, posterior, and log-likelihood for `L=1,3,5`, using the existing Chex eager/JIT variants.

**Controls and failure modes:**

- `L=T` must remain unchanged; `L=1` detects an off-by-one (`t >= length`) error.
- Do not assert padded-position outputs; the issue only specifies the valid prefix.
- If likelihood fails, investigate forward/length indexing; if beta passes but posterior fails, inspect normalization/shape alignment; if eager passes but JIT fails, inspect traced scalar `length` and equal-shaped `jnp.where` branches.
- Prior run’s NumPy oracle had to match Distrax’s normalization floor; avoid treating cross-dtype underflow as padding evidence.

**Search-efficiency:** no large search is warranted. The fixed two-state, five-step witness reduces an unbounded HMM parameter space to four reverse-scan transitions, two of which are padded. Parameterized `L=1,3,5` is the smallest safe extension covering boundary, interior, and unpadded cases.

**Outside acceptance path:** an authorized fork PR linked to #337, maintainer review, upstream CI/full suite, and preferably multi-device pmap validation. Local focused results are useful evidence only.

**Stop condition:** stop implementation work after the clean-checkout A/B discriminator, committed regression, and focused suite pass; remaining uncertainty is external review/CI, not mechanism discovery.

**What Sol should reject or independently verify:** reject any claim based only on likelihood equality, padded-output equality, or the dirty local checkout. Independently replay the artifact on pristine `6701435c`, verify the patch applies cleanly, and confirm the committed test checks alpha as well as beta/posterior/log-likelihood.

Current uncertainty: external acceptance and skipped multi-device variants. Active-route score: direct patch/regression 0.90 usefulness per unit effort; upstream CI/maintainer review 0.75 but requires authority; multi-device validation 0.25. No new computation was needed this pass; source status is the net-new verification.
