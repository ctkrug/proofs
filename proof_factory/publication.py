from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import store


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    if not cleaned:
        raise ValueError("invalid publication id")
    return cleaned


def _bullets(values: list[Any], *, empty: str = "None recorded.") -> str:
    return "\n".join(f"- {value}" for value in values) if values else empty


def _cff(value: Any) -> str:
    return str(value or "").replace('"', "\\\"").replace("\n", " ")


def validate_candidate(attempt: dict[str, Any]) -> None:
    required = {
        "claims": "a precise claim",
        "evidence": "reproducible evidence",
        "citations": "a source and novelty trail",
        "tool_disclosure": "an AI/tool disclosure",
        "artifact_hashes": "at least one hashed artifact",
        "independent_checker": "a separate checker or explicit not-yet-applicable justification",
    }
    missing = [label for field, label in required.items() if not attempt.get(field)]
    if missing:
        raise ValueError("candidate is not publication-ready; missing " + ", ".join(missing))


def build_packet(problem: dict[str, Any], attempt: dict[str, Any], review: dict[str, Any]) -> Path:
    """Create a deterministic, versionable public research-note packet after human approval."""
    validate_candidate(attempt)
    packet_id = _safe_id(str(attempt["id"]))
    packet = store.ROOT / "publications" / packet_id
    packet.mkdir(parents=True, exist_ok=True)
    repo_path = f"research/{problem['id']}/workspace"
    claims = list(attempt.get("claims") or [])
    evidence = list(attempt.get("evidence") or [])
    citations = list(attempt.get("citations") or [])
    hashes = dict(attempt.get("artifact_hashes") or {})
    contribution_type = str(problem.get("contribution_type") or "research note")

    readme = f"""# {problem['title']}

> Status: Charlie-approved public research note. This is not peer-reviewed, journal-accepted, or
> independently expert-confirmed unless a later record explicitly says so.

## Contribution

Type: {contribution_type}

{_bullets(claims)}

## Evidence

{_bullets(evidence)}

Reproducible source artifacts live under `{repo_path}`. Their SHA-256 hashes are in
`MANIFEST.sha256` and `metadata.json`.

Independent checker: {attempt.get('independent_checker')}

## Scope and limitations

{attempt.get('summary', '')}

{attempt.get('rationale', '')}

## Human approval

- Reviewer: {review['reviewer']}
- Reviewed: {review['reviewed_at']}
- Note: {review['note']}

Approval authorizes release of this research note; it does not substitute for independent review.

## Sources and novelty trail

{_bullets(citations)}

## Methods and disclosure

- Research mode: {attempt.get('research_mode', 'unspecified')}
- Techniques: {', '.join(attempt.get('techniques') or []) or 'None recorded'}
- Tools: {attempt.get('tool_disclosure', '')}

## Reproduce and challenge

Inspect the source, run the recorded experiment commands, compare hashes, and try to falsify the
claim with an independent implementation. Corrections are welcome through the repository issue
tracker. External acceptance or expert review is recorded separately from this release.
"""
    (packet / "README.md").write_text(readme)
    metadata = {
        "schema_version": 1,
        "title": problem["title"],
        "problem_id": problem["id"],
        "attempt_id": attempt["id"],
        "contribution_type": contribution_type,
        "status": "public-research-note",
        "peer_reviewed": False,
        "expert_confirmed": False,
        "created_at": review["reviewed_at"],
        "creator": "Charlie Krug",
        "ai_assistance_disclosed": True,
        "source_url": problem.get("source_url"),
        "claims": claims,
        "evidence": evidence,
        "independent_checker": attempt.get("independent_checker"),
        "citations": citations,
        "artifact_hashes": hashes,
        "review": review,
    }
    (packet / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    manifest = "\n".join(f"{digest}  {repo_path}/{path}" for path, digest in sorted(hashes.items())) + "\n"
    (packet / "MANIFEST.sha256").write_text(manifest)
    citation = f'''cff-version: 1.2.0
message: "If you use this research artifact, please cite it using this metadata."
title: "{_cff(problem['title'])}"
type: software
authors:
  - family-names: "Krug"
    given-names: "Charlie"
date-released: "{review['reviewed_at'][:10]}"
repository-code: "https://github.com/ctkrug/proofs"
url: "https://proofs.charliekrug.com/publications/{packet_id}/"
'''
    (packet / "CITATION.cff").write_text(citation)
    venue_plan = f"""# External validation plan

The website and GitHub release are provenance artifacts, not external scholarly acceptance.

1. Ask one relevant maintainer, recent author, or problem owner to check status and novelty.
2. Obtain an independent implementation or formal/certificate verification.
3. Route the result to the venue matching `{contribution_type}`: a maintained domain repository,
   formal-library pull request, OEIS contribution, Zenodo dataset/software record, workshop,
   preprint, or journal as appropriate.
4. Record replies, corrections, DOI, repository acceptance, and peer-review state without collapsing
   them into one generic “published” label.
5. Never bulk-submit or auto-email experts.
"""
    (packet / "EXTERNAL-VALIDATION.md").write_text(venue_plan)
    return packet
