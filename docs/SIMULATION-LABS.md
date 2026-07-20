# Simulation labs

The lab is the controlled execution plane for searches that outlive one Sol-Terra research epoch.
It is not a generic shell runner and it never turns compute consumption into evidence by itself.

## Submission contract

A job records:

- problem ID, name, falsifiable hypothesis, and expected decisive signal;
- direct source URLs;
- argv command, deterministic seed, segment time, memory ceiling, and segment count;
- a workspace-relative checkpoint path whenever more than one segment is requested.

Submit from a problem workspace with:

```bash
python3 /root/proof-factory/scripts/submit_lab.py \
  --problem ramsey-r55 \
  --name novel-42-search \
  --hypothesis "A constrained branch contains a new order-42 graph" \
  --expected-signal "dual verifier accepts a canonical graph outside the 656" \
  --segment-seconds 21600 --max-segments 7 --memory-mb 900 \
  --checkpoint-path checkpoints/novel42.json \
  -- python3 search_novel42.py --resume checkpoints/novel42.json
```

## Execution and safety

- No shell is invoked. The executable must be allowlisted or live inside that problem's workspace.
- Paths cannot escape the workspace. Research, SSH, GitHub, Codex, deployment, and project-factory
  credentials are inaccessible to the lab service.
- One job runs at a time with low CPU/IO priority, a 60% CPU quota, and explicit memory limits.
- A segment is at most 24 hours; at most seven segments may run. A timed-out job is requeued only when
  its declared checkpoint exists.
- The underlying experiment runner records command, sources, seed, platform, limits, input hashes,
  stdout/stderr hashes, return code, and timing. The lab ledger is append-only.
- Network access is denied during execution. Fetch and hash datasets during a bounded research epoch,
  then run the simulation against local inputs.

## Acceptance

A later research epoch must inspect the exact record, reproduce controls, and run an independent
checker. A completed lab job is an experiment artifact, not a proof, bound, or contribution candidate.
