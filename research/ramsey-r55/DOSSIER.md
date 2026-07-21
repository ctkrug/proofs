# R(5,5) research dossier

> Status audited: 2026-07-20; cross-field method scan integrated 2026-07-20. This is operational
> research memory, not a proof or originality claim.
> Every automated epoch should use the compact map in `data/research_states/ramsey-r55.json` first,
> then consult this dossier for the source trail and fuller context before opening a new route.

## 1. Exact target and evidence contract

`R(5,5)` is the least integer `n` such that every simple graph on `n` vertices contains either a
5-clique or an independent set of size 5. Equivalently, an `(5,5,n)` Ramsey graph contains neither.

The maintained 2026 Dynamic Survey records:

```text
43 <= R(5,5) <= 46
```

There are two terminal routes:

1. **Lower bound:** exhibit an `(5,5,43)` graph. The certificate is an adjacency list or graph6 string;
   an independent checker enumerates every 5-subset and finds neither a clique nor an independent set.
2. **Upper bound:** prove no `(5,5,n)` graph exists for `n=45`, `44`, or `43`. A computational proof
   must include a deterministic reduction, an independently checked exhaustive cover, and checked
   leaf certificates. A paper's custom program reporting no cases is not enough for our candidate gate.

Intermediate work counts only when it is externally useful: a new structural lemma, exact
classification, independently reproducible benchmark/dataset, formalization, or a measurable search
advance recognized by the Ramsey/computational-mathematics community. A lower heuristic score alone
is internal progress.

## 2. Epistemic labels used below

- **Established:** proved in a cited paper or directly checkable from a maintained artifact.
- **Replicated computation:** independently implemented computations agree, but no formal certificate
  is implied.
- **Conjectured:** explicitly proposed by experts; not proved.
- **Reported:** stated without a public artifact sufficient for independent reproduction.
- **Proposed experiment:** our synthesis; not a literature result.

## 3. Historical progression

| Year | Result | Mechanism | Operational lesson |
|---|---|---|---|
| 1965 | Lower bound 38 | Quadratic residues in `Z_37` | Algebraic seeds can compress a construction. |
| 1965–1971 | Upper bounds fell from 59 to 55 | Combinatorics plus linear programming | Exact counting inequalities can remove large regions without enumeration. |
| 1973 | Lower bound 42 | Sum-free-set construction | Structured additive templates matter. |
| 1989 | Exoo proved the lower bound 43 | Cyclic seed, vertex deletion, and 16 edge recolorings | The best witness is a carefully repaired near-miss, not a random graph. |
| 1991–1997 | Upper bound fell through 53, 52, 50, and 49 | `(4,5,n)` catalogues, subgraph identities, exact LP checks, graph gluing | Neighborhood structure is the main upper-bound lever. |
| 1997 | McKay–Radziszowski–Exoo conjectured `R(5,5)=43` | Many independent heuristic searches repeatedly found the same 656 known 42-vertex graphs | Strong evidence is not completeness; avoid treating the 656 as exhaustive. |
| 2018 | Upper bound 48 | Complete catalogue of 352,366 `(4,5,24)` graphs and roughly two trillion gluing operations | Exhaustive catalogues work only after a theorem makes the local state space small. |
| 2024/2026 | Upper bound 46 | Edge-extremal `(4,5,n)` catalogues, LP excess identity, pointed-graph gluing, two independent implementations | Directly scaling the method again is judged computationally excessive by its authors. |
| 2022–2023 | Exoo construction received a self-contained conceptual audit | Hand-verifiable analysis of the cyclic construction and K43 near-misses | Monochromatic-K5 burden on 43 vertices is a useful shaped objective. |
| 2026 | LLM-evolved search algorithms improved several other Ramsey lower bounds | Diverse structured seeds plus evolved stochastic repair code | Evolve mechanisms and evaluators; do not assume the method has solved or improved `R(5,5)`. |

Sources for this timeline:

- Dynamic Survey: https://www.cs.rit.edu/~spr/ElJC/sur.pdf
- McKay–Radziszowski 1997: https://users.cecs.anu.edu.au/~bdm/papers/r55.pdf
- Exoo construction study: https://arxiv.org/abs/2212.12630
- Angeltveit–McKay `R(5,5)<=46`: https://arxiv.org/abs/2409.15709
- AlphaEvolve Ramsey working paper: https://arxiv.org/abs/2603.09172

## 4. Current structural facts

### 4.1 Degree restrictions

Because `R(4,5)=25`, every vertex `v` of an `(5,5,m)` graph satisfies

```text
m - 25 <= degree(v) <= 24.
```

Consequences:

- a hypothetical 43-vertex witness has every degree in `18..24`;
- a hypothetical 46-vertex graph had every degree in `21..24`, the starting point of the current
  upper-bound proof;
- each vertex neighborhood is an `(4,5,d(v))` graph and each dual neighborhood is an
  `(5,4,m-1-d(v))` graph.

