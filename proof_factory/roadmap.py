from __future__ import annotations

import json
from typing import Any

from . import research_state, store


def path(problem_id: str):
    return store.DATA / "campaign_roadmaps" / f"{problem_id}.json"


def load(problem: dict[str, Any]) -> dict[str, Any] | None:
    value = store.read_json(path(problem["id"]), None)
    if not isinstance(value, dict) or value.get("problem_id") != problem["id"]:
        return None
    phases = value.get("phases")
    if not isinstance(phases, list) or not phases:
        return None
    return value


def current(problem: dict[str, Any]) -> dict[str, Any]:
    value = load(problem)
    if not value:
        return {"configured": False, "problem_id": problem["id"]}
    state = research_state.load(problem)
    start_after = int(value.get("start_after_epoch") or 0)
    next_session = max(1, int(state.get("epoch_count") or 0) - start_after + 1)
    active = next((
        row for row in value["phases"]
        if int(row.get("sessions", [0, 0])[0]) <= next_session <= int(row.get("sessions", [0, 0])[1])
    ), value["phases"][-1])
    return {
        "configured": True,
        "schema_version": value.get("schema_version"),
        "problem_id": problem["id"],
        "next_roadmap_session": next_session,
        "horizon_sessions": value.get("horizon_sessions"),
        "operating_rule": value.get("operating_rule"),
        "active_phase": active,
        "confidence_calibration": value.get("confidence_calibration"),
        "portfolio_allocation": value.get("portfolio_allocation"),
        "sources": value.get("sources", []),
    }


def compact_for_prompt(problem: dict[str, Any]) -> str:
    return json.dumps(current(problem), indent=2, ensure_ascii=False)
