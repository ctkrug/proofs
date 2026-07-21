from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import agent, store


SCOUT_RE = re.compile(r"```contribution_candidate\s*(\{.*?\})\s*```", re.DOTALL)
SOURCES_FILE = store.DATA / "source_registry.json"


def extract_candidate(text: str) -> dict[str, Any]:
    matches = SCOUT_RE.findall(text or "")
    if matches:
        value = json.loads(matches[-1])
    else:
        value = None
        decoder = json.JSONDecoder()
        for index, char in enumerate(text or ""):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and (parsed.get("outcome") or parsed.get("source_url")):
                value = parsed
        if value is None:
            raise ValueError("missing contribution_candidate JSON object")
    if not isinstance(value, dict):
        raise ValueError("contribution candidate must be an object")
    if value.get("outcome") == "no_candidate":
        if not isinstance(value.get("reason"), str) or not value["reason"].strip():
            raise ValueError("no_candidate requires a reason")
        return value
    required_text = {
        "title", "statement", "source_url", "source_name", "problem_state",
        "contribution_type", "verifiability", "rationale", "external_channel", "external_url",
    }
    missing = [key for key in required_text if not isinstance(value.get(key), str) or not value[key].strip()]
    if missing:
        raise ValueError(f"candidate missing fields: {missing}")
    for key in ("source_url", "external_url"):
        if urlparse(value[key]).scheme not in {"http", "https"}:
            raise ValueError(f"{key} must use http or https")
    if not isinstance(value.get("techniques"), list):
        raise ValueError("techniques must be a list")
    for key in ("difficulty", "verification_score", "contribution_score", "review_cost", "novelty_risk"):
        number = int(value.get(key) or 0)
        if number < 1 or number > 10:
            raise ValueError(f"{key} must be between 1 and 10")
    probability = float(value.get("estimated_success_probability") or 0)
    if probability <= 0 or probability > 1:
        raise ValueError("estimated_success_probability must be in (0, 1]")
    work = value.get("upstream_work_check")
    if not isinstance(work, dict) or work.get("active_prs") != 0:
        raise ValueError("candidate requires an upstream_work_check with active_prs=0")
    if not isinstance(work.get("checked_url"), str) or not work["checked_url"].startswith(("http://", "https://")):
        raise ValueError("upstream_work_check requires a checked_url")
    if not isinstance(work.get("checked_at"), str) or not work["checked_at"].strip():
        raise ValueError("upstream_work_check requires checked_at")
    return value


def _prompt(sources: list[dict[str, Any]]) -> str:
    return f"""Find exactly one unusually small, legitimate, currently open academic contribution target.

OPERATING SKILL
{agent._research_contract()}

NORTH STAR
Maximize externally verified, net-new scholarly credit per compute and human-review hour. A target
that is obscure, narrow, or useful to only one specialist is welcome. Fame has almost no value.

SOURCE ROUTES
{json.dumps(sources, indent=2, ensure_ascii=False)}

RULES
1. Browse current primary sources and recent literature. Never infer open status from an old list.
2. For any repository target, inspect the issue's linked/open pull requests and relevant branch/PR search. Reject it if any active PR claims the same work.
2. Prefer a finite witness, exact optimum, one-step classification extension, useful correction,
   formalization gap tied to research, or narrow explicit question from a recent paper.
3. Identify a real outside acceptance path. A self-published web record alone has zero credit.
4. Reject mature compute lotteries, vague conjectures, bulk sequence generation, and anything whose
   decisive check is another LLM.
5. The statement must be exact enough for a new researcher to begin without guessing.
6. Estimate conservatively. The target will receive an independent status audit during its first run.
7. End with exactly one JSON object:

```contribution_candidate
{{
  "outcome": "candidate",
  "title": "precise target",
  "statement": "exact bounded objective and what remains open",
  "source_url": "primary/current URL supporting status",
  "source_name": "source title or maintainer",
  "problem_state": "open|falsifiable|verifiable|decidable",
  "contribution_type": "finite witness|exact optimum|classification|sequence contribution|formalization|dataset correction|research software|computational bound|lemma",
  "verifiability": "certificate and independent checker",
  "rationale": "why this is unusually tractable and potentially new",
  "external_channel": "specific repository, maintainer, workshop, or journal",
  "external_url": "channel URL",
  "upstream_work_check": {{"active_prs":0,"checked_url":"direct issue/PR search URL","checked_at":"ISO date","evidence":"what linked/open PR search showed"}},
  "estimated_success_probability": 0.01,
  "difficulty": 1,
  "verification_score": 1,
  "contribution_score": 1,
  "review_cost": 1,
  "novelty_risk": 1,
  "techniques": ["specific technique"]
}}
```

If no target survives current-status and external-channel checks, return this instead of lowering the bar:

```contribution_candidate
{{"outcome":"no_candidate","reason":"specific searches performed and why every lead failed"}}
```
"""


def run() -> dict[str, Any]:
    sources = store.read_json(SOURCES_FILE, [])
    if not isinstance(sources, list) or not sources:
        raise ValueError("source registry is empty")
    workspace = store.RESEARCH / "scout" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    command = [
        os.environ.get("CODEX_BIN", "codex"), "exec", "--ephemeral", "--json",
        "--sandbox", "workspace-write", "-c", 'approval_policy="never"',
        "-c", 'forced_login_method="chatgpt"', "-c", 'model_reasoning_effort="high"',
        "--ignore-user-config", "--ignore-rules", "--model", "gpt-5.6-terra", "-",
    ]
    allowed = {"HOME", "PATH", "LANG", "LC_ALL", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env.setdefault("HOME", "/root")
    proc = subprocess.run(
        command, input=_prompt(sources), text=True, capture_output=True, cwd=workspace,
        env=env, timeout=int(os.environ.get("PROOF_SCOUT_TIMEOUT_SEC", "3600")), start_new_session=True,
    )
    text, usage, failed = agent._codex_text(proc.stdout)
    store.write_json_atomic(store.STATE / "scout-last.json", {
        "finished_at": store.now_iso(),
        "returncode": proc.returncode,
        "stream_failed": failed,
        "final_text": text[-20000:],
        "stderr_tail": proc.stderr[-4000:],
        "usage": usage,
    })
    if proc.returncode != 0 or failed:
        raise RuntimeError(f"scout failed rc={proc.returncode}: {proc.stderr[-1000:]}")
    candidate = extract_candidate(text)
    if candidate.get("outcome") == "no_candidate":
        return {"added": False, "reason": candidate["reason"]}
    key = hashlib.sha256((candidate["source_url"] + "\n" + candidate["statement"]).encode()).hexdigest()[:12]
    row = {
        "id": f"scout-{key}",
        **candidate,
        "lane": "easy",
        "status": "queued",
        "priority": 40,
        "attempt_count": 0,
        "research_attempt_count": 0,
        "accepted_result": False,
        "added_at": store.now_iso(),
        "source_checked_at": store.now_iso(),
        "intake_source": "agentic academic contribution scout",
        "scout_model": "gpt-5.6-terra",
        "scout_usage": usage,
    }
    with store.lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        problems = store.load_problems()
        if any(problem.get("source_url") == row["source_url"] or problem.get("id") == row["id"] for problem in problems):
            return {"added": False, "reason": "duplicate", "candidate": row["id"]}
        store.save_problems(problems + [row])
    return {"added": True, "candidate": row["id"], "title": row["title"], "source_url": row["source_url"]}
