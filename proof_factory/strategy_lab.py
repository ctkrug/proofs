from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from typing import Any
from urllib.parse import urlparse

from . import agent, config, research_state, store


PROPOSAL_RE = re.compile(r"```strategy_proposal\s*(\{.*?\})\s*```", re.DOTALL)
LIBRARY_FILE = store.DATA / "strategy_library.json"
PROPOSALS_FILE = store.DATA / "strategy_proposals.jsonl"


def extract_proposal(text: str) -> dict[str, Any]:
    matches = PROPOSAL_RE.findall(text or "")
    if not matches:
        raise ValueError("missing strategy_proposal JSON block")
    value = json.loads(matches[-1])
    if not isinstance(value, dict):
        raise ValueError("strategy proposal must be an object")
    if value.get("outcome") == "no_change":
        if not str(value.get("reason") or "").strip():
            raise ValueError("no_change requires a reason")
        return value
    if value.get("action") not in {"add", "improve"}:
        raise ValueError("action must be add or improve")
    required = ("family", "use_when", "mechanism", "first_discriminator", "efficiency_plan")
    missing = [key for key in required if not str(value.get(key) or "").strip()]
    if missing:
        raise ValueError(f"proposal missing fields: {missing}")
    if not isinstance(value.get("failure_modes"), list) or not value["failure_modes"]:
        raise ValueError("failure_modes must be a nonempty list")
    if not isinstance(value.get("sources"), list) or not value["sources"]:
        raise ValueError("sources must be a nonempty list")
    if any(urlparse(str(url)).scheme not in {"http", "https"} for url in value["sources"]):
        raise ValueError("all sources must use http or https")
    if value["action"] == "improve" and not str(value.get("target_id") or "").strip():
        raise ValueError("improve requires target_id")
    return value


def _prompt() -> str:
    library = store.read_json(LIBRARY_FILE, [])
    problems = store.load_problems()
    state_digest = []
    for problem in problems:
        state = research_state.load(problem)
        counts = research_state.summary_counts(state)
        state_digest.append({
            "id": problem["id"], "title": problem.get("title"), "contribution_type": problem.get("contribution_type"),
            "techniques": problem.get("techniques", []), "research_counts": counts,
            "last_synthesis": state.get("synthesis_summary"),
        })
    return f"""You maintain a small, executable research-strategy library for an autonomous academic contribution system.

NORTH STAR
Improve independently verifiable, net-new scholarly contribution per unit of compute and human review. Add one strategy
only when it changes an executable research decision. Prefer exact evaluators, independent checks, useful negative results,
formal methods, and resumable experiments. Avoid generic creativity advice or renaming an existing mechanism.

CURRENT LIBRARY
{json.dumps(library, indent=2, ensure_ascii=False)}

CURRENT PORTFOLIO DIGEST
{json.dumps(state_digest, indent=2, ensure_ascii=False)[:18000]}

TASK
Browse current primary sources (papers, official project documentation, or maintained repositories). Propose exactly one
new strategy or a concrete improvement to one existing entry. It must include: when to use it; the actual information-
generating mechanism; the cheapest discriminating test; at least two likely failure modes; and a direct experiment template
that one of the current problems could execute in its next bounded epoch. For any large search space it must also give a
quantified efficiency plan covering safe symmetry reduction, compression, batching/vectorization, incremental evaluation,
decomposition, pruning, or reusable solver/proof state, plus the check that makes the shortcut sound. Cite direct URLs. An improvement must materially
change selection, evaluation, preservation of diversity, or falsification—not merely wording.

Return exactly one block:
```strategy_proposal
{{
  "outcome":"proposal",
  "action":"add|improve",
  "target_id":"existing id when improving, otherwise blank",
  "family":"stable family name",
  "use_when":"observable applicability condition",
  "mechanism":"concrete information-generating loop",
  "first_discriminator":"cheapest test before scale-up",
  "efficiency_plan":"naive space and bottleneck -> safe compression/batching/vectorization/decomposition/pruning/reuse mechanism -> estimated savings -> soundness check; say not applicable with reason for a non-search strategy",
  "experiment_template":"problem id -> hypothesis -> command/tool -> expected decisive signal -> stop condition",
  "failure_modes":["specific failure"],
  "sources":["direct primary-source URL"],
  "change_rationale":"why this is distinct or materially better"
}}
```

If current primary-source research yields no material change, return:
```strategy_proposal
{{"outcome":"no_change","reason":"sources checked and why no proposed change cleared the bar"}}
```
"""


