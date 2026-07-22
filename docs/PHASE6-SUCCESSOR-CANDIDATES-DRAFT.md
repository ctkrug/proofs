# Phase 6 successor-target assessment (draft)

**Status date:** 2026-07-21

**Scope:** Target selection only. No target has been registered, no status/alignment inquiry has been
sent, and no technical research epoch, result outreach, or public claim has begun.

**Recommendation:** Make the exact covering number \(C(12,6,4)\) the first successor baseline. Its maintained live bracket is \(40\le C(12,6,4)\le41\), so either a 40-block witness or a certified exclusion of 40 is decisive.

**Post-pilot update (2026-07-22):** Charlie approved and started this successor after the R(5,5)
completion gate. Direct shallow cubing missed its continuation threshold, while the link-first route
has four audited link orbits, four residual exclusions, 189 replay-validated proof receipts, and 47
open canonical frontier nodes. The current strategic range is **70–85% for a field-usable contribution**
and **45–65% for exact resolution** within 90 days. These are judgment ranges, not calibrated
probabilities. No exact-value claim is made. The pre-pilot estimates below are retained as the dated
decision baseline rather than silently rewritten.

## Executive judgment

The easier-hard review changes the recommendation. The best balanced 90-day target is now the exact covering-design problem

\[
C(12,6,4)\in\{40,41\}.
\]