Any generator that spends material time outside these degree bounds is defective. Degree balance is a
necessary constraint, not a sufficient proxy.

### 4.2 Known 42-vertex corpus

McKay's maintained data page supplies 328 graph6 representatives; their complements give the 656
known `(5,5,42)` graphs:

- index: https://users.cecs.anu.edu.au/~bdm/data/ramsey.html
- graph6 data: https://users.cecs.anu.edu.au/~bdm/data/r55_42some.g6

For the 328 representatives with no more edges than their complements, the 1997 paper reports:

- edge counts `423..430`, with class counts `1, 7, 29, 66, 89, 77, 43, 16`;
- all vertex degrees lie in `19..22`;
- 212 have trivial automorphism group;
- the other 116 have one fixed-point-free involution.

These are controls and teacher objects. They are not a proved complete list.

### 4.3 What the historic searches actually established

The 656 set was reached by several routes:

- delete three vertices from known 42-vertex graphs and extend the 39-vertex subgraphs back to 42;
- incremental simulated annealing from a random 30-vertex graph, adding and repairing one vertex at a
  time until 42;
- a similar incremental tabu search;
- long searches in neighborhoods defined by common edges or common subgraphs;
- extension of 100 random 36-vertex subgraphs, generating more than 65 million 42-vertex outputs.

Every generated 42-vertex graph was isomorphic to one of the known 656, and none of the 656 extends by
one vertex to 43. This supports `R(5,5)=43`, but it does **not** exclude an unknown 42-vertex component
or a 43-vertex graph disconnected from those search basins.

The decisive search implication is stronger than “known graphs do not extend”:

> If an `(5,5,43)` graph exists, deleting any one of its 43 vertices gives an `(5,5,42)` graph. None
> of those 43 deletions can be among the known 656, because each known member has been exhaustively
> shown non-extendible.

So a successful 43-vertex construction would contain an entire family of **unknown** 42-vertex
controls. Finding even one new 42-vertex is therefore a meaningful prerequisite/milestone, and search
pressure toward the known 656 can be actively counterproductive.

The Dynamic Survey reports a 2014 McKay–Lieby computation that any unknown 42-vertex graph is at
induced-subgraph distance at least six from every known member: it shares no induced 37-vertex
subgraph with them. The underlying exhaustive artifact is not publicly replayable in our audit, so
store this as a high-confidence reported exclusion, not as an irreversible pruning rule, until it is
reproduced or obtained from the authors.

Radziszowski has also conjectured that below `R(s,t)` an almost-regular Ramsey graph exists
(`Delta-delta <= 1`). None of the known 656 order-42 graphs is almost regular. This creates a sharp,
falsifiable search branch: an almost-regular 42 witness would either expose a new component or, if the
656 catalogue were ever proved complete, refute the general conjecture. Almost-regularity is therefore
a targeted experimental constraint—not a global assumption about all solutions.

### 4.4 Exoo's construction and the 43-vertex near-miss landscape

Exoo starts from a cyclic coloring on 43 vertices. That cyclic coloring has exactly 43 red `K5`s of a
specific translated form and no blue `K5`. Deleting vertex 0 and recoloring sixteen red edges blue
destroys all remaining red `K5`s without creating a blue one, producing the 42-vertex witness.

The 2022–2023 audit studies the same recolorings without deleting vertex 0:

- the first variant has 4 red plus 9 blue monochromatic `K5`s;
- one additional recoloring gives 1 red plus 8 blue;
- the authors report an unpublished remark from Exoo that he had found a 43-vertex coloring with only
  2 monochromatic `K5`s.

Molnár et al.'s 2019 continuous-time MaxSAT experiment independently reports a K43 coloring with two
monochromatic `K5`s, both supported on a six-vertex union. This is the best published optimization
near-solution located in the audit, not a SAT/UNSAT proof and not a Ramsey bound. Recover the exact
supplementary graph, hash it, and independently verify it before admitting it as a trusted seed. Its
four-vertex intersection makes it unusually actionable: deleting any shared vertex destroys both
recorded conflicts, yielding at least four valid 42-vertex deletions to canonicalize against the 656.

Treat 13 and 9 as immediately reconstructible public controls. Treat 2 as a published seed requiring
artifact recovery and independent verification, not as an independently established minimum.

This suggests a useful burden vector for a 43-vertex candidate:

```text
(red_K5_count, blue_K5_count, total_K5_count,
 minimum vertex transversal of violations, violation overlap profile,
 degree-bound violations, canonical graph id)
```

The terminal target is `(0,0,0,...)`. Intermediate reductions are search evidence, not a Ramsey bound.

## 5. Current upper-bound architecture

Angeltveit and McKay proved `R(5,5)<=46` using theory plus two independent computational pipelines.
The proof does not enumerate all graphs on 46 vertices.

The main reduction is:

1. A hypothetical `(5,5,46)` graph has degrees `21..24`.
2. Only edge-dense slices of `(4,5,n)` are needed:
   - `(4,5,24,e>=127)`;
   - `(4,5,23,e>=119)`;
   - `(4,5,22,e>=113)`;
   - `(4,5,21,e=107)`.
