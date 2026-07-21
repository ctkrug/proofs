from __future__ import annotations

import json
import math
from typing import Any

from . import research_state, store


TERMINAL_STATUSES = {"blocked", "ruled_out", "exhausted", "superseded"}
STATUS_WEIGHT = {
    "promising": 5,
    "active": 3,
    "proposed": 1,
    "blocked": -10,
    "ruled_out": -12,
    "exhausted": -12,
    "superseded": -12,
}

VALUE_DEFAULTS = {
    "gate_proximity": 0.35,
    "contribution_value": 0.5,
    "decisiveness": 0.5,
    "novelty_confidence": 0.4,
    "novelty_risk": 0.5,
    "scope": 0.4,
    "reuse_value": 0.4,
    "model_cost": 1.0,
    "cpu_cost": 1.0,
}


def _text(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _number(value: Any, default: float, *, low: float, high: float) -> float:
    """Parse finite numeric route metadata, falling back safely for legacy rows."""
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return min(high, max(low, parsed))


def _route_evaluation(row: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    raw: dict[str, Any] = {}
    for container in ("route_evaluation", "route_economics", "selection_metrics", "evaluation"):
        value = row.get(container)
        if isinstance(value, dict):
            raw.update(value)
    for key in VALUE_DEFAULTS:
        if key in row:
            raw[key] = row[key]
    metrics = {
        key: _number(raw.get(key), default, low=0.0, high=1.0)
        for key, default in VALUE_DEFAULTS.items()
        if key not in {"model_cost", "cpu_cost"}
    }
    metrics.update({
        key: _number(raw.get(key), VALUE_DEFAULTS[key], low=0.1, high=20.0)
        for key in ("model_cost", "cpu_cost")
    })
    return metrics, [key for key in VALUE_DEFAULTS if key not in raw]


def _value_per_cost(metrics: dict[str, float]) -> tuple[float, float, float]:
    benefit = (
        0.25 * metrics["contribution_value"]
        + 0.20 * metrics["gate_proximity"]
        + 0.20 * metrics["decisiveness"]
        + 0.15 * metrics["novelty_confidence"]
        + 0.10 * metrics["scope"]
        + 0.10 * metrics["reuse_value"]
    )
    novelty_adjusted = benefit * (1.0 - 0.6 * metrics["novelty_risk"])
    cost = 0.65 * metrics["model_cost"] + 0.35 * metrics["cpu_cost"]
    return benefit, cost, novelty_adjusted / max(cost, 0.1)


def _score_strategy(row: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    status = _text(row.get("status"), 40) or "proposed"
    attempts = max(0, int(row.get("attempts") or 0))
    recommended_id = _text(state.get("next_session", {}).get("recommended_strategy_id"), 200)
    recommended_row = next((item for item in state.get("strategies", []) if item.get("id") == recommended_id), {})
    follows_recommended_redirect = (
        recommended_row.get("status") in TERMINAL_STATUSES
        and recommended_id in (row.get("parent_ids") or [])
    )
    metrics, defaulted_metrics = _route_evaluation(row)
    expected_value, combined_cost, value_per_cost = _value_per_cost(metrics)
    meaningful = research_state.strategy_is_meaningful(row)
    continuation = row.get("id") == recommended_id or follows_recommended_redirect
    components = {
        "status": STATUS_WEIGHT.get(status, 0),
        "value_per_cost": round(min(value_per_cost, 1.0) * 80, 3),
        "cheap_discriminator": 3 if row.get("discriminating_test") else -3,
        "falsifiable_hypothesis": 2 if row.get("hypothesis") else -2,
        "open_lead": 2 if any(
            lead.get("strategy_id") == row.get("id") and lead.get("status", "open") == "open"
            for lead in state.get("open_leads", [])
        ) else 0,
        "repetition_cost": -min(attempts, 8) * 2,
        "unresolved_blocker": -5 if row.get("blocker") else 0,
        "reopen_evidence": 0,
        # Retained for old API consumers. Only continuation_effective enters the score.
        "continuation_priority": 30 if continuation else 0,
        "continuation_effective": 3 if continuation else 0,
    }
    # Reopen evidence is consumed by the attempt that tests it. If that attempt
    # ends terminal again, continue through a new child mechanism rather than
    # silently making the same closed route eligible forever.
    eligible = status not in TERMINAL_STATUSES and meaningful
    score = sum(value for key, value in components.items() if key != "continuation_priority")
    return {
        "strategy_id": row.get("id"),
        "fingerprint": row.get("fingerprint"),
        "family": _text(row.get("family"), 200),
        "mechanism": _text(row.get("mechanism"), 700),
        "status": status,
        "attempts": attempts,
        "eligible": eligible,
        "ineligible_reason": "" if eligible else (
            "terminal_status" if status in TERMINAL_STATUSES else "empty_or_error_strategy"
        ),
        "score": round(score, 3),
        "score_components": components,
        "route_evaluation": metrics,
        "route_evaluation_defaulted_fields": defaulted_metrics,
        "expected_value": round(expected_value, 4),
        "combined_cost": round(combined_cost, 4),
        "value_per_cost": round(value_per_cost, 4),
        "discriminating_test": _text(row.get("discriminating_test"), 1000),
        "blocker": _text(row.get("blocker"), 700),
        "reopen_condition": _text(row.get("reopen_condition"), 700),
    }


def build(problem: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, inspectable route decision from durable campaign evidence."""
    reconciliation = research_state.reconcile_value(research_state.load(problem))
    state = reconciliation["state"]
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
        "schema_version": 2,
        "decision_rule": "Typed, bounded expected contribution-information value per estimated model/CPU cost, adjusted for novelty risk, readiness, repetition, and route status. Missing metrics receive conservative visible defaults. This is a priority heuristic, not a probability or proof.",
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
        "state_reconciliation": reconciliation["report"],
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
            "open_ended_discovery": "The route menu is not closed. A proposed synthesis must name its inputs, mechanism-level transfer hypothesis, nearest prior art, and a cheap falsifier before it is eligible for compute.",
            "reduction_priority": "Prefer a sound class/cube/profile/family elimination over many labelled point blocks. Report exact expressions or honest upper bounds; never imply local-family coverage is global.",
            "end_state": "Record surprise, failure signature, exact constraints learned, reusable assets, route decision, and next discriminator.",
        },
    }


def compact_for_prompt(problem: dict[str, Any]) -> str:
    return json.dumps(build(problem), indent=2, ensure_ascii=False)
