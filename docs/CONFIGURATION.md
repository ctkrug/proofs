# Proof Factory configuration

The version-controlled source for shared, non-secret deployment settings is
`deploy/proof-factory.env`. `scripts/install-box.sh` installs it at
`/etc/proof-factory/proof-factory.env` before reloading systemd. Every Proof Factory service requires
that file and runs a service-scoped `python -m proof_factory.config validate --profile ...` before
its workload starts. A malformed optional telemetry or KV setting therefore cannot stop an unrelated
lab or watchdog service.

Configuration consumers should use the typed getters in `proof_factory.config`. The getters read the
environment at call time, enforce bounds and accepted spellings, and raise `ConfigurationError` for an
explicit malformed value. New runtime settings should use these getters; foundational process paths
that determine module storage roots remain intentionally fixed at process import.

Keep these boundaries:

- Shared paths, timeouts, public identifiers, cache pins, and observability switches belong in the
  checked-in non-secret environment file.
- Workload-specific sandbox choices, cgroup/resource limits, network restrictions, and timers remain
  in their individual systemd units.
- Tokens, API keys, account credentials, and other secrets remain in the existing
  `/root/project-factory/.env` credential file. Only easy, hard, publish, and runtime-sync services may
  read it unless a reviewed change explicitly narrows or extends that scope.
- Long computational experiments set their own immutable per-job resource specification and segment
  limits; this shared file must not impose an overall wall-clock stop on checkpointed lab work.

Before installing a change, run:

```bash
python3 -m proof_factory.config validate
python3 -m pytest -q tests/test_config.py
```

When validating the checked-in deployment values locally, load `deploy/proof-factory.env` into the
process environment first. Never place a credential in that file or commit a generated copy of the
live credential file.