3. A subgraph-count/linear-programming excess identity forces enough vertex neighborhoods into these
   exceptional slices.
4. Pointed neighborhood graphs sharing a common `(3,5,d)` intersection are glued along an edge.
5. The theory proves that one of a finite list of gluing configurations must occur; computation excludes
   every configuration.

The first implementation used a simple special-purpose SAT solver and generated 8,485,247
`(5,5,37)` graphs, none extendible to 38. The second used staged propagation/backtracking, Glucose, and
Kissat sanity checks: about 12 million initial overlaps, 5.6 million sent to Glucose, 15,248 survivors
to phase two, 17 to phase three, and none ultimately extendible.

The authors estimate roughly 30 CPU-years for the first pipeline and 50 additional CPU-years for the
independent replication. They explicitly conclude that another upper-bound improvement probably needs
new theoretical insight rather than a direct scale-up.

Our audit found public edge-extremal Ramsey graph data, but not a public end-to-end proof-log package
that a small trusted checker can replay. Therefore:

- cite the published theorem as established mathematics;
- do not represent it as LRAT/Lean/formally replayed;
- treat a reproducibility or formalization project as a separate contribution requiring author contact,
  artifact licensing, and a bounded pilot.

## 6. Search-method trends and their limits

### 6.1 Simulated annealing, tabu search, and sequential growth

These methods found many major Ramsey lower bounds and all known 42-vertex `R(5,5)` controls. For this
cell they repeatedly collapse into the same known basins. A new implementation is valuable first as a
benchmark: can it recover all or a representative spread of the 656, including rare edge-count and
automorphism classes? Only then should it spend on 43.

### 6.2 Algebraic/cyclic seeds plus repair

Quadratic residues, sum-free sets, circulant graphs, Paley-type graphs, and Exoo's cyclic seed have a
long record of success. Integer-programming work establishes the circulant Ramsey number `C(5,5)=41`,
so pure circulant search cannot produce an order-42 or order-43 witness. The best 42 witness itself
requires breaking the original symmetry. Use algebraic structure for initialization and learned move
proposals, then deliberately relax it; do not spend epochs re-proving the closed pure-circulant case.

### 6.3 SAT and cube-and-conquer

SAT is strong when theory and symmetry reduce the space to a finite collection of meaningful cases.
For construction, SAT/MaxSAT can repair a near-miss or complete a partial graph. For nonexistence, every
normalization, cube cover, and UNSAT leaf must be checkable. A solver timeout or a large set of refuted
cubes proves only the recorded region.

### 6.4 Evolved search code

The 2026 AlphaEvolve Ramsey work reports new lower bounds for other cells and groups successful
initializations into random/stochastic, Paley/algebraic, circulant/cyclic, and hybrid/fractal/spectral
families. Its algorithms remain variants of stochastic search, with evolved scoring and repair logic.
It did not report a new `R(5,5)` result. Transfer the meta-method—diverse executable lineages scored by
an exact evaluator—not any claim of success on this cell.

### 6.5 Structural transfer

A 2026 proof-of-concept study extracts motif, compatibility, density, and operator priors from teacher
witnesses and search traces, then refines a portfolio of transferred candidates:

- paper: https://doi.org/10.3390/math14081367
- code: https://github.com/jurjsorinliviu/Transferable-Structural-Search-for-Ramsey-Graph-Construction

Its central caution is useful: similarity to known witness structure can improve while exact Ramsey
validity gets worse. Any transferred representation must be judged by exact `K5`/independent-5 burden,
not motif overlap or spectral resemblance alone. It is a method lead, not evidence about `R(5,5)`.

## 7. Ruled out, saturated, or unsafe routes

These labels are scoped; new evidence can reopen them.

1. **Directly append one vertex to any of the 656 known 42 graphs.** Exhaustively checked in the 1997
   work. Reopen only if the source corpus/hash is wrong or a new 42 is found.
2. **Blindly rerun ordinary simulated annealing/tabu search and call rediscovery progress.** Historic
   searches produced thousands of samples and only the same 656 isomorphism types.
3. **Neighborhood search around known 42 graphs using common edges/subgraphs.** More than a decade of
   historical CPU and a 65-million-output experiment saturated known types. A materially different
   representation or nonlocal surgery is required.
4. **Pure cyclic/circulant search as the whole space.** `C(5,5)=41` closes exact circulants at 42 and
   43. Almost-circulant seeds followed by explicit symmetry breaking remain open.
5. **Scale the `<=46` gluing computation directly to 45.** Its authors say the same method would need
   excessive compute; require a new structural reduction before production-scale enumeration.
6. **Trust structural similarity, neural score, floating-point LP, or LLM judgment as the evaluator.**
   Exact forbidden-subgraph checks and exact rational/certificate checks are mandatory.
7. **Treat 656 as a complete classification.** It is a strong conjecture supported by repeated search,
   not a proved census.
