# Research campaign design guidelines

These rules apply when Proof Factory turns an open problem into a sustained computational campaign.
They are intended to maximize independently verifiable contribution value per unit of model time,
compute, and expert attention. A famous problem does not relax the contribution or evidence bar.

## 1. Define progress before choosing a method

Start from a maintained authoritative status source. Write the decisive mathematical objects and the
smallest independently checkable certificate for each. Configure field-progress gates before the first
production run. A valid gate must be one of:

- a new witness, counterexample, extremal object, or isomorphism class;
- a natural exhaustive classification or exact optimum with a checked coverage certificate;
- a semantic lemma or reduction that changes a recognized downstream case;
- a reusable dataset, benchmark, correction, or verification component requested or valued by an
  identified community;
- a predeclared, leakage-safe algorithmic result that is statistically credible and practically changes
  a downstream research decision.

Counts such as clauses, profiles removed, speedup, solver calls, sessions, or compressed templates are
diagnostics. They become promotion thresholds only when a primary source, external expert, downstream
proof budget, or predeclared statistical decision rule explains why that exact threshold matters.

## 2. Maintain a live prior-art and active-work map

For every route, record the nearest known mechanism, its exact scope and outcome, primary sources, and
the material delta required for novelty. Distinguish:

1. replication or positive control;
2. material modification of a known mechanism;
3. genuinely different mechanism.

Before scaling a route that overlaps active work, contact the relevant author or maintainer. Send the
proposed mechanism and exact delta, and ask for current status, artifacts, novelty boundaries, and useful
independent-verification work. Record the response or documented nonresponse. Silence is not evidence of
novelty. Repeat the source and expert-alignment check before promoting a candidate.

## 3. Select routes by expected decision value

Rank routes by the expected change in the next research decision, multiplied by the chance that a result
passes a field-progress gate, and divided by measured model cost, compute cost, human review burden, and
novelty risk. A continuation bonus must never dominate this score.

Each route must declare:

- a falsifiable hypothesis and decisive observable;
- the natural mathematical scope;
- the nearest prior-art method and claimed delta;
- the cheapest bounded discriminator and controls;
- the positive and negative certificate formats;
- a semantic promotion condition, kill condition, and evidence-based reopen condition;
- an external user, author, venue, or accepted decomposition that would value success.

Reconcile route and lead state after every decision. A lead attached only to a killed or exhausted route is
closed unless its reopen evidence exists. Empty or stale routes are ineligible for selection.

### Successor selection: prefer an easier hard problem

The default successor is not the most famous available frontier. Prefer the smallest meaningful finite
uncertainty for which both positive and negative outcomes have compact, independently checkable evidence.
Gap-one exact optima, tightly constrained designs, and small classification boundaries should outrank wide
Ramsey or cage intervals when they offer a credible path to closure and a live expert/repository channel.

Before Charlie approves a successor pilot, compare at least six current candidates and require:

- a source-verified open statement and nearest active work;
- a 90-day probability for a **field-usable contribution**, separate from reproduction and from external
  acceptance, labeled as judgment until calibrated by a pilot;
- positive and negative certificate formats, independent checker cost, and expected artifact size;
- an objective acceptance owner or venue and a non-duplicative contribution class;
- a bounded first gate whose result can raise or lower the estimate materially.

Prefer a target above 50% estimated 90-day contribution probability when one remains mathematically
meaningful. Demote a prestige frontier below that threshold unless it uniquely exercises a reusable method
or outside evidence materially changes its cost profile. Reproduction alone is not success; it qualifies
only when it creates a genuinely new accepted certification or verification artifact.

## 4. Use event-driven model review and persistent computation

Models design experiments, interpret new evidence, compare mechanisms, and make route decisions.
Deterministic programs own enumeration, solving, checkpointing, retries, hashing, and resource accounting.
Do not repeatedly ask a model to supervise unchanged computation.

The normal cadence is:

1. a model review specifies a bounded job and its evidence contract;
2. a persistent lab worker runs it from an immutable input and checkpoint;
3. a new model review is triggered by a result, new source, route decision, or failed safety or
   reproducibility check;
4. the controller promotes, kills, holds, or redirects the route and schedules the next job.

