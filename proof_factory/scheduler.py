from __future__ import annotations

import json
import math
import os
import random
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any

from . import agent, render, store


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
    candidates = [row for row in problems if row.get("lane") == lane and row.get("status") in ACTIVE_STATUSES]
    if not candidates:
        raise RuntimeError(f"no active {lane} problems")
    if lane == "hard":
        return max(candidates, key=lambda row: (int(row.get("priority") or 0), -int(row.get("attempt_count") or 0)))

    solved = accepted_original_results(problems)
    if solved < 2:
        # Cycle the frontier while breaking ties by expected verifiable contribution per effort.
        return min(
            candidates,
            key=lambda row: (
                int(row.get("research_attempt_count") or 0),
                -low_hanging_score(row, problems),
            ),
        )

    # Afterwards exploit patterns behind accepted wins while retaining an exploration chance.
    attempt_total = sum(int(row.get("research_attempt_count") or 0) for row in problems)
    rng = random.Random(f"{datetime.now(timezone.utc).date().isoformat()}-{attempt_total}")
    floor = min(low_hanging_score(row, problems) for row in candidates)
    weights = [max(0.25, low_hanging_score(row, problems) - floor + 0.25) ** 2 for row in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


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
    with store.lock(f"lane-{lane}", nonblocking=True) as acquired:
        if not acquired:
            raise RuntimeError(f"{lane} lane already running")
        problems = store.load_problems()
        problem = choose_problem(lane, problems)
        store.update_runtime(**{f"{lane}_running": problem["id"], f"{lane}_started_at": store.now_iso()})
        render.build()
        attempt = agent.run(problem, lane)
        store.record_attempt(attempt)
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
    today = now.date().isoformat()
    hard_today = [row for row in attempts if row.get("lane") == "hard" and str(row.get("finished_at", "")).startswith(today)]
    easy = [row for row in attempts if row.get("lane") == "easy"]
    due_hard = sum(1 for hour in (6, 18) if now.hour >= hour + 2)
    current_runtime = store.runtime()
    hard_started = store.parse_iso(current_runtime.get("hard_started_at"))
    hard_in_flight = bool(
        current_runtime.get("hard_running")
        and hard_started
        and (now - hard_started).total_seconds() < 3 * 3600
    )
    issues: list[str] = []
    hard_credited = len(hard_today) + (1 if hard_in_flight else 0)
    if hard_credited < due_hard:
        issues.append(f"hard lane missed cadence: {len(hard_today)}/{due_hard} due runs")
    if easy:
        last_easy = store.parse_iso(easy[-1].get("finished_at"))
        if last_easy and (now - last_easy).total_seconds() > 6 * 3600:
            issues.append("easy lane has no completed attempt in more than 6 hours")
    elif now.hour >= 6:
        issues.append("easy lane has not completed its first attempt")
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
