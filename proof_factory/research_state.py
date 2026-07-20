from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from . import store


SCHEMA_VERSION = 1
STRATEGY_STATUSES = {
    "proposed", "active", "promising", "blocked", "ruled_out", "exhausted", "superseded",
}


def _text(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def strategy_fingerprint(family: Any, mechanism: Any) -> str:
    normalized = f"{_text(family).lower()}\n{_text(mechanism).lower()}"
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


def state_path(problem_id: str):
    return store.DATA / "research_states" / f"{problem_id}.json"


def _initial(problem: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": problem["id"],
        "objective": _text(problem.get("statement"), 8000),
        "completion_criteria": [_text(problem.get("verifiability"), 4000)] if problem.get("verifiability") else [],
        "non_results": [
            "Finite computation outside its stated range is not a proof of a universal claim.",
            "A candidate is not a solution until independent and human review are recorded.",
            "Restating a known reduction, checking examples, or giving an unproved key lemma is not terminal success.",
        ],
        "epoch_count": 0,
        "last_updated": None,
        "synthesis_summary": "No completed research epoch yet.",
        "established_facts": [],
        "strategies": [],
        "open_leads": [],
        "ruled_out": [],
        "unresolved_questions": [],
        "next_session": {},
        "recent_attempt_ids": [],
    }


def load(problem: dict[str, Any]) -> dict[str, Any]:
    value = store.read_json(state_path(problem["id"]), None)
    if not isinstance(value, dict) or value.get("problem_id") != problem["id"]:
        return _initial(problem)
    seeded = _initial(problem)
    seeded.update(value)
    for key in ("completion_criteria", "non_results", "established_facts", "strategies", "open_leads", "ruled_out", "unresolved_questions", "recent_attempt_ids"):
        if not isinstance(seeded.get(key), list):
            seeded[key] = []
    return seeded


def load_all(problems: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {problem["id"]: load(problem) for problem in problems}


def backfill() -> dict[str, int]:
    """Create ledgers for legacy attempts once; never rewrite a ledger that already exists."""
    problems = {problem["id"]: problem for problem in store.load_problems()}
    grouped: dict[str, list[dict[str, Any]]] = {problem_id: [] for problem_id in problems}
    for attempt in store.load_attempts():
        if attempt.get("problem_id") in grouped:
            grouped[str(attempt["problem_id"])].append(attempt)
    created = 0
    replayed = 0
    with store.lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        for problem_id, problem in problems.items():
            if state_path(problem_id).exists():
                continue
            for attempt in grouped[problem_id]:
                update_from_attempt(problem, attempt)
                replayed += 1
            if not grouped[problem_id]:
                store.write_json_atomic(state_path(problem_id), _initial(problem))
            created += 1
    return {"ledgers_created": created, "attempts_replayed": replayed}


def _object_rows(value: Any, fields: tuple[str, ...], limit: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in value if isinstance(value, list) else []:
        if isinstance(raw, str):
            raw = {fields[0]: raw}
        if not isinstance(raw, dict):
            continue
        row = {key: _text(raw.get(key), 4000) for key in fields if raw.get(key) not in (None, "")}
        if row:
            rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def _dedupe(rows: list[dict[str, Any]], keys: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for row in reversed(rows):
        token = "\n".join(_text(row.get(key)).lower() for key in keys)
        if not token or token in seen:
            continue
        seen.add(token)
        kept.append(row)
    return list(reversed(kept[:limit]))


def update_from_attempt(problem: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    """Project an immutable attempt into a compact, durable, machine-readable research memory."""
    state = load(problem)
    now = attempt.get("finished_at") or store.now_iso()
    state["epoch_count"] = int(state.get("epoch_count") or 0) + 1
    state["last_updated"] = now
    state["synthesis_summary"] = _text(attempt.get("summary"), 8000)
    state["recent_attempt_ids"] = (state.get("recent_attempt_ids", []) + [attempt["id"]])[-20:]

    strategy = attempt.get("strategy") if isinstance(attempt.get("strategy"), dict) else {}
    family = _text(strategy.get("family") or attempt.get("strategy_family") or "unspecified", 200)
    mechanism = _text(strategy.get("mechanism") or attempt.get("approach"), 2000)
    fingerprint = _text(strategy.get("fingerprint"), 100) or strategy_fingerprint(family, mechanism)
    status = _text(attempt.get("strategy_status") or ("promising" if attempt.get("outcome") in {"progress", "candidate"} else "blocked"), 50)
    if status not in STRATEGY_STATUSES:
        status = "active"
    strategy_row = {
        "id": f"strategy-{fingerprint}",
        "family": family,
        "fingerprint": fingerprint,
        "title": _text(attempt.get("approach"), 500),
        "mechanism": mechanism,
        "status": status,
        "hypothesis": _text(attempt.get("hypothesis"), 2000),
        "discriminating_test": _text(attempt.get("discriminating_test"), 2000),
        "blocker": _text(attempt.get("blocker"), 2000),
        "reopen_condition": _text(attempt.get("reopen_condition"), 2000),
        "reopen_evidence": _text(attempt.get("reopen_evidence"), 2000),
        "last_attempt_id": attempt["id"],
        "attempts": 1,
        "parent_ids": [_text(x, 100) for x in strategy.get("parent_ids", []) if _text(x, 100)][:10],
        "updated_at": now,
    }
    existing = next((row for row in state["strategies"] if row.get("fingerprint") == fingerprint), None)
    if existing:
        strategy_row["attempts"] = int(existing.get("attempts") or 0) + 1
        for key in ("title", "mechanism", "hypothesis", "discriminating_test", "blocker", "reopen_condition", "parent_ids"):
            if not strategy_row.get(key):
                strategy_row[key] = existing.get(key)
        state["strategies"] = [row for row in state["strategies"] if row.get("fingerprint") != fingerprint]
    state["strategies"].append(strategy_row)
    state["strategies"] = state["strategies"][-60:]

    facts = _object_rows(attempt.get("established_facts"), ("claim", "evidence", "scope", "status"))
    for row in facts:
        row.update({"source_attempt_id": attempt["id"], "updated_at": now})
    state["established_facts"] = _dedupe(state["established_facts"] + facts, ("claim", "scope"), 80)

    ruled = _object_rows(attempt.get("ruled_out"), ("claim_or_route", "scope", "reason", "evidence", "reopen_condition"))
    for row in ruled:
        row.update({"attempt_id": attempt["id"], "updated_at": now})
    state["ruled_out"] = _dedupe(state["ruled_out"] + ruled, ("claim_or_route", "scope"), 80)

    leads = _object_rows(attempt.get("open_leads"), ("description", "rationale", "next_experiment", "priority", "status"))
    for index, row in enumerate(leads):
        token = hashlib.sha256(f"{fingerprint}\n{row.get('description')}".encode()).hexdigest()[:10]
        row.update({"id": f"lead-{token}", "strategy_id": strategy_row["id"], "updated_at": now})
        row.setdefault("status", "open")
    state["open_leads"] = _dedupe(state["open_leads"] + leads, ("description",), 60)

    continuation = attempt.get("continuation") if isinstance(attempt.get("continuation"), dict) else {}
    if not continuation and attempt.get("next_steps"):
        continuation = {"objective": attempt["next_steps"][0], "first_action": attempt["next_steps"][0]}
    state["next_session"] = {
        "recommended_strategy_id": strategy_row["id"],
        "objective": _text(continuation.get("objective"), 2000),
        "first_action": _text(continuation.get("first_action"), 2000),
        "stop_condition": _text(continuation.get("stop_condition"), 2000),
        "source_attempt_id": attempt["id"],
    }
    proposals = _object_rows(attempt.get("strategy_proposals"), ("family", "mechanism", "hypothesis", "discriminating_test", "rationale"), 10)
    known = {row.get("fingerprint") for row in state["strategies"]}
    for proposal in proposals:
        proposal_fp = strategy_fingerprint(proposal.get("family"), proposal.get("mechanism"))
        if proposal_fp in known:
            continue
        proposal.update({
            "id": f"strategy-{proposal_fp}", "fingerprint": proposal_fp, "status": "proposed",
            "title": proposal.get("mechanism", "")[:500], "attempts": 0,
            "parent_ids": [strategy_row["id"]], "updated_at": now,
        })
        state["strategies"].append(proposal)
        known.add(proposal_fp)

    store.write_json_atomic(state_path(problem["id"]), state)
    return state


def compact_for_prompt(problem: dict[str, Any]) -> str:
    state = load(problem)
    payload = {
        "epoch_count": state.get("epoch_count"),
        "synthesis_summary": state.get("synthesis_summary"),
        "established_facts": state.get("established_facts", [])[-20:],
        "strategy_registry": state.get("strategies", [])[-30:],
        "open_leads": state.get("open_leads", [])[-20:],
        "ruled_out": state.get("ruled_out", [])[-20:],
        "next_session": state.get("next_session", {}),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def summary_counts(state: dict[str, Any]) -> dict[str, int]:
    counts = Counter(str(row.get("status") or "unknown") for row in state.get("strategies", []))
    return {
        "promising": counts["promising"],
        "blocked": counts["blocked"],
        "ruled_out": len(state.get("ruled_out", [])),
        "open_leads": sum(1 for row in state.get("open_leads", []) if row.get("status", "open") == "open"),
    }
