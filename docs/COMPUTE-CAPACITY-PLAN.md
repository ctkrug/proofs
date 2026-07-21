# Proof Factory compute-capacity plan

## Current host

The content droplet has 2 vCPU, 4 GiB RAM, 6 GiB swap, a 50 GB root disk, and a separate 25 GiB
volume shared by the immutable Alpha Factory tape and rebuildable Proof Factory formalization caches.
The checkpointed lab is low-priority and limited to one full CPU core (`CPUQuota=100%`), 1.3 GiB hard
memory, 128 tasks, offline execution, and at most 24 hours per segment. That leaves one CPU core and
most memory available for dashboards and orchestration.
Within an approved tranche the worker drains consecutive checkpointed segments without waiting for the
five-minute queue poll; it stops as soon as the next review, validation, redirect, or safety gate is due.

Admission is resource-specific. Every job retains root-disk and memory reserves. Model/formalization
work also requires at least 1 GiB free on the build-cache volume. Workspace-confined lab jobs cannot
write that volume, so a full Lean cache no longer blocks unrelated Python/SAT enumeration.

## Always-on operating modes

1. **Normal:** monitoring, validation, pilots, and one checkpointed lab segment run on the existing
   host at low priority.
2. **Research:** a pilot that passes its throughput, correctness, artifact-growth, and decision-value
   gates continues in reviewed tranches on the existing host.
3. **Burst:** only a measured job whose remaining work is decisive may move to temporary larger
   compute. Inputs, code revision, checkpoint, exact argv, and hashes must make the move mechanical.

Do not run arbitrary search merely to keep CPUs busy. The durable queue should remain available
continuously, but only qualified experiments consume it.

## Upgrade triggers

- Expand the shared volume before more Lean/Mathlib hydration. A 50 GiB volume provides roughly
  25 GiB headroom without moving the verified Alpha tape.
- Use temporary 4–8 vCPU / 16–32 GiB compute when a measured pilot shows useful parallel scaling or
  memory above the local 1.3 GiB lab ceiling.
- Use 16+ vCPU / 64+ GiB only for a verified proof/certificate search with a declared cost cap and
  independently checkable output.

Alert and pause on root free space below 8 GiB, required cache space below 1 GiB, available memory
below the lane reserve, OOM/restart, stale checkpoint, failed correctness/coverage, artifact growth
above the job threshold, or throughput below its declared floor.