def run() -> dict[str, Any]:
    workspace = store.RESEARCH / "strategy-lab" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    command = [
        config.get_text("CODEX_BIN", "codex"), "exec", "--ephemeral", "--json",
        "--sandbox", "workspace-write", "-c", 'approval_policy="never"',
        "-c", 'forced_login_method="chatgpt"', "-c", 'model_reasoning_effort="high"',
        "--ignore-user-config", "--ignore-rules", "--model", "gpt-5.6-terra", "-",
    ]
    allowed = {"HOME", "PATH", "LANG", "LC_ALL", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env.setdefault("HOME", "/root")
    proc = subprocess.run(
        command, input=_prompt(), text=True, capture_output=True, cwd=workspace, env=env,
        timeout=config.get_int("PROOF_STRATEGY_TIMEOUT_SEC", 3600, minimum=1, maximum=86_400),
        start_new_session=True,
    )
    text, usage, failed = agent._codex_text(proc.stdout)
    store.write_json_atomic(store.STATE / "strategy-lab-last.json", {
        "finished_at": store.now_iso(), "returncode": proc.returncode, "stream_failed": failed,
        "final_text": text[-20000:], "stderr_tail": proc.stderr[-4000:], "usage": usage,
    })
    if proc.returncode != 0 or failed:
        raise RuntimeError(f"strategy lab failed rc={proc.returncode}: {proc.stderr[-1000:]}")
    proposal = extract_proposal(text)
    if proposal.get("outcome") == "no_change":
        return {"changed": False, "reason": proposal["reason"]}

    with store.lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        library = store.read_json(LIBRARY_FILE, [])
        if not isinstance(library, list):
            raise ValueError("strategy library is invalid")
        if proposal["action"] == "improve":
            index = next((i for i, row in enumerate(library) if row.get("id") == proposal["target_id"]), None)
            if index is None:
                raise ValueError(f"unknown strategy target: {proposal['target_id']}")
            strategy_id = proposal["target_id"]
            version = int(library[index].get("version") or 1) + 1
            replacement = {"id": strategy_id, **{k: v for k, v in proposal.items() if k not in {"outcome", "action", "target_id", "change_rationale"}}, "version": version, "updated_at": store.now_iso()}
            library[index] = replacement
        else:
            strategy_id = re.sub(r"[^a-z0-9]+", "-", proposal["family"].lower()).strip("-")[:60]
            if not strategy_id:
                strategy_id = "strategy-" + research_state.strategy_fingerprint(proposal["family"], proposal["mechanism"])
            if any(row.get("id") == strategy_id for row in library):
                raise ValueError(f"strategy id already exists: {strategy_id}")
            library.append({"id": strategy_id, **{k: v for k, v in proposal.items() if k not in {"outcome", "action", "target_id", "change_rationale"}}, "version": 1, "updated_at": store.now_iso()})
        record = {
            "id": hashlib.sha256((store.now_iso() + json.dumps(proposal, sort_keys=True)).encode()).hexdigest()[:16],
            "recorded_at": store.now_iso(), "model": "gpt-5.6-terra", "usage": usage, **proposal,
        }
        store.write_json_atomic(LIBRARY_FILE, library)
        PROPOSALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PROPOSALS_FILE.open("a") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return {"changed": True, "action": proposal["action"], "strategy_id": strategy_id, "family": proposal["family"]}
