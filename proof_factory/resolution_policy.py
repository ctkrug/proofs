from __future__ import annotations

from typing import Any

from . import store


def load() -> dict[str, Any]:
    value = store.read_json(store.DATA / "research_policy.json", {})
    if not isinstance(value, dict) or not isinstance(value.get("required_resolution_paths"), list):
        return {"configured": False}
    return {"configured": True, **value}