8. **Treat Exoo's reported 2-violation K43 as a verified artifact.** Obtain the graph or reproduce it.
9. **Treat the reported distance-six neighborhood exhaustion as a machine-checkable theorem.** It is
   strong historical evidence, but the replayable coverage artifact was not found in this audit.
10. **Use a conditional one-vertex-extension preprint as `R(5,5)=43`.** The 2024 preprint explicitly
    depends on the incomplete 656 catalogue and acknowledges possible false negatives; it is a method
    lead only.

## 8. Operational strategy portfolio

Each route below has a cheapest discriminator. An epoch must select one route, state its fingerprint,
and stop when the discriminator resolves it.

### S1. Reproducible controls and dual checker

- **Hypothesis:** the maintained 328-representative graph6 corpus plus complements reproduces the
  reported 656 controls and structural statistics.
- **Experiment:** download and hash the corpus; implement independent bitset and straightforward
  combination-enumeration checkers; canonicalize with nauty/Traces; reproduce edge, degree, complement,
  and automorphism summaries.
- **Success:** exact agreement with no shared parsing/checking code.
- **Why first:** every later search depends on the evaluator and corpus.

### S2. K43 near-miss reproduction and Pareto archive

- **Hypothesis:** the public 13- and 9-violation cyclic variants can be reproduced exactly and provide
  useful seeds for lower-burden candidates.
- **Experiment:** reconstruct both from the paper, enumerate all monochromatic `K5`s independently,
  and retain a canonical Pareto archive by burden vector and structural diversity.
- **Success:** both checkers agree on exact violation identities, not just counts.

### S3. Unknown-42 basin search, including an almost-regular branch

- **Hypothesis:** useful 43-vertex search must first escape the known 42-vertex solution component;
  imposing almost-regularity in one branch may expose the conjectured missing class.
- **Mechanism:** destroy at least six vertices jointly, SAT/MaxSAT-repair the boundary, canonicalize
  every valid 42 result, and score novelty by explicit induced-subgraph and relabeled Hamming metrics.
  Run both unrestricted and `Delta-delta<=1` branches; never impose almost-regularity globally.
- **Discriminator:** find a verified 42 graph outside the 656, or prove a precisely bounded structural
  slice empty with a checked certificate. Repeated rediscovery of known classes is a failed epoch.
- **Escalation:** immediately test every novel 42 graph for one-vertex extension with proof logging.

### S4. Six-vertex conflict-core destroy and repair

- **Hypothesis:** the published two-conflict K43 state is trapped by a small coordinated boundary that
  exact local branching can resolve better than unrestricted single-edge moves.
- **Mechanism:** verify the graph; identify the two bad `K5`s and their six-vertex union; freeze the
  exterior, then optimize internal and incident edges. Expand the destroy set `6,8,10,...` using
  persistent-conflict load and learned UNSAT cores.
- **Discriminator:** certified optimum inside each bounded neighborhood plus matched-budget comparison
  with tabu/annealing. A local optimum of two is not a global lower bound.

**2026-07-21 UTC update:** two direct Springer retrievals of Supplementary Data 4 agreed byte-for-byte
at 3,812 bytes and SHA-256 `c2429869f6fa47ab7388134b580b014efae01e6f0e474f5bab2233afb1ef6990`.
Independent Python and C checks found exactly the two reported all-zero `K5`s and no all-one `K5`.
All 903 radius-1 edge flips were exhausted; the minimum burden remains two. The source blocker is closed,
but this is only a certified radius-1 result, not a witness or global bound. The saved next discriminator is
the complete 407,253-pair radius-2 neighborhood under two independent implementations.

### S5. Incremental exact-delta local search

- **Hypothesis:** moves chosen by exact change in the overlapping violation hypergraph outperform raw
  edge-flip annealing on the K43 near-miss benchmark.
- **Mechanism:** cache, for every edge, the set of 5-subsets whose monochromatic status changes;
  prioritize flips or small edge sets that hit multiple violations without creating more; use tabu and
  controlled temperature restarts.
- **Discriminator:** fixed-seed, matched-compute comparison against a basic annealer on recovery of
  known 42 graphs and best K43 burden.

### S6. MaxSAT repair around structured seeds

- **Hypothesis:** a bounded Hamming ball around the 9-violation K43 seed contains a lower-burden graph.
- **Mechanism:** edge variables, hard/soft monochromatic-K5 clauses, cardinality bound on changed edges,
  and exact decoding.
- **Discriminator:** solve radii in increasing order; a SAT model must pass both graph checkers; an
  UNSAT radius needs a proof log checked independently.
- **Limit:** this proves only the Hamming ball, never global nonexistence.

### S7. Nonlocal surgery and regrowth

- **Hypothesis:** removing `k>=2` vertices or a high-violation motif and jointly regrowing `k+1` vertices
  can escape the known one-vertex-extension basin.
- **Mechanism:** select cuts using violation overlap and canonical subgraph rarity, then SAT-complete the
  boundary under exact degree and forbidden-subgraph constraints.
