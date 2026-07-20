# Proof Factory

An always-on, certificate-first research system for open mathematics problems.

The public ledger at `proofs.charliekrug.com` shows every queued, active, failed, progressive,
candidate, verified, and published attempt. The system separates two research lanes:

- **Hard lane:** one famous problem is always active and receives two GPT-5.6 Sol / xhigh passes
  every UTC day.
- **Discovery lane:** six daily passes rotate through relatively approachable, objectively
  checkable problems. A daily source-only intake keeps a 12-problem frontier from the versioned
  Erdős Problems database; three bounded non-error passes park a problem and open space for another.

The system never equates model confidence with proof. A candidate is a review request. A result may
be called solved only after statement validation, independent criticism, literature review,
reproducible verification, and a remembered human approval.

## Commands

```bash
python3 -m proof_factory render
python3 -m proof_factory status
python3 -m proof_factory tick --lane easy
python3 -m proof_factory tick --lane hard
python3 -m proof_factory watchdog
python3 -m proof_factory doctor
python3 -m proof_factory intake --target 12
```

`tick` launches Codex headlessly with ChatGPT subscription authentication. API-key variables are
cleared before every model run, so there is no metered model fallback.

## Evidence model

- `data/problems.json` is the versioned problem registry.
- `data/attempts.jsonl` is append-only research history.
- `state/runtime.json` is an atomic operational projection.
- `research/<problem>/` holds literature notes, code, formalizations, and certificates.
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
