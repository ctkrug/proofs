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

## Phase 1 — operational integrity

- Publication lag was a batching gap, not a failed deploy: the two-hour publisher was healthy, but a
  completed attempt could remain local until the next `:50` run. A systemd path trigger now queues the
  isolated publisher whenever `data/attempts.jsonl` changes; the timer remains as a fallback. The
  watchdog also records the newest-attempt page state and becomes degraded if a durable attempt lacks
  a rendered page for more than four hours.
- Segment 49 was a genuine safety boundary, but its reviewer failed before a model call because ten
  accumulated events made the canonical brief exceed 18,000 characters. Emergency compaction now
  retains bounded events, live job progress, the active route, and the decisive roadmap fields while
  producing valid JSON within the ceiling.
- Review cadence can now be retuned only at a correctness-passing, decision-value-active
  `completed_awaiting_review` boundary. Every change updates the spec identity and appends an audit
  record. The measured R(5,5) census will move from 16 to 256 segments per periodic review after the
  segment-49 boundary, while per-segment mismatch, coverage, throughput, growth, and checkpoint gates
  remain unchanged.
- The three resolved corpus-authentication leads (`lead-3637dfa055`, `lead-1c7eaa0320`, and
  `lead-151bcf320d`) are closed with the frozen corpus hash and control receipts. The distinct unknown-
  basin lead remains open. DOSSIER section 13 now names the full 656-host census and bounded residual
  SAT as the next discriminators.
- The scoped local duplicate premise was low: 76 Finder/iCloud artifacts existed (36 generated-site
  entries and 40 empty certificate directories), totaling about 80 KB. All had canonical counterparts;
  they were moved to macOS Trash and are recoverable. No canonical certificate or unrelated duplicate
  was touched. Keep the active workspace outside iCloud synchronization (or explicitly exclude it) to
  prevent Finder conflict copies from recurring.

Phase acceptance: 60 local tests must pass; the deployed reviewer must serialize an under-18,000-
character brief, apply the audited 256-segment cadence only at segment 49, complete a model-backed
continue/redirect decision without losing its event, and expose the new path trigger and freshness
record on the live host.

Post-deployment result: all 60 production tests passed, the live brief was 14,447 characters, and the
path unit published attempt `ramsey-r55-20260721-204644-7cb261` within seconds. Its fresh cold replay
accepted every saved host through 49, then correctly chose `redirect`: the old job spec had not hashed
both imported enumerators, had not recorded historical worktree dirtiness, and did not enforce the
intended aggregate 30-second host gate. The valid prefix is preserved as calibration evidence; the job
is `stopped_with_reason` and must restart under the fail-closed wrapper in Phase 5. This is a safety-gate
success and a correction to the expected continuation premise, not a mathematical setback or result.

## Phase 2 — cheap engine-efficiency fixes

- A malformed principal result now receives at most one 180-second, low-effort serialization-repair
  call on the same Sol model. The original outcome, prior-art classification, and field-progress status
  must all be present, valid, and byte-for-byte unchanged; otherwise the epoch remains an error. The
  attempt records whether repair was attempted/used, its usage, and any repair error.
- Delegate admission is now event-driven. A routine segment event uses zero delegates, a lab-completion
  review uses only the experiment verifier, and source/route/external/evidence-change events retain the
  challenger-plus-verifier pair. The admitting kinds and selected roles are persisted in every attempt.
  On the last R(5,5) review, avoiding the unnecessary prior-art challenger would have avoided about
  1.12M input tokens (1.03M cached) and 6,478 output tokens.
- The canonical briefing packet is built once per epoch and serialized from that immutable snapshot at
  the 18k delegate and 24k principal caps. Compaction retries no longer repeat its disk-heavy build.
- Zero-reference checks preceded removal of four superseded module-level `compact_for_prompt` helpers,
  `brain.context_for_problem`, and two unused agent context/hash helpers. The canonical briefing remains
  the only prompt compactor; the research brain still builds the dashboard graph.