- **Discriminator:** first recover multiple known 42 isomorphism classes from damaged 41/40 controls;
  then compare K43 burden with local search.
- **Caveat:** older 36-to-42 and neighborhood searches were extensive, so novelty requires a clearly
  different selection/encoding and honest benchmark comparison.

### S8. Diverse program-evolution portfolio

- **Hypothesis:** evolving search programs across four initialization families finds mechanisms that a
  hand-written single annealer misses.
- **Families:** random/stochastic, Paley/algebraic, cyclic/Exoo, and transferred motif/operator seeds.
- **Evaluator:** exact burden first; runtime/memory, archive novelty, and robustness second.
- **Discriminator:** reproduce known bounds on small control cells and the R55 42-vertex benchmark
  without memorized adjacency matrices; then run matched budgets at 43.

### S9. Structural-prior transfer with validity firewall

- **Hypothesis:** motifs and repair operators shared by diverse known 42 graphs predict productive moves
  at 43 even when raw graph similarity does not.
- **Mechanism:** learn distributions of degree pairs, common-neighbor counts, small induced subgraphs,
  orbit/automorphism features, and successful repair traces; use them only to propose moves.
- **Discriminator:** ablate each prior under matched compute; retain it only if exact burden improves
  out of sample across seeds.

### S10. Exact inequality discovery for the upper route

- **Hypothesis:** edge-extremal `(4,5,n)` catalogues contain a short integer subgraph-count inequality
  that strengthens degree/neighborhood restrictions for hypothetical `(5,5,45)` graphs.
- **Mechanism:** generate candidate linear inequalities from exact feature tables, solve the dual LP,
  rationalize coefficients, then derive the inequality by explicit double counting.
- **Discriminator:** inequality holds on all available catalogue controls and cuts a nonempty family of
  previously admissible degree/neighborhood profiles; otherwise discard.
- **Rule:** machine-discovered coefficients are only a conjecture until an exact proof is written.

### S11. Certified small-case gluing pilot

- **Hypothesis:** one published small Ramsey or one tiny slice of the `<=46` architecture can be replayed
  with deterministic CNF generation, checked symmetry reduction, cube cover, and LRAT/DRAT leaves.
- **Discriminator:** full replay from source data with a separate checker and semantic mutation tests.
- **Value:** validates infrastructure and may expose a bounded formalization/reproducibility contribution;
  do not launch an 80-CPU-year replication.

### S12. Ramsey multiplicity subproblem at 43

- **Hypothesis:** the minimum number of monochromatic `K5`s in a two-coloring of `K43` is small and may be
  attacked more effectively as an optimization landscape than raw SAT.
- **Milestones:** reproduce public upper bound 9; obtain/verify the reported 2 or independently match it;
  seek structural relations among every minimum candidate's violations.
- **Terminal meaning:** a zero witness proves `R(5,5)>=44`; a checked global lower bound of one proves
  `R(5,5)=43`. Anything else is a scoped multiplicity result.

### S13. LDPC trapping-set atlas for recurrent Ramsey failure cores

**Transfer source.** In iterative error-correcting-code decoding, the global error floor can be dominated
by small, recurrent, decoder-dependent subgraphs called trapping sets. Richardson's original workflow is
especially relevant: enumerate candidate failure cores up to symmetry, measure which cores dominate, and
study overlapping clusters rather than treating every failed trajectory as unrelated. This is an analogy,
not a claim that Ramsey constraints are parity checks.

- **Ramsey representation:** use the 903 edge-color bits at `n=43` as variable nodes. Use violated `K5`
  checks and one-flip-from-violated `9:1` five-sets as colored active check nodes. From the final window of
  each failed deterministic run, retain edges that oscillate or remain incident to active checks and
  canonicalize the resulting colored bipartite core under vertex relabeling.
- **Hypothesis:** a small number of canonical active-core types account for a disproportionate fraction of
  low-energy stalls. Small exact MaxSAT solves on a core plus its boundary can then produce escape
  templates that transfer to held-out trajectories.
- **Cheapest discriminator:** collect fixed-seed traces from damaged held-out order-42 controls before a
  frontier run. Compare core recurrence with label-shuffled controls, then train templates on one split and
  require improved paired held-out time-to-escape or best exact burden under identical evaluator calls.
- **Stop conditions:** discard the transfer if active cores almost always percolate, are nearly unique, or
  template moves merely cycle. Never use a core score as witness validation; the full exact checkers remain
  the validity gate.

Primary source: https://web.stanford.edu/class/ee388/papers/ErrorFloors.pdf

### S14. Linkage-tree optimal mixing for overlapping edge epistasis

**Transfer source.** Gene-pool Optimal Mixing Evolutionary Algorithms learn which variables should be moved
together and greedily test donor subsets. Direct MAX-SAT experiments found that dynamically learned linkage
can outperform a fixed decomposition even when the visible factor structure is known. That warning fits
Ramsey search: every edge belongs to many overlapping five-set constraints, so “same `K5`” is not
automatically the best recombination block.

