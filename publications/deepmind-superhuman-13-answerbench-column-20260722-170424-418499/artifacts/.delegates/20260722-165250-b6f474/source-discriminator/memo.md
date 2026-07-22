Memo — source discriminator

- Best live route: human-authorized, one-byte upstream PR for issue #13. The issue remains open and `main` still resolves to pinned commit `96fa6c4…`; the issue text reports the missing delimiter before `$Y(x)=A+\frac{B}{x}-x$`. [Issue #13](https://github.com/google-deepmind/superhuman/issues/13) · [main commit](https://github.com/google-deepmind/superhuman/commit/96fa6c4cc3a9bb7450ee7b6773b659d3a030dace)

- Rationale: reported computation confirms the workspace file (`0c05a0d4…`) parses as 400 six-field records and differs from the pinned source (`275877a9…`) only by inserting `0x22` at offset 13,618. No open PR targeting `algebra-036` was found; unrelated AnswerBench PRs #6 and #11 should not be treated as competing repairs.

- Cheapest discriminator: immediately before an authorized PR, run:
  ```bash
  git ls-remote https://github.com/google-deepmind/superhuman.git refs/heads/main
  python3 tools/check_answerbench_036.py imobench/answerbench_v2.csv \
    --reference sources/96fa6c4cc3a9bb7450ee7b6773b659d3a030dace/answerbench_v2.csv
  ```
  Advance only if `main` remains `96fa6c4…` and both checker gates pass.

- Controls already evidenced: malformed baseline rejected; wrong-answer mutation rejected; an unrelated edit passes semantic checks but fails `--reference`; the one-byte repair passes. The exact-diff gate is therefore necessary for contribution scope.

- Failure modes / stop conditions: stop and rebase/reinvestigate if upstream head or target bytes change, issue #13 closes, a target-specific PR appears, the checker fails, or an authorized contributor cannot meet CLA/review requirements. Upstream acceptance requires a PR review and a Google CLA. [Contributing guide](https://github.com/google-deepmind/superhuman/blob/96fa6c4cc3a9bb7450ee7b6773b659d3a030dace/CONTRIBUTING.md)

- Reusable artifact: [check_answerbench_036.py](/root/proof-factory/research/deepmind-superhuman-13-answerbench-column/workspace/tools/check_answerbench_036.py) provides strict six-column parsing, target-field checking, and full-file one-byte equality. The audit is [release-audit-96fa6c4-0c05a0d4.json](/root/proof-factory/research/deepmind-superhuman-13-answerbench-column/workspace/artifacts/release-audit-96fa6c4-0c05a0d4.json).

- Sol should independently verify: the live ref and issue state, exact source hash, checker behavior from a clean checkout, and CLA/PR authorization. Reject a semantic-only validation certificate or any expanded “generic guard” in this patch unless maintainers request it.

No large search is warranted: the previously measured safe reduction leaves one permitted single-byte insertion out of 43,401,728 such edits; external acceptance is the remaining uncertainty.
