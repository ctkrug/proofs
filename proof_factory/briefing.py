from __future__ import annotations

import json
from typing import Any

from . import events, lab, prior_art, research_state, roadmap, tactics


def _trim(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


def _route(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "strategy_id": row.get("strategy_id") or row.get("id"),
        "fingerprint": row.get("fingerprint"),
        "family": _trim(row.get("family"), 160),
        "mechanism": _trim(row.get("mechanism"), 700),
        "status": row.get("status"),
        "score": row.get("score"),
        "score_components": row.get("score_components", {}),
        "route_evaluation": row.get("route_evaluation", {}),
        "value_per_cost": row.get("value_per_cost"),
        "discriminating_test": _trim(row.get("discriminating_test"), 700),
        "blocker": _trim(row.get("blocker"), 500),
        "reopen_condition": _trim(row.get("reopen_condition"), 500),
    }


def build(problem: dict[str, Any]) -> dict[str, Any]:
    state = research_state.load(problem)
    tactical = tactics.build(problem)
    active_roadmap = roadmap.current(problem)
    prior = prior_art.load(problem)
    live_ids = {
        str(value)
        for row in (tactical.get("incumbent"), tactical.get("challenger"))
        if isinstance(row, dict)
        for value in (row.get("nearest_method_ids") or [])
    }
    methods = prior.get("methods", [])
    compact_methods = [{
        "id": row.get("id"),
        "family": _trim(row.get("family"), 140),
        "mechanism": _trim(row.get("mechanism"), 320),
        "scope_and_outcome": _trim(row.get("scope_and_outcome"), 350),
        "material_delta_required": _trim(row.get("material_delta_required"), 350),
        "sources": row.get("sources", [])[:3],
    } for row in methods if not live_ids or row.get("id") in live_ids]
    if len(compact_methods) < min(5, len(methods)):
        seen = {row["id"] for row in compact_methods}
        compact_methods.extend({
            "id": row.get("id"),
            "family": _trim(row.get("family"), 140),
            "mechanism": _trim(row.get("mechanism"), 240),
            "scope_and_outcome": _trim(row.get("scope_and_outcome"), 260),
            "material_delta_required": _trim(row.get("material_delta_required"), 260),
            "sources": row.get("sources", [])[:2],
        } for row in methods if row.get("id") not in seen)
    terminal = {"blocked", "ruled_out", "exhausted", "superseded"}
    open_leads = [row for row in state.get("open_leads", []) if row.get("status", "open") == "open"]
    strategies = {row.get("id"): row for row in state.get("strategies", [])}
    open_leads = [row for row in open_leads if strategies.get(row.get("strategy_id"), {}).get("status") not in terminal]
    lab_jobs = []
    for row in lab.status(str(problem.get("id")))["jobs"][-10:]:
        lab_jobs.append({
            "id": row.get("id"), "name": _trim(row.get("name"), 200),
            "status": row.get("status"), "segment": row.get("segment"),
            "decision_value": _trim(row.get("decision_value"), 500),
            "latest_progress": row.get("latest_progress", {}),
            "stop_reason": _trim(row.get("stop_reason"), 500),
            "state_source": f"state/labs/jobs/{row.get('id')}.json",
            "artifact_workspace": f"research/{problem.get('id')}/workspace",
        })
    return {
        "schema_version": 1,
        "rule": "This is the only injected campaign packet. Load larger files only when the selected discriminator needs them.",
        "problem": {
            "id": problem.get("id"), "title": problem.get("title"),
            "statement": _trim(problem.get("statement"), 1200),
            "source_url": problem.get("source_url"),
            "field_progress_gates": problem.get("field_progress_gates", []),
        },
        "state": {
            "epoch_count": state.get("epoch_count"),
            "last_updated": state.get("last_updated"),
            "summary": _trim(state.get("synthesis_summary"), 1200),
            "next_session": state.get("next_session", {}),
            "current_bottleneck": _trim(state.get("tactical_memory", {}).get("current_bottleneck"), 800),
            "newest_facts": state.get("established_facts", [])[-5:],
            "newest_exclusions": state.get("ruled_out", [])[-5:],
            "eligible_open_leads": open_leads[-6:],
            "newest_decisions": state.get("tactical_memory", {}).get("decision_history", [])[-4:],
            "newest_reductions": state.get("tactical_memory", {}).get("reduction_ledger", [])[-3:],
        },
        "tactics": {
            "stage": tactical.get("stage"), "directive": tactical.get("directive"),
            "incumbent": _route(tactical.get("incumbent")),
            "challenger": _route(tactical.get("challenger")),
            "closed_route_ids": [row.get("strategy_id") for row in tactical.get("closed_routes", [])[:8]],
        },
        "active_roadmap_phase": active_roadmap.get("active_phase"),
        "research_events": events.pending(str(problem.get("id")))[:10],
        "lab_experiments": lab_jobs,
        "prior_art": compact_methods[:14],
    }


def compact_for_prompt(problem: dict[str, Any], *, max_chars: int = 24000,
                       payload: dict[str, Any] | None = None) -> str:
    """Serialize one canonical packet; callers may reuse a once-per-epoch build."""
    source = payload if payload is not None else build(problem)
    text = json.dumps(source, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        payload = json.loads(json.dumps(source, ensure_ascii=False))
        payload["prior_art"] = payload["prior_art"][:7]
        payload["state"]["newest_facts"] = payload["state"]["newest_facts"][-3:]
        payload["state"]["newest_exclusions"] = payload["state"]["newest_exclusions"][-3:]
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        payload["prior_art"] = payload["prior_art"][:3]
        payload["state"]["eligible_open_leads"] = payload["state"]["eligible_open_leads"][-3:]
        payload["state"]["newest_decisions"] = payload["state"]["newest_decisions"][-2:]
        payload["state"]["newest_reductions"] = payload["state"]["newest_reductions"][-1:]
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        payload["prior_art"] = payload["prior_art"][:2]
        payload["state"]["newest_facts"] = payload["state"]["newest_facts"][-1:]
        payload["state"]["newest_exclusions"] = payload["state"]["newest_exclusions"][-1:]
        payload["state"]["eligible_open_leads"] = payload["state"]["eligible_open_leads"][-2:]
        payload["state"]["newest_decisions"] = []
        payload["state"]["newest_reductions"] = []
        phase = payload.get("active_roadmap_phase")
        if isinstance(phase, dict):
            payload["active_roadmap_phase"] = {
                "id": phase.get("id"), "objective": _trim(phase.get("objective"), 700),
                "required_artifact": _trim(phase.get("required_artifact"), 700),
                "promote_if": _trim(phase.get("promote_if"), 700),
            }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        phase = payload.get("active_roadmap_phase")
        if isinstance(phase, dict):
            phase = {
                "id": phase.get("id"),
                "objective": _trim(phase.get("objective"), 500),
                "required_artifact": _trim(phase.get("required_artifact"), 500),
                "promote_if": _trim(phase.get("promote_if"), 500),
            }
        payload = {
            "schema_version": payload.get("schema_version"),
            "rule": payload.get("rule"),
            "problem": {
                **payload.get("problem", {}),
                "statement": _trim(payload.get("problem", {}).get("statement"), 700),
                "field_progress_gates": [
                    _trim(value, 500) for value in payload.get("problem", {}).get("field_progress_gates", [])[:3]
                ],
            },
            "state": {
                "epoch_count": payload.get("state", {}).get("epoch_count"),
                "last_updated": payload.get("state", {}).get("last_updated"),
                "summary": _trim(payload.get("state", {}).get("summary"), 700),
                "next_session": payload.get("state", {}).get("next_session", {}),
                "current_bottleneck": _trim(payload.get("state", {}).get("current_bottleneck"), 500),
                "newest_facts": payload.get("state", {}).get("newest_facts", [])[-1:],
                "newest_exclusions": payload.get("state", {}).get("newest_exclusions", [])[-1:],
                "eligible_open_leads": payload.get("state", {}).get("eligible_open_leads", [])[-2:],
            },
            "tactics": payload.get("tactics", {}),
            "active_roadmap_phase": phase,
            "research_events": [{
                "id": row.get("id"), "kind": row.get("kind"), "created_at": row.get("created_at"),
                "evidence": _trim(row.get("evidence"), 600), "source": _trim(row.get("source"), 300),
            } for row in payload.get("research_events", [])[-3:]],
            "lab_experiments": [{
                "id": row.get("id"), "name": row.get("name"), "status": row.get("status"),
                "segment": row.get("segment"), "decision_value": _trim(row.get("decision_value"), 300),
                "latest_progress": {
                    key: row.get("latest_progress", {}).get(key)
                    for key in ("completed_units", "total_units", "throughput_per_second", "artifact_growth_bytes",
                                "correctness_checks_passed", "decision_value_active", "complete", "message")
                },
                "stop_reason": _trim(row.get("stop_reason"), 300), "state_source": row.get("state_source"),
            } for row in payload.get("lab_experiments", [])[-3:]],
            "prior_art": payload.get("prior_art", [])[:2],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        raise ValueError(f"canonical research brief exceeds {max_chars} characters after emergency compaction")
    return text
