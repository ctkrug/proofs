# Architecture

## Separation of concerns

```text
systemd timers
  ├─ hard lane: 06:00 + 18:00 UTC → GPT-5.6 Sol / xhigh
  ├─ discovery lane: every four hours → GPT-5.6 Terra / high
  ├─ broad scout: daily → one sourced cross-field contribution candidate
  ├─ strategy lab: daily → one sourced, executable method addition or improvement
  └─ watchdog: every six hours → cadence and state checks
          ↓
injected computational-researcher skill
          ↓
bounded, indefinitely resumable epoch → scripts/solvers + reproducibility records + structured result
          ↓
append-only attempts.jsonl + durable research maps → self-improving selector and next checkpoint
          ↓
static renderer → Cloudflare Pages → proofs.charliekrug.com
```

Cloudflare serves only generated static files. It is not coupled to the model runtime, so the ledger
stays available if the content box, Codex login, or an individual attempt fails.

## State invariants

1. Attempts are append-only and IDs are unique.
2. A failed attempt changes a problem to `attempted`, never `disproved`.
3. `candidate` is a review state, not a mathematical verdict.
4. `accepted_result=true` is written only by the explicit human review command.
5. The initial Jacobian reproduction never counts toward the two original-results scaling gate.
6. The hard problem remains selected across runs; the discovery lane is easier-first until two
   original results have passed the full gate.
7. Every model run clears metered API credentials and forces ChatGPT subscription login.
8. The discovery selector optimizes expected verifiable contribution per compute/review cost and
   increases priors for techniques behind accepted results while retaining exploration.
9. An approved release must contain hashed artifacts; website/GitHub publication is mechanical, while
   expert outreach and third-party venue submission remain separate human actions.
10. “Unbounded horizon” means no preset number of bounded epochs, never an immortal process. Each
    epoch has a resource ceiling and must record its objective, first action, and stop condition.
11. Research maps contain only claims, evidence, scoped decisions, and continuation instructions;
    private chain-of-thought is neither requested nor stored.
12. A blocked or ruled-out strategy can be retried only after its explicit reopen condition is met
    or materially new evidence is recorded.

## Availability and cadence

- The public ledger is a Cloudflare Pages deployment.
- Each completed attempt publishes once. At eight scheduled runs/day, that is at most 248 deployments
  in a 31-day month, leaving room under the documented 500 monthly Pages deployments for manual
  reviews and exceptional repairs. A future dynamic state endpoint should be considered before
  adding more lanes.
- Research services never receive Cloudflare or social credentials. A separate, serialized publisher
  service loads deployment credentials only after the research process exits; the research model runs
  with a minimal environment and a workspace-write sandbox.
- Discovery problems receive three bounded non-error passes before being parked only if their map has
  no live lead, promising route, or untried proposal. A daily,
  deterministic intake job refills the active frontier to 12 from the versioned `teorth/erdosproblems`
  catalog and exact statement HTML on erdosproblems.com; easier and formalized metadata rank first.
- Persistent timers catch up after a reboot. The watchdog reports missed hard-lane cadence rather
  than silently backfilling fake work.
- Services run at low CPU/IO priority with memory ceilings on the shared content box.
