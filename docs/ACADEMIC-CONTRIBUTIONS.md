# Academic contribution strategy

## North star

Maximize expected **externally verified, net-new scholarly credit** per unit of compute and human
review. A self-published page, an unverified model claim, or a larger repetition of a known record
scores zero until a relevant outside community accepts or confirms it.

The selector approximates:

```text
P(still novel) × P(technical success) × P(independent verification)
× P(external acceptance) × contribution value
───────────────────────────────────────────────────────────────
compute cost + human review burden
− integrity and reputation risk
```

The live heuristic begins with problem difficulty, certificate quality, likely contribution value,
review cost, and novelty risk. It adds an exploration bonus and learns from accepted wins by boosting
targets that share contribution types or techniques. It retains rotation so early guesses do not
trap the portfolio.

## Ranked target classes

1. Finite counterexamples and explicit combinatorial constructions with tiny checkers.
2. Improvements to best-known exact constructions in maintained field repositories.
3. Small exact optima with a matching SAT/SMT/ILP or exhaustive certificate.
4. Research-connected OEIS extensions, formulas, corrections, and cross-references.
5. Formalization gaps and reusable lemmas accepted upstream.
6. Exhaustive classifications one parameter beyond current literature.
7. Exact solver or research-software improvements on recognized benchmarks.
8. Narrow questions explicitly left open in recent papers.
9. Motivated prime/integer records with a certificate and recognized registry.
10. Famous universal conjectures, confined to the permanent hard lane.

Do not target “the next largest prime”: there is no largest prime, and recognized record searches are
mature compute competitions. Prefer a mathematically motivated prime property, an algorithmic
improvement, or a gap in a recognized table.

## Model and compute roles

- Sol/xhigh is the research lead for theorem synthesis, representations, cross-domain transfer,
  experiment design, and diagnosing why promising routes fail.
- Terra/high is the default discovery researcher and implementation engineer.
- Deterministic scripts, exact solvers, CAS, proof assistants, and independent checkers perform
  enumeration and validation. The model should spend tokens choosing discriminating experiments,
  not manually simulating them.
- Luna or another efficient model may later handle high-volume source triage only after an eval shows
  it preserves statement and citation accuracy. “Fable” is not a documented current OpenAI model
  role and is not hard-coded.

## Portfolio

- 55% finite witnesses, constructions, and adjacent parameter records.
- 20% exact optimization and classifications.
- 15% formalization, datasets, and research software.
- 10% one famous Sol/xhigh moonshot, twice daily.

Every target must have a claim contract: exact statement, source/status date, novelty definition,
success certificate, independent checker, recognized external channel, likely expert/maintainer,
resource estimate, and stop conditions.

A daily Terra scout searches the versioned source registry and adds at most one cross-field target.
The scout must supply a primary/current source and a real outside acceptance channel. Because target
selection is still model-generated, the first research pass re-audits status and literature before
technical work; an invalid or duplicate lead is a failed intake, not research progress.

## Publication ladder

`candidate → independently reproduced → Charlie-approved packet → public research note → expert or
repository confirmed → venue accepted → peer reviewed`

One Charlie approval action creates and releases a versioned packet on the website and GitHub. The
packet contains the precise claim, evidence, code locations, hashes, citation metadata, scope limits,
human review note, a bounded copy of the actual artifacts, novelty trail, AI disclosure, and venue
plan. Mechanical publication is automated;
expert email, OEIS submission, formal-library PR, arXiv/journal submission, and irreversible DOI
release remain explicit human actions.

Human approval sets `human_approved`; it does not count as a selector win. Only a sourced
`expert-confirmed`, `repository-accepted`, `venue-accepted`, or `peer-reviewed` validation changes
`accepted_result` and reinforces that contribution type or technique family.

Bundle related tiny results into coherent notes. Do not bulk-submit AI-generated sequences, mass
email academics, buy authorship, use predatory venues, or represent self-publication as peer review.

## External credit routes

- OEIS requires a human author responsible for correctness and prohibits bulk/serial AI submissions:
  <https://oeis.org/wiki/Use_of_AI_for_OEIS_Submissions>
- Zenodo can assign a DOI to immutable, versioned software, data, and publication artifacts:
  <https://help.zenodo.org/docs/deposit/about-records/>
- Mathlib accepts scoped, kernel-checked formal contributions:
  <https://github.com/leanprover-community/mathlib4>
- House of Graphs accepts interesting extremal graphs and counterexamples:
  <https://houseofgraphs.org/help>
- GIMPS illustrates the independent verification standard for prime records:
  <https://www.mersenne.org/various/math.php>
- AMS guidance requires human accountability and AI-use disclosure:
  <https://www.ams.org/notices/202401/rnoti-p93.pdf>

External outreach is one precise 120–180 word email to the most relevant maintainer or recent author
after independent reproduction. Ask whether prior work was missed; disclose AI; link the packet. Send
at most one follow-up after 10–14 days. Never auto-send.
