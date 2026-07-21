from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from . import store


ALLOWED_KINDS = {
    "lab_completed",
    "lab_segment_completed",
    "source_changed",
    "route_authorized",
    "external_feedback",
    "evidence_repaired",
}


def _pending_root() -> Path:
    return store.STATE / "research-events" / "pending"


def _archive_root() -> Path:
    return store.STATE / "research-events" / "archive"


def enqueue(problem_id: str, kind: str, *, evidence: str, source: str) -> dict[str, Any]:
    if problem_id not in {row["id"] for row in store.load_problems()}:
        raise ValueError(f"unknown problem_id: {problem_id}")
    kind = str(kind).strip()
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"invalid research event kind: {kind}")
    if not str(evidence).strip() or not str(source).strip():
        raise ValueError("research events require evidence and source")
    event = {
        "schema_version": 1,
        "id": f"event-{problem_id}-{uuid.uuid4().hex[:12]}",
        "problem_id": problem_id,
        "kind": kind,
        "evidence": str(evidence)[:4000],
        "source": str(source)[:1000],
        "created_at": store.now_iso(),
    }
    root = _pending_root()
    root.mkdir(parents=True, exist_ok=True)
    store.write_json_atomic(root / f"{event['id']}.json", event)
    return event


def pending(problem_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(_pending_root().glob("*.json")):
        value = store.read_json(path, None)
        if isinstance(value, dict) and value.get("problem_id") == problem_id:
            rows.append(value)
    return rows


def consume(problem_id: str, attempt_id: str, *, event_ids: set[str] | None = None) -> list[dict[str, Any]]:
    """Archive selected pending events, or every pending event when no selection is supplied."""
    archived: list[dict[str, Any]] = []
    archive = _archive_root()
    archive.mkdir(parents=True, exist_ok=True)
    for event in pending(problem_id):
        if event_ids is not None and event["id"] not in event_ids:
            continue
        source = _pending_root() / f"{event['id']}.json"
        if not source.exists():
            continue
        value = {**event, "consumed_at": store.now_iso(), "attempt_id": attempt_id}
        destination = archive / source.name
        store.write_json_atomic(destination, value)
        source.unlink()
        archived.append(value)
    return archived