- The invariant principal prefix now places the computational-research skill, static contribution and
  orchestration contracts, and the full output schema before epoch-specific task, memo, and brief data.
  Two unlike problem prompts share a measured 15,526-character prefix.

Phase acceptance: 62 local tests pass, including repair success, unrepairable fail-closed behavior,
protected-field upgrade rejection, delegate admission, once-per-epoch briefing construction, emergency
compaction, and constant-prefix ordering. Production must pass the same suite and a non-model dry-run
must show the expected role counts and bounded prompt/brief sizes.

Post-deployment result: all 62 production tests passed. The live non-model dry-run selected 0/1/2
delegates for segment/lab-completion/new-evidence events respectively; the delegate and principal briefs
were 13,823 and 21,393 characters, the schema began at character 7,018, and task-specific data began at
15,762. The public endpoint returned HTTP 200.

## Phase 3 — contribution-first portfolio reallocation

- The standing `PROOF_HARD_PRIORITY` code and service override are removed. R(5,5) keeps checkpointed
  low-priority lab CPU and evidence-gated reviews on the six-daily baseline; neither clock polls nor a
  stale/missing usage snapshot manufacture an extra model call.
- The discovery lane, sourced intake, and daily scout return to the deployed timer set. The active
  campaign remains `scout-bdf77f43574b`, the Erdős #530 Lean formalization, with its 25-pass minimum;
  scheduler incumbency means newly queued intake/scout rows cannot preempt it. Intake remains fixed at
  12 active frontier problems.
- Scout completion is now internally limited to one call per rolling 24 hours in addition to its daily
  timer. Repeated/manual starts return the durable next-eligible time without invoking a model.
- The usage governor declares discovery before hard in simultaneous-admissibility ties and defers a new
  hard start while discovery is already running. It never interrupts an already running lane. Provider
  hard limits, spend controls, stale-cache fallback, and the one-shot operator mechanism are unchanged.
- The capacity plan now documents contribution-first allocation and the faster objective upstream path
  for #530. Project Factory production and Proof Factory strategy-lab remain paused; backups, watchdogs,
  lab, runtime sync, and publication remain active.

Phase acceptance: 64 local tests pass. Production must show easy, intake, scout, hard, lab, watchdog,
runtime-sync, and publish timers enabled; strategy-lab remains disabled; the hard unit contains no
priority override; hard next-run cadence is four hours; and the active easy campaign remains Erdős #530.

## Phase 4 — Lean capacity and reproducible bootstrap

- The 25 GiB research volume contained 15 GiB of immutable Alpha evidence and 9.4 GiB of rebuildable
  Proof Factory state: one pinned 2.5 GiB Lean 4.27 toolchain and a single 6.9 GiB Formal Conjectures /
  Mathlib checkout. There was no stale pinned-volume toolchain to delete. The toolchain was copied with
  metadata, independently checksum-compared with `rsync -narc`, then relocated to the root disk. Only
  after the comparison returned no differences was the exact old volume directory removed. The volume
  rose from 0 bytes to 2.1 GiB free while root retained 16 GiB free. The Alpha tape was not touched.
- A diagnostic invocation omitted `ELAN_HOME` and therefore hydrated an unrelated Lean 4.32 toolchain
  under `/root/.elan`. Its new timestamp and exact 2.8 GiB path were verified, then that directory alone
  was removed; it never became a research input. The existing global stable installation remains.
- The bootstrap now pins the Formal Conjectures commit and manifest SHA-256, never performs an implicit
  `lake update`, refuses tracked input drift, verifies the final `FormalConjecturesUtil.olean`, and checks
  immutable inputs again after the build. Its atomic lock now tracks ownership explicitly and fails after
  the bounded wait instead of mistaking another process's lock directory for acquisition. Easy and hard
  services receive the project-scoped cache and `ELAN_HOME` explicitly.
