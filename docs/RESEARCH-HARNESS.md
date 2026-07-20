# Research harness

The harness is designed around the failure modes documented by the Erdős Problems community and the
Leiden Declaration: wrong problem statements, missed literature, sycophantic self-review, plausible
but invalid prose, and publicity before community evaluation.

## Intake

- Treat `teorth/erdosproblems` as a versioned index, not infallible truth.
- Save the canonical problem URL and follow its original-source citations.
- Prefer records marked `verifiable`, `falsifiable`, or `decidable`, especially those already
  formalized in Google DeepMind's Formal Conjectures repository.
- Define the success certificate before scheduling work.
- Recheck source status before every candidate is escalated; obscurity often masquerades as novelty.

## Attempt design

The project has no preset endpoint, but each run is a bounded, restartable epoch. The prompt loads a
compact durable map rather than a shallow chat transcript. Every epoch identifies a stable strategy
family and mechanism, chooses the cheapest discriminator, and leaves an objective, exact first action,
and stop condition. Useful outputs include:

- a finite witness with an independent checker;
- a smaller equivalent search space;
- an exact parametric identity;
- a congruence or SAT cover with a checkable certificate;
- a formally stated lemma;
- a rigorously falsified approach that should not be repeated.

The approach archive follows the useful part of AlphaEvolve's pattern: preserve candidate programs
and strategies, score them only through objective evaluators, and let future runs mutate the most
promising artifacts. Eloquence is never an evaluator.

The portfolio also borrows concrete mechanisms from FunSearch (executable candidates plus an objective
evaluator and diverse archive), the AI co-scientist system (independent generation, reflection, ranking,
evolution, proximity checks, and synthesis), and LeanDojo/LeanAgent (retrieval-guided formal work and a
continuing curriculum). These are method templates, not evidence that any mathematical claim is true.

The problem-specific map distinguishes `proposed`, `active`, `promising`, `blocked`, `ruled_out`,
`exhausted`, and `superseded`. Negative results always carry their exact scope; dead routes carry an
explicit reopen condition. A daily strategy lab browses current primary sources and can change the
global library only by supplying an executable experiment, evaluator/discriminator, applicability
condition, and named failure modes.

The injected `computational-researcher` skill makes the agent behave as a principal investigator:
translate a claim into one falsifiable hypothesis, choose a discriminating test, write a deterministic
harness, and use exact computation for repetition. `scripts/run_experiment.py` runs argv without a
shell and records seeds, limits, stdout/stderr, platform data, and hashes under the problem workspace.

The north star and broader target taxonomy live in `docs/ACADEMIC-CONTRIBUTIONS.md`.

## Verification ladder

1. **Statement check:** compare natural language, original source, and third-party formalization.
2. **Adversarial examples:** test boundaries and unused hypotheses.
3. **Exact checker:** rational/integer arithmetic, SAT certificate, exhaustive finite check, or CAS
   identity with a separately written verifier.
4. **Formal kernel:** use a pinned Lean/mathlib/Formal Conjectures snapshot when feasible. A Lean
   proof validates the formal statement, so the translation itself still requires independent review.
5. **Isolated skeptic:** start from the statement and candidate artifact, not the researcher's full
   chain of thought or confidence.
6. **Post-candidate literature search:** backward and forward citations, MathSciNet/zbMATH/Scholar,
   recent arXiv, MathOverflow, and the problem page's comments.
7. **Human approval:** Charlie records accept, reject, or needs-work. Accepted means ready for wider
   expert/community review, not that a blog replaces peer review.

Before step 5, the deterministic contribution gate separates a correct internal experiment from a
candidate scholarly contribution. Model-declared candidates fail closed unless they show meaningful
delta, reproducible novelty work, a named acceptance channel, independent validation beyond another
local implementation, and sourced relevance to a recognized target. Arbitrary range extensions are
explicitly rejected unless they improve the actual best-known bound, answer a source's request, have
confirmed expert interest, or produce a structural result. The original model outcome remains in the
immutable record; a gate adjudication controls the public label.

## Initial lanes

Before either lane performs technical work on a newly selected problem, its first Sol-Terra epoch is
a mandatory research baseline: verify statement and live status, trace closest prior work, inventory
facts and artifacts, scope negative results, identify open leads and tools, estimate verification and
compute cost, and name a legitimate external acceptance path. The resulting facts, exclusions, leads,
and first discriminator become durable state and feed the cross-problem research brain.

- **Hard:** Exact `R(5,5)`, because the remaining question is finite and every meaningful result has a
  checkable artifact. A 43-vertex graph with no 5-clique or independent 5-set gives a compact lower-bound
  witness; an upper-bound improvement requires a deterministic encoding, checked SAT/UNSAT leaf proofs,
  and an exhaustive checked cover. Hourly Sol/xhigh principal runs, each preceded by two bounded
  Terra/high delegate memos, continue the audited research map around the clock. Locks prevent overlap
  within the lane; missed starts are not fabricated. Construction and certificate-carrying reduction
  work remain distinct rather than extending an open-ended verification range.
- **Discovery:** Erdős #647 first. A positive answer is one integer and a bounded divisor-count
  certificate. Twelve daily Terra-delegate → Sol-principal epochs rotate through other finite-witness
  problems using difficulty, source quality, formalization availability, and non-duplication of
  existing AI attempts.

Long simulations never run through ad hoc `nohup`, `screen`, `tmux`, or shell backgrounding. Agents
submit an argv-only lab job with a hypothesis, decisive signal, seed, memory/time ceiling, source URLs,
and—when spanning multiple segments—a workspace checkpoint. The cloud worker runs one job at low
priority, records hashes and logs through the experiment harness, and automatically resumes only when
a timed-out segment produced the declared checkpoint.

## Sources used to design this harness

- <https://github.com/teorth/erdosproblems>
- <https://github.com/teorth/erdosproblems/wiki/Getting-started-with-using-AI-for-research-mathematics>
- <https://github.com/teorth/erdosproblems/wiki/What-to-do-when-I-think-I-managed-to-get-AI-to-solve-an-Erd%C5%91s-problem%3F>
- <https://github.com/google-deepmind/formal-conjectures>
- <https://lean-lang.org/doc/reference/latest/>
- <https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/>
- <https://doi.org/10.1038/s41586-023-06924-6>
- <https://arxiv.org/abs/2506.13131>
- <https://doi.org/10.1038/s41586-026-10644-y>
- <https://arxiv.org/abs/2306.15626>
- <https://leandojo.org/leanagent.html>
- <https://leidendeclaration.ai/>
