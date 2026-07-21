# Phase 6 successor-target assessment (draft)

**Status date:** 2026-07-21

**Scope:** Target selection only. No search, outreach, or technical research epoch has begun.

**Recommendation:** Make the exact covering number \(C(12,6,4)\) the first successor baseline. Its maintained live bracket is \(40\le C(12,6,4)\le41\), so either a 40-block witness or a certified exclusion of 40 is decisive.

## Executive judgment

The easier-hard review changes the recommendation. The best balanced 90-day target is now the exact covering-design problem

\[
C(12,6,4)\in\{40,41\}.
\]

A \((12,6,4)\)-cover is a collection of 6-subsets (blocks) of a 12-point set such that every 4-subset lies in at least one block. The covering number is the minimum number of blocks. The [La Jolla Covering Repository entry](https://ljcr.dmgordon.org/cover/show_cover.php?v=12&k=6&t=4) maintains the lower bound 40 and a 41-block construction; it is also the next unresolved entry in [OEIS A066019](https://oeis.org/A066019).

This instance has only 924 possible blocks and 495 coverage constraints, strong exact structural consequences at the lower bound, compact positive certificates, and standard proof-logging routes for a negative result. A successful computation settles an exact classical design number rather than moving one side of a wide interval. The estimated 62% probability of a field-usable result within 90 days is a strategic judgment, not a measured frequency or calibrated statistical forecast.

The old cage-first recommendation is therefore demoted. Improving \(n(4,9)\) remains meaningful, but its 14% 90-day contribution estimate, nonlinear order-to-order cost, and bespoke exhaustive-coverage burden make it a worse next production target. It should remain a later method benchmark, not the default successor.

## Selection method and probability warning

Targets were compared on decisiveness, compactness of the instance, independent verifiability, certificate standards, likely compute, acceptance path, and the probability of producing either new mathematics or a clearly reusable formal artifact within 90 days.

All percentages below are **strategic judgments** made from current bounds, instance size, proof surfaces, and known workflows. They are not empirical success rates, confidence intervals, or guarantees. They must be revised after a measured pilot and live-priority check.

## Ranked shortlist

| Rank | Target | Decisive or reusable result | 90-day judgment | Expected resources | Why it ranks here |
|---:|---|---|---:|---|---|
| 1 | Exact \(C(12,6,4)\), currently 40–41 | 40-block cover or certified nonexistence at 40 | **62%** | 1–4 core-hour pilot; likely 20–250 core-hours; hard tail up to 1,000; 2–8 GB working storage | One-bit exact problem, very small model, strong structure, direct witness checker, and proof-log route |
| 2 | Active compact covering-record portfolio | A repository-accepted improved covering for one predeclared compact instance | **70%** | 200–1,500 core-hours across bounded candidates | Highest chance of some record, but lower decisiveness and credit than settling one exact number; susceptible to record churn |
| 3 | Lean-certified proof of the known \(C(17,5,3)=68\) result | Reusable verifier/formal theorem; upstream acceptance if accepted | **65% artifact; 35% upstream** | Primarily proof engineering; retain the pinned one-thread Mathlib workflow | Very checkable and reusable, but not new mathematics unless it exposes and closes a substantive proof gap |

The record portfolio's numerical probability is higher than the recommended target's because it permits several attempts. It is not ranked first because “some improved upper bound” is less decisive, easier to duplicate, and usually earns less mathematical credit than resolving \(C(12,6,4)\).

## Wider ranking

| Rank | Candidate | Live target type | 90-day contribution judgment | Disposition |
|---:|---|---|---:|---|
| 4 | Exact \(C(13,6,3)\), currently 20–21 | One-bit exact covering number | 55% | First exact fallback if the lead instance is duplicated or the pilot fails |
| 5 | Compact \(v=14/16\) covering-record portfolio | Improved upper witnesses | 52% | Fold into the bounded record portfolio, not a permanent open-ended lane |
| 6 | Exact \(C(15,6,3)\), currently 30–31 | One-bit exact covering number | 42% | Strong second fallback; larger proof surface |
| 7 | NIST-relevant covering-array benchmark | Compact construction/certification artifact | 35% | Select exact parameters and acceptance owner before any run |
| 8 | Exact \(C(15,5,3)\), currently 54–55 | One-bit exact covering number | 31% | Retain as a later SAT/canonical-augmentation target |
| 9 | Degree-diameter problem at degree 4, diameter 4 | Construction or exclusion | 18% | Interesting but less direct to certify and less likely in 90 days |
| 10 | Cage \(n(4,9)\), currently 165–270 | Incremental lower bound or smaller witness | 14% | Demoted from first successor; revisit only after measured evidence changes the cost profile |
| 11 | Lean formalization of \(R(4,5)\) | Known-result formal artifact | 6% | Low near-term probability under the present broad-import/one-vCPU workflow |

Prestige targets \(R(3,10)\), \(R(4,6)\), maximal determinant \(D(23)\), and \(\operatorname{cr}(K_{13})\) remain useful horizon problems, but none has a source-backed, compact, high-confidence 90-day completion path comparable to the lead covering instance.

## Full baseline for \(C(12,6,4)\)

### Exact statement and live frontier

Let \(V\) be a 12-point set. Determine the minimum size of a family \(\mathcal B\subseteq\binom{V}{6}\) such that every member of \(\binom{V}{4}\) is contained in some \(B\in\mathcal B\). The maintained bracket is

\[
40\le C(12,6,4)\le41.
\]

There are

\[
\binom{12}{6}=924
\]

candidate blocks and

\[
\binom{12}{4}=495
\]

4-subsets to cover. A 40-block cover proves \(C(12,6,4)=40\); an independently validated proof that no 40-block cover exists, together with the repository's checked 41-block witness, proves \(C(12,6,4)=41\).

### Structural constraints at size 40

The lower-bound case is unusually rigid and gives strong, independently derivable constraints:

- Each point must occur in at least \(C(11,5,3)=20\) blocks: after fixing a point, its incident blocks must cover every triple on the other 11 points. Forty 6-blocks have 240 point incidences, so every point must occur **exactly 20 times**. The maintained subproblem is recorded at the [LJCR \((11,5,3)\) entry](https://ljcr.dmgordon.org/cover/show_cover.php?v=11&k=5&t=3).
- Each pair must occur in at least \(C(10,4,2)=9\) blocks: after fixing a pair, the remaining four points of an incident block must cover every pair on the other ten points. The 40 blocks have \(40\binom62=600\) pair incidences, while 66 pairs at multiplicity 9 consume 594. Thus there are only **six excess pair incidences** above the mandatory baseline. See the maintained [LJCR \((10,4,2)\) entry](https://ljcr.dmgordon.org/cover/show_cover.php?v=10&k=4&t=2).

These facts are not optional heuristic assumptions. They must be independently proved in the research record, encoded as redundant sound constraints, and checked against any result.

## First decision gate: two independent bounded pilots

Before a long job, implement and compare two materially different formulations on immutable inputs.

### Encoding A: direct set-cover SAT/PB

- one Boolean variable for each of the 924 possible 6-blocks;
- one coverage constraint for each of the 495 4-subsets;
- cardinality exactly 40;
- redundant exact point-degree-20 constraints;
- pair-multiplicity-at-least-9 constraints plus the six-excess accounting identity;
- one fixed block and only written, checked orbit/symmetry restrictions;
- proof logging for every decisive UNSAT solve.

### Encoding B: link-first canonical augmentation

Build the block family through point links/pair multiplicities and canonical augmentation, independently checking isomorph rejection and complete orbit coverage. This must not merely translate Encoding A's clauses through the same generator. It should provide a second semantic path to a witness or to a partition of the remaining search.

### Pilot envelope and continuation rule

Run each formulation, or a representative disjoint tranche of each, for a combined **1–4 core-hours** with checkpointing and durable receipts. Continue beyond the pilot only when all of the following hold:

1. both formulations agree on shared bounded cases and direct semantic checks;
2. measured throughput gives a credible full-run estimate inside the likely 20–250 core-hour range, or a documented hard-tail plan no larger than 1,000 core-hours;
3. the negative-certificate projection fits the declared 2–30 GB proof-artifact envelope and can be streamed, hashed, resumed, and independently checked;
4. canonical/orbit reductions have a written soundness basis and independently checked coverage;
5. no current repository maintainer or author reports the exact case already settled or substantially complete.

Pause or redirect if correctness checks diverge, proof growth exceeds the envelope, throughput makes the hard tail noncredible, or the output can no longer be made independently checkable. A completed result must persist as completed-awaiting-review even when no reviewer is scheduled.

## Resource profile

| Resource | Predeclared envelope |
|---|---|
| Pilot | 1–4 core-hours, bounded resumable tranches |
| Likely full computation | 20–250 core-hours |
| Hard tail | Up to 1,000 core-hours only after a positive continuation review |
| Working memory/disk | 2–8 GB, measured during pilot |
| Positive witness | Kilobytes plus provenance and checker receipts |
| Negative proof | Projected 2–30 GB, segmented/compressed where the checker permits |
| Parallelism | Only after measured scaling; deterministic cube ownership and no overlap |

The existing droplet is suitable for formulation work, small pilots, orchestration, and independent witness checks. A long proof-producing run may be moved to temporary multicore compute only after the pilot establishes decision value, scaling behavior, certificate growth, and a cost cap. It must remain portable and resumable.

## Certificate and independent-validation standard

### If a 40-block cover is found

Publish the sorted block list, canonicalized representation, immutable code/input hashes, exact command, environment receipt, and a tiny checker that verifies:

- exactly 40 distinct 6-subsets of a 12-point ground set;
- coverage of all 495 4-subsets;
- point degree exactly 20 and pair multiplicity at least 9;
- canonical hash and replay from the raw witness.

A second checker should be short and share no solver or producer code. The positive artifact should remain only kilobytes.

### If size 40 is impossible

A negative result requires more than a solver exit code. Preserve:

- the unsymmetrized semantic specification and a checked bridge from every symmetry/canonical restriction to it;
- deterministic cube/segment definitions with disjointness and complete-coverage manifests;
- LRAT or an equivalently independently checkable proof for every UNSAT segment;
- exact generator, solver, checker, input, proof, and manifest hashes;
- successful replay with an independent proof checker and, where practical, a second encoding;
- the independently checked 41-block construction establishing the matching upper bound.

If a monolithic proof cannot fit safely, use proof prefixes or cubes whose coverage is independently checked. Compression may reduce storage, never the semantic verification surface.

## Efficiency-design pass

Before the first substantial run, document:

1. the naive \(\binom{924}{40}\) selection space and every exact reduction;
2. complement symmetry, fixed-block stabilization, point/pair orbits, and canonical augmentation;
3. bitset coverage, batched evaluation, incremental cardinality/degree/link constraints, and sound cheap infeasibility filters;
4. memoized link types, reusable learned clauses, proof prefixes, and cache-key soundness;
5. deterministic cube-and-conquer or link decomposition, restart/checkpoint behavior, and independent coverage accounting;
6. compressed streamed artifacts, hash-verified manifests, expected throughput gain, and what remains uncompressed or trusted.

Record naive cost, chosen reductions, measured and expected gains, soundness basis, and residual verification surface. A speedup without an independently checkable mapping to the original problem does not qualify.

## Acceptance path

First confirm the live bracket and priority with the maintainers of the [La Jolla Covering Repository](https://www.coveringrepository.com/default.aspx) and compare against repository witnesses. No outreach or public claim should occur before independent validation.

A decisive result has a clear route to the *Journal of Combinatorial Designs* or *Discrete Mathematics and Theoretical Computer Science*, provided the paper includes the mathematical reductions, immutable witness or proof artifacts, independent checkers, and reproducible commands. A repository and [OEIS A066019](https://oeis.org/A066019) update should follow validation/publication coordination; neither database entry substitutes for peer review.

The Lean-certified \(C(17,5,3)=68\) fallback is a different contribution type. It should target an upstreamable theorem and reusable covering-design verifier in [Google DeepMind's Formal Conjectures repository](https://github.com/google-deepmind/formal-conjectures), using the already validated pinned cache, target-only build, `LEAN_NUM_THREADS=1`, and separate scheduling from heavy SAT work.

## Ninety-day staged plan

| Period | Work product | Gate |
|---|---|---|
| Days 1–5 | Freeze live sources/witnesses; derive and independently check the point/pair constraints; write the efficiency report | Stop if the 40–41 status or subproblem bounds do not reproduce |
| Days 6–12 | Build both encodings and tiny positive checker; reproduce known neighboring/relaxed cases | No target run until both semantic paths agree |
| Days 13–16 | Run the 1–4 core-hour measured pilot; project runtime, memory, proof growth, and scaling | Continue only under the declared thresholds |
| Days 17–55 | Execute checkpointed tranches, preserving proof prefixes, manifests, and completion events | Review at predeclared tranche boundaries; no universal wall-clock stop |
| Days 56–72 | Independently replay the result with direct checker/LRAT and second formulation | Any disagreement returns the result to investigation, never promotion |
| Days 73–90 | Prepare expert review packet and manuscript-quality record | Promote only after independent validation and clean-clone replay |

## Redirect and stop conditions

- The exact instance is already settled or substantially complete elsewhere.
- The two formulations disagree and the discrepancy cannot be resolved within the bounded pilot.
- Symmetry or canonical coverage cannot be bridged to the unsymmetrized problem.
- Runtime projects beyond 1,000 core-hours without a new, predeclared decision-value review.
- Negative proof growth projects beyond 30 GB or cannot be segmented and independently replayed.
- Solver output cannot yield either a decisive result or a reusable independently checked artifact.

Redirect first to exact \(C(13,6,3)\), then to a predeclared compact covering-record portfolio. Do not fall back automatically to \(n(4,9)\), \(R(3,10)\), or \(R(4,6)\).

## Final recommendation

After the current \(R(5,5)\) Phase 5 gate, approve only the **baseline, dual-encoding, and 1–4 core-hour pilot phase for exact \(C(12,6,4)\)**. Its intended contribution is one of two fully decisive outcomes:

1. a verified 40-block cover proving \(C(12,6,4)=40\); or
2. a complete independently checked exclusion of 40, combined with the known 41-block witness, proving \(C(12,6,4)=41\).

This is the preferred easier-hard successor because it preserves genuine mathematical significance while materially improving the chance of completion, verification, and expert acceptance. The 62% 90-day estimate remains a judgment to be updated after the pilot. Cage \(n(4,9)\) is explicitly not the next production target.

## Source record

### Lead covering-design sources

- [La Jolla Covering Repository: \((12,6,4)\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=12&k=6&t=4)
- [La Jolla Covering Repository: \((11,5,3)\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=11&k=5&t=3)
- [La Jolla Covering Repository: \((10,4,2)\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=10&k=4&t=2)
- [Covering Repository home](https://www.coveringrepository.com/default.aspx)
- [OEIS A066019](https://oeis.org/A066019)
- [Gordon, Kuperberg, and Patashnik, *New Constructions for Covering Designs*](https://arxiv.org/abs/math/9502238)
- [Google DeepMind, *Formal Conjectures*](https://github.com/google-deepmind/formal-conjectures)

### Retained horizon-problem sources

- [Radziszowski, *Small Ramsey Numbers*, DS1.18 (2026)](https://www.combinatorics.org/ojs/index.php/eljc/article/download/DS1/pdf/0)
- [Angeltveit, *The Ramsey Number R(3,10) Is at Most 41*](https://arxiv.org/abs/2401.00392)
- [Exoo, *On the Ramsey Number R(4,6)*](https://www.combinatorics.org/ojs/index.php/eljc/article/download/v19i1p66/pdf)
- [de la Cruz and Pizana, *On Cages and Choosing with Symmetries* (2026)](https://www.combinatorics.org/ojs/index.php/eljc/article/download/v33i1p54/pdf/)
- [Exoo et al., *New small regular graphs of given girth: the cage problem and beyond*](https://arxiv.org/abs/2511.07247)
- [Rowley, *An Improved Lower Bound for S(7) and Some Interesting Templates*](https://arxiv.org/abs/2107.03560)
- [Rabung and Lotts, *Improving the Use of Cyclic Zippers in Finding Lower Bounds for Van der Waerden Numbers*](https://www.combinatorics.org/ojs/index.php/eljc/article/download/v19i2p35/pdf/)
- [Browne et al., *A Survey of the Hadamard Maximal Determinant Problem*](https://www.combinatorics.org/ojs/index.php/eljc/article/view/v28i4p41)
- [Richard Brent's maintained maximal-determinant research/data page](https://maths-people.anu.edu.au/~brent/maxdet/)
- [Schaefer, *The Graph Crossing Number and its Variants: A Survey*, DS21](https://www.combinatorics.org/ojs/index.php/eljc/article/download/DS21/pdf/)
- [McQuillan, Pan, and Richter, *On the crossing number of K13*](https://arxiv.org/abs/1307.3297)
