# Proof Factory

An always-on, certificate-first academic contribution system.

Its north star is **the smallest legitimate, independently verifiable net-new contribution with the
highest expected external scholarly credit per unit of compute and human review**. Fame is a
tie-breaker, not the objective. Full proofs are only one eligible output alongside finite witnesses,
exact optima, exhaustive classifications, new or corrected sequences, formalizations, datasets,
research software, computational bounds, and narrow lemmas.

The public ledger at `proofs.charliekrug.com` shows every queued, active, failed, progressive,
candidate, verified, and published attempt. The system separates two research lanes:

- **Hard lane:** one famous finite exact problem receives an hourly launch opportunity around the clock.
  It currently targets `R(5,5)`. Each epoch uses two GPT-5.6 Terra/high reconnaissance delegates and
  one GPT-5.6 Sol/xhigh principal; a 43-vertex Ramsey graph is a compact lower-bound witness and upper
  bounds require checked exhaustive certificates.
- **Discovery lane:** twelve daily Sol/high + Terra/high delegated passes rotate through approachable, objectively
  checkable contributions. A daily source-only intake currently keeps a 12-problem frontier from
  the versioned Erdős Problems database; the schema and selector support broader contribution types.
  Three bounded non-error passes park a target only when no actionable lead or untried strategy remains.

The system never equates model confidence with proof, and a model cannot promote its own output.
`candidate` is a fail-closed contribution-gate result, not a confidence label: it requires a meaningful
delta from URL-backed prior work, reproducible novelty searches, a named outside acceptance path,
independent validation beyond another local implementation, and evidence that the result advances a
recognized target. Arbitrary cutoff extensions remain `internal result`. A result may be called solved
only after statement validation, independent criticism, literature review, reproducible verification,
and a remembered human approval.

## Commands

```bash
python3 -m proof_factory render
python3 -m proof_factory status
python3 -m proof_factory tick --lane easy
python3 -m proof_factory tick --lane hard
python3 -m proof_factory watchdog
python3 -m proof_factory doctor
python3 -m proof_factory intake --target 12
python3 -m proof_factory scout
python3 -m proof_factory strategy-lab
python3 -m proof_factory backfill-state
python3 -m proof_factory brain-build
python3 -m proof_factory lab-status
python3 scripts/submit_lab.py --problem PROBLEM --name NAME --hypothesis H --expected-signal S -- python3 search.py
python3 -m proof_factory review --attempt ID --decision reject --reviewer "Proof Factory contribution gate" --note "..."
scripts/approve-and-publish.sh ATTEMPT_ID "human review note"
python3 -m proof_factory validate --attempt ATTEMPT_ID --state expert-confirmed --source-url URL --note "..."
```

`tick` launches Codex headlessly with ChatGPT subscription authentication. API-key variables are
cleared before every model run, so there is no metered model fallback. Terra reconnaissance is stored
as a hashed advisory memo, then injected into the Sol principal prompt; model agreement never counts
as independent verification.

## Evidence model

- `data/problems.json` is the versioned problem registry.
- `data/attempts.jsonl` is append-only research history.
- `data/research_states/<problem>.json` is the durable, resumable research map: strategy fingerprints,
  established facts, scoped negative results, reopen conditions, open leads, and the next first action.
- Every problem must complete a source/status baseline before its first technical pass. That baseline
  maps prior work, known facts, ruled-out routes, current leads, tools/artifacts, verification cost,
  and the outside acceptance path; later status changes can explicitly invalidate it.
- `state/research_brain.json` and `/brain/` are generated knowledge-graph projections over the canonical
  registry, research maps, append-only attempts, citations, concepts, and strategies. Agents receive
  the relevant backlinks and neighboring problems in every prompt; a graph link is a transfer
  hypothesis, never proof.
- `data/strategy_library.json` contains executable cross-problem methods. A daily source-grounded
  strategy lab can add or materially improve one entry; every revision is appended to
  `data/strategy_proposals.jsonl`.
- `data/validations.json` records externally observable outcomes; only positive external validation
  teaches the selector that a contribution family is a win.
- `data/source_registry.json` routes a daily Terra scout across current papers and maintained
  community repositories. One sourced candidate is added per run; its first research pass must audit
  status and novelty again before doing technical work.
- `state/runtime.json` is an atomic operational projection.
- `research/<problem>/` holds literature notes, code, formalizations, and certificates.
- `research/<problem>/workspace/lab-queue/` accepts validated shell-free simulation jobs. The cloud lab
  runs one low-priority job at a time in hash-recorded segments, requires checkpoints for multisegment
  searches, and can resume for at most seven 24-hour segments.
- `skills/computational-researcher/` is the injected principal-investigator operating contract and
  deterministic experiment recorder.
- `publications/<attempt>/` is generated only after human approval and contains a research note,
  citation metadata, hashes, and an external-validation plan.
- `site/` is a static projection deployed to Cloudflare Pages after state changes.

The first record is a credited reproduction of the 2026 Jacobian counterexample. It calibrates the
verification and publishing path and is not counted as an original result.

## Sources and standards

- [Erdős Problems database](https://github.com/teorth/erdosproblems)
- [Google DeepMind Formal Conjectures](https://github.com/google-deepmind/formal-conjectures)
- [Lean 4](https://lean-lang.org/doc/reference/latest/)
- [Leiden Declaration on AI and Mathematics](https://leidendeclaration.ai/)

AI and computational tool use is disclosed per attempt. Charlie Krug is responsible for anything
he approves for publication.
