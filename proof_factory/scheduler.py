from __future__ import annotations

import json
import math
import os
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any

from . import agent, brain, render, repositories, research_state, resources, store, usage


ACTIVE_STATUSES = {"queued", "active", "attempted", "candidate"}


def accepted_original_results(problems: list[dict[str, Any]]) -> int:
    return sum(1 for row in problems if row.get("external_validation_state") in {
        "expert-confirmed", "repository-accepted", "venue-accepted", "peer-reviewed",
    })


def low_hanging_score(problem: dict[str, Any], problems: list[dict[str, Any]]) -> float:
    """Estimate verifiable contribution value per unit effort, then learn from accepted wins."""
    difficulty = min(10, max(1, int(problem.get("difficulty") or 10)))
    success = float(problem.get("estimated_success_probability") or (11 - difficulty) / 12)
    verification = float(problem.get("verification_score") or (
        5 if any(word in str(problem.get("verifiability", "")).lower()
                 for word in ("finite", "exact", "certificate", "witness", "formal")) else 2
    ))
    contribution = float(problem.get("contribution_score") or 3)
    review_cost = float(problem.get("review_cost") or max(1, difficulty / 2))
    novelty_risk = float(problem.get("novelty_risk") or 2)

    accepted = [row for row in problems if row.get("accepted_result") is True]
    techniques = set(problem.get("techniques") or [])
    transfer_bonus = 0.0
    for win in accepted:
        shared = techniques.intersection(win.get("techniques") or [])
        transfer_bonus += min(0.6, 0.15 * len(shared))
        if problem.get("contribution_type") and problem.get("contribution_type") == win.get("contribution_type"):
            transfer_bonus += 0.35

    attempts = int(problem.get("research_attempt_count") or 0)
    exploration = math.sqrt(math.log2(2 + sum(int(row.get("research_attempt_count") or 0) for row in problems)) / (1 + attempts))
    return (
        6.0 * success
        + 0.7 * verification
        + 0.45 * contribution
        - 0.8 * review_cost
        - 0.55 * novelty_risk
        + transfer_bonus
        + 0.35 * exploration
    )


def choose_problem(lane: str, problems: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = ACTIVE_STATUSES if lane == "hard" else {"queued", "active", "attempted"}
    candidates = [row for row in problems if row.get("lane") == lane and row.get("status") in statuses]
    if not candidates:
        raise RuntimeError(f"no active {lane} problems")
    if lane == "hard":
        return max(candidates, key=lambda row: (int(row.get("priority") or 0), -int(row.get("attempt_count") or 0)))

    incumbents = [row for row in candidates if row.get("campaign_state") == "active"]
    if incumbents:
        return max(incumbents, key=lambda row: str(row.get("campaign_started_at") or ""))

    # Start the next campaign on the target with the best expected verifiable contribution per effort.
    # Once scheduler.tick persists that choice, every later dispatch stays on it until campaign review.
    return max(
        candidates,
        key=lambda row: (
            low_hanging_score(row, problems),
            -int(row.get("research_attempt_count") or 0),
            str(row.get("id") or ""),
        ),
    )


def publish_if_configured() -> None:
    command = os.environ.get("PROOF_FACTORY_PUBLISH_CMD", "").strip()
    if not command:
        return
    proc = subprocess.run(shlex.split(command), cwd=store.ROOT, text=True, capture_output=True, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"publish failed: {(proc.stdout + proc.stderr)[-2000:]}")


def tick(lane: str, *, publish: bool = False) -> dict[str, Any]:
    if lane not in {"easy", "hard"}:
        raise ValueError("lane must be easy or hard")
    admission = usage.admission(lane)
    store.update_runtime(usage_policy=admission)
    if not admission["allowed"]:
        render.build()
        return {"status": "deferred", "lane": lane, "usage_policy": admission}
    with store.lock(f"lane-{lane}", nonblocking=True) as acquired:
        if not acquired:
            raise RuntimeError(f"{lane} lane already running")
        problems = store.load_problems()
        problem = choose_problem(lane, problems)
        if lane == "easy":
            problem = store.start_discovery_campaign(problem["id"])
        phase = "baseline" if research_state.needs_baseline(problem) else "technical"
        repositories.ensure(problem)
        workspace = store.RESEARCH / problem["id"] / "workspace"
        try:
            resources.prepare(problem, workspace)
        except resources.ResourceProvisionError as exc:
            blocker = {
                "title": "Required research source is unavailable",
                "detail": str(exc),
                "problem_id": problem["id"],
                "priority": "urgent",
                "next_action": "Automatic retrieval will retry on the next scheduled pass; investigate host networking if it persists.",
            }
            store.update_runtime(operational_blockers=[blocker])
            render.build()
            raise
        store.update_runtime(operational_blockers=[])
        store.update_runtime(**{f"{lane}_running": problem["id"], f"{lane}_started_at": store.now_iso()})
        brain.refresh()
        render.build()
        attempt = agent.run(problem, lane, phase=phase)
        store.record_attempt(attempt)
        repositories.record_attempt(problem, attempt)
        brain.refresh()
        store.update_runtime(**{
            f"{lane}_running": None,
            f"{lane}_last_attempt_at": attempt["finished_at"],
            f"{lane}_last_outcome": attempt["outcome"],
        })
        render.build()
        if publish:
            publish_if_configured()
        return attempt


def watchdog(*, publish: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    attempts = store.load_attempts()
    hard = [row for row in attempts if row.get("lane") == "hard"]
    easy = [row for row in attempts if row.get("lane") == "easy"]
    current_runtime = store.runtime()
    hard_started = store.parse_iso(current_runtime.get("hard_started_at"))
    hard_in_flight = bool(
        current_runtime.get("hard_running")
        and hard_started
        and (now - hard_started).total_seconds() < 3 * 3600
    )
    issues: list[str] = []
    if hard:
        last_hard = store.parse_iso(hard[-1].get("finished_at"))
        if not hard_in_flight and last_hard and (now - last_hard).total_seconds() > 1.5 * 3600:
            issues.append("twice-hourly Ramsey campaign has no completed or active attempt in more than 1.5 hours")
    elif not hard_in_flight and now.hour >= 2:
        issues.append("twice-hourly Ramsey campaign has not completed its first attempt")
    easy_expected = os.environ.get("PROOF_EASY_EXPECTED", "1").strip().lower() not in {"0", "false", "no", "off"}
    if easy_expected:
        if easy:
            last_easy = store.parse_iso(easy[-1].get("finished_at"))
            if last_easy and (now - last_easy).total_seconds() > 3 * 3600:
                issues.append("open-problem program has no completed attempt in more than 3 hours")
        elif now.hour >= 3:
            issues.append("open-problem program has not completed its first attempt")
    health = "degraded" if issues else "healthy"
    report = store.update_runtime(health=health, health_issues=issues, watchdog_at=store.now_iso())
    render.build()
    if publish:
        publish_if_configured()
    return report


def status() -> dict[str, Any]:
    problems = store.load_problems()
    attempts = store.load_attempts()
    return {
        "problems": len(problems),
        "attempts": len(attempts),
        "candidates": sum(1 for row in problems if row.get("status") == "candidate"),
        "accepted_original_results": accepted_original_results(problems),
        "runtime": store.runtime(),
    }
