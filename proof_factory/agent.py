from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from . import brain, contribution_gate, prior_art, research_state, roadmap, store, tactics, telemetry


RESULT_RE = re.compile(r"```proof_result\s*(\{.*?\})\s*```", re.DOTALL)
OUTCOMES = {"failed", "no_progress", "progress", "candidate"}
RESEARCH_SKILL = store.ROOT / "skills" / "computational-researcher" / "SKILL.md"
EXPERIMENT_RUNNER = store.ROOT / "skills" / "computational-researcher" / "scripts" / "run_experiment.py"
TERRA_MODEL = "gpt-5.6-terra"
SOL_MODEL = "gpt-5.6-sol"
DELEGATE_ROLES = {
    "hard": ("literature-strategy", "experiment-verification"),
    "easy": ("source-discriminator",),
}


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
    result = json.loads(matches[-1])
    if not isinstance(result, dict):
        raise ValueError("proof_result must be an object")
    if result.get("outcome") not in OUTCOMES:
        raise ValueError(f"invalid outcome: {result.get('outcome')!r}")
    for key in ("approach", "summary", "rationale"):
        if not isinstance(result.get(key), str) or not result[key].strip():
            raise ValueError(f"missing result field: {key}")
    for key in (
        "claims", "evidence", "next_steps", "citations", "techniques", "experiments", "transfer_insights",
        "established_facts", "ruled_out", "open_leads", "strategy_proposals", "synthesis_candidates",
    ):
        if not isinstance(result.get(key, []), list):
            raise ValueError(f"{key} must be a list")
    for candidate in result.get("synthesis_candidates", []):
        if not isinstance(candidate, dict):
            raise ValueError("synthesis_candidates entries must be objects")
        required_candidate = (
            "family", "mechanism", "source_inputs", "transfer_hypothesis",
            "discriminating_test", "falsification_signal",
        )
        missing_candidate = [key for key in required_candidate if not str(candidate.get(key) or "").strip()]
        if missing_candidate:
            raise ValueError(f"synthesis candidate missing fields: {missing_candidate}")
        if not isinstance(candidate.get("parent_strategy_ids", []), list):
            raise ValueError("synthesis_candidate.parent_strategy_ids must be a list")
    for key in ("strategy", "continuation", "candidate_profile", "campaign_assessment", "search_efficiency", "space_reduction", "tactical_learning", "prior_art_check", "field_progress_assessment"):
        if not isinstance(result.get(key, {}), dict):
            raise ValueError(f"{key} must be an object")
    efficiency = result.get("search_efficiency")
    if not isinstance(efficiency, dict):
        raise ValueError("search_efficiency must be an object")
    required_efficiency = ("naive_space", "chosen_mechanism", "estimated_or_measured_savings", "soundness_guard")
    missing_efficiency = [key for key in required_efficiency if not str(efficiency.get(key) or "").strip()]
    if missing_efficiency:
        raise ValueError(f"search_efficiency missing fields: {missing_efficiency}")
    if not isinstance(efficiency.get("reductions_considered"), list) or not efficiency["reductions_considered"]:
        raise ValueError("search_efficiency.reductions_considered must be a nonempty list")
    reduction = result.get("space_reduction")
    if not isinstance(reduction, dict):
        raise ValueError("space_reduction must be an object")
    required_reduction = (
        "ambient_space", "represented_space_before", "eliminated_or_quotiented",
        "represented_space_after", "reduction_factor", "measurement_status", "unit",
        "coverage_scope", "soundness_basis", "remaining_unknown", "next_bulk_elimination",
    )
    missing_reduction = [key for key in required_reduction if not str(reduction.get(key) or "").strip()]
    if missing_reduction:
        raise ValueError(f"space_reduction missing fields: {missing_reduction}")
    if reduction.get("measurement_status") not in {"exact", "upper_bound", "estimate", "not_applicable"}:
        raise ValueError("space_reduction.measurement_status must be exact|upper_bound|estimate|not_applicable")
    learning = result.get("tactical_learning")
    if not isinstance(learning, dict):
        raise ValueError("tactical_learning must be an object")
    required_learning = ("prediction", "observation", "surprise", "failure_signature", "bottleneck_update", "route_decision", "next_discriminator")
    missing_learning = [key for key in required_learning if not str(learning.get(key) or "").strip()]
    if missing_learning:
        raise ValueError(f"tactical_learning missing fields: {missing_learning}")
    if learning.get("route_decision") not in {"continue", "hold", "redirect", "close"}:
        raise ValueError("tactical_learning.route_decision must be continue|hold|redirect|close")
    for key in ("reusable_assets", "constraints_learned"):
        if not isinstance(learning.get(key), list):
            raise ValueError(f"tactical_learning.{key} must be a list")
    prior = result.get("prior_art_check")
    if not isinstance(prior, dict):
        raise ValueError("prior_art_check must be an object")
    required_prior = ("exact_delta", "duplicate_risk", "comparison_test")
    missing_prior = [key for key in required_prior if not str(prior.get(key) or "").strip()]
    if missing_prior:
        raise ValueError(f"prior_art_check missing fields: {missing_prior}")
    if not isinstance(prior.get("nearest_method_ids"), list) or not prior["nearest_method_ids"]:
        raise ValueError("prior_art_check.nearest_method_ids must be a nonempty list")
    if not isinstance(prior.get("source_urls"), list):
        raise ValueError("prior_art_check.source_urls must be a list")
    if prior.get("classification") not in {"genuinely_different", "material_modification", "replication_control"}:
        raise ValueError("prior_art_check.classification must be genuinely_different|material_modification|replication_control")
    if prior.get("decision") not in {"proceed", "control_only", "stop"}:
        raise ValueError("prior_art_check.decision must be proceed|control_only|stop")
    field_progress = result.get("field_progress_assessment")
    if not isinstance(field_progress, dict):
        raise ValueError("field_progress_assessment must be an object")
    if field_progress.get("status") not in {"met", "not_met"}:
        raise ValueError("field_progress_assessment.status must be met|not_met")
    required_progress = (
        "gate_id", "contribution_class", "closest_prior_result", "measurable_improvement",
        "independent_validation", "external_audience", "remains_unproved", "route_recommendation",
    )
    missing_progress = [key for key in required_progress if not str(field_progress.get(key) or "").strip()]
    if missing_progress:
        raise ValueError(f"field_progress_assessment missing fields: {missing_progress}")
    return result