- **Mechanism:** retain a diverse population of exact low-burden colorings. Each generation, build separate
  linkage trees from elite-population mutual information, active-constraint co-occurrence, and a hybrid of
  the two. Traverse subsets from small to large, copy a subset from a donor, and retain it only when the
  exact incremental evaluator and an explicit archive-diversity rule accept it. Include univariate and
  uniform-crossover arms as negative controls.
- **Hypothesis:** learned multi-edge blocks preserve useful epistatic partial structures and escape
  single-edge local minima more reliably than ordinary crossover or exact-delta tabu.
- **Cheapest discriminator:** split complement pairs and isomorphism families before creating 6-to-12-edge
  damaged order-42 controls. Under paired seeds and equal evaluator calls, require higher held-out valid-42
  recovery and lower median burden than univariate mixing, uniform crossover, and tabu before using K43
  budget.
- **Failure modes:** near-clonal populations produce false linkage; dense overlap collapses the tree into
  unhelpful giant blocks; greedy acceptance forbids necessary uphill moves; damaged-42 recovery fails to
  predict K43 behavior. Treat each as an ablation, not a tuning excuse.

Primary sources: https://ir.cwi.nl/pub/22078 and https://arxiv.org/abs/2109.05259

### S15. Adjacency-row code moments and a Terwilliger-style upper-route filter

**Transfer source.** Coding theory bounds a binary code through exact weight, distance, and triple-
intersection distributions; Schrijver's Terwilliger-algebra SDP strengthens pairwise Delsarte bounds and has
a constant-weight form. A Ramsey adjacency matrix supplies a constrained binary code—its rows—but not an
ordinary free code, so off-the-shelf numerical bounds are only a first relaxation.

For adjacency rows `a_u,a_v`, degrees `d_u,d_v`, and `c_uv=|N(u) intersect N(v)|`, the exact identity is

```text
d_H(a_u,a_v) = d_u + d_v - 2 c_uv.
```

There is also an elementary pair constraint from `R(3,5)=14`:

- if `uv` is an edge, its common-neighbor graph contains neither a triangle (which would complete a `K5`
  with `u,v`) nor an independent 5-set, so `c_uv<=13`;
- if `uv` is a nonedge, its common-nonneighbor graph contains neither an independent triple (which would
  complete an independent 5-set with `u,v`) nor a `K5`, so that set also has size at most 13.

This is a proved input constraint, not a new Ramsey bound.

- **Hypothesis:** pair and triple row-code moments exclude at least one degree/common-neighbor profile that
  survives the current scalar degree and excess constraints.
- **Cheapest discriminator:** extract exact row weight/intersection distributions from all authenticated
  order-42 controls. First solve a rational pair-distance LP for hypothetical `n=43..45` profiles. Stop and
  archive the negative result if it cuts nothing new. Only after a nonempty exact cut, add Schrijver-style
  triple-intersection PSD blocks and finally a colored edge/nonedge refinement.
- **Validity gate:** every known control must remain feasible. Floating-point duals are conjecture generators
  only; rationalize any useful dual into an exact inequality or checked pseudo-Boolean certificate.
- **Main risk:** an ordinary code relaxation loses adjacency symmetry, the zero diagonal, and the edge/
  nonedge pair color. Do not invest in the custom coherent-configuration model unless the cheap relaxation
  changes at least one profile decision.

Primary sources: https://ir.cwi.nl/pub/14098 and the `R(3,5)=14` entry in
https://www.cs.rit.edu/~spr/ElJC/ejcram18.pdf

## 9. Combining ideas without making analogy soup

Use at most three transfers in one epoch and attach a prediction to each:

| Transfer | Operational prediction | Cheap test |
|---|---|---|
| Exoo near-miss + MaxSAT | Small coordinated edge sets beat single flips | Exhaust Hamming radii 1–3 with proof logs. |
| Known-42 corpus + structural transfer | Repair operators, not raw motifs, transfer to 43 | Trace operators on held-out 42 controls, then ablate at 43. |
| AlphaEvolve + exact evaluator | Program diversity beats one tuned annealer | Matched-compute tournament on small cells and K43 burden. |
| 46-proof LP + data mining | Dense neighborhood catalogues imply a short new exact inequality | Learn coefficients, rationalize, and falsify on all controls. |
| Graph gluing + nonlocal surgery | Joint boundary completion escapes direct-extension dead ends | Recover held-out 42 graphs after deleting 2–4 vertices. |
| Violation hypergraph + hitting set | High-overlap violation transversals identify productive compound moves | Compare predicted versus actual burden delta on controls. |
| Almost-regular conjecture + unknown-42 implication | A constrained 42 search reaches a basin absent from the 656 | SAT/MaxSAT at 42 with explicit degree-spread constraint and canonical novelty checks. |
| Two-conflict core + exact local branching | Small nonlocal repair neighborhoods reveal whether the best seed is locally rigid | Certify success or minimum two for increasing destroy sets. |
| LDPC trapping sets + exact core MaxSAT | A few canonical active cores dominate stalled trajectories | Recurrence versus shuffled cores, then held-out template escape under matched calls. |
| GOMEA linkage learning + exact delta evaluation | Learned edge blocks transfer useful epistatic structure better than whole-bitstring crossover | Leakage-safe damaged-42 recovery tournament before K43. |
| Coding-theory moments + adjacency-row identities | Pair/triple distributions remove profiles missed by scalar counts | Rational pair LP first; stop before SDP if it cuts nothing. |

