# Epoch 3: candidate gate replay and review packet

On 2026-07-22, a live `git ls-remote` still resolved
`google-deepmind/superhuman` `main` to
`96fa6c4cc3a9bb7450ee7b6773b659d3a030dace`. GitHub issue #13 remained open,
and repository PR searches for `algebra-036` and `answerbench_v2.csv` each
returned zero results.

The bounded harness experiment `20260722-165537-7895ed` returned zero. It
rejected the malformed baseline, accepted the materialized candidate, verified
all 400 data records as strict-parsed six-field records, verified exact Short
Answer `$Y(x)=A+\frac{B}{x}-x$`, and rejected both a wrong-answer mutation and a
collateral problem-ID edit. The candidate is exactly the pinned baseline plus
one `0x22` byte at zero-based offset 13,618.

The materially separate checker experiment `20260722-165635-489734` also
returned zero and printed both required PASS lines. The checker independently
constructs the allowed byte sequence from the malformed separator, while the
harness derives it from the unique answer token and exercises negative controls.

Candidate SHA-256:
`0c05a0d4af9cbe3e70413b250d6c9cac1bfe4d848f6c196f83ed61ebef9ced16`.
Baseline SHA-256:
`275877a9d988d85278fad3a5f8a41d7f83393a60bf259531ec0a5161e6b21cf9`.

The review patch is `artifacts/answerbench-036-one-byte.patch`. No PR, issue
comment, remote mutation, or publication was made. Human-owner authorization,
CLA readiness, and upstream maintainer review remain external gates.
