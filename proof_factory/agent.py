from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from . import briefing, config, contribution_gate, evidence as evidence_layer, research_state, schemas, store, telemetry


RESULT_RE = re.compile(r"```proof_result\s*(\{.*?\})\s*```", re.DOTALL)
OUTCOMES = {"failed", "no_progress", "progress", "candidate"}
RESEARCH_SKILL = store.ROOT / "skills" / "computational-researcher" / "SKILL.md"
EXPERIMENT_RUNNER = store.ROOT / "skills" / "computational-researcher" / "scripts" / "run_experiment.py"
TERRA_MODEL = "gpt-5.6-terra"
SOL_MODEL = "gpt-5.6-sol"
DELEGATE_ROLES = {
    "hard": ("challenger-prior-art", "experiment-verification"),
    "easy": ("source-discriminator",),
}
ROUTE_DECISION_EVENT_KINDS = {"route_authorized", "source_changed", "external_feedback", "evidence_repaired"}
REPAIR_TIMEOUT_SECONDS = 180


def _text_projection(max_chars: int, *, default: str = "", strip: bool = False) -> dict[str, Any]:
    return {"kind": "text", "max_chars": max_chars, "default": default, "strip": strip}


def _string_list_projection(max_items: int, max_chars: int) -> dict[str, Any]:
    return {"kind": "string_list", "max_items": max_items, "max_chars": max_chars}


def _object_list_projection(max_items: int) -> dict[str, Any]:
    return {"kind": "object_list", "max_items": max_items}


def _object_projection(
    fields: dict[str, dict[str, Any]] | None = None, *, default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {"kind": "object", "fields": fields, "default": default or {}}


# One contract owns accepted result shapes, failure defaults, and the bounded attempt
# projection. Fields without a projection are consumed only while enforcing policy.
RESULT_SCHEMA: dict[str, dict[str, Any]] = {
    "outcome": {"kind": "enum", "choices": OUTCOMES, "default": "failed"},
    "approach": {"kind": "string", "required_nonempty": True, "default": "", "projection": _text_projection(4000, strip=True)},
    "summary": {"kind": "string", "required_nonempty": True, "default": "", "projection": _text_projection(8000, strip=True)},
    "rationale": {"kind": "string", "required_nonempty": True, "default": "", "projection": _text_projection(4000, strip=True)},
    "claims": {"kind": "list", "default": [], "projection": _string_list_projection(20, 2000)},
    "evidence": {"kind": "list", "default": [], "projection": _string_list_projection(30, 2000)},
    "evidence_files": {"kind": "list", "default": [], "projection": _string_list_projection(2000, 1000)},
    "next_steps": {"kind": "list", "default": [], "projection": _string_list_projection(20, 2000)},
    "citations": {"kind": "list", "default": [], "projection": _string_list_projection(30, 1000)},
    "techniques": {"kind": "list", "default": [], "projection": _string_list_projection(30, 200)},
    "experiments": {"kind": "list", "default": [], "projection": _string_list_projection(30, 2000)},
    "transfer_insights": {"kind": "list", "default": [], "projection": _string_list_projection(20, 2000)},
    "established_facts": {"kind": "list", "default": [], "projection": _object_list_projection(30)},
    "ruled_out": {"kind": "list", "default": [], "projection": _object_list_projection(30)},
    "open_leads": {"kind": "list", "default": [], "projection": _object_list_projection(30)},
    "strategy_proposals": {"kind": "list", "default": [], "projection": _object_list_projection(10)},
    "synthesis_candidates": {
        "kind": "list", "default": [], "projection": _object_list_projection(30),
        "item": {
            "kind": "object",
            "required_nonempty": (
                "family", "mechanism", "source_inputs", "transfer_hypothesis",
                "discriminating_test", "falsification_signal",
            ),
            "list_fields": {"parent_strategy_ids": False},
        },
    },
    "strategy": {"kind": "object", "default": {}, "projection": _object_projection()},
    "continuation": {"kind": "object", "default": {}, "projection": _object_projection()},
    "candidate_profile": {"kind": "object", "default": {}, "projection": _object_projection()},
    "campaign_assessment": {"kind": "object", "default": {}, "projection": _object_projection()},
    "resolution_portfolio": {"kind": "object", "default": {}, "projection": _object_projection()},
    "search_efficiency": {
        "kind": "object", "required": True, "default": {},
        "required_nonempty": ("naive_space", "chosen_mechanism", "estimated_or_measured_savings", "soundness_guard"),
        "list_fields": {"reductions_considered": True},
        "projection": _object_projection({
            "naive_space": _text_projection(2000),
            "reductions_considered": _string_list_projection(20, 500),
            "chosen_mechanism": _text_projection(2000),
            "estimated_or_measured_savings": _text_projection(2000),
            "soundness_guard": _text_projection(2000),
        }),
    },
    "space_reduction": {
        "kind": "object", "required": True, "default": {},
        "required_nonempty": (
            "ambient_space", "represented_space_before", "eliminated_or_quotiented",
            "represented_space_after", "reduction_factor", "measurement_status", "unit",
            "coverage_scope", "soundness_basis", "remaining_unknown", "next_bulk_elimination",
        ),
        "enum_fields": {"measurement_status": {"exact", "upper_bound", "estimate", "not_applicable"}},
        "projection": _object_projection({
            key: _text_projection(4000) for key in (
                "ambient_space", "represented_space_before", "eliminated_or_quotiented",
                "represented_space_after", "reduction_factor", "measurement_status", "unit",
                "coverage_scope", "soundness_basis", "remaining_unknown", "next_bulk_elimination",
            )
        }),
    },
    "tactical_learning": {
        "kind": "object", "required": True, "default": {},
        "required_nonempty": (
            "prediction", "observation", "surprise", "failure_signature", "bottleneck_update",
            "route_decision", "next_discriminator",
        ),
        "list_fields": {"reusable_assets": False, "constraints_learned": False},
        "enum_fields": {"route_decision": {"continue", "hold", "redirect", "close"}},
        "projection": _object_projection({
            "prediction": _text_projection(2000),
            "observation": _text_projection(2000),
            "surprise": _text_projection(2000),
            "failure_signature": _text_projection(2000),
            "bottleneck_update": _text_projection(2000),
            "reusable_assets": _object_list_projection(20),
            "constraints_learned": _object_list_projection(20),
            "route_decision": _text_projection(40),
            "next_discriminator": _text_projection(2000),
        }),
    },
    "prior_art_check": {
        "kind": "object", "required": True, "default": {},
        "required_nonempty": ("exact_delta", "duplicate_risk", "comparison_test"),
        "list_fields": {"nearest_method_ids": True, "source_urls": False},
        "enum_fields": {
            "classification": {"genuinely_different", "material_modification", "replication_control"},
            "decision": {"proceed", "control_only", "stop"},
        },
        "projection": _object_projection({
            "nearest_method_ids": _string_list_projection(20, 200),
            "classification": _text_projection(80),
            "exact_delta": _text_projection(3000),
            "duplicate_risk": _text_projection(3000),
            "comparison_test": _text_projection(3000),
            "decision": _text_projection(40),
            "source_urls": _string_list_projection(20, 1000),
        }),
    },
    "field_progress_assessment": {
        "kind": "object", "required": True, "default": {},
        "required_nonempty": (
            "gate_id", "contribution_class", "closest_prior_result", "measurable_improvement",
            "independent_validation", "external_audience", "remains_unproved", "route_recommendation",
        ),
        "enum_fields": {"status": {"met", "not_met"}},
        "projection": _object_projection({
            key: _text_projection(4000) for key in (
                "status", "gate_id", "contribution_class", "closest_prior_result", "measurable_improvement",
                "independent_validation", "external_audience", "remains_unproved", "route_recommendation",
            )
        }),
    },
    "lab_review": {
        "kind": "object", "default": {"decision": "none"},
        "enum_fields": {"decision": {"none", "continue", "validate", "promote", "redirect"}},
        "actionable_required": ("job_id", "reason"),
        "projection": _object_projection(default={"decision": "none"}),
    },
    "hypothesis": {"kind": "any", "default": "", "projection": _text_projection(4000)},
    "discriminating_test": {"kind": "any", "default": "", "projection": _text_projection(4000)},
    "strategy_status": {"kind": "any", "default": "active", "projection": _text_projection(100, default="active")},
    "research_mode": {"kind": "any", "default": "unspecified", "projection": _text_projection(100, default="unspecified")},
    "independent_checker": {"kind": "any", "default": "not provided", "projection": _text_projection(4000, default="not provided")},
    "blocker": {"kind": "any", "default": "", "projection": _text_projection(4000)},
    "reopen_condition": {"kind": "any", "default": "", "projection": _text_projection(4000)},
    "reopen_evidence": {"kind": "any", "default": "", "projection": _text_projection(4000)},
    "tool_disclosure": {"kind": "any", "default": "", "projection": _text_projection(4000)},
}


def _result_defaults() -> dict[str, Any]:
    return {
        name: value.copy() if isinstance((value := spec.get("default")), (dict, list)) else value
        for name, spec in RESULT_SCHEMA.items()
    }


def _project_value(value: Any, projection: dict[str, Any]) -> Any:
    kind = projection["kind"]
    if kind == "text":
        default = projection.get("default", "")
        rendered = str(value or default)
        if projection.get("strip"):
            rendered = rendered.strip()
        return rendered[:projection["max_chars"]]
    if kind == "string_list":
        rows = value if isinstance(value, list) else []
        return [str(row)[:projection["max_chars"]] for row in rows][:projection["max_items"]]
    if kind == "object_list":
        rows = value if isinstance(value, list) else []
        return [row for row in rows if isinstance(row, dict)][:projection["max_items"]]
    if kind == "object":
        if not isinstance(value, dict):
            return projection.get("default", {}).copy()
        fields = projection.get("fields")
        if fields is None:
            return value
        return {name: _project_value(value.get(name), field) for name, field in fields.items()}
    raise ValueError(f"unknown result projection kind: {kind}")


def _project_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        name: _project_value(result.get(name, spec.get("default")), spec["projection"])
        for name, spec in RESULT_SCHEMA.items()
        if "projection" in spec
    }


