from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from itertools import combinations
from typing import Any
from urllib.parse import urlparse

from . import research_state, store


SCHEMA_VERSION = 1
BRAIN_FILE = "research_brain.json"


def _text(value: Any, limit: int = 1200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _slug(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", _text(value).lower()).strip("-")
    return normalized[:80] or hashlib.sha256(_text(value).encode()).hexdigest()[:12]


def _urls(value: Any) -> list[str]:
    found = re.findall(r"https?://[^\s,;)]+", str(value or ""))
    return list(dict.fromkeys(url.rstrip(".\"") for url in found))


def _source_id(url: str) -> str:
    parsed = urlparse(url)
    token = hashlib.sha256(url.encode()).hexdigest()[:12]
    return f"source:{parsed.netloc or 'unknown'}:{token}"


def build(
    problems: list[dict[str, Any]] | None = None,
    attempts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    problems = problems if problems is not None else store.load_problems()
    attempts = attempts if attempts is not None else store.load_attempts()
    states = research_state.load_all(problems)
    attempts_by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        attempts_by_problem[str(attempt.get("problem_id"))].append(attempt)

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    edge_keys: set[tuple[str, str, str]] = set()
    concepts_by_problem: dict[str, set[str]] = defaultdict(set)

    def node(node_id: str, node_type: str, label: str, **fields: Any) -> None:
        prior = nodes.get(node_id, {})
        nodes[node_id] = {**prior, "id": node_id, "type": node_type, "label": _text(label, 500), **fields}

    def edge(source: str, target: str, relation: str, **fields: Any) -> None:
        key = (source, target, relation)
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append({"source": source, "target": target, "relation": relation, **fields})

    for problem in problems:
        problem_id = str(problem["id"])
        problem_node = f"problem:{problem_id}"
        state = states[problem_id]
        node(
            problem_node, "problem", problem.get("title") or problem_id,
            problem_id=problem_id, lane=problem.get("lane"), status=problem.get("status"),
            summary=_text(state.get("synthesis_summary") or problem.get("rationale"), 2000),
            url=f"/problems/{problem_id}/", source_url=problem.get("source_url"),
            baseline_status=(state.get("baseline_review") or {}).get("status", "required"),
        )

        concept_values = list(problem.get("techniques") or [])
        concept_values += [problem.get("contribution_type"), problem.get("problem_state")]
        for attempt in attempts_by_problem[problem_id][-20:]:
            concept_values += list(attempt.get("techniques") or [])
            strategy = attempt.get("strategy") if isinstance(attempt.get("strategy"), dict) else {}
            concept_values.append(strategy.get("family"))
        for strategy in state.get("strategies", []):
            concept_values.append(strategy.get("family"))
        for value in concept_values:
            if not _text(value):
                continue
            concept_id = f"concept:{_slug(value)}"
            node(concept_id, "concept", value)
            edge(problem_node, concept_id, "uses_concept")
            concepts_by_problem[problem_id].add(concept_id)

        source_urls = [problem.get("source_url"), problem.get("formalization_url")]
        for attempt in attempts_by_problem[problem_id][-20:]:
            source_urls += list(attempt.get("citations") or [])
        for fact in state.get("established_facts", []):
            source_urls += _urls(fact.get("evidence"))
        for url in list(dict.fromkeys(str(value) for value in source_urls if str(value or "").startswith("http"))):
            source_id = _source_id(url)
            node(source_id, "source", urlparse(url).netloc or url, url=url)
            edge(problem_node, source_id, "grounded_in")

        memory_groups = (
            ("fact", state.get("established_facts", [])[-30:], "claim", "establishes"),
            ("lead", state.get("open_leads", [])[-20:], "description", "has_lead"),
            ("exclusion", state.get("ruled_out", [])[-20:], "claim_or_route", "rules_out"),
        )
        for kind, rows, primary, relation in memory_groups:
            for index, row in enumerate(rows):
                label = _text(row.get(primary), 1000)
                if not label:
                    continue
                token = hashlib.sha256(f"{problem_id}\n{kind}\n{label}".encode()).hexdigest()[:12]
                memory_id = f"{kind}:{problem_id}:{token}"
                node(memory_id, kind, label, problem_id=problem_id, detail=row)
                edge(problem_node, memory_id, relation)

        for strategy in state.get("strategies", [])[-30:]:
            raw_id = strategy.get("id") or f"strategy-{strategy.get('fingerprint')}"
            strategy_id = f"strategy:{problem_id}:{_slug(raw_id)}"
            node(
                strategy_id, "strategy", strategy.get("family") or raw_id,
                problem_id=problem_id, status=strategy.get("status"),
                mechanism=_text(strategy.get("mechanism"), 2400),
                discriminator=_text(strategy.get("discriminating_test"), 1600),
            )
            edge(problem_node, strategy_id, "pursues")

    for left, right in combinations(sorted(concepts_by_problem), 2):
        shared = sorted(concepts_by_problem[left].intersection(concepts_by_problem[right]))
        if not shared:
            continue
        labels = [nodes[concept_id]["label"] for concept_id in shared[:8]]
        edge(f"problem:{left}", f"problem:{right}", "shares_concepts", concepts=labels)
        edge(f"problem:{right}", f"problem:{left}", "shares_concepts", concepts=labels)

    graph = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": store.now_iso(),
        "canonical_sources": [
            "data/problems.json", "data/research_states/*.json", "data/attempts.jsonl",
            "data/strategy_library.json",
        ],
        "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
        "edges": sorted(edges, key=lambda row: (row["source"], row["relation"], row["target"])),
    }
    return graph


def refresh() -> dict[str, Any]:
    graph = build()
    store.write_json_atomic(store.STATE / BRAIN_FILE, graph)
    return graph


def summary(graph: dict[str, Any] | None = None) -> dict[str, int]:
    graph = graph or build()
    counts: dict[str, int] = defaultdict(int)
    for row in graph.get("nodes", []):
        counts[str(row.get("type"))] += 1
    return {"nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", [])), **dict(counts)}