- The first canonical #530 lab retry exposed a resource-unit mismatch rather than a source error:
  `memory_mb=1100` was enforced as virtual address space, and Lean failed while mapping its own
  `PatternVar.olean` at only 321 MiB resident usage. A measured 4 GiB retry advanced to the candidate
  but exhausted address space while mapping Mathlib at 890 MiB resident usage; an 8 GiB retry reached
  about 1.1 GiB resident, hit the 900 MiB high watermark, and moved roughly 240 MiB to swap before the
  same mapped-file failure. The lab now permits a 16 GiB virtual envelope while systemd retains a
  bounded physical envelope, reallocated to a 3.4 GiB high watermark and 3.6 GiB hard cap after direct
  `/proc` inspection showed a 2.2 GiB peak dominated by read-only mapped OLean pages, with only about
  44 MiB anonymous resident memory. One CPU, admission reserves, timeouts, offline isolation, task
  limits, and append-only failed records remain.
- A second, partial 771 MiB Mathlib package tree inside the #530 workspace had the same manifest,
  Mathlib commit, and Lean toolchain as the canonical cache. It is an unpinned rebuildable duplicate;
  after the canonical support build completes it is replaced by a read-only link to the pinned packages,
  leaving the workspace's own build outputs isolated and evidence-scannable.
- Charlie expanded the mounted research volume from 25 to 50 GiB during the monitored target run.
  Live `df` and `lsblk` confirmed the ext4 filesystem itself is 50 GiB and has 26 GiB free; this is
  durable capacity, not merely a larger unexpanded block device. No volume-expansion task remains.
- The first real post-repair discovery epoch honestly recorded `no_progress`: it preserved the
  original warning-fatal build and identified eight missing AMS metadata attributes, applied only
  those annotations, and reran the 512-case semantic regression successfully. It then queued the
  repaired target as a bounded lab job instead of claiming an unobserved build. Its evidence receipt
  still failed closed because the model cited `lab-archive/**`, a mutable projection. The principal
  prompt now explicitly routes lab claims to immutable `records/labs/**` records and content-addressed
  `lab-runs/**` outputs; the failed receipt remains unchanged in the ledger.
- The repaired target lab then completed in 886.5 seconds with exit 0, empty stderr, all 8,038 Lake
  jobs successful, byte-identical candidate copies at SHA-256 `208af82a...71c9`, and a nonempty
  `530.olean` at SHA-256 `5401908c...3201`. The independent post-run inspection reproduced those
  hashes and confirmed the immutable stdout/stderr digests. Peak child RSS was 2,711,332 KiB; the
  lab cgroup peaked at 3,435,134,976 bytes with about 409 MiB swap and zero high/max/OOM events.
  The durable lifecycle state is `completed_awaiting_review`, so this is a successful target build,
  not yet a validated contribution or an upstream-ready claim.
- The measured run also settles the resource question for this target: more RAM is not required.
  The standing profile is pinned-cache retention, target-only builds, one Lean thread, OLean reuse,
  quick edit checks followed by one final warning-fatal evidence run, and no overlap with heavy
  Ramsey/SAT lab work. Narrower imports are only a future benchmark candidate because they change the
  verification surface; they are not an assumed optimization.

Phase acceptance: the full local suite passes 67 tests. Production must retain at least 1 GiB on both
filesystems, produce the pinned support OLean from a clean/hash-matching checkout, pass a warning-fatal
#530 target build with durable lab records, and complete one real discovery epoch whose evidence receipt
is valid. The superseded hand-written #530 queue spec correctly failed closed as an unknown job after the
new durable lab-state requirement; it is not reused or rewritten.

## Phase 5 — R(5,5) decisive supplied-corpus boundary (active monitored continuation)

- Full v2 preserved 254 canonical hosts with exact bitset/NetworkX stream agreement, then correctly
  stopped at segment 255 when `source_record_255` exceeded the predeclared 30-second aggregate host
  gate. The segment used about 54 MiB child memory; the service's earlier peak was about 105 MiB with
  no service swap. Root retained 16 GiB and the research volume 26 GiB, so this was an algorithmic
  timing gate, not a CPU, memory, disk, swap, systemd, or restart failure.
