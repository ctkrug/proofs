from __future__ import annotations

from typing import Any

from . import store


def path(problem_id: str):
    return store.DATA / "prior_art" / f"{problem_id}.json"


def load(problem: dict[str, Any]) -> dict[str, Any]:
    value = store.read_json(path(problem["id"]), None)
    if not isinstance(value, dict) or value.get("problem_id") != problem["id"]:
        return {"configured": False, "problem_id": problem["id"], "methods": []}
    methods = value.get("methods") if isinstance(value.get("methods"), list) else []
    value["configured"] = True
    value["methods"] = methods
    return value