A \((12,6,4)\)-cover is a collection of 6-subsets (blocks) of a 12-point set such that every 4-subset lies in at least one block. The covering number is the minimum number of blocks. The [La Jolla Covering Repository entry](https://ljcr.dmgordon.org/cover/show_cover.php?v=12&k=6&t=4) maintains the lower bound 40 and a 41-block construction; it is also the next unresolved entry in [OEIS A066019](https://oeis.org/A066019).

This instance has only 924 possible blocks and 495 coverage constraints, strong exact structural consequences at the lower bound, compact positive certificates, and standard proof-logging routes for a negative result. A successful computation settles an exact classical design number rather than moving one side of a wide interval. The decision range is a **45–70% judgment** for a field-usable result within 90 days, with roughly 60% as the planning midpoint. It is not a measured frequency, confidence interval, or calibrated statistical forecast.

The old cage-first recommendation is therefore demoted. Improving \(n(4,9)\) remains meaningful, but its prior 14% point estimate is withdrawn in favor of a coarse 10–20% planning range. Its nonlinear order-to-order cost and bespoke exhaustive-coverage burden make it a worse next production target. It should remain a later method benchmark, not the default successor.

## Selection method and probability warning

Targets were compared on decisiveness, compactness of the instance, independent verifiability, certificate standards, likely compute, acceptance path, and the probability of producing either new mathematics or a clearly reusable formal artifact within 90 days.

All ranges below are **strategic judgments** made from current bounds, instance size, proof surfaces, and known workflows. They are not empirical success rates, statistical confidence intervals, or guarantees. They must be revised after a measured pilot and live-priority check.

For this draft, “field-usable within 90 days” means either (a) a decisive exact result that passes independent validation and is ready for specialist review, or (b) an independently checkable reusable artifact whose usefulness is confirmed by a relevant maintainer or specialist. Merely running a solver, reproducing a known witness, or preparing a polished narrative does not count.

### Auditable judgment basis for the lead target

The 45–70% range is a scenario judgment over four recorded factors, not a multiplication of invented independent probabilities:

| Factor | Evidence available on 2026-07-21 | Downside represented in 45% case | Upside required to approach 70% |
|---|---|---|---|
| Status and novelty headroom | LJCR still displays \(40\le C(12,6,4)\le41\); the displayed 41-block construction is directly downloadable | A maintainer reports unpublished duplication or an active near-complete effort | A Charlie-approved private status inquiry confirms the gap and useful scope |
| Technical tractability | 924 binary block choices, 495 cover constraints, and exact point/pair consequences | Symmetry reduction is weak or the proof-producing UNSAT tail exceeds the declared envelope | Both independent pilots agree and measured throughput supports a bounded completion plan |
| Independent verification | A positive result has a tiny direct checker; a negative result has a standard proof-log/cube route | The symmetry bridge, cube coverage, or proof replay cannot be independently checked | Clean-clone witness replay or every proof segment and coverage manifest validates independently |
| External usefulness | Resolving a one-bit classical covering number has a clear repository record and specialist audience | The work is only a reproduction or no specialist confirms artifact value | A maintainer/specialist confirms priority or usefulness after the private alignment step |

The base case is approximately 60%, not 62% precision: the live bracket survives the status check, the bounded pilot is informative, and one independently checkable outcome reaches specialist review. The downside case is 45% because duplication risk and a proof-producing UNSAT tail are both material. The upside is capped at 70% until measured scaling and external alignment exist. Record the inquiry response and pilot measurements, then replace this range rather than incrementally “tuning” it from model opinion.

## Ranked shortlist

| Rank | Target | Decisive or reusable result | 90-day judgment | Expected resources | Why it ranks here |
|---:|---|---|---:|---|---|
| 1 | Exact \(C(12,6,4)\), currently 40–41 | 40-block cover or certified nonexistence at 40 | **45–70%** (about 60% planning midpoint) | 1–4 core-hour pilot; likely 20–250 core-hours; hard tail up to 1,000; 2–8 GB working storage | One-bit exact problem, very small model, strong structure, direct witness checker, and proof-log route |
| 2 | Active compact covering-record portfolio | A repository-accepted improved covering for one predeclared compact instance | **50–75%** provisional | 200–1,500 core-hours across bounded candidates | Highest chance of some record, but lower decisiveness and credit than settling one exact number; susceptible to record churn |
| 3 | Lean-certified proof of the known \(C(17,5,3)=68\) result | Reusable verifier/formal theorem; upstream acceptance if accepted | **50–75% artifact; 20–45% upstream** provisional | Primarily proof engineering; retain the pinned one-thread Mathlib workflow | Very checkable and reusable, but not new mathematics unless it exposes and closes a substantive proof gap |

The record portfolio's range extends higher than the recommended target's because it permits several attempts. It is not ranked first because “some improved upper bound” is less decisive, easier to duplicate, and usually earns less mathematical credit than resolving \(C(12,6,4)\). Rows 2 and 3 are comparison strategies, not approved targets; each still needs a parameter-specific primary-source/status pass before promotion.

## Six-candidate source-verified finite comparison

The six covering entries below were checked directly on 2026-07-21 against their maintained LJCR
parameter pages and the successor Covering Repository's [current classical-improvements
feed](https://www.coveringrepository.com/systems.aspx?li=2). None appeared in the post-import improvement
feed. The probability ranges are deliberately broad feasibility judgments before any target-specific
encoding pilot; only the lead target has completed the fuller baseline above.

| Rank | Exact target and maintained bracket | Raw blocks / constraints | Decisive artifact | Pre-pilot 90-day judgment | Disposition |
|---:|---|---:|---|---:|---|
| 1 | [\(C(12,6,4)=40\text{–}41\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=12&k=6&t=4) | 924 / 495 | 40 blocks or no-40 LRAT/coverage proof | **45–70%** | Recommended; strongest rigidity and smallest balanced one-bit instance |
| 2 | [\(C(18,11,3)=9\text{–}10\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=18&k=11&t=3) | 31,824 / 816 | 9 blocks or no-9 proof | 35–60% | Best one-bit alternate; test complement/orbit compression first |
| 3 | [\(C(22,17,5)=10\text{–}11\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=22&k=17&t=5) | 26,334 / 26,334 | 10 blocks or no-10 proof | 30–55% | Strong symmetric alternate; larger constraint surface |
| 4 | [\(C(13,7,4)=28\text{–}30\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=13&k=7&t=4) | 1,716 / 715 | 28/29 blocks or exclusions at both sizes | 30–55% | Tiny model, but exact closure may need two decisions |
| 5 | [\(C(20,12,3)=9\text{–}10\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=20&k=12&t=3) | 125,970 / 1,140 | 9 blocks or no-9 proof | 20–45% | Clean certificate path; second-tier candidate universe |
| 6 | [\(C(23,16,4)=10\text{–}11\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=23&k=16&t=4) | 245,157 / 8,855 | 10 blocks or no-10 proof | 10–30% | Source-clean reserve; substantially larger proof surface |

The ranges are not comparable measurements: each means a field-usable, independently validated result
within 90 days and an approved compute envelope. They encode only present structural size, number of gap
decisions, and certificate surface. A bounded symmetry-reduced SAT discriminator is required before any
alternate can replace the lead or retain a numerical estimate.

Two source-verified negative calibration points reinforce the ease-first choice. The current survey gives
[\(40\le R(3,10)\le41\)](https://www.cs.rit.edu/~spr/ElJC/ejcram18.pdf), but its tens of millions of
boundary graphs make it a much harder completeness problem. The [five-dimensional kissing-number
frontier](https://cohn.mit.edu/kissing-numbers/) remains a continuous certificate problem, not the compact
finite Boolean route sought here. Neither is an automatic fallback.

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
- For any point \(x\), summing the multiplicities of its 11 incident pairs gives \(5r_x=100\). The mandatory baseline contributes 99, so exactly one pair through \(x\) has multiplicity 10 and all other pairs through \(x\) have multiplicity 9. Consequently the six excess pairs form a perfect matching. Fixing that matching is a sound quotient by all \(12!/(2^6 6!)=10{,}395\) possible perfect matchings; its stabilizer has order \(2^6 6!=46{,}080\).
- Relative to the fixed matching, let \(r(B)\) count the complete matched pairs in block \(B\). The 40 blocks have \(\sum_B r(B)=60\), so a complete root split needs only two disjoint cases: a canonical \(r=0\) block exists, or no \(r=0\) block exists and a canonical \(r=1\) block exists. The second case is exhaustive because the average is 1.5.

These facts are not optional heuristic assumptions. They must be independently proved in the research record, encoded as redundant sound constraints, and checked against any result.

Block complementation is **not** an automorphism of the covering constraints: a block containing a 4-set is sent to a complementary block disjoint from it. It must not be used for symmetry reduction without a separate proved bridge.

## First decision gate: two independent bounded pilots

Before a long job, implement and compare two materially different formulations on immutable inputs.

### Encoding A: direct set-cover SAT/PB

- one Boolean variable for each of the 924 possible 6-blocks;
- one coverage constraint for each of the 495 4-subsets;
- cardinality exactly 40;
- redundant exact point-degree-20 constraints;
- exact pair multiplicity 10 on a fixed perfect matching and 9 on every other pair (these equations already imply both 40 blocks and point degree 20, so benchmark redundant constraints rather than assuming they help);
- the two exhaustive canonical root cases above, with only written and independently checked orbit restrictions;
- proof logging for every decisive UNSAT solve.

### Encoding B: link-first canonical augmentation

Fix a point and its matched partner. The point's 20 incident blocks induce an optimal \((11,5,3)\)-cover whose point degrees are 10 at the matched partner and 9 at each other point. Enumerate these links up to the fixed-matching stabilizer, then solve the exact residual problem of choosing 20 blocks that exclude the fixed point. Independently check isomorph rejection and complete orbit coverage. This must not merely translate Encoding A's clauses through the same generator. Without a checked complete link-orbit manifest, use this route only as a discriminator and retain Encoding A's proof-producing cube tree as the completeness path.

### Pilot envelope and continuation rule

Run each formulation, or a representative disjoint tranche of each, for a combined **1–4 core-hours** with checkpointing and durable receipts. Continue beyond the pilot only when all of the following hold:

1. known 41-block and smaller-parameter controls pass, including a checked exclusion of eight blocks for \(C(10,4,2)\);
2. both formulations agree on at least 32 determinate shared-prefix cases, and timeouts are recorded as inconclusive rather than disagreements;
3. shallow orbit counts match an independent checker and checkpoint replay is byte-identical;
4. at least 80% of a deterministic stratified sample of at least 128 direct-encoding cubes close within their cap;
5. measured throughput gives a conservative full-run estimate no larger than 250 core-hours, with a separately reviewed hard-tail ceiling of 1,000 core-hours;
6. the negative-certificate projection is at most 30 GB and can be streamed, hashed, resumed, and independently checked;
7. no current repository maintainer or author reports the exact case already settled or substantially complete.

If only 20--80% of sampled cubes close, permit one bounded deeper-cubing or encoding-redesign tranche. Pause or redirect on any semantic disagreement, symmetry-coverage or proof-replay failure, proof growth above 30 GB, a post-redesign estimate above 1,000 core-hours, or loss of independent checkability. Any 40-block witness immediately stops exhaustive work and enters dual validation. A completed result must persist as completed-awaiting-review even when no reviewer is scheduled.

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

The source pages were checked directly on **2026-07-21**: the [La Jolla Covering Repository entry](https://ljcr.dmgordon.org/cover/show_cover.php?v=12&k=6&t=4) displayed \(40\le C(12,6,4)\le41\) and its 41 listed blocks, while the maintained [Covering Repository](https://www.coveringrepository.com/default.aspx) said its historical \((v,k,t)\) data through March 2026 came from the Dan Gordon repository and that later improvements are maintained on the new site.

Before pre-scale work, Charlie may separately approve a **private status/alignment inquiry** to the relevant repository maintainer or author. That message may ask whether the bracket is still live, whether substantially complete work is already under way, and what artifact format would be useful. It must not assert a result, request priority, imply endorsement, or release nonpublic result artifacts. The question and response become dated source records. This inquiry is a pre-scale novelty check, not result outreach.

**Result outreach and public claims are a separate gate.** They remain prohibited until a result has passed the independent-validation standard in this document and Charlie gives a distinct release approval. Approval to send the private status inquiry does not authorize result outreach, manuscript circulation, repository submission, social posting, or any public claim.

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

Do not redirect automatically to any exploratory entry. Run a new primary-source/status and active-work audit, compare the now-verified candidates, and obtain Charlie's target approval. In particular, do not fall back automatically to \(n(4,9)\), \(R(3,10)\), or \(R(4,6)\).

## Final recommendation

After the current \(R(5,5)\) Phase 5 gate, Charlie may approve (1) the narrow private status/alignment inquiry described above and, separately, (2) only the **baseline, dual-encoding, and 1–4 core-hour pilot phase for exact \(C(12,6,4)\)**. Neither approval registers or starts work before that gate. Its intended contribution is one of two fully decisive outcomes:

1. a verified 40-block cover proving \(C(12,6,4)=40\); or
2. a complete independently checked exclusion of 40, combined with the known 41-block witness, proving \(C(12,6,4)=41\).

This is the preferred easier-hard successor because it preserves genuine mathematical significance while materially improving the chance of completion, verification, and expert acceptance. The 45–70% 90-day judgment range, with an approximately 60% planning midpoint, must be replaced after the status response and measured pilot. Cage \(n(4,9)\) is explicitly not the next production target.

## Source record

### Lead status sources (directly checked 2026-07-21)

- [La Jolla Covering Repository: \((12,6,4)\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=12&k=6&t=4) — displayed the 40–41 bracket and 41 blocks
- [Covering Repository home](https://www.coveringrepository.com/default.aspx) — identified the post-March-2026 maintained successor repository and its archival relationship to LJCR
- [OEIS A066019](https://oeis.org/A066019) — approved maintained covering-number triangle; retrieved 2026-07-21

### Supporting method and subproblem sources

- [La Jolla Covering Repository: \((11,5,3)\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=11&k=5&t=3)
- [La Jolla Covering Repository: \((10,4,2)\)](https://ljcr.dmgordon.org/cover/show_cover.php?v=10&k=4&t=2)
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