- All 254 manifest rows, gzip packets, artifact hashes, checkpoint rows, and sequential indices were
  independently rechecked. The stopped v2 checkpoint, progress, and manifest hashes remain
  `12dd99da...d2332`, `ec8f949e...71629`, and `50946975...fff95`; the timer polled the stopped job and
  did not silently resume it.
- A new hash-locked cap-60 wrapper, exact prefix-copy auditor, mixed 30/60 final validator, and
  residual-SAT producer/cold auditor were implemented with 25 focused positive/adversarial tests. The
  original job was never continued or rewritten.
- The isolated one-host calibration `lab-ramsey-r55-99d6e467cd79` copied the frozen prefix to a new
  path. Host 254 finished in 21.617 seconds (3.516 bitset + 18.101 NetworkX), below the predeclared
  45-second continuation threshold, with exact stream agreement and no change to the stopped v2 hashes.
- The calibration exposed a lifecycle accounting defect: a newly submitted resumed job measured its
  first delta from zero instead of from the imported progress record. New jobs now bind an engine-
  generated progress baseline into the immutable spec and measure first-segment throughput/artifact
  growth from it. Mutable checkpoint/progress paths are opt-in exact argv paths with starting hashes,
  per-segment before/after chains, reboot recovery receipts, and explicit immutable coverage for all
  other file arguments. The engine passes 166 local tests plus 17 subtests; production passes 141
  engine tests, all 25 R55 tests, configuration validation, and `doctor`.
- New job `lab-ramsey-r55-868014a68d6e` imported the verified 255-host prefix. Its lifecycle pilot
  advanced exactly one host at 0.0454 hosts/second with exact agreement and 4.5 KiB measured growth.
  The durable operator review continued the remaining 400 one-host segments under 120-second/1,000 MiB
  per-segment limits, a 60-second host cap, a 0.015-host/second threshold, and a 64 MiB growth gate. It
  is monitored and checkpointed; no same-family or residual-SAT work can consume a partial manifest.

## Phase 6 — easier-hard successor selection (prepared in parallel; execution gated)

- The successor criterion now prefers the smallest meaningful finite uncertainty with two decisive,
  independently checkable outcomes over the most prestigious frontier. Six exact covering targets were
  verified against their maintained parameter pages and current-improvements feed; `R(3,10)` and the
  five-dimensional kissing number were retained only as harder negative calibration points.
- Exact covering number `C(12,6,4)` replaces cage `n(4,9)` as the recommendation. The maintained live
  bracket is `40 <= C(12,6,4) <= 41`; there are 924 candidate blocks and 495 coverage constraints. At a
  hypothetical size 40, every point has degree exactly 20 and the 66 pairs share only six excess
  incidences above multiplicity nine. A 40-block witness or a complete independently checked exclusion
  of 40 therefore resolves the same exact target.
- The lead's honest pre-pilot estimate is a 45–70% judgment range with roughly 60% as the planning
  midpoint. Its factor table separates status/duplication, technical tractability, independent
  verification, and external usefulness; the number must be replaced after alignment and pilot evidence.
- The only authorized first computation is a 1–4 core-hour, dual-encoding pilot after Phase 5 closes:
  direct set-cover SAT/PB with exact degree and pair constraints, plus a materially separate link-first
  canonical augmentation. Positive output needs a tiny non-importing checker; negative output needs an
  unsymmetrized semantic bridge, checked cube/orbit coverage, and LRAT or equivalent proof evidence.
- `docs/PHASE6-SUCCESSOR-CANDIDATES-DRAFT.md` contains the full sourced baseline, rankings, resource
  envelope, acceptance channels, and redirect conditions. No successor search has started. The Charlie
  decision task remains deliberately unqueued until the current R(5,5) census and residual-SAT gate are
  complete, as required by the directive.
- Automated dispatch now fails closed on a distinct `research_authorization` object. It requires
  Charlie's identity, timestamp, exact scope, a predecessor machine-state predicate, and the SHA-256 of
  the independently validated completion receipt. Missing, malformed, incomplete, or hash-mismatched
  authorization excludes the target from scheduling. `human_approved` remains reserved for result/
  publication approval and is not reused.