def _original_protected_fields(text: str) -> dict[str, str]:
    patterns = {
        "outcome": r'"outcome"\s*:\s*"([^"]+)"',
        "prior_art_classification": r'"classification"\s*:\s*"([^"]+)"',
        "field_progress_status": r'"field_progress_assessment"\s*:\s*\{.*?"status"\s*:\s*"([^"]+)"',
    }
    return {
        key: match.group(1)
        for key, pattern in patterns.items()
        if (match := re.search(pattern, text or "", re.DOTALL))
    }


def _enforce_repair_guard(original_text: str, repaired: dict[str, Any]) -> None:
    protected = _original_protected_fields(original_text)
    if protected.get("outcome") not in RESULT_SCHEMA["outcome"]["choices"]:
        raise ValueError("JSON repair cannot recover a missing or invalid original outcome")
    if protected.get("prior_art_classification") not in RESULT_SCHEMA["prior_art_check"]["enum_fields"]["classification"]:
        raise ValueError("JSON repair cannot recover a missing or invalid original prior-art classification")
    if protected.get("field_progress_status") not in RESULT_SCHEMA["field_progress_assessment"]["enum_fields"]["status"]:
        raise ValueError("JSON repair cannot recover a missing or invalid original field-progress status")
    repaired_fields = {
        "outcome": str(repaired.get("outcome") or ""),
        "prior_art_classification": str(repaired.get("prior_art_check", {}).get("classification") or ""),
        "field_progress_status": str(repaired.get("field_progress_assessment", {}).get("status") or ""),
    }
    for key, original in protected.items():
        if repaired_fields.get(key) != original:
            raise ValueError(f"JSON repair changed protected field {key}: {original!r} -> {repaired_fields.get(key)!r}")


def _repair_prompt(original_text: str, validation_error: Exception) -> str:
    return f"""You repair serialization only. Do not change, add, reinterpret, strengthen, or upgrade substantive content.
Emit exactly one fenced `proof_result` JSON object and no other prose.

SCHEMA CONTRACT
- outcome is failed|no_progress|progress|candidate and must remain exactly the original value.
- approach, summary, and rationale are nonempty strings.
- claims, evidence, evidence_files, next_steps, citations, techniques, experiments, transfer_insights,
  established_facts, ruled_out, open_leads, strategy_proposals, and synthesis_candidates are arrays.
- strategy, continuation, candidate_profile, campaign_assessment, search_efficiency, space_reduction,
  tactical_learning, prior_art_check, field_progress_assessment, lab_review, and resolution_portfolio are objects.
- prior_art_check.classification and field_progress_assessment.status must remain exactly their original values.
- Fill only structurally missing JSON fields with neutral empty/default values; never invent evidence or a stronger class.

VALIDATION ERROR
{type(validation_error).__name__}: {str(validation_error)[:2000]}

ORIGINAL OUTPUT
{(original_text or '')[-32000:]}
"""


def repair_result(text: str, validation_error: Exception, *, model: str, workspace: Path,
                  timeout: int) -> tuple[dict[str, Any], dict[str, Any]]:
    repaired_text, usage = _run_codex(
        _repair_prompt(text, validation_error), model=model, effort="low", workspace=workspace,
        timeout=min(REPAIR_TIMEOUT_SECONDS, timeout),
        telemetry_meta={"role": "json-repair", "lane": "repair", "problem_id": workspace.parent.name, "phase": "repair"},
    )
    result = extract_result(repaired_text)
    _enforce_repair_guard(text, result)
    return result, usage


def _codex_text(raw: str) -> tuple[str, dict[str, Any], bool]:
    text = ""
    usage: dict[str, Any] = {}
    failed = False
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                text = item["text"]
        elif event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
        elif event.get("type") in {"turn.failed", "error"}:
            failed = True
    return text, usage, failed


