from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from . import store


RESULT_RE = re.compile(r"```proof_result\s*(\{.*?\})\s*```", re.DOTALL)
OUTCOMES = {"failed", "no_progress", "progress", "candidate"}
RESEARCH_SKILL = store.ROOT / "skills" / "computational-researcher" / "SKILL.md"
EXPERIMENT_RUNNER = store.ROOT / "skills" / "computational-researcher" / "scripts" / "run_experiment.py"


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
    for key in ("claims", "evidence", "next_steps", "citations", "techniques", "experiments", "transfer_insights"):
        if not isinstance(result.get(key, []), list):
            raise ValueError(f"{key} must be a list")
    return result


def _research_contract() -> str:
    try:
        return RESEARCH_SKILL.read_text()
    except OSError as exc:
        raise RuntimeError(f"computational researcher skill unavailable: {exc}") from exc


def _workspace_artifacts(workspace: Path) -> dict[str, str]:
    """Hash bounded, research-created artifacts without archiving environments or caches."""
    hashes: dict[str, str] = {}
    ignored = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
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


def build_prompt(problem: dict[str, Any], lane: str, workspace: Path) -> str:
    hard = lane == "hard"
    return f"""You are running one bounded, headless research attempt.

OPERATING SKILL
{_research_contract()}

PROBLEM
Title: {problem['title']}
Contribution type: {problem.get('contribution_type') or 'open-problem research'}
Statement: {problem['statement']}
Official/current source: {problem['source_url']}
Source status: {problem.get('problem_state')}
Formalization: {problem.get('formalization_url') or '(none known)'}
Why selected: {problem.get('rationale')}
Verification contract: {problem.get('verifiability')}
Known techniques: {', '.join(problem.get('techniques') or [])}

LANE
{('Hard/famous lane. Seek one genuinely new lemma, reduction, parametric family, computational bound, or falsifiable route. Do not spend the run narrating the whole famous problem.' if hard else 'Discovery lane. Prefer a concrete witness, executable search, exact identity, formal lemma, or rigorous elimination of a bounded route.')}

PRIOR ATTEMPTS
{_prior_context(problem['id'])}

WORK RULES
1. Read the official source and its cited/original references before relying on the statement. Search for newer literature and preserve direct URLs.
2. Choose one approach that is materially different from failed fingerprints above. State why it is worth this run.
3. Work concretely. You may create code, notes, Lean files, and certificates only under {workspace}.
   For a reproducible computational test, run:
   python3 {EXPERIMENT_RUNNER} --name NAME --hypothesis HYPOTHESIS --expected-signal SIGNAL --timeout SECONDS --memory-mb MB --source-url URL -- COMMAND ARGS...
   It runs argv directly without a shell and stores logs, metadata, seeds, limits, source/script/dependency hashes, git state, and peak memory under .proof-experiments/.
4. Test examples and edge cases. Try to falsify every central lemma. A computation is evidence only for the exact range checked.
5. A suspiciously short proof, unused hypothesis, stronger-than-requested conclusion, or mismatch with the source is a red flag, not a breakthrough.
6. `candidate` means only “worth independent human/skeptic review.” Never write that the problem is solved or disproved.
7. Cite prior human work and disclose every automated tool used. Do not optimize for publicity.
8. Spend reasoning on selecting information-rich experiments; use programs for enumeration and repetition. Record failed controls.
9. End with exactly one fenced JSON block in this schema:

```proof_result
{{
  "outcome": "failed|no_progress|progress|candidate",
  "approach": "specific route attempted",
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
  "tool_disclosure": "models, CAS, proof assistants, solvers, and code used"
}}
```

Do not include a confidence score. Correct uncertainty is part of the result.
"""


def run(problem: dict[str, Any], lane: str) -> dict[str, Any]:
    model = "gpt-5.6-sol" if lane == "hard" else "gpt-5.6-terra"
    effort = "xhigh" if lane == "hard" else "high"
    ceiling = int(os.environ.get("PROOF_HARD_TIMEOUT_SEC" if lane == "hard" else "PROOF_EASY_TIMEOUT_SEC",
                                 "7200" if lane == "hard" else "3600"))
    workspace = store.RESEARCH / problem["id"] / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(problem, lane, workspace)
    started = store.now_iso()
    start = time.monotonic()
    command = [
        os.environ.get("CODEX_BIN", "codex"), "exec", "--ephemeral", "--json",
        "--sandbox", "workspace-write",
        "-c", 'approval_policy="never"',
        "-c", 'forced_login_method="chatgpt"',
        "-c", f'model_reasoning_effort="{effort}"',
        "--ignore-user-config", "--ignore-rules", "--model", model, "-",
    ]
    # The research model gets the minimum process environment needed to run Codex.
    # Deployment, social, and other service credentials must never enter its context.
    allowed_env = {
        "HOME", "PATH", "LANG", "LC_ALL", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed_env}
    env.setdefault("HOME", "/root")
    try:
        proc = subprocess.run(
            command, input=prompt, text=True, capture_output=True, cwd=workspace,
            env=env, timeout=ceiling, start_new_session=True,
        )
        text, usage, stream_failed = _codex_text(proc.stdout)
        if proc.returncode != 0 or stream_failed:
            raise RuntimeError(f"Codex failed rc={proc.returncode}: {proc.stderr[-1000:]}")
        result = extract_result(text)
        outcome = result["outcome"]
        error = ""
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        usage = {}
        result = {
            "approach": "Headless research pass",
            "summary": f"The pass did not produce a valid research result: {type(exc).__name__}: {exc}",
            "rationale": "Infrastructure or output-contract failure is not mathematical progress.",
            "claims": [], "evidence": [], "next_steps": ["Repair the failed pass and rerun."],
            "citations": [problem["source_url"]], "techniques": [],
            "tool_disclosure": f"Codex {model}; run failed before a valid disclosure was returned.",
        }
        outcome = "error"
        error = str(exc)

    finished = store.now_iso()
    stamp = finished[:19].replace(":", "").replace("-", "").replace("T", "-")
    attempt_id = f"{problem['id']}-{stamp}-{uuid.uuid4().hex[:6]}"
    return {
        "id": attempt_id,
        "problem_id": problem["id"],
        "started_at": started,
        "finished_at": finished,
        "duration_seconds": round(time.monotonic() - start, 1),
        "lane": lane,
        "model": model,
        "effort": effort,
        "outcome": outcome,
        "approach": result["approach"].strip()[:4000],
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
        "tool_disclosure": str(result.get("tool_disclosure") or "")[:4000],
        "review_status": "needs Charlie review" if outcome == "candidate" else "not a result claim",
        "usage": usage,
        "error": error,
        "artifact_hashes": _workspace_artifacts(workspace),
    }