The successor gate has now run. Direct depth-7 cubing closed only 10/128 sampled leaves (7.8125%) and
was stopped; the link-first route found four exact link orbits and excluded all four residual extensions.
Primary, secondary, and one tertiary canonical partition now carry 189 replay-validated external proofs
with 47 canonical frontier nodes still open. This raises the judgment range for a field-usable 90-day
contribution to 70–85% and exact resolution to 45–65%; neither is a calibrated probability. The campaign
is active, but no exact value is claimed, and a global negative result still needs complete frontier
coverage plus a second independently validated cardinality translation.

A subsequent coordinated hard-tail pass added exact fourth-level stabilizer partitions and a schema-2
incremental-assumptions harness. Independent review accepted their semantics after provenance, aggregate,
root-context, mutation, and receipt hardening. The fourth-layer run sampled only biased child zero and is
strictly a smoke test; all ten results were UNKNOWN. Glucose4 incremental reuse also closed 0/10 exact
parent leaves and its interruption caps were best-effort, so its receipts are explicitly ineligible for
the 40% route gate. Neither method scales unchanged. The reusable-contribution range remains 70–85%, while
the exact-resolution judgment narrows to 40–60% pending a materially different propagation or encoding
discriminator.

The reusable design guidelines now encode this ease-first policy and permit parallel source review,
adversarial audit, independent checker construction, documentation, and packet tooling while serializing
shared ledgers, deployments, final assembly, and CPU/cache-conflicting computation.

## Phase 7 — outreach preparation (drafted; all sending remains Charlie-gated)

- `docs/R55-OUTREACH-DRAFTS-2026-07-21.md` contains short, non-claiming drafts for Thibault Gauthier,
  John Mackey/CMU, and BigCompute. The first two addresses were source-checked; BigCompute retains only
  its confirmed public maintainer channel because no reliable email was found.
- The R55 repo now has an allowlist-only deterministic packet builder and three-packet specification.
  It rejects symlinks, untracked inputs, path traversal, dirty/spec drift, and missing replay hooks;
  emits a SHA-256 manifest and explicit nonclaims; and rechecks a detached clean clone. Eight packet
  tests pass. The final packet remains intentionally absent until the census and residual discriminator
  reach their independently validated terminal scope.
- No email, repository submission, social post, or public result claim was sent. The urgent Charlie
  send task will be registered only when the referenced final packet exists and hash-verifies.

## Phase 8 — lifecycle and evidence engineering debt

- Principal result parsing, error stubs, attempt projection, and truncation now share one schema-driven
  field table. Strict JSON rejects duplicate keys and non-finite numbers; URL and Boolean gates no longer
  coerce malformed values.
- Attempt append, problem projection, and discovery-campaign transitions are separated and covered by
  focused minimum-run, close-signal, and hold-review tests. Repository projection failures journal atomic
  retry receipts; legacy JSONL entries migrate without silently discarding malformed or pending work.
- Rendered pages use default-escaped templates with smoke coverage. Configuration is typed and service-
  scoped through one checked-in environment file; systemd units validate only the profile they consume.
- Research-state, lab, evidence, and contribution-gate loaders explicitly migrate supported versions or
  fail loudly. Lab validate/promote requires a distinct completed validation job, exact checker/input
  hashes, execution record, stdout/result hashes, and a fresh final-artifact rehash. Automated models may
  recommend but cannot apply validate/promote.
- Lab state parsing, threshold arithmetic, mutable checkpoint chains, live root/artifact-growth monitors,
  event/job matching, and stopped-job continuation all fail closed. A completed segment publishes its next
  executable spec only after state, append-only ledger, repository receipt, and completion event are durable.
- The hardened engine was deployed from Git revision `17337be`; production engine tests, R55 tests, all
  configuration profiles, systemd timer state, and `doctor` pass. The live-only automated projection commit
  was preserved, rebased, pushed, and then refreshed to the current R55 repository revision.