Discard a transfer when the stated prediction fails. Do not preserve it as inspirational prose.

## 10. Verification architecture

### Witness path

1. Normalize and hash adjacency artifact.
2. Checker A: transparent enumeration of all `C(n,5)` subsets.
3. Checker B: independent bitset/clique implementation in another language or representation.
4. Verify simplicity, vertex count, symmetry of adjacency, no loops, degree bounds, complement behavior.
5. Semantic mutation tests: add known `K5`, add known independent 5-set, corrupt one edge, truncate input.
6. Canonicalize and compare with known corpus.

### Nonexistence path

1. Formal statement-to-CNF correspondence.
2. Deterministic generator plus independent semantic audit on small instances.
3. Sound symmetry-breaking proof or mechanically checked canonical augmentation.
4. Explicit pairwise-disjoint/exhaustive cube cover.
5. Proof-logged UNSAT leaves; decoded independently checked SAT leaves.
6. Independently verify every proof and the cover; preserve hashes and resource records.
7. Isolated skeptic receives statement, artifacts, schema, and hashes—not the researcher's narrative.

### Hard metadata gates

Every nonexistence claim must separately record:

```text
claim_class, verification_level, encoding_soundness, cover_completeness,
symmetry_soundness, checker_independence, artifact_availability
```

Automatically reject: UNSAT without a proof log; cubes without a checked cover; isomorphism or
symmetry pruning without a coverage argument; catalogue counts without orbit coverage; and any
artifact lacking immutable hashes. “Two independent implementations agree” is powerful evidence, but
it is not the same verification level as an end-to-end replayable certificate.

### Verification ladder and reusable precedents

1. **Controls:** mirror and hash the 328 representatives, derive complements, use two checkers in
   separate representations/languages, and test all `2*C(43,5)=1,925,196` forbidden-color clauses.
2. **Toy proof:** reproduce `R(3,3)=6` with LRAT-Catcher plus `cake_lpr`; scale only after the entire
   cube cover and theorem boundary replay.
3. **Bounded R55 slices:** certify one-vertex extensions, local MaxSAT neighborhoods, or a tiny gluing
   family before attempting a frontier-wide exclusion.
4. **Formal boundary:** separately prove encoding soundness, degree restrictions, excess/counting
   identities, gluing coverage, and the link from refuted leaves to the Ramsey theorem.
5. **Archive packet:** source, environment, schemas, input/output hashes, logs, checker versions, and a
   cold-start replay script.

Relevant models are the HOL4 proof of `R(4,5)=25`, the SAT+CAS certificate proof of `R(3,8)=28` and
`R(3,9)=36`, and the new Lean/LRAT-Catcher `R(4,4)=18` demonstration. They show that exact Ramsey
verification is possible, while their storage/memory footprints warn against treating formal replay as
cheap. SMS and VeriPB are promising for symmetry and pseudo-Boolean/excess arguments, but must be
benchmarked as components rather than trusted by reputation.

## 11. External validation and likely experts

The most directly relevant current researchers/maintainers are:

- Brendan McKay: 42-graph corpus, upper-bound history, nauty/Traces, 2024/2026 theorem.
- Vigleik Angeltveit: independent upper-bound implementation and edge-extremal catalogues.
- Stanisław Radziszowski: Dynamic Survey and historical small-Ramsey record.
- Geoffrey Exoo: 1989 lower-bound construction, heuristic construction methods, reported 2-violation
  K43 near-miss.
- Marijn Heule and the SAT+CAS/formal-verification community: certificate-carrying combinatorial proofs.
- AlphaEvolve Ramsey authors: current program-evolution algorithms and public lower-bound artifacts.

Do not contact anyone automatically. After an independently reproduced, precisely scoped artifact,
Charlie may approve one concise email asking whether prior work was missed and what acceptance channel
is appropriate.

## 12. Source registry

### Core status and history

- Dynamic Survey 1, *Small Ramsey Numbers*: https://www.cs.rit.edu/~spr/ElJC/sur.pdf
- 2017 revision containing the McKay–Lieby distance report and almost-regular conjecture discussion:
  https://www.cs.rit.edu/~spr/PUBL/sur14.pdf
- McKay–Radziszowski, *Subgraph Counting Identities and Ramsey Numbers*:
  https://users.cecs.anu.edu.au/~bdm/papers/r55.pdf
