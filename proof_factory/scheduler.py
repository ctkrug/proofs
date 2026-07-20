from __future__ import annotations

import json
import os
import random
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any

from . import agent, render, store


ACTIVE_STATUSES = {"queued", "active", "attempted", "candidate"}


def accepted_original_results(problems: list[dict[str, Any]]) -> int:
    return sum(1 for row in problems if row.get("accepted_result") is True)


def choose_problem(lane: str, problems: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in problems if row.get("lane") == lane and row.get("status") in ACTIVE_STATUSES]
    if not candidates:
        raise RuntimeError(f"no active {lane} problems")
    if lane == "hard":
        return max(candidates, key=lambda row: (int(row.get("priority") or 0), -int(row.get("attempt_count") or 0)))

    solved = accepted_original_results(problems)
    if solved < 2:
        # Demonstrate the loop on the easiest certificate-first work before scaling.
        return min(
            candidates,
            key=lambda row: (
                int(row.get("difficulty") or 10),
                int(row.get("attempt_count") or 0),
                -(int(row.get("priority") or 0)),
            ),
        )

    # Afterwards keep a strong easy bias without starving more ambitious discovery work.
    rng = random.Random(datetime.now(timezone.utc).date().isoformat())
    weights = [max(1, (11 - int(row.get("difficulty") or 10)) ** 2) for row in candidates]
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
