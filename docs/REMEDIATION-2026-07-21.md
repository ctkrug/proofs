# Proof Factory remediation ledger — 2026-07-21

This is the durable execution ledger for the 2026-07-21 full-remediation directive. It records
observed state, changes, tests, deployment evidence, and any premise corrections. Evidence and
contribution gates remain fail-closed throughout.

## Phase 0 — synchronized baseline

Recorded at 2026-07-21 20:12 UTC from the canonical local repositories and the live content droplet.

- Engine: local and live revision `ed8d03eb834522aba13914d6fc6e64de233150e6`; the live tree has
  only expected runtime projections modified (`data/attempts.jsonl`, `data/problems.json`, and the
  R(5,5) research-state projection).
- R(5,5) repository: synchronized through `43fdcc4`; the stored census receipts through segment 33
  arrived from the live publisher during baseline pull.
- Wiki: revision `fe8e932fafe65c6b1c6e66df1e337b022e8d9030`; the pre-existing untracked
  `projects/charlie-consulting 2.md` remains untouched.
- Live census `lab-ramsey-r55-872a7c3ee855`: `completed_awaiting_review` at 49/656 hosts,
  segment 49, last reviewed segment 33. Exact-stream correctness remains true; observed last-segment
  throughput was 0.05964 host/s and artifact growth was 819 bytes. The review interval is 16 segments.
- Research attempts: 34 total, 17 for R(5,5): 13 progress, 3 no-progress, 1 error. R(5,5) usage sums
  to 107,615,168 principal input tokens (104,683,008 cached), 672,291 principal output tokens
  (167,126 reasoning), 23,385,059 delegate input tokens (21,013,760 cached), and 207,742 delegate
  output tokens (91,894 reasoning). These are telemetry totals, not a claim that cached input carried
  equivalent marginal cost.
- Live scheduling: hard, lab, and publish timers active; factory work, easy, intake, scout, and
  strategy-lab timers inactive under the temporary R(5,5)-priority allocation. Hard review polls
  every 15 minutes; lab polls every 5 minutes; publish runs every 2 hours.
- Host: 2 vCPU; 3.82 GiB RAM with 3.13 GiB available; 6.00 GiB swap with 5.86 GiB free. Root disk is
  48 GiB with 18 GiB available. The 25 GiB cache volume at
  `/mnt/volume_sfo3_1784567780659` is 100% full.
- Mathematical status: the monitored pilot remains infrastructure evidence, not an R(5,5) result;
  the maintained bound remains `43 <= R(5,5) <= 46`. The next decisive discriminator remains the
  complete 656-host census followed by bounded residual SAT and independent validation.

Phase result: baseline established. One stale premise was corrected: the census was not at the
previously documented 43/656; it had durably advanced to 49/656 and was awaiting its next review.