- McKay data index and 42-vertex graph6 corpus:
  https://users.cecs.anu.edu.au/~bdm/data/ramsey.html
  and https://users.cecs.anu.edu.au/~bdm/data/r55_42some.g6
- Exoo's construction archive: https://cs.indstate.edu/ge/RAMSEY/index.html

### Lower-bound understanding and search

- Ge–Jayasooriya–Qiu–Sun–Yuan, *Study of Exoo's Lower Bound*:
  https://arxiv.org/abs/2212.12630
- Piwakowski, *Applying Tabu Search to Determine New Ramsey Graphs*:
  https://doi.org/10.37236/1230
- Nagda–Raghavan–Thakurta, *Reinforced Generation of Combinatorial Structures: Ramsey Numbers*:
  https://arxiv.org/abs/2603.09172
- Public AlphaEvolve improved-bound artifacts:
  https://github.com/google-research/google-research/tree/master/ramsey_number_bounds/improved_bounds
- Jurj, *Transferable Structural Search for Ramsey Graph Construction*:
  https://doi.org/10.3390/math14081367
- Molnár et al., continuous-time MaxSAT and the two-conflict K43:
  https://doi.org/10.1038/s41467-018-07327-2
- Furini–Ljubić–San Segundo, circulant integer-programming search (`C(5,5)=41`):
  https://optimization-online.org/wp-content/uploads/2021/09/8578.pdf
- Kunkel, historical genetic search baseline:
  https://www.micsymposium.org/mics_2003/Kunkel.PDF
- Fox–Wigderson, Ramsey multiplicity and the known-42 landscape:
  https://ywigderson.math.ethz.ch/math/static/RamseyMultiplicity.pdf
- Engström, subgraph-count identities as an inequality source:
  https://arxiv.org/abs/1002.4304

### Cross-field method sources

- Richardson, *Error Floors of LDPC Codes* (trapping-set enumeration and clustered failure cores):
  https://web.stanford.edu/class/ee388/papers/ErrorFloors.pdf
- Sadowski–Bosman–Thierens, *On the Usefulness of Linkage Processing for Solving MAX-SAT*:
  https://ir.cwi.nl/pub/22078
- Dushatskiy et al., *Parameterless Gene-pool Optimal Mixing Evolutionary Algorithms*:
  https://arxiv.org/abs/2109.05259
- Schrijver, *New Code Upper Bounds from the Terwilliger Algebra and Semidefinite Programming*:
  https://ir.cwi.nl/pub/14098

### Upper bounds and computational proof

- Angeltveit–McKay, `R(5,5)<=46`: https://arxiv.org/abs/2409.15709
- Angeltveit–McKay, `R(5,5)<=48`: https://arxiv.org/abs/1703.08768
- Edge-extremal `(4,5)` graph data: https://users.cecs.anu.edu.au/~bdm/data/ramsey.html
- Direct edge-extremal archives: https://users.cecs.anu.edu.au/~bdm/data/r45extreme.tar.gz and
  https://users.cecs.anu.edu.au/~bdm/data/r45_24.g6
- nauty/Traces: https://pallini.di.uniroma1.it/
- DRAT-trim: https://github.com/marijnheule/drat-trim
- LRAT verified-checker background: https://www.cs.utexas.edu/~marijn/publications/lrat.pdf
- HOL4 exact proof of `R(4,5)=25`: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ITP.2024.16
- Released HOL4 Ramsey code: https://github.com/barakeel/ramsey
- Certificate-verified `R(3,8)` and `R(3,9)` paper and artifacts:
  https://arxiv.org/abs/2502.06055 and https://github.com/ConDug/MathCheckRamsey
- LRAT-Catcher Lean pipeline: https://arxiv.org/abs/2607.00815 and
  https://github.com/leansolving/lrat-catcher
- `cake_lpr` verified checker: https://cakeml.org/checkers.html
- SAT Modulo Symmetries: https://doi.org/10.1145/3670405 and
  https://sat-modulo-symmetries.readthedocs.io/
- VeriPB: https://veripb.org/
- Gauthier, exploratory HOL4/SAT route toward `R(5,5)<=43`:
  https://aitp-conference.org/2025/abstract/AITP_2025_paper_3.pdf
- Conditional one-vertex-extension method preprint (not an unconditional bound):
  https://arxiv.org/abs/2411.04267

## 13. Required first research epoch

Before original search:

1. Fetch and hash `r55_42some.g6`.
2. Implement two independent exact checkers.
3. Reproduce corpus validity, complement pairs, edge/degree distributions, and canonical uniqueness.
4. Reconstruct and verify the public 13- and 9-violation K43 controls from the Exoo study.
5. Record the first mismatch and stop; do not silently repair source data.

Only after these controls pass should the engine choose among S3–S15. The authenticated order-42 corpus
and publisher K43 seed now permit the held-out-control discriminators in S13–S15. The current direct K43
continuation is S4's complete radius-2 enumeration; S3 remains the default route into a genuinely unknown
order-42 basin. Neither control gate nor radius-1 exhaustion changes the Ramsey bound.