def extract_result(text: str) -> dict[str, Any]:
    matches = RESULT_RE.findall(text or "")
    if not matches:
        raise ValueError("missing final proof_result JSON block")
    result = schemas.parse_json_object(matches[-1], kind="proof_result")
    if result.get("outcome") not in RESULT_SCHEMA["outcome"]["choices"]:
        raise ValueError(f"invalid outcome: {result.get('outcome')!r}")
    for key, spec in RESULT_SCHEMA.items():
        if spec.get("kind") == "string" and spec.get("required_nonempty"):
            if not isinstance(result.get(key), str) or not result[key].strip():
                raise ValueError(f"missing result field: {key}")
    for key, spec in RESULT_SCHEMA.items():
        if spec.get("kind") == "list" and not isinstance(result.get(key, spec["default"]), list):
            raise ValueError(f"{key} must be a list")
    for candidate in result.get("synthesis_candidates", []):
        if not isinstance(candidate, dict):
            raise ValueError("synthesis_candidates entries must be objects")
        candidate_schema = RESULT_SCHEMA["synthesis_candidates"]["item"]
        required_candidate = candidate_schema["required_nonempty"]
        missing_candidate = [key for key in required_candidate if not str(candidate.get(key) or "").strip()]
        if missing_candidate:
            raise ValueError(f"synthesis candidate missing fields: {missing_candidate}")
        for key in candidate_schema["list_fields"]:
            if not isinstance(candidate.get(key, []), list):
                raise ValueError(f"synthesis_candidate.{key} must be a list")
    for key, spec in RESULT_SCHEMA.items():
        if spec.get("kind") != "object" or key == "lab_review":
            continue
        value = result.get(key) if spec.get("required") else result.get(key, spec["default"])
        if not isinstance(value, dict):
            raise ValueError(f"{key} must be an object")
    lab_review = result.get("lab_review", {})
    if not isinstance(lab_review, dict):
        raise ValueError("lab_review must be an object")
    lab_schema = RESULT_SCHEMA["lab_review"]
    if lab_review.get("decision", "none") not in lab_schema["enum_fields"]["decision"]:
        raise ValueError("lab_review.decision is invalid")
    if lab_review.get("decision", "none") != "none" and not all(
        str(lab_review.get(key) or "").strip() for key in lab_schema["actionable_required"]
    ):
        raise ValueError("an actionable lab_review requires job_id and reason")
    efficiency = result["search_efficiency"]
    efficiency_schema = RESULT_SCHEMA["search_efficiency"]
    required_efficiency = efficiency_schema["required_nonempty"]
    missing_efficiency = [key for key in required_efficiency if not str(efficiency.get(key) or "").strip()]
    if missing_efficiency:
        raise ValueError(f"search_efficiency missing fields: {missing_efficiency}")
    if not isinstance(efficiency.get("reductions_considered"), list) or (
        efficiency_schema["list_fields"]["reductions_considered"] and not efficiency["reductions_considered"]
    ):
        raise ValueError("search_efficiency.reductions_considered must be a nonempty list")
    reduction = result["space_reduction"]
    reduction_schema = RESULT_SCHEMA["space_reduction"]
    required_reduction = reduction_schema["required_nonempty"]
    missing_reduction = [key for key in required_reduction if not str(reduction.get(key) or "").strip()]
    if missing_reduction:
        raise ValueError(f"space_reduction missing fields: {missing_reduction}")
    if reduction.get("measurement_status") not in reduction_schema["enum_fields"]["measurement_status"]:
        raise ValueError("space_reduction.measurement_status must be exact|upper_bound|estimate|not_applicable")
    learning = result["tactical_learning"]
    learning_schema = RESULT_SCHEMA["tactical_learning"]
    required_learning = learning_schema["required_nonempty"]
    missing_learning = [key for key in required_learning if not str(learning.get(key) or "").strip()]
    if missing_learning:
        raise ValueError(f"tactical_learning missing fields: {missing_learning}")
    if learning.get("route_decision") not in learning_schema["enum_fields"]["route_decision"]:
        raise ValueError("tactical_learning.route_decision must be continue|hold|redirect|close")
    for key in learning_schema["list_fields"]:
        if not isinstance(learning.get(key), list):
            raise ValueError(f"tactical_learning.{key} must be a list")
    prior = result["prior_art_check"]
    prior_schema = RESULT_SCHEMA["prior_art_check"]
    required_prior = prior_schema["required_nonempty"]
    missing_prior = [key for key in required_prior if not str(prior.get(key) or "").strip()]
    if missing_prior:
        raise ValueError(f"prior_art_check missing fields: {missing_prior}")
    if not isinstance(prior.get("nearest_method_ids"), list) or (
        prior_schema["list_fields"]["nearest_method_ids"] and not prior["nearest_method_ids"]
    ):
        raise ValueError("prior_art_check.nearest_method_ids must be a nonempty list")
    if not isinstance(prior.get("source_urls"), list):
        raise ValueError("prior_art_check.source_urls must be a list")
    if prior.get("classification") not in prior_schema["enum_fields"]["classification"]:
        raise ValueError("prior_art_check.classification must be genuinely_different|material_modification|replication_control")
    if prior.get("decision") not in prior_schema["enum_fields"]["decision"]:
        raise ValueError("prior_art_check.decision must be proceed|control_only|stop")
    field_progress = result["field_progress_assessment"]
    progress_schema = RESULT_SCHEMA["field_progress_assessment"]
    if field_progress.get("status") not in progress_schema["enum_fields"]["status"]:
        raise ValueError("field_progress_assessment.status must be met|not_met")
    required_progress = progress_schema["required_nonempty"]
    missing_progress = [key for key in required_progress if not str(field_progress.get(key) or "").strip()]
    if missing_progress:
        raise ValueError(f"field_progress_assessment missing fields: {missing_progress}")
    return result


def _error_result(problem: dict[str, Any], model: str, exc: Exception) -> dict[str, Any]:
    result = _result_defaults()
    result.update({
        "approach": "Headless research pass",
        "summary": f"The pass did not produce a valid research result: {type(exc).__name__}: {exc}",
        "rationale": "Infrastructure or output-contract failure is not mathematical progress.",
        "search_efficiency": {
            "naive_space": "not reached", "reductions_considered": ["not reached"],
            "chosen_mechanism": "not reached", "estimated_or_measured_savings": "not reached",
            "soundness_guard": "no mathematical claim accepted",
        },
        "space_reduction": {
            "ambient_space": "research epoch", "represented_space_before": "not reached",
            "eliminated_or_quotiented": "none", "represented_space_after": "unchanged",
            "reduction_factor": "none", "measurement_status": "not_applicable", "unit": "not applicable",
            "coverage_scope": "no mathematical search completed", "soundness_basis": "no claim accepted",
            "remaining_unknown": "the full target", "next_bulk_elimination": "repair the epoch before search",
        },
        "tactical_learning": {
            "prediction": "produce a valid bounded epoch", "observation": "output contract or infrastructure failure",
            "surprise": "the epoch failed before evaluation", "failure_signature": f"{type(exc).__name__}: invalid epoch output",
            "bottleneck_update": "repair the epoch failure before further research",
            "reusable_assets": [], "constraints_learned": [], "route_decision": "hold",
            "next_discriminator": "rerun the smallest valid output-contract control",
        },
        "prior_art_check": {
            "nearest_method_ids": ["not-applicable"], "classification": "replication_control",
            "exact_delta": "none; the epoch failed before comparison", "duplicate_risk": "unknown",
            "comparison_test": "repair and rerun the smallest output-contract control", "decision": "stop",
            "source_urls": [problem["source_url"]],
        },
        "field_progress_assessment": {
            "status": "not_met", "gate_id": "none", "contribution_class": "infrastructure failure",
            "closest_prior_result": "previous valid epoch", "measurable_improvement": "none",
            "independent_validation": "not applicable", "external_audience": "none",
            "remains_unproved": "the full research target", "route_recommendation": "hold and repair the epoch failure",
        },
        "next_steps": ["Repair the failed pass and rerun."],
        "citations": [problem["source_url"]],
        "tool_disclosure": f"Codex {model} principal with {TERRA_MODEL} delegates; run failed before a valid disclosure was returned.",
    })
    return result


def _research_contract() -> str:
    try:
        return RESEARCH_SKILL.read_text()
    except OSError as exc:
        raise RuntimeError(f"computational researcher skill unavailable: {exc}") from exc


def delegate_roles(lane: str, admitting_events: list[dict[str, Any]] | None = None) -> tuple[str, ...]:
    """Spend challenger calls only when the admitting evidence can change the route."""
    if lane != "hard":
        return DELEGATE_ROLES[lane]
    kinds = {str(row.get("kind") or "") for row in (admitting_events or [])}
    if kinds.intersection(ROUTE_DECISION_EVENT_KINDS):
        return DELEGATE_ROLES["hard"]
    if kinds and kinds.issubset({"lab_segment_completed"}):
        return ()
    if kinds and kinds.issubset({"lab_segment_completed", "lab_completed"}):
        return ("experiment-verification",)
    return DELEGATE_ROLES["hard"]


