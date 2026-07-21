from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(os.environ.get("PROOF_FACTORY_ROOT", Path(__file__).resolve().parents[1])).resolve()
DATA = ROOT / "data"
STATE = ROOT / "state"
SITE = ROOT / "site"
RESEARCH = ROOT / "research"
PROBLEMS_FILE = DATA / "problems.json"
ATTEMPTS_FILE = DATA / "attempts.jsonl"
RUNTIME_FILE = STATE / "runtime.json"
DISCOVERY_CAMPAIGN_MIN_RUNS = 25


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


@contextlib.contextmanager
def lock(name: str, *, nonblocking: bool = False) -> Iterator[bool]:
    lock_dir = STATE / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / f"{name}.lock").open("a+") as handle:
        flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
        try:
            fcntl.flock(handle.fileno(), flags)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_problems() -> list[dict[str, Any]]:
    rows = read_json(PROBLEMS_FILE, [])
    if not isinstance(rows, list):
        raise ValueError(f"{PROBLEMS_FILE} must contain a JSON list")
    return [row for row in rows if isinstance(row, dict) and row.get("id")]


def save_problems(rows: list[dict[str, Any]]) -> None:
    write_json_atomic(PROBLEMS_FILE, rows)


def discovery_campaign_run_count(problem: dict[str, Any]) -> int:
    """Count non-error research runs since the current discovery campaign began."""
    total = int(problem.get("research_attempt_count") or 0)
    baseline = int(problem.get("campaign_start_research_attempt_count") or 0)
    return max(0, total - baseline)


def start_discovery_campaign(problem_id: str) -> dict[str, Any]:
    """Persist one discovery incumbent so scheduled passes cannot rotate away from it."""
    with lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        problems = load_problems()
        problem = next((row for row in problems if row["id"] == problem_id), None)
        if not problem or problem.get("lane") != "easy":
            raise ValueError(f"unknown discovery problem: {problem_id}")
        for row in problems:
            if row.get("lane") != "easy" or row["id"] == problem_id:
                continue
            if row.get("campaign_state") == "active":
                row["campaign_state"] = "superseded"
                row["campaign_decision"] = "superseded by a newer persisted campaign"
        if problem.get("campaign_state") != "active":
            problem["campaign_state"] = "active"
            problem["campaign_started_at"] = now_iso()
            problem["campaign_start_research_attempt_count"] = int(problem.get("research_attempt_count") or 0)
            problem["campaign_min_runs"] = DISCOVERY_CAMPAIGN_MIN_RUNS
            problem["campaign_decision"] = "continue through the minimum campaign"
        save_problems(problems)
        return problem


def load_attempts() -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    if not ATTEMPTS_FILE.exists():
        return attempts
    for line_number, line in enumerate(ATTEMPTS_FILE.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid attempt JSON at line {line_number}: {exc}") from exc
        if isinstance(row, dict):
            attempts.append(row)
    return attempts


def record_attempt(attempt: dict[str, Any]) -> None:
    """Append an immutable attempt, then atomically refresh its problem projection."""
    required = {"id", "problem_id", "started_at", "finished_at", "lane", "outcome", "summary"}
    missing = required - set(attempt)
    if missing:
        raise ValueError(f"attempt missing fields: {sorted(missing)}")
    with lock("state") as acquired:
        if not acquired:
            raise RuntimeError("state lock unavailable")
        prior_ids = {row.get("id") for row in load_attempts()}
        if attempt["id"] in prior_ids:
            raise ValueError(f"duplicate attempt id: {attempt['id']}")

        problems = load_problems()
        problem = next((row for row in problems if row["id"] == attempt["problem_id"]), None)
        if not problem:
            raise ValueError(f"unknown problem: {attempt['problem_id']}")

        ATTEMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ATTEMPTS_FILE.open("a") as handle:
            handle.write(json.dumps(attempt, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        # Imported here to avoid a module cycle: research_state deliberately uses store's
        # atomic JSON primitives. This projection is public research memory, not chain-of-thought.
        from . import research_state
        durable_state = research_state.update_from_attempt(problem, attempt)

        problem["attempt_count"] = int(problem.get("attempt_count") or 0) + 1
        problem["last_attempt_at"] = attempt["finished_at"]
        outcome = attempt["outcome"]
        if outcome != "error":
            problem["research_attempt_count"] = int(problem.get("research_attempt_count") or 0) + 1
        actionable = any(
            row.get("status") in {"proposed", "promising", "active"} and row.get("last_attempt_id") != attempt["id"]
            for row in durable_state.get("strategies", [])
        ) or any(row.get("status", "open") == "open" for row in durable_state.get("open_leads", []))
        campaign = problem.get("lane") == "easy" and problem.get("campaign_state") == "active"
        assessment = attempt.get("campaign_assessment") if isinstance(attempt.get("campaign_assessment"), dict) else {}
        campaign_decision = str(assessment.get("decision") or "").strip().lower()
        close_signal = str(assessment.get("close_signal") or "").strip()
        if campaign and assessment:
            problem["campaign_last_assessment"] = {
                "attempt_id": attempt["id"],
                "decision": campaign_decision,
                "close_signal": close_signal[:2000],
                "reason": str(assessment.get("reason") or "")[:2000],
            }

        if outcome == "candidate":
            problem["status"] = "candidate"
            problem["candidate_attempt_id"] = attempt["id"]
            if campaign:
                problem["campaign_state"] = "review"
                problem["campaign_decision"] = "candidate awaiting review"
        elif campaign and outcome != "error":
            completed = discovery_campaign_run_count(problem)
            minimum = max(DISCOVERY_CAMPAIGN_MIN_RUNS, int(problem.get("campaign_min_runs") or 0))
            problem["campaign_min_runs"] = minimum
            if completed < minimum:
                problem["status"] = "active" if outcome == "progress" else "attempted"
                problem["campaign_decision"] = f"continue through run {minimum}"
            else:
                should_continue = (
                    campaign_decision == "continue" and bool(close_signal)
                ) or (
                    not campaign_decision and outcome == "progress" and actionable
                )
                if should_continue:
                    problem["status"] = "active"
                    problem["campaign_state"] = "active"
                    problem["campaign_decision"] = "continue: concrete close signal recorded"
                else:
                    problem["status"] = "parked"
                    problem["campaign_state"] = "hold"
                    problem["campaign_decision"] = "hold after minimum-run review"
        elif outcome == "progress":
            problem["status"] = "active"
        elif outcome in {"failed", "error", "no_progress"}:
            if (
                problem.get("lane") == "easy"
                and outcome != "error"
                and int(problem.get("research_attempt_count") or 0) >= DISCOVERY_CAMPAIGN_MIN_RUNS
                and not actionable
            ):
                problem["status"] = "parked"
            else:
                problem["status"] = "attempted"
        elif outcome in {"verified", "published"}:
            problem["status"] = outcome
        save_problems(problems)


def runtime() -> dict[str, Any]:
    value = read_json(RUNTIME_FILE, {})
    return value if isinstance(value, dict) else {}


def update_runtime(**fields: Any) -> dict[str, Any]:
    with lock("runtime") as acquired:
        if not acquired:
            raise RuntimeError("runtime lock unavailable")
        value = runtime()
        value.update(fields)
        value["updated_at"] = now_iso()
        write_json_atomic(RUNTIME_FILE, value)
        return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
