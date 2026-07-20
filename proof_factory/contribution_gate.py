from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


CONTRIBUTION_CLASSES = {
    "terminal_result",
    "recognized_open_subproblem",
    "bounded_extension",
    "research_artifact",
}
INDEPENDENT_VALIDATORS = {
    "formal_kernel",
    "independent_third_party",
    "repository_ci",
    "external_expert",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _http_url(value: Any) -> bool:
    try:
        return urlparse(_text(value)).scheme in {"http", "https"}
    except ValueError:
        return False


def assess(result: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed eligibility check for elevating a research result to candidate status.

    This checks evidence structure, not mathematical truth. A passing result is eligible for the
    isolated skeptic/human queue; it is not verified, accepted, or publishable.
    """
    profile = result.get("candidate_profile") if isinstance(result.get("candidate_profile"), dict) else {}
    reasons: list[str] = []
    contribution_class = _text(profile.get("contribution_class"))
    if contribution_class not in CONTRIBUTION_CLASSES:
        reasons.append("No recognized contribution class was supplied.")
    for key, label in (
        ("scholarly_question", "the scholarly question answered"),
        ("meaningful_delta", "a meaningful delta from prior work"),
        ("acceptance_test", "an objective acceptance test"),
    ):
        if not _text(profile.get(key)):
            reasons.append(f"Missing {label}.")

    prior = profile.get("closest_prior_work") if isinstance(profile.get("closest_prior_work"), list) else []
    valid_prior = [row for row in prior if isinstance(row, dict) and _http_url(row.get("url")) and _text(row.get("difference"))]
    if not valid_prior:
        reasons.append("No URL-backed comparison with the closest prior work was supplied.")

    searches = profile.get("novelty_searches") if isinstance(profile.get("novelty_searches"), list) else []
    valid_searches = [
        row for row in searches
        if isinstance(row, dict) and _text(row.get("source")) and _text(row.get("query"))
        and _text(row.get("finding")) and _http_url(row.get("url"))
    ]
    if len(valid_searches) < 2:
        reasons.append("Fewer than two reproducible, URL-backed novelty searches were recorded.")

    channel = profile.get("external_channel") if isinstance(profile.get("external_channel"), dict) else {}
    if not (_text(channel.get("recipient")) and _http_url(channel.get("url")) and _text(channel.get("acceptance_path"))):
        reasons.append("No named external recipient/channel with a concrete acceptance path was supplied.")

    validations = profile.get("independent_validations") if isinstance(profile.get("independent_validations"), list) else []
    valid_validations = [
        row for row in validations
        if isinstance(row, dict) and row.get("type") in INDEPENDENT_VALIDATORS
        and _text(row.get("validator")) and _text(row.get("result"))
        and (_http_url(row.get("evidence_url")) or _text(row.get("artifact")))
    ]
    if not valid_validations:
        reasons.append(
            "No formal-kernel, repository-CI, external-expert, or independent-third-party validation was recorded."
        )

    relevance = profile.get("relevance") if isinstance(profile.get("relevance"), dict) else {}
    relevance_claims = {
        "settles_exact_open_target": bool(relevance.get("settles_exact_open_target")),
        "improves_best_known_result": bool(relevance.get("improves_best_known_result")),
        "source_explicitly_requests_result": bool(relevance.get("source_explicitly_requests_result")),
        "expert_interest_confirmed": bool(relevance.get("expert_interest_confirmed")),
        "new_structural_result": bool(relevance.get("new_structural_result")),
    }
    if not any(relevance_claims.values()):
        reasons.append("No evidence that the result settles, improves, answers, or structurally advances a recognized target.")
    if any(relevance_claims.values()) and not _http_url(relevance.get("evidence_url")):
        reasons.append("The claimed scholarly relevance has no supporting source URL.")

    if bool(profile.get("arbitrary_cutoff_extension")):
        reasons.append("A larger unrequested cutoff alone is an internal experiment, not a candidate contribution.")
    if contribution_class == "bounded_extension" and not any(
        relevance_claims[key] for key in (
            "improves_best_known_result", "source_explicitly_requests_result",
            "expert_interest_confirmed", "new_structural_result",
        )
    ):
        reasons.append("A bounded extension needs a best-known improvement, explicit request, expert interest, or structural result.")

    return {
        "schema_version": 1,
        "passed": not reasons,
        "status": "candidate_eligible" if not reasons else "internal_result",
        "reasons": reasons,
        "contribution_class": contribution_class or "unspecified",
        "meaningful_delta": _text(profile.get("meaningful_delta"))[:4000],
        "scholarly_question": _text(profile.get("scholarly_question"))[:4000],
        "external_recipient": _text(channel.get("recipient"))[:500],
        "independent_validation_types": sorted({str(row.get("type")) for row in valid_validations}),
    }