def build_delegate_prompt(
    problem: dict[str, Any], lane: str, workspace: Path, role: str, phase: str = "technical",
    canonical_brief: str | None = None,
) -> str:
    dossier = store.RESEARCH / problem["id"] / "DOSSIER.md"
    role_job = {
        "challenger-prior-art": (
            "Attack the incumbent from a genuinely different route and current prior art. Identify overlap, a missing premise, "
            "or a cheaper challenger. Do not duplicate the experiment delegate's execution plan."
        ),
        "experiment-verification": (
            "Design the cheapest decisive experiment and its independent verification plan. Inspect existing artifacts, "
            "name exact controls and stop conditions, and attack the likely failure modes."
        ),
        "source-discriminator": (
            "Verify the target's exact source/status and propose the cheapest executable discriminator, including the "
            "artifact and outside acceptance path that would make a positive result matter."
        ),
    }.get(role, "Produce a bounded research memo that helps the principal choose and falsify one route.")
    return f"""You are a GPT-5.6 Terra delegate in a Sol-Terra computational-research team.
You are not the principal investigator and may not promote a result. Your job is compact reconnaissance that makes the
upcoming Sol pass more concrete, less duplicative, and easier to falsify.

TARGET
Title: {problem['title']}
Statement: {problem['statement']}
Official/current source: {problem['source_url']}
Lane: {lane}
Phase: {phase}
Shared research workspace: {workspace}
This workspace is its own public Git repository. Preserve substantive literature notes, code, proof
files, checkers, findings, negative results, and write-ups here. The checkpoint service records the complete
epoch automatically; do not rewrite Git history, change remotes, or treat a commit as validation.
Full project dossier when present: {dossier}

DELEGATE ROLE: {role}
{role_job}

CANONICAL ROUTE BRIEF
{canonical_brief if canonical_brief is not None else briefing.compact_for_prompt(problem, max_chars=18000)}

PRIOR-ART ANTI-REDISCOVERY REGISTER
The current compact register is embedded in the canonical route brief. Open the full JSON only for the selected route.

RULES
1. Read relevant files in the shared workspace and consult the full project dossier when it exists.
2. Do not repeat a blocked or ruled-out route without satisfying its recorded reopen condition. Compare the proposed
   mechanism with the nearest registered historical methods; label replications as controls and state the exact delta.
3. Distinguish sourced fact, reported computation, inference, and proposal. Preserve direct source URLs.
4. Do not declare a proof, disproof, or candidate. Do not edit the durable research map or append-only ledger.
5. Return a memo under 800 words with: best live route; exact rationale; cheapest discriminator; controls; failure modes;
   reusable artifact; stop condition; and what the Sol principal should reject or verify independently. For any large
   search, include a search-efficiency pass covering symmetry/canonicalization, compression, batching/vectorization,
   incremental evaluation, decomposition, pruning, and reusable solver state; quantify the best safe reduction.
6. This research service has network access and installed lab tools, but no deployment, GitHub, or personal credentials.
   If a source or tool is practically missing, try the safe, reproducible repair or retrieval first and preserve its URL,
   command, and hash. Do not end a pass by merely reporting a fixable access restriction.
"""


