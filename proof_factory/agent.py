from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from . import brain, contribution_gate, research_state, store


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
        "established_facts", "ruled_out", "open_leads", "strategy_proposals",
    ):
        if not isinstance(result.get(key, []), list):
            raise ValueError(f"{key} must be a list")
    for key in ("strategy", "continuation", "candidate_profile"):
        if not isinstance(result.get(key, {}), dict):
            raise ValueError(f"{key} must be an object")
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

CROSS-PROBLEM RESEARCH BRAIN
{brain.context_for_problem(problem)}

RULES
1. Read relevant files in the shared workspace and consult the full project dossier when it exists.
2. Do not repeat a blocked or ruled-out route without satisfying its recorded reopen condition.
3. Distinguish sourced fact, reported computation, inference, and proposal. Preserve direct source URLs.
4. Do not declare a proof, disproof, or candidate. Do not edit the durable research map or append-only ledger.
5. Return a memo under 1,500 words with: best live route; exact rationale; cheapest discriminator; controls; failure modes;
   reusable artifact; stop condition; and what the Sol principal should reject or verify independently.
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


def _run_codex(prompt: str, *, model: str, effort: str, workspace: Path, timeout: int) -> tuple[str, dict[str, Any]]:
    command = [
        os.environ.get("CODEX_BIN", "codex"), "exec", "--ephemeral", "--json",
        "--sandbox", os.environ.get("PROOF_CODEX_SANDBOX", "danger-full-access"),
        "-c", 'approval_policy="never"',
        "-c", 'forced_login_method="chatgpt"',
        "-c", f'model_reasoning_effort="{effort}"',
        "--ignore-user-config", "--ignore-rules", "--model", model, "-",
    ]
    proc = subprocess.run(
        command, input=prompt, text=True, capture_output=True, cwd=workspace,
        env=_minimal_env(), timeout=timeout, start_new_session=True,
    )
    text, usage, stream_failed = _codex_text(proc.stdout)
    if proc.returncode != 0 or stream_failed or not text.strip():
        detail = (proc.stderr or proc.stdout)[-1000:]
        raise RuntimeError(f"Codex {model} failed rc={proc.returncode}: {detail}")
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

RESEARCH PHASE
{phase_contract}

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
   {store.ROOT / 'scripts' / 'bootstrap-formal-conjectures.sh'}; it installs no system packages,
   changes no shell profile, and serializes the shared Lean cache. Do not install system packages,
   alter global configuration, or use credentials without explicit authorization.
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
4. Test examples and edge cases. Try to falsify every central lemma. A computation is evidence only for the exact range checked.
5. A suspiciously short proof, unused hypothesis, stronger-than-requested conclusion, or mismatch with the source is a red flag.
6. Cite prior human work and disclose every automated tool used. Do not optimize for publicity.
7. Report concrete lemmas, equations, maps, programs, certificates, and counterexamples. Reject vague “promising direction” language.
8. A larger arbitrary cutoff is not a contribution. It becomes candidate-eligible only if it improves
   the actual best-known result, answers a source's explicit request, has confirmed expert interest,
   or yields a new structural result. “We did not find it in a quick search” is not novelty evidence.
9. End with exactly one fenced JSON block in this schema:

```proof_result
{{
  "outcome": "failed|no_progress|progress|candidate",
  "approach": "specific route attempted",
  "strategy": {{"family":"named approach family","fingerprint":"reuse existing or blank for deterministic creation","mechanism":"what actually generates information","parent_ids":["strategy-id if combined"]}},
  "hypothesis": "falsifiable claim tested this epoch",
  "discriminating_test": "cheapest observation that separates success from failure",
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
  "strategy_proposals": [{{"family":"different family","mechanism":"concrete mechanism","hypothesis":"testable claim","discriminating_test":"cheap test","rationale":"why it may outperform current routes"}}],
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
        text, usage = _run_codex(prompt, model=model, effort=effort, workspace=workspace, timeout=ceiling)
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

    return {
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
        "strategy_proposals": objects("strategy_proposals", 10),
        "tool_disclosure": disclosure[:4000],
        "review_status": "needs isolated skeptic review" if outcome == "candidate" else ("internal result; not a contribution candidate" if result.get("outcome") == "candidate" else "not a result claim"),
        "usage": usage,
        "error": error,
        "artifact_hashes": _workspace_artifacts(workspace),
    }
