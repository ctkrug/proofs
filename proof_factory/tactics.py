from __future__ import annotations

import json
from typing import Any

from . import research_state, store


TERMINAL_STATUSES = {"blocked", "ruled_out", "exhausted", "superseded"}
STATUS_WEIGHT = {
    "promising": 32,
    "active": 26,
    "proposed": 24,
    "blocked": -24,
    "ruled_out": -40,
    "exhausted": -44,
    "superseded": -48,
}


def _text(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _score_strategy(row: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    status = _text(row.get("status"), 40) or "proposed"
    attempts = max(0, int(row.get("attempts") or 0))
    components = {
        "status": STATUS_WEIGHT.get(status, 0),
        "cheap_discriminator": 10 if row.get("discriminating_test") else 0,
        "falsifiable_hypothesis": 6 if row.get("hypothesis") else 0,
        "open_lead": 8 if any(
            lead.get("strategy_id") == row.get("id") and lead.get("status", "open") == "open"
            for lead in state.get("open_leads", [])
        ) else 0,
        "repetition_cost": -min(attempts, 8) * 3,
        "unresolved_blocker": -8 if row.get("blocker") else 0,
        "reopen_evidence": 36 if status in TERMINAL_STATUSES and row.get("reopen_evidence") else 0,
    }
    eligible = status not in TERMINAL_STATUSES or bool(row.get("reopen_evidence"))
    return {
        "strategy_id": row.get("id"),
        "fingerprint": row.get("fingerprint"),
        "family": _text(row.get("family"), 200),
        "mechanism": _text(row.get("mechanism"), 700),
        "status": status,
        "attempts": attempts,
        "eligible": eligible,
        "score": sum(components.values()),
        "score_components": components,
        "discriminating_test": _text(row.get("discriminating_test"), 1000),
        "blocker": _text(row.get("blocker"), 700),
        "reopen_condition": _text(row.get("reopen_condition"), 700),
    }


def build(problem: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, inspectable route decision from durable campaign evidence."""
    state = research_state.load(problem)
    ranked = sorted(
        (_score_strategy(row, state) for row in state.get("strategies", [])),
        key=lambda row: (row["eligible"], row["score"], -row["attempts"], row.get("fingerprint") or ""),
        reverse=True,
    )
    eligible = [row for row in ranked if row["eligible"]]
    incumbent = eligible[0] if eligible else None
    challenger = next(
        (row for row in eligible[1:] if not incumbent or row["family"] != incumbent["family"]),
        eligible[1] if len(eligible) > 1 else None,
    )
    memory = state.get("tactical_memory", {})
    if state.get("baseline_review", {}).get("status") != "complete":
        stage = "baseline"
        directive = "Map authoritative status, prior work, exact acceptance tests, reusable assets, and scoped exclusions."
    elif not eligible:
        stage = "redirect"
        directive = "Do not repeat a closed route. Generate a different mechanism or produce evidence satisfying a recorded reopen condition."
    elif incumbent and incumbent["attempts"] >= 3 and incumbent["score_components"]["open_lead"] == 0:
        stage = "redirect"
        directive = "The leading route is repetition-heavy. Run a challenger discriminator or close the route at an exact scope."
    else:
        stage = "discriminate"
        directive = "Execute one cheapest test that can kill, redirect, or materially advance the top eligible route."

    return {
        "schema_version": 1,
        "decision_rule": "Transparent heuristic priority, not a probability or proof. Closed routes are ineligible without reopen evidence.",
        "contribution_target": {
            "objective": _text(state.get("objective") or problem.get("statement"), 2000),
            "acceptance_tests": problem.get("field_progress_gates") or state.get("completion_criteria", []),
            "external_verification": _text(problem.get("verifiability"), 1500),
        },
        "stage": stage,
        "directive": directive,
        "incumbent": incumbent,
        "challenger": challenger,
        "portfolio": ranked[:12],
        "knowledge_inventory": {
            "established_facts": len(state.get("established_facts", [])),
            "scoped_exclusions": len(state.get("ruled_out", [])),
            "open_leads": sum(1 for row in state.get("open_leads", []) if row.get("status", "open") == "open"),
            "failure_signatures": memory.get("failure_signatures", [])[-12:],
            "reusable_assets": memory.get("reusable_assets", [])[-12:],
            "reduction_ledger": memory.get("reduction_ledger", [])[-12:],
            "prior_art_decisions": memory.get("prior_art_decisions", [])[-12:],
            "current_bottleneck": _text(memory.get("current_bottleneck"), 1500),
        },
        "closed_routes": [row for row in ranked if not row["eligible"]][:12],
        "execution_contract": {
            "predeclare": ["prediction", "cheapest discriminator", "success signal", "failure signal", "redirect signal"],
            "one_epoch_limit": "One bounded discriminator; scale only after measured pilot throughput and shortcut validation.",
            "reduction_priority": "Prefer a sound class/cube/profile/family elimination over many labelled point blocks. Report exact expressions or honest upper bounds; never imply local-family coverage is global.",
            "end_state": "Record surprise, failure signature, exact constraints learned, reusable assets, route decision, and next discriminator.",
        },
    }


def compact_for_prompt(problem: dict[str, Any]) -> str:
    return json.dumps(build(problem), indent=2, ensure_ascii=False)
