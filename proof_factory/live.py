from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import store


def next_hard_after(now: datetime) -> datetime:
    """Return the next half-hour hard-lane dispatch strictly after *now*."""
    now = now.astimezone(timezone.utc)
    candidate = now.replace(minute=30 if now.minute >= 30 else 0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(minutes=30)
    return candidate


def next_easy_after(now: datetime) -> datetime:
    """Return the next even-hour :30 easy-lane dispatch strictly after *now*."""
    now = now.astimezone(timezone.utc)
    candidate = now.replace(minute=30, second=0, microsecond=0)
    if candidate.hour % 2:
        candidate += timedelta(hours=1)
    if candidate <= now:
        candidate += timedelta(hours=2)
    return candidate


def _effective_outcome(attempt: dict[str, Any], reviews: list[dict[str, Any]]) -> str:
    latest = reviews[-1] if reviews else {}
    if attempt.get("outcome") == "candidate" and latest.get("display_status") == "internal_result":
        return "internal_result"
    return str(attempt.get("outcome") or "unknown")


def snapshot(
    problems: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    runtime: dict[str, Any],
    reviews: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the small public operations payload consumed by the homepage."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    problem_by_id = {str(row["id"]): row for row in problems}
    reviews_by_attempt: dict[str, list[dict[str, Any]]] = {}
    for review in reviews or []:
        reviews_by_attempt.setdefault(str(review.get("attempt_id")), []).append(review)

    lanes: dict[str, dict[str, Any]] = {}
    for lane in ("hard", "easy"):
        running_id = runtime.get(f"{lane}_running")
        running_problem = problem_by_id.get(str(running_id)) if running_id else None
        next_at = next_hard_after(now) if lane == "hard" else next_easy_after(now)
        lanes[lane] = {
            "status": "running" if running_id else "idle",
            "running_problem_id": running_id,
            "running_problem_title": (running_problem or {}).get("title"),
            "started_at": runtime.get(f"{lane}_started_at") if running_id else None,
            "next_at": next_at.isoformat(),
            "last_attempt_at": runtime.get(f"{lane}_last_attempt_at"),
            "last_outcome": runtime.get(f"{lane}_last_outcome"),
        }

    recent_runs = []
    for attempt in reversed(attempts[-20:]):
        problem = problem_by_id.get(str(attempt.get("problem_id")), {})
        next_steps = attempt.get("next_steps") or []
        next_action = next_steps[0] if next_steps else None
        if isinstance(next_action, dict):
            next_action = next_action.get("action") or next_action.get("description") or str(next_action)
        evidence = attempt.get("experiments") or attempt.get("evidence") or []
        recent_runs.append(
            {
                "id": attempt.get("id"),
                "href": f"/attempts/{attempt.get('id')}/",
                "problem_id": attempt.get("problem_id"),
                "problem_title": problem.get("title") or attempt.get("problem_id"),
                "lane": attempt.get("lane"),
                "outcome": _effective_outcome(attempt, reviews_by_attempt.get(str(attempt.get("id")), [])),
                "started_at": attempt.get("started_at"),
                "finished_at": attempt.get("finished_at"),
                "duration_seconds": attempt.get("duration_seconds"),
                "approach": attempt.get("approach"),
                "accomplishment": attempt.get("summary"),
                "next_action": next_action,
                "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
                "model": attempt.get("model"),
            }
        )

    return {
        "schema_version": 1,
        "available": True,
        "generated_at": runtime.get("updated_at") or now.isoformat(),
        "health": runtime.get("health", "starting"),
        "health_issues": runtime.get("health_issues") or [],
        "operational_blockers": runtime.get("operational_blockers") or [],
        "lanes": lanes,
        "recent_runs": recent_runs,
    }
