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

Each run pursues one bounded route. The prompt retrieves prior approach summaries and requires the
new route to differ materially. Useful outputs include:

- a finite witness with an independent checker;
- a smaller equivalent search space;
- an exact parametric identity;
- a congruence or SAT cover with a checkable certificate;
- a formally stated lemma;
- a rigorously falsified approach that should not be repeated.

The approach archive follows the useful part of AlphaEvolve's pattern: preserve candidate programs
and strategies, score them only through objective evaluators, and let future runs mutate the most
promising artifacts. Eloquence is never an evaluator.

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

## Initial lanes

- **Hard:** Erdős–Straus (#242), because it is famous, exact, formally stated, computationally
  falsifiable, and has concrete congruence/parametric subgoals. Two Sol/xhigh runs per UTC day.
- **Discovery:** Erdős #647 first. A positive answer is one integer and a bounded divisor-count
  certificate. Then rotate through other finite-witness problems using difficulty, source quality,
  formalization availability, and non-duplication of existing AI attempts.

## Sources used to design this harness

- <https://github.com/teorth/erdosproblems>
- <https://github.com/teorth/erdosproblems/wiki/Getting-started-with-using-AI-for-research-mathematics>
- <https://github.com/teorth/erdosproblems/wiki/What-to-do-when-I-think-I-managed-to-get-AI-to-solve-an-Erd%C5%91s-problem%3F>
- <https://github.com/google-deepmind/formal-conjectures>
- <https://lean-lang.org/doc/reference/latest/>
- <https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/>
- <https://leidendeclaration.ai/>
