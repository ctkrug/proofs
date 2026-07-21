from __future__ import annotations

import json
from typing import Any

from . import store, tactics


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
    tactical = tactics.build(problem)
    incumbent = tactical.get("incumbent") or {}
    fingerprint = str(incumbent.get("fingerprint") or "")
    active = next((
        row for row in value["phases"]
        if fingerprint and fingerprint in (row.get("strategy_fingerprints") or [])
    ), next((row for row in value["phases"] if row.get("id") == value.get("default_phase")), value["phases"][0]))
    return {
        "configured": True,
        "schema_version": value.get("schema_version"),
        "problem_id": problem["id"],
        "selection": "active tactical incumbent matched to a roadmap stage; evidence may change it every epoch",
        "incumbent_fingerprint": fingerprint,
        "operating_rule": value.get("operating_rule"),
        "selection_policy": value.get("selection_policy", []),
        "portfolio_rule": value.get("portfolio_rule"),
        "active_phase": active,
        "confidence_calibration": value.get("confidence_calibration"),
        "sources": value.get("sources", []),
    }


def compact_for_prompt(problem: dict[str, Any]) -> str:
    return json.dumps(current(problem), indent=2, ensure_ascii=False)
