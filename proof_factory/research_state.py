from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from collections import Counter
from typing import Any

from . import store


SCHEMA_VERSION = 5
STRATEGY_STATUSES = {
    "proposed", "active", "promising", "blocked", "ruled_out", "exhausted", "superseded",
}
TERMINAL_STRATEGY_STATUSES = {"blocked", "ruled_out", "exhausted", "superseded"}
_EMPTY_STRATEGY_VALUES = {"", "error", "none", "n/a", "not applicable", "unspecified"}


def _text(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def strategy_fingerprint(family: Any, mechanism: Any) -> str:
    normalized = f"{_text(family).lower()}\n{_text(mechanism).lower()}"
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


def mechanism_similarity(left: Any, right: Any) -> float:
    """Cheap deterministic guard against paraphrased strategy duplication."""
    left_tokens = set(re.findall(r"[a-z0-9]+", _text(left).lower()))
    right_tokens = set(re.findall(r"[a-z0-9]+", _text(right).lower()))
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def strategy_is_meaningful(row: dict[str, Any]) -> bool:
    """Return whether a route contains enough mechanism information to be actionable."""
    if not isinstance(row, dict):
        return False
    mechanism = _text(row.get("mechanism"), 4000).lower()
    family = _text(row.get("family"), 500).lower()
    title = _text(row.get("title"), 1000).lower()
    if mechanism in _EMPTY_STRATEGY_VALUES:
        return False
    if mechanism.startswith("error:") or title.startswith("error:"):
        return False
    return bool(family not in _EMPTY_STRATEGY_VALUES or title not in _EMPTY_STRATEGY_VALUES)


def reconcile_value(state: dict[str, Any], *, reconciled_at: str | None = None) -> dict[str, Any]:
    """Return a non-destructive, hygienic state view plus an inspectable change report.

    This is intentionally a pure function so dashboards and tactical prompts can stop
    advertising stale work without silently rewriting the durable ledger.
    """
    clean = deepcopy(state) if isinstance(state, dict) else {}
    strategies = [row for row in clean.get("strategies", []) if isinstance(row, dict)]
    strategy_by_id: dict[str, dict[str, Any]] = {}
    invalid_strategy_ids: list[str] = []
    for row in strategies:
        strategy_id = _text(row.get("id"), 200)
        if not strategy_is_meaningful(row):
            row["status"] = "superseded"
            row["ineligible_reason"] = "empty_or_error_strategy"
            if strategy_id:
                invalid_strategy_ids.append(strategy_id)
        if strategy_id:
            strategy_by_id[strategy_id] = row
    clean["strategies"] = strategies

    closed_lead_ids: list[str] = []
    orphaned_lead_ids: list[str] = []
    leads = [row for row in clean.get("open_leads", []) if isinstance(row, dict)]
    for row in leads:
        if _text(row.get("status"), 40).lower() != "open":
            continue
        strategy_id = _text(row.get("strategy_id"), 200)
        strategy = strategy_by_id.get(strategy_id)
        reason = ""
        if not strategy_id:
            reason = "missing_strategy_id"
            orphaned_lead_ids.append(_text(row.get("id"), 200))
        elif strategy is None:
            reason = "orphaned_strategy"
            orphaned_lead_ids.append(_text(row.get("id"), 200))
        elif strategy and strategy.get("status") in TERMINAL_STRATEGY_STATUSES:
            reason = "terminal_strategy"
        if reason:
            row["status"] = "closed"
            row["closure_reason"] = reason
            if reconciled_at:
                row["closed_at"] = reconciled_at
            closed_lead_ids.append(_text(row.get("id"), 200))
    clean["open_leads"] = leads
    return {
        "state": clean,
        "report": {
            "invalid_strategy_ids": [value for value in invalid_strategy_ids if value],
            "closed_lead_ids": [value for value in closed_lead_ids if value],
            "orphaned_lead_ids": [value for value in orphaned_lead_ids if value],
            "changed": bool(invalid_strategy_ids or closed_lead_ids),
        },
    }


def reconcile(problem: dict[str, Any], *, write: bool = False) -> dict[str, Any]:
    """CLI-ready stale-state reconciliation; dry-run by default, persist with ``write``."""
    result = reconcile_value(load(problem), reconciled_at=store.now_iso())
    if write and result["report"]["changed"]:
        store.write_json_atomic(state_path(problem["id"]), result["state"])
    result["report"]["written"] = bool(write and result["report"]["changed"])
    return result


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
        "baseline_review": {
            "status": "required",
            "reviewed_at": None,
            "source_attempt_id": None,
            "requirement": "Audit exact statement/status, prior work, established facts, ruled-out routes, open leads, tools, and acceptance path before technical research.",
        },
        "synthesis_summary": "No completed research epoch yet.",
        "established_facts": [],
        "strategies": [],
        "open_leads": [],
        "ruled_out": [],
        "unresolved_questions": [],
        "next_session": {},
        "recent_attempt_ids": [],
        "tactical_memory": {
            "current_bottleneck": "",
            "failure_signatures": [],
            "reusable_assets": [],
            "constraints_learned": [],
            "decision_history": [],
            "reduction_ledger": [],
            "prior_art_decisions": [],
        },
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
    if not isinstance(seeded.get("baseline_review"), dict):
        seeded["baseline_review"] = _initial(problem)["baseline_review"]
    if not isinstance(seeded.get("tactical_memory"), dict):
        seeded["tactical_memory"] = _initial(problem)["tactical_memory"]
    else:
        memory = _initial(problem)["tactical_memory"]
        memory.update(seeded["tactical_memory"])
        for key in ("failure_signatures", "reusable_assets", "constraints_learned", "decision_history", "reduction_ledger", "prior_art_decisions"):
            if not isinstance(memory.get(key), list):
                memory[key] = []
        seeded["tactical_memory"] = memory
    return seeded


def needs_baseline(problem: dict[str, Any]) -> bool:
    return load(problem).get("baseline_review", {}).get("status") != "complete"


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
    evidence_validation = attempt.get("evidence_validation")
    if isinstance(evidence_validation, dict) and evidence_validation.get("status") != "valid":
        state["synthesis_summary"] = (
            "Attempt retained without durable claim projection because its evidence receipt did not validate: "
            + state["synthesis_summary"]
        )[:8000]
        store.write_json_atomic(state_path(problem["id"]), state)
        return state
    if attempt.get("phase") == "baseline" and attempt.get("outcome") != "error":
        state["baseline_review"] = {
            "status": "complete",
            "reviewed_at": now,
            "source_attempt_id": attempt["id"],
            "source_status": _text(problem.get("problem_state"), 200),
            "facts_recorded": len(attempt.get("established_facts") or []),
            "exclusions_recorded": len(attempt.get("ruled_out") or []),
            "leads_recorded": len(attempt.get("open_leads") or []),
            "requirement": "Repeat when the authoritative status changes materially or the baseline is explicitly invalidated.",
        }

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
    route_evaluation = strategy.get("route_evaluation") or attempt.get("route_evaluation")
    if isinstance(route_evaluation, dict):
        strategy_row["route_evaluation"] = {
            key: value for key, value in route_evaluation.items()
            if key in {
                "gate_proximity", "contribution_value", "decisiveness", "novelty_confidence",
                "novelty_risk", "model_cost", "cpu_cost", "scope", "reuse_value",
            } and isinstance(value, (int, float)) and not isinstance(value, bool)
        }
    existing = next((row for row in state["strategies"] if row.get("fingerprint") == fingerprint), None)
    if existing:
        strategy_row["attempts"] = int(existing.get("attempts") or 0) + 1
        for key in ("title", "mechanism", "hypothesis", "discriminating_test", "blocker", "reopen_condition", "parent_ids", "route_evaluation"):
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

    learning = attempt.get("tactical_learning") if isinstance(attempt.get("tactical_learning"), dict) else {}
    memory = state.get("tactical_memory", _initial(problem)["tactical_memory"])
    bottleneck = _text(learning.get("bottleneck_update"), 2000)
    if bottleneck:
        memory["current_bottleneck"] = bottleneck
    signature = _text(learning.get("failure_signature"), 1000)
    if signature and signature.lower() not in {"none", "not applicable", "n/a"}:
        signature_id = hashlib.sha256(signature.lower().encode()).hexdigest()[:12]
        existing_signature = next((row for row in memory["failure_signatures"] if row.get("id") == signature_id), None)
        signature_row = {
            "id": signature_id, "signature": signature,
            "count": int(existing_signature.get("count") or 0) + 1 if existing_signature else 1,
            "last_strategy_id": strategy_row["id"], "last_attempt_id": attempt["id"], "updated_at": now,
        }
        memory["failure_signatures"] = [row for row in memory["failure_signatures"] if row.get("id") != signature_id]
        memory["failure_signatures"].append(signature_row)
        memory["failure_signatures"] = memory["failure_signatures"][-40:]
    assets = _object_rows(learning.get("reusable_assets"), ("name", "use", "evidence"), 20)
    for row in assets:
        row.update({"source_attempt_id": attempt["id"], "updated_at": now})
    memory["reusable_assets"] = _dedupe(memory["reusable_assets"] + assets, ("name",), 60)
    constraints = _object_rows(learning.get("constraints_learned"), ("constraint", "scope", "evidence"), 20)
    for row in constraints:
        row.update({"source_attempt_id": attempt["id"], "updated_at": now})
    memory["constraints_learned"] = _dedupe(memory["constraints_learned"] + constraints, ("constraint", "scope"), 80)
    reduction = attempt.get("space_reduction") if isinstance(attempt.get("space_reduction"), dict) else {}
    if reduction:
        reduction_row = {
            key: _text(reduction.get(key), 2000)
            for key in (
                "ambient_space", "represented_space_before", "eliminated_or_quotiented",
                "represented_space_after", "reduction_factor", "measurement_status", "unit",
                "coverage_scope", "soundness_basis", "remaining_unknown", "next_bulk_elimination",
            )
        }
        reduction_row.update({"source_attempt_id": attempt["id"], "strategy_id": strategy_row["id"], "updated_at": now})
        memory["reduction_ledger"] = _dedupe(
            memory["reduction_ledger"] + [reduction_row],
            ("ambient_space", "represented_space_after", "coverage_scope"), 60,
        )
    decision = _text(learning.get("route_decision"), 40)
    if decision:
        memory["decision_history"] = (memory["decision_history"] + [{
            "attempt_id": attempt["id"], "strategy_id": strategy_row["id"], "decision": decision,
            "prediction": _text(learning.get("prediction"), 1000),
            "observation": _text(learning.get("observation"), 1000),
            "surprise": _text(learning.get("surprise"), 1000),
            "next_discriminator": _text(learning.get("next_discriminator"), 1000), "updated_at": now,
        }])[-40:]
    prior = attempt.get("prior_art_check") if isinstance(attempt.get("prior_art_check"), dict) else {}
    if prior:
        memory["prior_art_decisions"] = (memory["prior_art_decisions"] + [{
            "attempt_id": attempt["id"], "strategy_id": strategy_row["id"],
            "nearest_method_ids": [_text(x, 200) for x in prior.get("nearest_method_ids", [])][:20],
            "classification": _text(prior.get("classification"), 80),
            "exact_delta": _text(prior.get("exact_delta"), 2000),
            "duplicate_risk": _text(prior.get("duplicate_risk"), 2000),
            "comparison_test": _text(prior.get("comparison_test"), 2000),
            "decision": _text(prior.get("decision"), 40),
            "source_urls": [_text(x, 1000) for x in prior.get("source_urls", [])][:20],
            "updated_at": now,
        }])[-60:]
    state["tactical_memory"] = memory

    proposals = _object_rows(
        attempt.get("strategy_proposals"),
        ("family", "mechanism", "hypothesis", "discriminating_test", "rationale"),
        10,
    )
    synthesis = _object_rows(
        attempt.get("synthesis_candidates"),
        (
            "family", "mechanism", "source_inputs", "transfer_hypothesis",
            "discriminating_test", "falsification_signal", "rationale",
        ),
        5,
    )
    for candidate in synthesis:
        candidate["hypothesis"] = candidate.get("transfer_hypothesis", "")
        candidate["origin"] = "cross_problem_or_cross_field_synthesis"
        candidate["parent_ids"] = [
            _text(value, 100)
            for value in next(
                (row.get("parent_strategy_ids", []) for row in attempt.get("synthesis_candidates", [])
                 if isinstance(row, dict) and _text(row.get("mechanism")) == candidate.get("mechanism")),
                [],
            )
            if _text(value, 100)
        ][:10]
    proposals.extend(synthesis)
    known = {row.get("fingerprint") for row in state["strategies"]}
    added_proposal_ids: list[str] = []
    for proposal in proposals:
        proposal_fp = strategy_fingerprint(proposal.get("family"), proposal.get("mechanism"))
        if proposal_fp in known:
            existing_id = next(row.get("id") for row in state["strategies"] if row.get("fingerprint") == proposal_fp)
            added_proposal_ids.append(existing_id)
            continue
        same_mechanism = next((
            row for row in state["strategies"]
            if row.get("status") not in {"blocked", "ruled_out", "exhausted", "superseded"}
            and _text(row.get("family"), 500).lower() == _text(proposal.get("family"), 500).lower()
            and mechanism_similarity(row.get("mechanism"), proposal.get("mechanism")) >= 0.25
        ), None)
        if same_mechanism:
            for key in ("hypothesis", "discriminating_test", "rationale"):
                if proposal.get(key):
                    same_mechanism[key] = proposal[key]
            same_mechanism["updated_at"] = now
            added_proposal_ids.append(same_mechanism["id"])
            continue
        proposal.update({
            "id": f"strategy-{proposal_fp}", "fingerprint": proposal_fp, "status": "proposed",
            "title": proposal.get("mechanism", "")[:500], "attempts": 0,
            "parent_ids": proposal.get("parent_ids") or [strategy_row["id"]], "updated_at": now,
        })
        state["strategies"].append(proposal)
        added_proposal_ids.append(proposal["id"])
        known.add(proposal_fp)

    continuation = attempt.get("continuation") if isinstance(attempt.get("continuation"), dict) else {}
    if not continuation and attempt.get("next_steps"):
        continuation = {"objective": attempt["next_steps"][0], "first_action": attempt["next_steps"][0]}
    recommended_strategy_id = strategy_row["id"]
    if decision == "redirect" and added_proposal_ids:
        recommended_strategy_id = added_proposal_ids[0]
    state["next_session"] = {
        "recommended_strategy_id": recommended_strategy_id,
        "objective": _text(continuation.get("objective"), 2000),
        "first_action": _text(continuation.get("first_action"), 2000),
        "stop_condition": _text(continuation.get("stop_condition"), 2000),
        "source_attempt_id": attempt["id"],
    }

    # New projections should never reintroduce stale actionable work. Historical
    # state remains available, but terminal-route leads and malformed strategies
    # are persisted as closed/ineligible at the projection boundary.
    state = reconcile_value(state, reconciled_at=now)["state"]
    store.write_json_atomic(state_path(problem["id"]), state)
    return state


def compact_for_prompt(problem: dict[str, Any]) -> str:
    state = reconcile_value(load(problem))["state"]
    payload = {
        "epoch_count": state.get("epoch_count"),
        "baseline_review": state.get("baseline_review", {}),
        "synthesis_summary": state.get("synthesis_summary"),
        "established_facts": state.get("established_facts", [])[-20:],
        "strategy_registry": state.get("strategies", [])[-30:],
        "open_leads": state.get("open_leads", [])[-20:],
        "ruled_out": state.get("ruled_out", [])[-20:],
        "tactical_memory": state.get("tactical_memory", {}),
        "next_session": state.get("next_session", {}),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def summary_counts(state: dict[str, Any]) -> dict[str, int]:
    state = reconcile_value(state)["state"]
    counts = Counter(str(row.get("status") or "unknown") for row in state.get("strategies", []))
    return {
        "promising": counts["promising"],
        "blocked": counts["blocked"],
        "ruled_out": len(state.get("ruled_out", [])),
        "open_leads": sum(1 for row in state.get("open_leads", []) if row.get("status", "open") == "open"),
    }
