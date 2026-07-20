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

        problem["attempt_count"] = int(problem.get("attempt_count") or 0) + 1
        problem["last_attempt_at"] = attempt["finished_at"]
        outcome = attempt["outcome"]
        if outcome != "error":
            problem["research_attempt_count"] = int(problem.get("research_attempt_count") or 0) + 1
        if outcome == "candidate":
            problem["status"] = "candidate"
            problem["candidate_attempt_id"] = attempt["id"]
        elif outcome == "progress":
            problem["status"] = "active"
        elif outcome in {"failed", "error", "no_progress"}:
            if (
                problem.get("lane") == "easy"
                and outcome != "error"
                and int(problem.get("research_attempt_count") or 0) >= 3
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
