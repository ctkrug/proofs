"""Shared Codex-usage admission control for Proof Factory."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config, store


DEFAULT_CACHE = Path("/root/project-factory/state/usage_cache.json")
MAX_AGE_SECONDS = 30 * 60
LANE_TIE_PRIORITY = ("easy", "hard")


def preferred_lane(admissions: dict[str, dict[str, Any]]) -> str | None:
    """Choose discovery first when multiple model lanes are simultaneously admissible."""
    return next((lane for lane in LANE_TIE_PRIORITY if admissions.get(lane, {}).get("allowed")), None)


def _cache_path() -> Path:
    return config.get_path("PROOF_USAGE_CACHE_PATH", DEFAULT_CACHE)


def _baseline_slot(lane: str, now: datetime) -> bool:
    # Hard-lane model reviews are event-gated and poll six times daily. The
    # baseline controls provider usage only; scheduler admission still requires
    # a concrete research event. The easy lane retains its independent cadence.
    return lane == "easy" or (now.hour % 4 == 0 and now.minute < 5)


def admission(lane: str, *, now: datetime | None = None, monotonic_now: float | None = None) -> dict[str, Any]:
    """Return whether a model-backed proof pass may start.

    A successful, fresh Codex weekly snapshot permits the primary schedule only
    while usage is no greater than elapsed-week percentage. Missing/stale data
    fails conservatively to the defined polling baseline. Hard polls still need
    an unconsumed evidence event and therefore do not imply a model pass.
    """
    if lane not in {"hard", "easy"}:
        raise ValueError("lane must be hard or easy")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    clock = time.time() if monotonic_now is None else monotonic_now
    payload = store.read_json(_cache_path(), {})
    baseline = _baseline_slot(lane, now)
    operator_authorized = config.get_bool("PROOF_OPERATOR_RUN", False)
    result: dict[str, Any] = {
        "checked_at": payload.get("checked_at") if isinstance(payload, dict) else None,
        "mode": "baseline",
        "allowed": baseline,
        "lane": lane,
        "baseline_slot": baseline,
        "operator_authorized": operator_authorized,
        "lane_tie_priority": list(LANE_TIE_PRIORITY),
        "tie_break_rule": "discovery/easy wins simultaneous admissibility; no running lane is preempted",
        "reason": "usage snapshot unavailable; retaining baseline only",
    }
    if not isinstance(payload, dict) or not payload.get("ok"):
        return result
    checked_at = payload.get("checked_at")
    if not isinstance(checked_at, (int, float)) or clock - checked_at > MAX_AGE_SECONDS:
        result["reason"] = "usage snapshot stale; retaining baseline only"
        return result
    if payload.get("rate_limit_reached_type") or payload.get("spend_control_reached"):
        result.update({"mode": "paused", "allowed": False, "reason": "provider usage limit or spend control reached"})
        return result
    if lane == "hard" and store.runtime().get("easy_running"):
        result.update({
            "mode": "portfolio", "allowed": False,
            "reason": "discovery lane is already running; it wins simultaneous admissibility without preemption",
        })
        return result
    if operator_authorized:
        result.update({
            "mode": "operator", "allowed": True,
            "reason": "one-shot operator-authorized pass; provider hard limits remain enforced",
        })
        return result
    week = payload.get("week")
    if not isinstance(week, dict):
        result["reason"] = "weekly usage window unavailable; retaining baseline only"
        return result
    used = week.get("used_pct")
    resets_at = week.get("resets_at")
    duration = week.get("window_seconds")
    if not all(isinstance(value, (int, float)) for value in (used, resets_at, duration)) or duration <= 0:
        result["reason"] = "weekly usage window invalid; retaining baseline only"
        return result
    week_start = float(resets_at) - float(duration)
    elapsed_pct = min(100.0, max(0.0, 100.0 * (clock - week_start) / float(duration)))
    result.update({"used_pct": float(used), "elapsed_pct": elapsed_pct, "resets_at": float(resets_at)})
    if float(used) <= elapsed_pct:
        result.update({"mode": "primary", "allowed": True, "reason": "usage is within elapsed-week allowance"})
    else:
        result.update({
            "mode": "baseline", "allowed": baseline,
            "reason": "usage is ahead of elapsed-week allowance; retaining baseline only",
        })
    return result
