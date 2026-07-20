from __future__ import annotations

import html
import re
import urllib.request
from typing import Any

import yaml

from . import store


CATALOG_URL = "https://raw.githubusercontent.com/teorth/erdosproblems/master/data/problems.yaml"
PROBLEM_URL = "https://www.erdosproblems.com/{number}"
ELIGIBLE_STATES = {"open", "falsifiable", "verifiable", "decidable"}
ACTIVE_EASY = {"queued", "active", "attempted", "candidate"}


def _get(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ProofFactory/1.0 (+https://proofs.charliekrug.com)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_statement(page: str) -> str:
    match = re.search(r'<div\s+id=["\']content["\']\s*>(.*?)</div>', page, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError("official problem page has no statement container")
    value = re.sub(r"<br\s*/?>", "\n", match.group(1), flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _score(row: dict[str, Any]) -> tuple[int, int, int, str]:
    state = str((row.get("status") or {}).get("state") or "")
    formalized = str((row.get("formalized") or {}).get("state") or "no") == "yes"
    prize = str(row.get("prize") or "no").lower() not in {"", "no", "none"}
    return (
        0 if state in {"verifiable", "falsifiable", "decidable"} else 2,
        0 if formalized else 1,
        1 if prize else 0,
        str(row.get("number")),
    )


def _problem(row: dict[str, Any], statement: str) -> dict[str, Any]:
    number = str(row["number"])
    state = str((row.get("status") or {}).get("state") or "open")
    formalized = str((row.get("formalized") or {}).get("state") or "no") == "yes"
    prize = str(row.get("prize") or "no").lower() not in {"", "no", "none"}
    witness_friendly = statement.lower().startswith(("are there any", "does there exist", "is there some"))
    difficulty = (
        (5 if state in {"verifiable", "falsifiable", "decidable"} and witness_friendly else 7)
        + (0 if formalized else 1)
        + (1 if prize else 0)
    )
    return {
        "id": f"erdos-{number}",
        "title": f"Erdős problem #{number}",
        "statement": statement[:4000],
        "source_url": PROBLEM_URL.format(number=number),
        "source_name": f"Erdős Problems #{number}",
        "problem_state": state,
        "formalization_url": (
            f"https://github.com/google-deepmind/formal-conjectures/blob/main/FormalConjectures/ErdosProblems/{number}.lean"
            if formalized else None
        ),
        "lane": "easy",
        "status": "queued",
        "difficulty": min(9, difficulty),
        "priority": 20,
        "rationale": (
            "Added from the versioned Erdős Problems community database to keep the discovery frontier broad. "
            "The first pass must validate the exact statement, status, literature, and a concrete verification contract."
        ),
        "verifiability": f"Official database status is {state}; refine the exact certificate contract before any candidate claim.",
        "techniques": [str(tag)[:100] for tag in row.get("tags") or []][:12],
        "attempt_count": 0,
        "research_attempt_count": 0,
        "accepted_result": False,
        "added_at": store.now_iso(),
        "intake_source": CATALOG_URL,
    }


def replenish(*, target: int = 12) -> dict[str, Any]:
    if target < 1 or target > 50:
        raise ValueError("target must be between 1 and 50")
    current = store.load_problems()
    active_count = sum(
        1 for row in current
        if row.get("lane") == "easy" and row.get("status") in ACTIVE_EASY
    )
    needed = max(0, target - active_count)
    if not needed:
        return {"target": target, "active_before": active_count, "added": [], "source": CATALOG_URL}

    catalog = yaml.safe_load(_get(CATALOG_URL))
    if not isinstance(catalog, list):
        raise ValueError("official catalog is not a list")
    known = {str(row.get("id")) for row in current}
    candidates = [
        row for row in catalog
        if isinstance(row, dict)
        and str((row.get("status") or {}).get("state") or "") in ELIGIBLE_STATES
        and f"erdos-{row.get('number')}" not in known
    ]
    candidates.sort(key=_score)
    additions: list[dict[str, Any]] = []
    for row in candidates:
        if len(additions) >= needed:
            break
        number = str(row.get("number"))
        try:
            statement = parse_statement(_get(PROBLEM_URL.format(number=number)))
        except (OSError, ValueError):
            continue
        if 20 <= len(statement) <= 4000:
            additions.append(_problem(row, statement))

    accepted: list[dict[str, Any]] = []
    with store.lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        latest = store.load_problems()
        latest_ids = {str(row.get("id")) for row in latest}
        accepted = [row for row in additions if row["id"] not in latest_ids]
        if accepted:
            store.save_problems(latest + accepted)
    return {
        "target": target,
        "active_before": active_count,
        "added": [row["id"] for row in accepted],
        "source": CATALOG_URL,
    }