def _minimal_env() -> dict[str, str]:
    allowed = {
        "HOME", "PATH", "LANG", "LC_ALL", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env.setdefault("HOME", "/root")
    return env


def _run_codex(prompt: str, *, model: str, effort: str, workspace: Path, timeout: int,
               telemetry_meta: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
    command = [
        config.get_text("CODEX_BIN", "codex"), "exec", "--ephemeral", "--json",
        "--sandbox", config.get_text(
            "PROOF_CODEX_SANDBOX", "danger-full-access",
            choices={"read-only", "workspace-write", "danger-full-access"},
        ),
        "-c", 'approval_policy="never"',
        "-c", 'forced_login_method="chatgpt"',
        "-c", f'model_reasoning_effort="{effort}"',
        "--ignore-user-config", "--ignore-rules", "--model", model, "-",
    ]
    started = time.monotonic()
    proc = subprocess.run(
        command, input=prompt, text=True, capture_output=True, cwd=workspace,
        env=_minimal_env(), timeout=timeout, start_new_session=True,
    )
    text, usage, stream_failed = _codex_text(proc.stdout)
    if proc.returncode != 0 or stream_failed or not text.strip():
        detail = (proc.stderr or proc.stdout)[-1000:]
        if telemetry_meta:
            telemetry.codex_call(prompt=prompt, output=detail, usage=usage, model=model, effort=effort,
                                 duration_seconds=time.monotonic() - started, outcome="error", **telemetry_meta)
        raise RuntimeError(f"Codex {model} failed rc={proc.returncode}: {detail}")
    if telemetry_meta:
        telemetry.codex_call(prompt=prompt, output=text, usage=usage, model=model, effort=effort,
                             duration_seconds=time.monotonic() - started, outcome="ok", **telemetry_meta)
    return text, usage


def _constant_prefix_first(prompt: str) -> str:
    """Move invariant principal contracts ahead of every epoch-specific value."""
    skill_marker = "OPERATING SKILL\n"
    current_marker = "CURRENT TASK STATEMENT\n"
    if skill_marker not in prompt or current_marker not in prompt:
        return prompt
    intro, body = prompt.split(skill_marker, 1)
    body = skill_marker + body
    spans: list[tuple[int, int, str]] = []
    for start_marker, end_marker in (
        ("ACCEPTABLE CONTRIBUTIONS\n", "LANE AND THIS EPOCH'S JOB\n"),
        ("SOL-TERRA ORCHESTRATION\n", "TERRA DELEGATE MEMOS\n"),
    ):
        start = body.index(start_marker)
        end = body.index(end_marker, start)
        spans.append((start, end, body[start:end]))
    schema_start = body.index("11. End with exactly one fenced JSON block in this schema:\n")
    spans.append((schema_start, len(body), body[schema_start:]))
    for start, end, _ in sorted(spans, reverse=True):
        body = body[:start] + body[end:]
    insertion = body.index(current_marker)
    constant_blocks = "\n".join(block for _, _, block in spans)
    return body[:insertion] + constant_blocks + "\n" + intro + body[insertion:]


def build_prompt(
    problem: dict[str, Any], lane: str, workspace: Path,
    delegate_memos: list[dict[str, Any]] | None = None,
    phase: str = "technical",
    canonical_brief: str | None = None,
) -> str:
    hard = lane == "hard"
    epoch_minutes = 120 if hard else 60
    delegated = delegate_memos or []
    phase_contract = (
        "MANDATORY BASELINE PHASE. Do not try to solve the problem or launch a frontier search. Audit the exact statement "
        "and current status from authoritative sources; map historical/current methods; record established facts, scoped "
        "negative results, live leads, closest prior work, reusable datasets/software, verification tooling, compute scale, "
        "and a credible external acceptance path. Populate the structured memory fields and leave one first technical "
        "experiment with controls and a stop condition. Use outcome progress unless the source is invalid or the audit fails."
        if phase == "baseline" else
        "TECHNICAL PHASE. The source/status baseline is complete. Start from its live leads and exclusions; execute one "
        "bounded discriminator and update the durable map with exact evidence."
    )
    completed_campaign_runs = store.discovery_campaign_run_count(problem)
    campaign_minimum = max(
        store.DISCOVERY_CAMPAIGN_MIN_RUNS,
        int(problem.get("campaign_min_runs") or 0),
    )
    next_campaign_run = completed_campaign_runs + 1
    one_shot = bool(
        not hard
        and problem.get("automation_eligible") is True
        and int(problem.get("difficulty") or 10) <= 3
        and int(problem.get("verification_score") or 0) >= 8
        and "github.com/" in str(problem.get("source_url") or "")
    )
    one_shot_contract = "" if not one_shot else """
ONE-SHOT CONTRIBUTION MODE
This is a bounded, high-verifiability repository contribution. Aim to finish the implementation, focused regression
tests, independent deterministic checker, and review-ready patch in this epoch. Do not spend a separate turn merely
repeating source triage that is already recorded. A completed contribution must request `candidate` immediately; the
campaign minimum never delays a completed candidate. Record the materially separate checker as an independent validation
of type `deterministic_checker` with its immutable artifact path. This makes the result eligible for isolated human review,
not verified, accepted, or published. If the task cannot be completed, preserve the exact blocker and smallest next action.
"""
    campaign_contract = "" if hard else f"""
DISCOVERY CAMPAIGN
This is non-error research run {next_campaign_run} on this problem; the minimum review point is run {campaign_minimum}.
The minimum applies only while the recognized target remains unresolved; it never blocks a completed `candidate`.
Do not recommend switching an unresolved problem before that minimum. At the end of every run, return `campaign_assessment`.
Before run {campaign_minimum}, its decision must be `continue` for unresolved work. At or after run {campaign_minimum}, use `continue` only
when `close_signal` names concrete evidence that the next bounded pass has a credible path to a verifiable contribution;
otherwise use `hold`. A merely open problem, generic optimism, or a renamed dead route is not a close signal.
{one_shot_contract}
"""
    prompt = f"""You are the next principal-investigator epoch in an indefinitely continuing, headless research campaign.
The campaign has no preset final number of epochs. This process has a {epoch_minutes}-minute safety ceiling, so leave a
precise checkpoint that lets a future session continue without rediscovering your work. Never interpret the long horizon
as permission to inflate a claim, repeat a dead route, or hide uncertainty.

OPERATING SKILL
{_research_contract()}

CURRENT TASK STATEMENT
Title: {problem['title']}
Contribution type: {problem.get('contribution_type') or 'open-problem research'}
Statement: {problem['statement']}
Official/current source: {problem['source_url']}
Source status: {problem.get('problem_state')}
Formalization: {problem.get('formalization_url') or '(none known)'}
Why selected: {problem.get('rationale')}
Verification contract: {problem.get('verifiability')}
Known techniques: {', '.join(problem.get('techniques') or [])}
Field-progress gates: {json.dumps(problem.get('field_progress_gates') or ['Use the sourced contribution and verification contract.'], ensure_ascii=False)}

RESEARCH PHASE
{phase_contract}
{campaign_contract}

LAB AUTHORITY
Use pinned, project-scoped tools and the pre-acquired sources in the workspace. Do not install system packages, change
host configuration, edit credentials, or write outside the problem workspace. Submit deterministic work expected to
take more than two minutes to the checkpointed lab; a model epoch should design or review that job, not babysit it.

ACCEPTABLE CONTRIBUTIONS
Terminal success is a concrete proof, counterexample/witness, exact optimum/classification, verified computational bound,
formalization, correction, or research-software contribution that satisfies the verification contract. On a famous problem,
a genuinely new rigorous lemma, reduction, parametric family, or falsified major route is useful progress even when it is
not terminal success. A model cannot promote its own work: `candidate` is only a request to run the
fail-closed contribution gate below. If that gate fails, the system records an internal result/progress.

WHAT DOES NOT COUNT
- Checking examples without a theorem matching the checked scope.
- Repackaging a known reduction or silently assuming the theorem-strength missing lemma.
- A formal power series, numerical inverse, local result, or conditional result presented as a global/unconditional result.
- An LLM agreeing with another LLM. Decisive checks must be mathematical, formal, computational, or human-verifiable.
- Reopening a blocked or ruled-out route without satisfying its recorded reopen condition or providing materially new evidence.

LANE AND THIS EPOCH'S JOB
{('Hard/famous lane. Seek one genuinely new lemma, reduction, parametric family, computational bound, or falsifiable route. Do not spend the run narrating the whole famous problem.' if hard else ('Bounded contribution lane. One-shot the complete patch, focused tests, independent deterministic checker, and review packet whenever the verification contract can be satisfied.' if one_shot else 'Discovery lane. Prefer a concrete witness, executable search, exact identity, formal lemma, or rigorous elimination of a bounded route.'))}

SOL-TERRA ORCHESTRATION
You are the GPT-5.6 Sol principal. Terra delegates performed bounded reconnaissance before this pass. Their memos are
advisory leads, not evidence and not votes. Audit every claim against primary sources or deterministic artifacts, use the
best concrete discriminator when it survives scrutiny, and explicitly reject misleading suggestions. Do not count model
agreement as independent validation. Promote any delegate artifact you rely on into the main workspace with provenance;
ephemeral delegate directories are not part of the accepted artifact set. Disclose the Sol principal and Terra delegate
roles in the final tool disclosure.

TERRA DELEGATE MEMOS
{json.dumps(delegated, indent=2, ensure_ascii=False)[:12000] if delegated else '(No delegate memo survived; proceed, but record the orchestration failure.)'}

CANONICAL ROUTE BRIEF
{canonical_brief if canonical_brief is not None else briefing.compact_for_prompt(problem, max_chars=22000)}

DURABLE RESEARCH STATE
Summarized in the canonical route brief; load the versioned state file only for a selected fact.

CROSS-PROBLEM RESEARCH BRAIN
Not injected. Consult it on demand only when testing a named transfer hypothesis.

DETERMINISTIC TACTICAL BRIEF
Summarized in the canonical route brief.

AUTOMATED CAMPAIGN ROADMAP
The active phase and campaign policy are included in the canonical route brief.

GLOBAL RESOLUTION POLICY
The canonical route brief contains the standing policy for all targets. At selection and after every substantive result,
compare constructive witnesses, exhaustive/impossibility certificates, structural reductions, alternative formalisms,
and adjacent-field transfers. Give constructive and negative routes symmetric consideration. Select by expected marginal
validated uncertainty reduction per compute and model effort; momentum and sunk engineering are not evidence.

PRIOR-ART ANTI-REDISCOVERY REGISTER
The compact current registry is included in the canonical route brief; open the full JSON before a novelty claim.

REUSABLE STRATEGY LIBRARY
Load only the entry required by the selected route.

STRATEGY PORTFOLIO RULES
1. Identify your approach family and mechanism before working. Use a stable fingerprint from the ledger when continuing it.
2. Prefer a proposed/open lead or a genuinely different family. If continuing, start from the saved first action.
3. Treat superficially different prose with the same mechanism as the same strategy. Do not manufacture diversity by renaming.
4. Preserve incompatible proof and disproof routes. Cross-pollinate only with a concrete transfer: source result -> predicted signal -> test.
5. If the route depends on a missing lemma essentially as strong as the target, mark it blocked and state the exact reopen condition.
6. Use an adversarial audit appropriate to the claim: quantifiers, domain/codomain, exact hypotheses, singularities, exhaustive scope,
   numerical tolerance, solver/model assumptions, certificate checking, novelty/status, and unused hypotheses.
7. End the epoch with a synthesis: what is established, what was ruled out and at what scope, live leads, and the next first action.
8. Follow the tactical brief unless concrete evidence overrides it. Compare its incumbent and challenger, predeclare success,
   failure, and redirect signals, and record the override reason. Never confuse a high route score with mathematical evidence.
9. Treat the roadmap as an evidence-driven stage graph, not a sequence. Recompute the active stage after every epoch and
   switch immediately when a promote, kill, hold, redirect, or reopen condition is observed.
10. The current portfolio is an evidence-backed working set, not an exhaustive ontology. You may propose one genuinely
   new or composite mechanism from this problem, another problem, or another field when it has a concrete transfer
   hypothesis and a cheap falsifier. Do not force a synthesis: an empty list is correct when no candidate clears that bar.
11. Obey the global resolution policy and any campaign certificate-portfolio policy in the canonical brief. Preserve fixed
   experiment protocols, but do not turn a method-comparison threshold into a campaign-wide veto. Mixed-method coverage is
   valid only when every component certificate and the final union are independently checked.

WORK RULES
1. Read the official source and its cited/original references before relying on the statement. Search for newer literature and preserve direct URLs.
2. Work concretely. You may create code, notes, Lean files, and certificates only under {workspace}.
   This workspace is a standalone public Git repository. Keep substantive research notes, code,
   findings, negative results, checkers, and write-ups in it. The checkpoint service records the epoch
   under Charlie's ctkrug identity;
   do not rewrite history, change remotes, or claim that a Git commit validates the mathematics.
   Do not stop solely because a non-secret development dependency is missing: you may provision a
   project-scoped toolchain/cache from its official pinned source, verify the installed version, and
   record that setup in the experiment. For a Formal Conjectures target, first run
   {store.ROOT / 'scripts' / 'bootstrap-formal-conjectures.sh'}; it serializes the shared Lean cache.
   You may install system packages, repair host configuration, and use the host network when that is needed to unblock
   reproducible research. Record every system-level change and its verification in the workspace. Do not spend money,
   publish externally, change remotes or identity, or access unrelated personal/financial/deployment accounts.
   For a reproducible computational test, run:
   python3 {EXPERIMENT_RUNNER} --name NAME --hypothesis HYPOTHESIS --expected-signal SIGNAL --timeout SECONDS --memory-mb MB --source-url URL -- COMMAND ARGS...
   It runs argv directly without a shell and stores logs, metadata, seeds, limits, source/script/dependency hashes, git state, and peak memory under .proof-experiments/.
   For a checkpointed search that needs longer than this epoch, submit it to the cloud simulation lab instead of using
   nohup, screen, tmux, `&`, or an untracked background process:
   python3 {store.ROOT / 'scripts' / 'submit_lab.py'} --problem {problem['id']} --name NAME --hypothesis HYPOTHESIS \
     --expected-signal SIGNAL --decision-value VALUE --efficiency-design REPORT.json \
     --segment-seconds SECONDS --max-segments SEGMENTS --memory-mb MB \
     --checkpoint-path CHECKPOINT.json --progress-path PROGRESS.json -- COMMAND ARGS...
   The lab is shell-free, low-priority, hash-recorded, and limited to 24-hour resource-capped segments, but a justified
   checkpointed experiment may continue across any number of reviewed tranches. Substantial jobs require an efficiency
   design, immutable inputs, checkpoint and progress records, measured continuation thresholds, and independent checks.
   Queueing compute is not evidence. For completed-awaiting-review jobs in the canonical brief, inspect durable state,
   logs, hashes, and artifacts, then emit exactly one lab_review decision: continue, validate, promote, or redirect.
3. Choose the cheapest discriminating test first. Use programs for enumeration and repetition; reserve reasoning for models,
   invariants, decompositions, experiment design, and interpreting failures. Record negative controls and exact bounds.
4. SEARCH-EFFICIENCY PASS: before any large-space run, estimate the naive candidate count, memory traffic, and dominant
   operation. Explicitly consider proved symmetry quotients/canonical forms, compressed or sparse representations,
   batching/vectorization/bitsets, incremental delta evaluation and memoization, meet-in-the-middle or cube decomposition,
   dominance/monotone bounds, cheap sound prefilters, and learned-clause/proof-prefix reuse. Choose the best combination,
   record projected and observed reduction or throughput, and independently check shortcut soundness and coverage. Do not
   scale brute force until this pass is written; do not use an unsound shortcut to support a mathematical claim.
   Maintain the reduction ledger: distinguish labelled assignments, isomorphism classes, cubes, profiles, and whole
   families; give exact expressions or honest upper bounds before and after; state coverage and the independent soundness
   basis. Prefer bulk class/cube/profile elimination over accumulating point blocks. Never present a local-family fraction
   as a reduction of the global target space.
5. Test examples and edge cases. Try to falsify every central lemma. A computation is evidence only for the exact range checked.
6. A suspiciously short proof, unused hypothesis, stronger-than-requested conclusion, or mismatch with the source is a red flag.
7. Cite prior human work and disclose every automated tool used. Do not optimize for publicity.
8. Report concrete lemmas, equations, maps, programs, certificates, and counterexamples. Reject vague “promising direction” language.
9. A larger arbitrary cutoff is not a contribution. It becomes candidate-eligible only if it improves
   the actual best-known result, answers a source's explicit request, has confirmed expert interest,
   or yields a new structural result. “We did not find it in a quick search” is not novelty evidence.
10. PRIOR-ART CHECK: before allocating substantial compute, identify the nearest method IDs in the supplied register and
   inspect their primary sources. State the mechanism-level delta and cheapest matched comparison. A replication may run
   only as a bounded calibration/control; it cannot be novelty and must not receive scale-up compute without a material delta.
11. End with exactly one fenced JSON block in this schema:

```proof_result
{{
  "outcome": "failed|no_progress|progress|candidate",
  "approach": "specific route attempted",
  "strategy": {{"family":"named approach family","fingerprint":"reuse existing or blank for deterministic creation","mechanism":"what actually generates information","parent_ids":["strategy-id if combined"],"route_evaluation":{{"gate_proximity":0.0,"contribution_value":0.0,"decisiveness":0.0,"novelty_confidence":0.0,"novelty_risk":0.0,"scope":0.0,"reuse_value":0.0,"model_cost":1.0,"cpu_cost":1.0}}}},
  "hypothesis": "falsifiable claim tested this epoch",
  "discriminating_test": "cheapest observation that separates success from failure",
  "search_efficiency": {{"naive_space":"candidate count and bottleneck","reductions_considered":["symmetry/compression/batching/vectorization/incremental/decomposition/pruning/reuse options"],"chosen_mechanism":"bulk-elimination design","estimated_or_measured_savings":"reduction ratio or throughput","soundness_guard":"independent equivalence or one-sided coverage check"}},
  "space_reduction": {{"ambient_space":"exact reference universe, such as 2^903 labelled K43 graphs","represented_space_before":"exact expression or honest bound before this epoch","eliminated_or_quotiented":"what this epoch removed or identified","represented_space_after":"exact expression or honest bound after this epoch","reduction_factor":"exact factor, bound, estimate, or none","measurement_status":"exact|upper_bound|estimate|not_applicable","unit":"labelled assignments|isomorphism classes|cubes|profiles|families|proof states|not applicable","coverage_scope":"precise family or global scope","soundness_basis":"proof/check establishing safe elimination or quotient coverage","remaining_unknown":"what is not counted or excluded","next_bulk_elimination":"next class/cube/profile/family-level reduction"}},
  "tactical_learning": {{"prediction":"predeclared expected signal","observation":"what occurred","surprise":"difference from prediction, or none","failure_signature":"reusable failure pattern, or none","bottleneck_update":"current limiting uncertainty or operation","reusable_assets":[{{"name":"artifact/checker/dataset","use":"future use","evidence":"path/hash/check"}}],"constraints_learned":[{{"constraint":"exact restriction learned","scope":"valid scope","evidence":"support"}}],"route_decision":"continue|hold|redirect|close","next_discriminator":"cheapest next test"}},
  "prior_art_check": {{"nearest_method_ids":["stable registry ID or none-found"],"classification":"genuinely_different|material_modification|replication_control","exact_delta":"mechanism-level difference from the nearest work","duplicate_risk":"what could merely rediscover a known result","comparison_test":"cheapest matched test against the nearest baseline","decision":"proceed|control_only|stop","source_urls":["direct primary URL"]}},
  "field_progress_assessment": {{"status":"met|not_met","gate_id":"exact configured gate number/name, or none","contribution_class":"exact contribution class or verified negative/infrastructure result","closest_prior_result":"closest prior result or baseline","measurable_improvement":"quantified delta, or none","independent_validation":"validator and result, or not yet independently validated","external_audience":"accepted audience/channel, or none","remains_unproved":"precise remaining gap","route_recommendation":"close|broaden|redirect|continue and why"}},
  "lab_review": {{"job_id":"durable lab job ID or blank","decision":"none|continue|validate|promote|redirect","reason":"artifact-grounded review reason or blank","evidence":["state/artifact/check read"]}},
  "strategy_status": "proposed|active|promising|blocked|ruled_out|exhausted|superseded",
  "summary": "what actually happened, including limits",
  "rationale": "why the evidence supports this outcome",
  "claims": ["precise claim, if any"],
  "evidence": ["file/command/check and exact scope"],
  "evidence_files": ["normalized workspace-relative immutable file path; list every decisive file supporting a computed claim"],
  "next_steps": ["specific next move"],
  "citations": ["direct URL"],
  "techniques": ["technique used"],
  "research_mode": "theoretical|computational|hybrid",
  "experiments": ["experiment directory and decisive observation"],
  "independent_checker": "separate checker or materially different encoding, or why not yet applicable",
  "transfer_insights": ["source domain -> operational prediction -> observed result"],
  "established_facts": [{{"claim":"precise durable fact","evidence":"reproducible support","scope":"exact scope","status":"proved|computed|conditional"}}],
  "ruled_out": [{{"claim_or_route":"route eliminated","scope":"exactly how far","reason":"why","evidence":"check/certificate","reopen_condition":"new fact that would justify trying again"}}],
  "open_leads": [{{"description":"concrete lead","rationale":"why information-rich","next_experiment":"first executable action","priority":"high|normal|low","status":"open"}}],
  "blocker": "the theorem-strength or practical blocker, if any",
  "reopen_condition": "specific evidence required before retrying this strategy",
  "reopen_evidence": "new evidence satisfying the prior reopen condition, or blank",
  "continuation": {{"objective":"next epoch objective","first_action":"exact command/lemma/source to start with","stop_condition":"evidence that ends or redirects it"}},
  "campaign_assessment": {{"decision":"continue|hold","close_signal":"concrete evidence of nearness, or blank when holding","reason":"why another bounded pass is or is not worth its compute"}},
  "resolution_portfolio": {{"current_uncertainty":"exact unresolved target state","active_routes_and_scores":[{{"route":"materially distinct route","score":"expected marginal value with cost and useful-signal basis","success_certificate":"exact accepted artifact","smallest_decisive_experiment":"bounded test","switch_condition":"evidence causing immediate reroute"}}],"what_changed_this_turn":"evidence delta","net_new_validated_progress":"only independently validated progress","cheapest_next_experiment_for_each_route":[{{"route":"route name","experiment":"smallest decisive test"}}],"why_selected_next_route_has_best_expected_value":"comparison across routes","immediate_route_switch_conditions":["specific evidence-triggered switch"]}},
  "strategy_proposals": [{{"family":"different family","mechanism":"concrete mechanism","hypothesis":"testable claim","discriminating_test":"cheap test","rationale":"why it may outperform current routes"}}],
  "synthesis_candidates": [{{"family":"stable composite family","mechanism":"how the inputs combine into a new information-generating mechanism","parent_strategy_ids":["strategy-id", "strategy-id"],"source_inputs":["specific current strategy, other problem, or external field"],"transfer_hypothesis":"why this structure should transfer to this exact problem","discriminating_test":"cheapest bounded test before scale-up","falsification_signal":"observation that rejects the transfer","rationale":"why this is not a renamed existing route"}}],
  "candidate_profile": {{
    "contribution_class":"terminal_result|recognized_open_subproblem|bounded_extension|research_artifact",
    "scholarly_question":"what recognized question this answers",
    "meaningful_delta":"specific difference from the closest prior result",
    "acceptance_test":"objective condition for accepting this contribution",
    "closest_prior_work":[{{"url":"direct primary-source URL","difference":"exact difference"}}],
    "novelty_searches":[{{"source":"database or citation graph","query":"reproducible query","url":"direct results/source URL","finding":"what was found"}}],
    "external_channel":{{"recipient":"named maintainer/expert/venue","url":"channel URL","acceptance_path":"how it can be accepted"}},
    "independent_validations":[{{"type":"deterministic_checker|formal_kernel|independent_third_party|repository_ci|external_expert","validator":"who or what","result":"exact result","artifact":"local certificate path or blank","evidence_url":"public evidence or blank"}}],
    "relevance":{{"settles_exact_open_target":false,"improves_best_known_result":false,"source_explicitly_requests_result":false,"expert_interest_confirmed":false,"new_structural_result":false,"evidence_url":"supporting URL"}},
    "arbitrary_cutoff_extension":false
  }},
  "tool_disclosure": "models, CAS, proof assistants, solvers, and code used"
}}
```

Do not include a confidence score. Correct uncertainty is part of the result.

EVIDENCE FILE RULE: `evidence_files` must contain immutable source, script, checker,
experiment, certificate, and result-artifact paths only. Never include mutable projections
or aggregate state such as `.git/**`, `.venv/**`, `.delegates/**`, `CHECKPOINT.md`, `README.md`,
`docs/DOSSIER.md`, `lab-queue/**`, `lab-archive/**`, `records/problem.json`, or
`records/research-state.json`. For lab evidence, claim the immutable `records/labs/**` record and
its content-addressed `lab-runs/**` outputs instead. Those files may
be updated for navigation, but claiming any of them as evidence deliberately invalidates the
receipt and downgrades the epoch. Keep the list decisive and minimal.
"""
    return _constant_prefix_first(prompt)


def run(problem: dict[str, Any], lane: str, *, phase: str = "technical",
        admitting_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    model = SOL_MODEL
    effort = "high"
    ceiling = config.get_int(
        "PROOF_HARD_TIMEOUT_SEC" if lane == "hard" else "PROOF_EASY_TIMEOUT_SEC",
        7200 if lane == "hard" else 3600,
        minimum=1,
        maximum=86_400,
    )
    workspace = store.RESEARCH / problem["id"] / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    before_snapshot = evidence_layer.capture_workspace_snapshot(workspace)
    started = store.now_iso()
    start = time.monotonic()
    delegate_ceiling = config.get_int(
        "PROOF_HARD_DELEGATE_TIMEOUT_SEC" if lane == "hard" else "PROOF_EASY_DELEGATE_TIMEOUT_SEC",
        1200 if lane == "hard" else 600,
        minimum=1,
        maximum=86_400,
    )
    epoch_key = f"{started[:19].replace(':', '').replace('-', '').replace('T', '-')}-{uuid.uuid4().hex[:6]}"
    delegate_root = workspace / ".delegates" / epoch_key
    delegate_records: list[dict[str, Any]] = []
    repair_attempted = False
    repair_used = False
    repair_usage: dict[str, Any] = {}
    repair_error = ""
    repair_timeout_seconds = min(
        REPAIR_TIMEOUT_SECONDS,
        config.get_int(
            "PROOF_JSON_REPAIR_TIMEOUT_SEC", REPAIR_TIMEOUT_SECONDS, minimum=1, maximum=3600,
        ),
    )
    brief_payload = briefing.build(problem)
    delegate_brief = briefing.compact_for_prompt(problem, max_chars=18000, payload=brief_payload)
    principal_brief = briefing.compact_for_prompt(problem, max_chars=22000, payload=brief_payload)

    def run_delegate(role: str) -> dict[str, Any]:
        delegate_workspace = delegate_root / role
        delegate_workspace.mkdir(parents=True, exist_ok=True)
        try:
            memo, delegate_usage = _run_codex(
                build_delegate_prompt(problem, lane, workspace, role, phase, canonical_brief=delegate_brief),
                model=TERRA_MODEL, effort="high", workspace=delegate_workspace, timeout=delegate_ceiling,
                telemetry_meta={"role": f"delegate:{role}", "lane": lane, "problem_id": problem["id"], "phase": phase},
            )
            memo = memo.strip()[:7000]
            status = "completed"
            error_note = ""
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            memo = f"Delegate failed before a usable memo: {type(exc).__name__}: {exc}"
            delegate_usage = {}
            status = "error"
            error_note = str(exc)[:2000]
        memo_file = delegate_workspace / "memo.md"
        memo_file.write_text(memo + "\n")
        return {
            "role": role, "model": TERRA_MODEL, "effort": "high", "status": status,
            "memo_path": str(memo_file.relative_to(workspace)), "memo_sha256": store.sha256_file(memo_file),
            "memo": memo, "usage": delegate_usage, "error": error_note,
        }

    roles = delegate_roles(lane, admitting_events)
    completed: dict[str, dict[str, Any]] = {}
    if roles:
        with ThreadPoolExecutor(max_workers=len(roles)) as pool:
            futures = {pool.submit(run_delegate, role): role for role in roles}
            completed = {futures[future]: future.result() for future in as_completed(futures)}
    delegate_records = [completed[role] for role in roles]
    prompt = build_prompt(
        problem, lane, workspace, delegate_records, phase, canonical_brief=principal_brief,
    )
    try:
        text, usage = _run_codex(
            prompt, model=model, effort=effort, workspace=workspace, timeout=ceiling,
            telemetry_meta={"role": "principal", "lane": lane, "problem_id": problem["id"], "phase": phase},
        )
        try:
            result = extract_result(text)
        except (ValueError, json.JSONDecodeError) as exc:
            repair_attempted = True
            try:
                result, repair_usage = repair_result(
                    text, exc, model=model, workspace=workspace,
                    timeout=repair_timeout_seconds,
                )
                repair_used = True
            except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, json.JSONDecodeError) as repair_exc:
                repair_error = f"{type(repair_exc).__name__}: {repair_exc}"[:2000]
                raise
        outcome = result["outcome"]
        policy_flags: list[str] = []
        strategy = result.get("strategy") if isinstance(result.get("strategy"), dict) else {}
        fingerprint = str(strategy.get("fingerprint") or "").strip() or research_state.strategy_fingerprint(
            strategy.get("family"), strategy.get("mechanism") or result.get("approach")
        )
        prior_strategy = next(
            (row for row in research_state.load(problem).get("strategies", []) if row.get("fingerprint") == fingerprint), None
        )
        if prior_strategy and prior_strategy.get("status") in {"blocked", "ruled_out", "exhausted"} and not str(result.get("reopen_evidence") or "").strip():
            policy_flags.append(
                f"Repeated {prior_strategy.get('status')} strategy {fingerprint} without evidence satisfying its reopen condition."
            )
            outcome = "no_progress"
            result["strategy_status"] = prior_strategy.get("status")
        prior_check = result.get("prior_art_check", {})
        if result.get("outcome") == "candidate" and (
            prior_check.get("classification") == "replication_control" or prior_check.get("decision") != "proceed"
        ):
            policy_flags.append("Candidate is a prior-art replication/control or lacks a proceed decision; it cannot be promoted as novelty.")
            outcome = "progress"
        field_progress = result.get("field_progress_assessment", {})
        configured_gates = problem.get("field_progress_gates") or []
        if field_progress.get("status") == "met" and configured_gates:
            gate_id = str(field_progress.get("gate_id") or "")
            valid_gate_ids = {str(index) for index in range(1, len(configured_gates) + 1)}
            if gate_id not in valid_gate_ids:
                policy_flags.append(f"Field-progress claim names unconfigured gate {gate_id!r}; expected one of {sorted(valid_gate_ids)}.")
                field_progress["status"] = "not_met"
                outcome = "no_progress"
        if field_progress.get("status") == "met" and result.get("outcome") != "candidate":
            policy_flags.append("A field-progress claim must request candidate review and pass the fail-closed contribution gate.")
            field_progress["status"] = "not_met"
        if result.get("outcome") == "candidate" and field_progress.get("status") != "met":
            policy_flags.append("Candidate outcome did not identify a satisfied configured field-progress gate.")
            outcome = "progress"
        gate = (
            contribution_gate.assess(result)
            if result.get("outcome") == "candidate"
            else contribution_gate.not_requested()
        )
        if result.get("outcome") == "candidate" and not gate["passed"]:
            policy_flags.extend(f"Contribution gate: {reason}" for reason in gate["reasons"])
            if outcome == "candidate":
                outcome = "progress"
        error = ""
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        usage = {}
        result = _error_result(problem, model, exc)
        outcome = "error"
        error = str(exc)
        policy_flags = []
        gate = contribution_gate.not_requested()

    finished = store.now_iso()
    stamp = finished[:19].replace(":", "").replace("-", "").replace("T", "-")
    attempt_id = f"{problem['id']}-{stamp}-{uuid.uuid4().hex[:6]}"
    disclosure = str(result.get("tool_disclosure") or "")[:3200]
    if TERRA_MODEL not in disclosure:
        disclosure = (disclosure + f"; orchestration: {model} principal with {TERRA_MODEL} delegates.").lstrip("; ")
    projected_result = _project_result({**result, "tool_disclosure": disclosure})

    attempt = {
        "id": attempt_id,
        "problem_id": problem["id"],
        "started_at": started,
        "finished_at": finished,
        "duration_seconds": round(time.monotonic() - start, 1),
        "lane": lane,
        "phase": phase,
        "model": model,
        "effort": effort,
        "orchestration": {
            "architecture": "sol-principal-terra-delegates",
            "principal_model": model,
            "delegate_model": TERRA_MODEL,
            "delegate_roles": [row["role"] for row in delegate_records],
            "delegate_statuses": {row["role"]: row["status"] for row in delegate_records},
            "delegate_admission": {
                "event_kinds": sorted({str(row.get("kind") or "") for row in (admitting_events or [])}),
                "selected_roles": list(roles),
                "route_decision_event_kinds": sorted(ROUTE_DECISION_EVENT_KINDS),
            },
        },
        "delegates": [{
            "role": row["role"], "model": row["model"], "effort": row["effort"],
            "status": row["status"], "memo_path": row["memo_path"], "memo_sha256": row["memo_sha256"],
            "usage": row["usage"],
            "error": row["error"],
        } for row in delegate_records],
        "outcome": outcome,
        **projected_result,
        "policy_flags": policy_flags,
        "contribution_gate": gate,
        "contribution_status": "candidate_eligible" if outcome == "candidate" else ("internal_result" if result.get("outcome") == "candidate" else "research_attempt"),
        "review_status": "needs isolated skeptic review" if outcome == "candidate" else ("internal result; not a contribution candidate" if result.get("outcome") == "candidate" else "not a result claim"),
        "usage": usage,
        "json_repair": {
            "attempted": repair_attempted, "used": repair_used, "model": model if repair_attempted else None,
            "effort": "low" if repair_attempted else None, "timeout_seconds": repair_timeout_seconds,
            "usage": repair_usage, "error": repair_error,
            "policy": "serialization-only; protected outcome and classification fields must remain unchanged",
        },
        "error": error,
        "artifact_hashes": {},
    }
    mutable_patterns = (
        ".git/**", ".venv/**", "venv/**", ".delegates/**", "__pycache__/**",
        ".pytest_cache/**", "lab-queue/**", "lab-archive/**", "CHECKPOINT.md", "README.md",
        "docs/DOSSIER.md", "records/problem.json", "records/research-state.json",
    )
    try:
        manifest_path = evidence_layer.create_attempt_manifest(
            workspace,
            attempt_id,
            before_snapshot,
            claimed_evidence_paths=attempt["evidence_files"],
            mutable_projection_patterns=mutable_patterns,
            manifest_root=workspace / "evidence",
        )
        receipt_path = evidence_layer.create_evidence_receipt(manifest_path, workspace=workspace)
        receipt = evidence_layer.load_evidence_receipt(receipt_path)
        manifest = evidence_layer.load_attempt_manifest(manifest_path)
        attempt["artifact_hashes"] = {
            row["path"]: row.get("after", {}).get("sha256")
            for row in manifest.get("artifacts", [])
            if row.get("role") == "immutable_artifact"
            and isinstance(row.get("after"), dict)
            and row.get("after", {}).get("sha256")
        }
        attempt["evidence_validation"] = {
            "status": receipt["status"],
            "manifest": str(manifest_path.relative_to(workspace)),
            "manifest_sha256": receipt["manifest_file_sha256"],
            "receipt": str(receipt_path.relative_to(workspace)),
            "artifact_count": receipt["artifact_count"],
            "claimed_evidence_count": receipt["claimed_evidence_count"],
            "errors": receipt["errors"][:20],
        }
        needs_claimed_files = attempt["outcome"] in {"progress", "candidate"} and bool(
            attempt["claims"] or attempt["experiments"] or attempt["established_facts"]
        )
        if receipt["status"] != "valid" or (needs_claimed_files and receipt["claimed_evidence_count"] == 0):
            if needs_claimed_files and receipt["claimed_evidence_count"] == 0:
                attempt["evidence_validation"]["errors"].append(
                    "computed progress requires at least one explicit immutable evidence file"
                )
            attempt["policy_flags"].append("Attempt evidence did not validate; durable progress is withheld.")
            if attempt["outcome"] in {"progress", "candidate"}:
                attempt["outcome"] = "no_progress"
                attempt["contribution_status"] = "research_attempt"
                attempt["review_status"] = "evidence invalid or incomplete; not durable progress"
    except Exception as exc:
        attempt["evidence_validation"] = {
            "status": "invalid", "errors": [f"{type(exc).__name__}: {exc}"],
        }
        attempt["policy_flags"].append("Evidence receipt creation failed; durable progress is withheld.")
        if attempt["outcome"] in {"progress", "candidate"}:
            attempt["outcome"] = "no_progress"
            attempt["contribution_status"] = "research_attempt"
            attempt["review_status"] = "evidence receipt failure; not durable progress"
    telemetry.epoch_summary(attempt)
    return attempt