def _research_contract() -> str:
    try:
        return RESEARCH_SKILL.read_text()
    except OSError as exc:
        raise RuntimeError(f"computational researcher skill unavailable: {exc}") from exc


def _workspace_artifacts(workspace: Path) -> dict[str, str]:
    """Hash bounded, research-created artifacts without archiving environments or caches."""
    hashes: dict[str, str] = {}
    ignored = {".git", ".venv", "venv", ".delegates", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
    for path in sorted(workspace.rglob("*")):
        if path.is_symlink() or not path.is_file() or any(part in ignored for part in path.relative_to(workspace).parts):
            continue
        try:
            path.resolve().relative_to(workspace.resolve())
            if path.stat().st_size > 50 * 1024 * 1024:
                continue
            relative = path.relative_to(workspace).as_posix()
            hashes[relative] = store.sha256_file(path)
        except (OSError, ValueError):
            continue
        if len(hashes) >= 250:
            break
    return hashes


def _prior_context(problem_id: str) -> str:
    rows = [row for row in store.load_attempts() if row.get("problem_id") == problem_id][-12:]
    if not rows:
        return "No prior attempts."
    lines = []
    for row in rows:
        lines.append(
            f"- {row.get('finished_at')} [{row.get('outcome')}]: {row.get('approach')}\n"
            f"  Result: {row.get('summary')}\n  Next: {'; '.join(row.get('next_steps') or [])}"
        )
    return "\n".join(lines)


def build_delegate_prompt(
    problem: dict[str, Any], lane: str, workspace: Path, role: str, phase: str = "technical",
) -> str:
    dossier = store.RESEARCH / problem["id"] / "DOSSIER.md"
    role_job = {
        "literature-strategy": (
            "Audit the durable state and cited literature, identify the strongest live route, and expose any historical "
            "duplication, missing premise, or combination with another recorded strategy."
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

DURABLE CAMPAIGN STATE
{research_state.compact_for_prompt(problem)}

DETERMINISTIC TACTICAL BRIEF
{tactics.compact_for_prompt(problem)}

PRIOR-ART ANTI-REDISCOVERY REGISTER
{prior_art.compact_for_prompt(problem)}

CROSS-PROBLEM RESEARCH BRAIN
{brain.context_for_problem(problem)}

RULES
1. Read relevant files in the shared workspace and consult the full project dossier when it exists.
2. Do not repeat a blocked or ruled-out route without satisfying its recorded reopen condition. Compare the proposed
   mechanism with the nearest registered historical methods; label replications as controls and state the exact delta.
3. Distinguish sourced fact, reported computation, inference, and proposal. Preserve direct source URLs.
4. Do not declare a proof, disproof, or candidate. Do not edit the durable research map or append-only ledger.
5. Return a memo under 1,500 words with: best live route; exact rationale; cheapest discriminator; controls; failure modes;
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
        os.environ.get("CODEX_BIN", "codex"), "exec", "--ephemeral", "--json",
        "--sandbox", os.environ.get("PROOF_CODEX_SANDBOX", "danger-full-access"),
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


def build_prompt(
    problem: dict[str, Any], lane: str, workspace: Path,
    delegate_memos: list[dict[str, Any]] | None = None,
    phase: str = "technical",
) -> str:
    hard = lane == "hard"
    epoch_minutes = 120 if hard else 60
    strategy_library = store.read_json(store.DATA / "strategy_library.json", [])
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
    completed_campaign_runs = int(problem.get("research_attempt_count") or 0)
    campaign_minimum = max(
        store.DISCOVERY_CAMPAIGN_MIN_RUNS,
        int(problem.get("campaign_min_runs") or 0),
    )
    next_campaign_run = completed_campaign_runs + 1
    campaign_contract = "" if hard else f"""
DISCOVERY CAMPAIGN
This is non-error research run {next_campaign_run} on this problem; the minimum review point is run {campaign_minimum}.
Do not recommend switching problems before that minimum. At the end of every run, return `campaign_assessment`.
Before run {campaign_minimum}, its decision must be `continue`. At or after run {campaign_minimum}, use `continue` only
when `close_signal` names concrete evidence that the next bounded pass has a credible path to a verifiable contribution;
otherwise use `hold`. A merely open problem, generic optimism, or a renamed dead route is not a close signal.
"""
    return f"""You are the next principal-investigator epoch in an indefinitely continuing, headless research campaign.
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
You have network access and the installed mathematics toolchain inside a credential-isolated research service. Use them
to retrieve primary sources and run bounded experiments when necessary. Treat a practical source/tool failure as the
first task to repair, with reproducible commands and hashes, rather than as a reason to abandon the epoch.

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
{('Hard/famous lane. Seek one genuinely new lemma, reduction, parametric family, computational bound, or falsifiable route. Do not spend the run narrating the whole famous problem.' if hard else 'Discovery lane. Prefer a concrete witness, executable search, exact identity, formal lemma, or rigorous elimination of a bounded route.')}

SOL-TERRA ORCHESTRATION
You are the GPT-5.6 Sol principal. Terra delegates performed bounded reconnaissance before this pass. Their memos are
advisory leads, not evidence and not votes. Audit every claim against primary sources or deterministic artifacts, use the
best concrete discriminator when it survives scrutiny, and explicitly reject misleading suggestions. Do not count model
agreement as independent validation. Promote any delegate artifact you rely on into the main workspace with provenance;
ephemeral delegate directories are not part of the accepted artifact set. Disclose the Sol principal and Terra delegate
roles in the final tool disclosure.

TERRA DELEGATE MEMOS
{json.dumps(delegated, indent=2, ensure_ascii=False)[:28000] if delegated else '(No delegate memo survived; proceed, but record the orchestration failure.)'}

DURABLE RESEARCH STATE (claims/evidence/decisions, never private chain-of-thought)
{research_state.compact_for_prompt(problem)}

CROSS-PROBLEM RESEARCH BRAIN (links are transfer hypotheses, not evidence)
{brain.context_for_problem(problem)}

DETERMINISTIC TACTICAL BRIEF (inspectable priorities, not probabilities)
{tactics.compact_for_prompt(problem)}

AUTOMATED CAMPAIGN ROADMAP (evidence-driven stage graph; no fixed session sequence)
{roadmap.compact_for_prompt(problem)}

PRIOR-ART ANTI-REDISCOVERY REGISTER (method IDs are stable comparison keys)
{prior_art.compact_for_prompt(problem)}

REUSABLE STRATEGY LIBRARY
{json.dumps(strategy_library, indent=2, ensure_ascii=False)[:18000]}

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
     --expected-signal SIGNAL --segment-seconds SECONDS --max-segments SEGMENTS --memory-mb MB \
     --checkpoint-path RELATIVE_CHECKPOINT -- COMMAND ARGS...
   The lab is shell-free, low-priority, hash-recorded, limited to 24-hour segments and seven resumable segments, and accepts
   only allowlisted math runtimes/solvers or executables inside this problem workspace. A multisegment job must actually
   write its checkpoint. Queueing compute is not evidence; a later epoch must inspect its exact record and artifacts.
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
  "strategy": {{"family":"named approach family","fingerprint":"reuse existing or blank for deterministic creation","mechanism":"what actually generates information","parent_ids":["strategy-id if combined"]}},
  "hypothesis": "falsifiable claim tested this epoch",
  "discriminating_test": "cheapest observation that separates success from failure",
  "search_efficiency": {{"naive_space":"candidate count and bottleneck","reductions_considered":["symmetry/compression/batching/vectorization/incremental/decomposition/pruning/reuse options"],"chosen_mechanism":"bulk-elimination design","estimated_or_measured_savings":"reduction ratio or throughput","soundness_guard":"independent equivalence or one-sided coverage check"}},
  "space_reduction": {{"ambient_space":"exact reference universe, such as 2^903 labelled K43 graphs","represented_space_before":"exact expression or honest bound before this epoch","eliminated_or_quotiented":"what this epoch removed or identified","represented_space_after":"exact expression or honest bound after this epoch","reduction_factor":"exact factor, bound, estimate, or none","measurement_status":"exact|upper_bound|estimate|not_applicable","unit":"labelled assignments|isomorphism classes|cubes|profiles|families|proof states|not applicable","coverage_scope":"precise family or global scope","soundness_basis":"proof/check establishing safe elimination or quotient coverage","remaining_unknown":"what is not counted or excluded","next_bulk_elimination":"next class/cube/profile/family-level reduction"}},
  "tactical_learning": {{"prediction":"predeclared expected signal","observation":"what occurred","surprise":"difference from prediction, or none","failure_signature":"reusable failure pattern, or none","bottleneck_update":"current limiting uncertainty or operation","reusable_assets":[{{"name":"artifact/checker/dataset","use":"future use","evidence":"path/hash/check"}}],"constraints_learned":[{{"constraint":"exact restriction learned","scope":"valid scope","evidence":"support"}}],"route_decision":"continue|hold|redirect|close","next_discriminator":"cheapest next test"}},
  "prior_art_check": {{"nearest_method_ids":["stable registry ID or none-found"],"classification":"genuinely_different|material_modification|replication_control","exact_delta":"mechanism-level difference from the nearest work","duplicate_risk":"what could merely rediscover a known result","comparison_test":"cheapest matched test against the nearest baseline","decision":"proceed|control_only|stop","source_urls":["direct primary URL"]}},
  "field_progress_assessment": {{"status":"met|not_met","gate_id":"exact configured gate number/name, or none","contribution_class":"exact contribution class or verified negative/infrastructure result","closest_prior_result":"closest prior result or baseline","measurable_improvement":"quantified delta, or none","independent_validation":"validator and result, or not yet independently validated","external_audience":"accepted audience/channel, or none","remains_unproved":"precise remaining gap","route_recommendation":"close|broaden|redirect|continue and why"}},
  "strategy_status": "proposed|active|promising|blocked|ruled_out|exhausted|superseded",
  "summary": "what actually happened, including limits",
  "rationale": "why the evidence supports this outcome",
  "claims": ["precise claim, if any"],
  "evidence": ["file/command/check and exact scope"],
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
    "independent_validations":[{{"type":"formal_kernel|independent_third_party|repository_ci|external_expert","validator":"who or what","result":"exact result","artifact":"local certificate path or blank","evidence_url":"public evidence or blank"}}],
    "relevance":{{"settles_exact_open_target":false,"improves_best_known_result":false,"source_explicitly_requests_result":false,"expert_interest_confirmed":false,"new_structural_result":false,"evidence_url":"supporting URL"}},
    "arbitrary_cutoff_extension":false
  }},
  "tool_disclosure": "models, CAS, proof assistants, solvers, and code used"
}}
```

Do not include a confidence score. Correct uncertainty is part of the result.
"""


def run(problem: dict[str, Any], lane: str, *, phase: str = "technical") -> dict[str, Any]:
    model = SOL_MODEL
    effort = "high"
    ceiling = int(os.environ.get("PROOF_HARD_TIMEOUT_SEC" if lane == "hard" else "PROOF_EASY_TIMEOUT_SEC",
                                 "7200" if lane == "hard" else "3600"))
    workspace = store.RESEARCH / problem["id"] / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    started = store.now_iso()
    start = time.monotonic()
    delegate_ceiling = int(os.environ.get(
        "PROOF_HARD_DELEGATE_TIMEOUT_SEC" if lane == "hard" else "PROOF_EASY_DELEGATE_TIMEOUT_SEC",
        "1200" if lane == "hard" else "600",
    ))
    epoch_key = f"{started[:19].replace(':', '').replace('-', '').replace('T', '-')}-{uuid.uuid4().hex[:6]}"
    delegate_root = workspace / ".delegates" / epoch_key
    delegate_records: list[dict[str, Any]] = []
    for role in DELEGATE_ROLES[lane]:
        delegate_workspace = delegate_root / role
        delegate_workspace.mkdir(parents=True, exist_ok=True)
        try:
            memo, delegate_usage = _run_codex(
                build_delegate_prompt(problem, lane, workspace, role, phase),
                model=TERRA_MODEL, effort="high", workspace=delegate_workspace, timeout=delegate_ceiling,
                telemetry_meta={"role": f"delegate:{role}", "lane": lane, "problem_id": problem["id"], "phase": phase},
            )
            memo = memo.strip()[:12000]
            status = "completed"
            error_note = ""
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            memo = f"Delegate failed before a usable memo: {type(exc).__name__}: {exc}"
            delegate_usage = {}
            status = "error"
            error_note = str(exc)[:2000]
        memo_file = delegate_workspace / "memo.md"
        memo_file.write_text(memo + "\n")
        delegate_records.append({
            "role": role, "model": TERRA_MODEL, "effort": "high", "status": status,
            "memo_path": str(memo_file.relative_to(workspace)), "memo_sha256": store.sha256_file(memo_file),
            "memo": memo, "usage": delegate_usage, "error": error_note,
        })
    prompt = build_prompt(problem, lane, workspace, delegate_records, phase)
    try:
        text, usage = _run_codex(
            prompt, model=model, effort=effort, workspace=workspace, timeout=ceiling,
            telemetry_meta={"role": "principal", "lane": lane, "problem_id": problem["id"], "phase": phase},
        )
        result = extract_result(text)
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
        gate = contribution_gate.assess(result) if result.get("outcome") == "candidate" else {
            "schema_version": 1, "passed": False, "status": "not_requested", "reasons": [],
        }
        if result.get("outcome") == "candidate" and not gate["passed"]:
            policy_flags.extend(f"Contribution gate: {reason}" for reason in gate["reasons"])
            if outcome == "candidate":
                outcome = "progress"
        error = ""
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        usage = {}
        result = {
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
            "claims": [], "evidence": [], "next_steps": ["Repair the failed pass and rerun."],
            "citations": [problem["source_url"]], "techniques": [],
            "tool_disclosure": f"Codex {model} principal with {TERRA_MODEL} delegates; run failed before a valid disclosure was returned.",
        }
        outcome = "error"
        error = str(exc)
        policy_flags = []
        gate = {"schema_version": 1, "passed": False, "status": "not_requested", "reasons": []}

    finished = store.now_iso()
    stamp = finished[:19].replace(":", "").replace("-", "").replace("T", "-")
    attempt_id = f"{problem['id']}-{stamp}-{uuid.uuid4().hex[:6]}"
    def objects(name: str, limit: int = 30) -> list[dict[str, Any]]:
        return [row for row in result.get(name, []) if isinstance(row, dict)][:limit]
    disclosure = str(result.get("tool_disclosure") or "")[:3200]
    if TERRA_MODEL not in disclosure:
        disclosure = (disclosure + f"; orchestration: {model} principal with {TERRA_MODEL} delegates.").lstrip("; ")

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
        },
        "delegates": [{
            "role": row["role"], "model": row["model"], "effort": row["effort"],
            "status": row["status"], "memo_path": row["memo_path"], "memo_sha256": row["memo_sha256"],
            "usage": row["usage"],
            "error": row["error"],
        } for row in delegate_records],
        "outcome": outcome,
        "approach": result["approach"].strip()[:4000],
        "strategy": result.get("strategy") if isinstance(result.get("strategy"), dict) else {},
        "hypothesis": str(result.get("hypothesis") or "")[:4000],
        "discriminating_test": str(result.get("discriminating_test") or "")[:4000],
        "search_efficiency": {
            "naive_space": str(result["search_efficiency"].get("naive_space") or "")[:2000],
            "reductions_considered": [str(x)[:500] for x in result["search_efficiency"].get("reductions_considered", [])][:20],
            "chosen_mechanism": str(result["search_efficiency"].get("chosen_mechanism") or "")[:2000],
            "estimated_or_measured_savings": str(result["search_efficiency"].get("estimated_or_measured_savings") or "")[:2000],
            "soundness_guard": str(result["search_efficiency"].get("soundness_guard") or "")[:2000],
        },
        "space_reduction": {
            key: str(result["space_reduction"].get(key) or "")[:4000]
            for key in (
                "ambient_space", "represented_space_before", "eliminated_or_quotiented",
                "represented_space_after", "reduction_factor", "measurement_status", "unit",
                "coverage_scope", "soundness_basis", "remaining_unknown", "next_bulk_elimination",
            )
        },
        "tactical_learning": {
            "prediction": str(result["tactical_learning"].get("prediction") or "")[:2000],
            "observation": str(result["tactical_learning"].get("observation") or "")[:2000],
            "surprise": str(result["tactical_learning"].get("surprise") or "")[:2000],
            "failure_signature": str(result["tactical_learning"].get("failure_signature") or "")[:2000],
            "bottleneck_update": str(result["tactical_learning"].get("bottleneck_update") or "")[:2000],
            "reusable_assets": [row for row in result["tactical_learning"].get("reusable_assets", []) if isinstance(row, dict)][:20],
            "constraints_learned": [row for row in result["tactical_learning"].get("constraints_learned", []) if isinstance(row, dict)][:20],
            "route_decision": str(result["tactical_learning"].get("route_decision") or "")[:40],
            "next_discriminator": str(result["tactical_learning"].get("next_discriminator") or "")[:2000],
        },
        "prior_art_check": {
            "nearest_method_ids": [str(x)[:200] for x in result["prior_art_check"].get("nearest_method_ids", [])][:20],
            "classification": str(result["prior_art_check"].get("classification") or "")[:80],
            "exact_delta": str(result["prior_art_check"].get("exact_delta") or "")[:3000],
            "duplicate_risk": str(result["prior_art_check"].get("duplicate_risk") or "")[:3000],
            "comparison_test": str(result["prior_art_check"].get("comparison_test") or "")[:3000],
            "decision": str(result["prior_art_check"].get("decision") or "")[:40],
            "source_urls": [str(x)[:1000] for x in result["prior_art_check"].get("source_urls", [])][:20],
        },
        "field_progress_assessment": {
            key: str(result["field_progress_assessment"].get(key) or "")[:4000]
            for key in (
                "status", "gate_id", "contribution_class", "closest_prior_result", "measurable_improvement",
                "independent_validation", "external_audience", "remains_unproved", "route_recommendation",
            )
        },
        "strategy_status": str(result.get("strategy_status") or "active")[:100],
        "summary": result["summary"].strip()[:8000],
        "rationale": result["rationale"].strip()[:4000],
        "claims": [str(x)[:2000] for x in result.get("claims", [])][:20],
        "evidence": [str(x)[:2000] for x in result.get("evidence", [])][:30],
        "next_steps": [str(x)[:2000] for x in result.get("next_steps", [])][:20],
        "citations": [str(x)[:1000] for x in result.get("citations", [])][:30],
        "techniques": [str(x)[:200] for x in result.get("techniques", [])][:30],
        "research_mode": str(result.get("research_mode") or "unspecified")[:100],
        "experiments": [str(x)[:2000] for x in result.get("experiments", [])][:30],
        "independent_checker": str(result.get("independent_checker") or "not provided")[:4000],
        "transfer_insights": [str(x)[:2000] for x in result.get("transfer_insights", [])][:20],
        "established_facts": objects("established_facts"),
        "ruled_out": objects("ruled_out"),
        "open_leads": objects("open_leads"),
        "blocker": str(result.get("blocker") or "")[:4000],
        "reopen_condition": str(result.get("reopen_condition") or "")[:4000],
        "reopen_evidence": str(result.get("reopen_evidence") or "")[:4000],
        "policy_flags": policy_flags,
        "candidate_profile": result.get("candidate_profile") if isinstance(result.get("candidate_profile"), dict) else {},
        "contribution_gate": gate,
        "contribution_status": "candidate_eligible" if outcome == "candidate" else ("internal_result" if result.get("outcome") == "candidate" else "research_attempt"),
        "continuation": result.get("continuation") if isinstance(result.get("continuation"), dict) else {},
        "campaign_assessment": result.get("campaign_assessment") if isinstance(result.get("campaign_assessment"), dict) else {},
        "strategy_proposals": objects("strategy_proposals", 10),
        "tool_disclosure": disclosure[:4000],
        "review_status": "needs isolated skeptic review" if outcome == "candidate" else ("internal result; not a contribution candidate" if result.get("outcome") == "candidate" else "not a result claim"),
        "usage": usage,
        "error": error,
        "artifact_hashes": _workspace_artifacts(workspace),
    }
    telemetry.epoch_summary(attempt)
    return attempt