Clock timers may poll or maintain workers, but they do not create research epochs without new evidence.
Long jobs are allowed when their declared decision value remains credible, including jobs that take days.
There is no universal overall wall-clock cutoff. Before substantial computation, write an efficiency-design
report that records the naive cost; symmetry/canonical/orbit opportunities; bitset, batching, vectorization,
and incremental-evaluation options; caching and reusable learned-prefix options; decomposition,
cube-and-conquer, meet-in-the-middle, and distributed/resumable options; compressed streaming artifacts;
sound cheap prefilters; the selected reductions and expected throughput gain; their soundness basis; and
what remains uncompressed.

Begin with a measured pilot or tranche. Divide execution into resource-bounded, atomic segments that resume
after reboot or deployment. Bind every segment to immutable inputs, code revision, hashes, and exact argv;
fsync durable progress, logs, partial results, checkpoints, and compressed/hash-verified manifests. Project
remaining runtime and artifact growth from observed throughput. Continue only while the remainder can still
produce the predeclared decisive result or reusable artifact. Automatically pause for review when throughput,
artifact growth, correctness checks, coverage, or decision value crosses a declared threshold.

Every completed segment emits a durable event. The lifecycle is `running`, `checkpointed`,
`completed_awaiting_review`, `validated`, or `stopped_with_reason`; dashboards and records must preserve the
distinction. A later reviewer reads the recorded state and artifacts and chooses `continue`, `validate`,
`promote`, or `redirect`. Completion never depends on a model being scheduled at that instant.

## 5. Validate evidence before updating research memory

An attempt is not durable progress until an evidence validator accepts it. Each attempt receives an
immutable delta manifest containing every claimed input and output hash, exact command, seed, dependency
and solver versions, exit status, limits, logs, and checker results. Never truncate the evidence list by a
file-count cap.

Positive computational claims require a non-importing checker or materially different encoding. Exhaustive
claims additionally require an independent coverage check and generator-to-object correspondence. Proof
logs must be bound to exact formula hashes and checked with a separately maintained checker; document the
trusted base. Interrupted proof streams and solver timeouts are not UNSAT evidence.

The state transition is:

`attempt -> evidence_validated -> progress -> candidate -> independent_review -> contribution`

Failure at any gate preserves the artifacts and scoped negative result but does not project the claim into
durable strategy memory. Before release, replay the contribution packet from a clean clone or frozen image.

## 6. Compress prompts and reuse artifacts

Keep one canonical machine-readable route packet. Model prompts should contain only its current decision
surface: status, incumbent and challengers, new evidence receipts, nearest prior art, costs, and open
decision. Link to detailed ledgers and artifacts instead of injecting overlapping roadmaps, summaries, and
delegate memos.

Use deterministic tools for mechanical searches and independent agents only for genuinely complementary
work such as separate implementations or source audits. Cache source extracts and stable context by hash.
Measure model input, output, wall time, solver time, and artifact growth per decisive observation.

Parallelize source review, adversarial code audit, independent checker construction, documentation, and
packet tooling when their files and decisions are disjoint. Serialize shared-ledger writes, deployment,
schema migrations, final artifact assembly, and any computation that competes for the same CPU/cache or
depends on an earlier proof gate. Every parallel branch must state its write scope and return evidence to
one integration review; delegation never creates an independent authority to promote, publish, spend, or
bypass a gate.

## 7. Calibrate chances on explicit horizons

Every planning probability must name its event and horizon: for example, “a candidate passing a configured
field-progress gate within the next 90 days and the approved compute budget.” Keep separate estimates for
technical success, novelty after review, external acceptance, and solving or improving the headline bound.
Update only on decisive evidence or material prior-art changes, and record the observation that moved the
estimate. Do not present probabilities with incompatible horizons as comparable.

## 8. Stop honestly and transfer what worked

Park a route when its next test has low decision value, repeats stronger known work, lacks a credible
external path, or exceeds the approved proof and review budget. Preserve exact negative scope, checkers,
benchmarks, and reusable infrastructure. When a flagship stalls, prefer transferring a validated method to
a tractable neighboring problem over manufacturing local “progress” on the famous target.

At campaign review, report separately:

- mathematical status and whether any recognized bound changed;
- new verified objects, classifications, lemmas, or infrastructure;
- strongest failed route and what was actually excluded;
- model, compute, and human-review cost;
- current prior-art overlap and expert feedback;
- next cheapest discriminator, or the evidence-based reason to park.
