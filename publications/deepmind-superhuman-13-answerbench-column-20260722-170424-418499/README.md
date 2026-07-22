# Restore the missing short answer in IMO AnswerBench algebra problem 036

> Status: Charlie-approved public research note. This is not peer-reviewed, journal-accepted, or
> independently expert-confirmed unless a later record explicitly says so.

## Contribution

Type: dataset correction

- For candidate SHA-256 0c05a0d4af9cbe3e70413b250d6c9cac1bfe4d848f6c196f83ed61ebef9ced16, Python 3.12.3 csv.reader(strict=True) parses the header and all 400 data records with exactly six fields.
- The unique imo-bench-algebra-036 record has Short Answer exactly $Y(x)=A+\frac{B}{x}-x$.
- The candidate equals pinned baseline SHA-256 275877a9d988d85278fad3a5f8a41d7f83393a60bf259531ec0a5161e6b21cf9 plus one inserted byte 0x22 at zero-based offset 13,618.
- At the run-3 refresh, upstream main remained 96fa6c4cc3a9bb7450ee7b6773b659d3a030dace, issue #13 was open, and both target-specific PR searches returned zero.

## Evidence

- Full harness experiment 20260722-165537-7895ed returned 0.
- Standalone checker experiment 20260722-165635-489734 returned 0.
- git apply --check --reverse artifacts/answerbench-036-one-byte.patch returned 0.
- git ls-remote returned upstream main 96fa6c4cc3a9bb7450ee7b6773b659d3a030dace.

Reproducible source artifacts are bundled under `artifacts/`. Their SHA-256 hashes are in
`MANIFEST.sha256` and `metadata.json`.

Independent checker: tools/check_answerbench_036.py is materially separate from tools/baseline_answerbench_036.py: it constructs the only allowed full byte sequence from a unique malformed separator and checks the complete target Problem/tail, while the harness derives the edit from the unique answer token, reparses independently, and generates mutations.

## Scope and limitations

Run 3 refreshed the official source state, replayed the complete candidate gate and a materially separate checker, and added a checked one-byte patch artifact. The candidate exactly repairs algebra-036 and satisfies the full local verification contract. No external action was taken.

The decisive result is reproducible and independently encoded: both implementations require the same exact target semantics and whole-file one-byte scope, while the harness additionally rejects malformed, wrong-answer, and collateral-edit controls.

## Human approval

- Reviewer: Charlie Krug
- Reviewed: 2026-07-22T17:42:37.502176+00:00
- Note: Charlie reviewed the candidate record and approves release of the exact one-byte AnswerBench CSV correction for upstream submission.

Approval authorizes release of this research note; it does not substitute for independent review.

## Sources and novelty trail

- https://github.com/google-deepmind/superhuman/issues/13
- https://github.com/google-deepmind/superhuman/blob/96fa6c4cc3a9bb7450ee7b6773b659d3a030dace/imobench/answerbench_v2.csv#L150
- https://github.com/google-deepmind/superhuman/blob/96fa6c4cc3a9bb7450ee7b6773b659d3a030dace/CONTRIBUTING.md
- https://github.com/google-deepmind/superhuman/pulls?q=is%3Apr+answerbench_v2

## Methods and disclosure

- Research mode: computational
- Techniques: strict standard-library CSV parsing, exact target-field assertion, full-file byte-diff certification, negative mutation controls, hash-bound experiment recording
- Tools: OpenAI Codex acted as the Sol principal in the campaign's GPT-5.6 role; a GPT-5.6 Terra source-discriminator memo was treated only as advisory and every relied-on claim was independently rechecked. Deterministic evidence used Python 3.12.3 standard-library csv/hash/subprocess code, the supplied experiment recorder, git, curl/GitHub API reads, and git apply --check. No CAS, proof assistant, SAT/SMT solver, or external publishing tool was used.; orchestration: gpt-5.6-sol principal with gpt-5.6-terra delegates.

## Reproduce and challenge

Inspect the source, run the recorded experiment commands, compare hashes, and try to falsify the
claim with an independent implementation. Corrections are welcome through the repository issue
tracker. External acceptance or expert review is recorded separately from this release.

## External record — submitted

- Recorded: 2026-07-22T17:51:15.303442+00:00
- Source: [https://github.com/google-deepmind/superhuman/pull/18](https://github.com/google-deepmind/superhuman/pull/18)
- Note: Draft pull request #18 opened against google-deepmind/superhuman main with the approved one-byte CSV correction.
