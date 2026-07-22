from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import config, store


SCHEMA_VERSION = 1
def _github_owner() -> str:
    return config.get_text("PROOF_REPO_GITHUB_OWNER", "ctkrug")


def _git_author_name() -> str:
    return config.get_text("PROOF_REPO_GIT_NAME", "ctkrug")


def _git_author_email() -> str:
    return config.get_text("PROOF_REPO_GIT_EMAIL", "ctkrug4501@gmail.com")


def _max_tracked_file_bytes() -> int:
    return config.get_int(
        "PROOF_REPO_MAX_FILE_BYTES", 50 * 1024 * 1024, minimum=1024, maximum=10 * 1024**3,
    )
LEGACY_GITIGNORE = """# Reproducible research belongs in Git; local environments and caches do not.
.DS_Store
.venv/
venv/
__pycache__/
*.pyc
.mypy_cache/
.pytest_cache/
node_modules/
*.tmp
"""
GITIGNORE = """# proof-factory:start
# Reproducible research belongs in Git; local environments, caches, and in-flight queue names do not.
.DS_Store
.venv/
venv/
__pycache__/
*.pyc
.mypy_cache/
.pytest_cache/
node_modules/
*.tmp
lab-queue/*.running.json
# proof-factory:end
"""


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not cleaned:
        raise ValueError("problem id cannot produce an empty repository slug")
    return cleaned[:80]


def repo_name(problem_id: str) -> str:
    return f"proofs-{_slug(problem_id)}"


def workspace(problem_id: str) -> Path:
    return (store.RESEARCH / problem_id / "workspace").resolve()


def _problem(problem_id: str) -> dict[str, Any]:
    problem = next((row for row in store.load_problems() if row["id"] == problem_id), None)
    if not problem:
        raise ValueError(f"unknown problem: {problem_id}")
    return problem


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], text=True, capture_output=True, env=env, timeout=300,
    )
    if check and proc.returncode != 0:
        detail = (proc.stdout + proc.stderr).strip()[-3000:]
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {detail}")
    return proc


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def _ensure_gitignore(path: Path) -> None:
    if not path.exists() or path.read_text() == LEGACY_GITIGNORE:
        path.write_text(GITIGNORE)
        return
    kept: list[str] = []
    in_managed_block = False
    for line in path.read_text().splitlines():
        if line == "# proof-factory:start":
            in_managed_block = True
            continue
        if line == "# proof-factory:end":
            in_managed_block = False
            continue
        if not in_managed_block:
            kept.append(line)
    path.write_text("\n".join([*kept, GITIGNORE.rstrip()]).lstrip("\n") + "\n")


def _readme(problem: dict[str, Any]) -> str:
    title = str(problem.get("title") or problem["id"])
    statement = str(problem.get("statement") or "Statement awaiting baseline review.")
    source = str(problem.get("source_url") or "")
    return f"""# {title}

This is the public, problem-scoped research repository maintained by Charlie Krug with AI and
computational assistance disclosed in each attempt record.

## Problem

{statement}

Authoritative source: {source}

## Repository contract

- `records/attempts/` contains immutable structured attempt records and readable write-ups.
- `records/research-state.json` is the latest compact memory of facts, exclusions, leads, and strategy state.
- `records/labs/` records submitted and completed simulation-lab segments.
- Code, proof files, checkers, notes, and bounded-search artifacts live beside those records.
- Generated files too large for ordinary Git are hash-manifested in `.proof-repository/LARGE_ARTIFACTS.json`.
- A commit records work; it does not establish correctness, novelty, or peer review.

AI assistance and computational tools are disclosed in each attempt record. Positive findings still
require independent verification, a novelty check, Charlie's approval, and external validation.
"""


def _metadata(problem: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "problem_id": problem["id"],
        "title": problem.get("title"),
        "source_url": problem.get("source_url"),
        "lane": problem.get("lane"),
        "github_owner": _github_owner(),
        "github_repository": repo_name(problem["id"]),
        "visibility_policy": "public-research-history",
        "canonical_engine": "https://github.com/ctkrug/proofs",
    }


def _large_artifacts(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    excluded_parts = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    for path in sorted(repo.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(repo)
        if any(part in excluded_parts for part in relative.parts):
            continue
        size = path.stat().st_size
        if size <= _max_tracked_file_bytes():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        rows.append({"path": relative.as_posix(), "bytes": size, "sha256": digest.hexdigest()})
    return rows


def _exclude_large_artifacts(repo: Path) -> None:
    rows = _large_artifacts(repo)
    manifest = repo / ".proof-repository" / "LARGE_ARTIFACTS.json"
    store.write_json_atomic(manifest, {
        "schema_version": SCHEMA_VERSION,
        "max_tracked_file_bytes": _max_tracked_file_bytes(),
        "files": rows,
        "note": "Files remain on the research host; Git records their path, size, and SHA-256 instead of the bytes.",
    })
    exclude = repo / ".git" / "info" / "exclude"
    existing: list[str] = []
    inside_generated_block = False
    for line in exclude.read_text().splitlines():
        if line == "# proof-large:start":
            inside_generated_block = True
            continue
        if line == "# proof-large:end":
            inside_generated_block = False
            continue
        if not inside_generated_block:
            existing.append(line)
    generated = ["# proof-large:start", *[f"/{row['path']}" for row in rows], "# proof-large:end"]
    exclude.write_text("\n".join(existing + generated).rstrip() + "\n")
    for row in rows:
        _git(repo, "rm", "--cached", "--ignore-unmatch", "--", row["path"], check=False)


def _checkpoint_unlocked(repo: Path, message: str) -> str:
    _exclude_large_artifacts(repo)
    _git(repo, "add", "--all")
    staged = _git(repo, "diff", "--cached", "--quiet", check=False)
    if staged.returncode == 1:
        _git(repo, "commit", "-m", message[:240])
    elif staged.returncode != 0:
        raise RuntimeError(f"could not inspect staged changes in {repo}")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return head


def _ensure_unlocked(problem: dict[str, Any]) -> tuple[Path, str]:
    repo = workspace(problem["id"])
    repo.mkdir(parents=True, exist_ok=True)
    created = not (repo / ".git").is_dir()
    if created:
        proc = subprocess.run(
            ["git", "init", "--initial-branch=main", str(repo)], text=True, capture_output=True, timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git init failed for {problem['id']}: {(proc.stdout + proc.stderr)[-2000:]}")
    _git(repo, "config", "user.name", _git_author_name())
    _git(repo, "config", "user.email", _git_author_email())
    _ensure_gitignore(repo / ".gitignore")
    _write_if_missing(repo / "README.md", _readme(problem))
    store.write_json_atomic(repo / ".proof-repository" / "metadata.json", _metadata(problem))
    head_result = _git(repo, "rev-parse", "HEAD", check=False)
    if created or head_result.returncode != 0:
        head = _checkpoint_unlocked(repo, f"Initialize research repository for {problem['id']}")
    else:
        head = head_result.stdout.strip()
    return repo, head


def ensure(problem: dict[str, Any]) -> dict[str, Any]:
    lock_name = f"repo-{hashlib.sha256(problem['id'].encode()).hexdigest()[:16]}"
    with store.lock(lock_name) as acquired:
        if not acquired:
            raise RuntimeError(f"repository lock unavailable: {problem['id']}")
        repo, head = _ensure_unlocked(problem)
    return {"problem_id": problem["id"], "path": str(repo), "commit": head}


def initialize_all() -> dict[str, Any]:
    initialized = []
    for problem in store.load_problems():
        initialized.append(ensure(problem))
    return {"initialized": initialized, "count": len(initialized)}


def backfill() -> dict[str, Any]:
    attempts_by_problem: dict[str, list[dict[str, Any]]] = {}
    for attempt in store.load_attempts():
        attempts_by_problem.setdefault(str(attempt.get("problem_id")), []).append(attempt)
    rows = []
    for raw_problem in store.load_problems():
        problem = _problem(raw_problem["id"])
        lock_name = f"repo-{hashlib.sha256(problem['id'].encode()).hexdigest()[:16]}"
        with store.lock(lock_name) as acquired:
            if not acquired:
                raise RuntimeError(f"repository lock unavailable: {problem['id']}")
            repo, _ = _ensure_unlocked(problem)
            attempts = attempts_by_problem.get(problem["id"], [])
            records = repo / "records" / "attempts"
            for attempt in attempts:
                attempt_id = _slug(str(attempt["id"]))
                store.write_json_atomic(records / f"{attempt_id}.json", attempt)
                (records / f"{attempt_id}.md").write_text(_attempt_markdown(problem, attempt))
            _refresh_problem_projection(repo, problem)
            head = _checkpoint_unlocked(
                repo, f"Backfill {len(attempts)} historical Proof Factory attempt record(s)",
            )
        rows.append({"problem_id": problem["id"], "attempts": len(attempts), "commit": head})
    return {"repositories": rows, "count": len(rows), "attempts": sum(row["attempts"] for row in rows)}


def _attempt_markdown(problem: dict[str, Any], attempt: dict[str, Any]) -> str:
    def bullets(values: Any) -> str:
        rows = [f"- {value}" for value in values or []]
        return "\n".join(rows) if rows else "- None recorded."

    return f"""# Research attempt {attempt['id']}

- Problem: {problem.get('title') or problem['id']}
- Phase: {attempt.get('phase', 'technical')}
- Outcome: {attempt.get('outcome')}
- Started: {attempt.get('started_at')}
- Finished: {attempt.get('finished_at')}
- Orchestration: {attempt.get('orchestration', {}).get('architecture', 'unspecified')}

## Approach

{attempt.get('approach') or 'Not recorded.'}

## Summary

{attempt.get('summary') or 'Not recorded.'}

## Claims

{bullets(attempt.get('claims'))}

## Evidence

{bullets(attempt.get('evidence'))}

## Established facts

```json
{json.dumps(attempt.get('established_facts') or [], indent=2, ensure_ascii=False)}
```

## Scoped exclusions

```json
{json.dumps(attempt.get('ruled_out') or [], indent=2, ensure_ascii=False)}
```

## Open leads and next steps

```json
{json.dumps(attempt.get('open_leads') or [], indent=2, ensure_ascii=False)}
```

{bullets(attempt.get('next_steps'))}

## Sources

{bullets(attempt.get('citations'))}

## Tool disclosure

{attempt.get('tool_disclosure') or 'Not recorded.'}

This commit is a research record, not a correctness or novelty claim.
"""


def _refresh_problem_projection(repo: Path, problem: dict[str, Any]) -> None:
    records = repo / "records"
    store.write_json_atomic(records / "problem.json", problem)
    state_source = store.DATA / "research_states" / f"{problem['id']}.json"
    if state_source.is_file():
        shutil.copyfile(state_source, records / "research-state.json")
    dossier = store.RESEARCH / problem["id"] / "DOSSIER.md"
    if dossier.is_file():
        (repo / "docs").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dossier, repo / "docs" / "DOSSIER.md")
    problem_root = store.RESEARCH / problem["id"]
    reference = repo / "reference"
    for source in problem_root.iterdir() if problem_root.is_dir() else []:
        if source.name in {"workspace", "DOSSIER.md"}:
            continue
        destination = reference / source.name
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        elif source.is_file() and not source.is_symlink():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)


def record_attempt(problem: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    problem = _problem(problem["id"])
    lock_name = f"repo-{hashlib.sha256(problem['id'].encode()).hexdigest()[:16]}"
    with store.lock(lock_name) as acquired:
        if not acquired:
            raise RuntimeError(f"repository lock unavailable: {problem['id']}")
        repo, _ = _ensure_unlocked(problem)
        attempt_id = _slug(str(attempt["id"]))
        records = repo / "records" / "attempts"
        store.write_json_atomic(records / f"{attempt_id}.json", attempt)
        (records / f"{attempt_id}.md").write_text(_attempt_markdown(problem, attempt))
        _refresh_problem_projection(repo, problem)
        head = _checkpoint_unlocked(
            repo, f"Record {attempt.get('phase', 'technical')} attempt {attempt['id']} ({attempt.get('outcome')})",
        )
    return {"problem_id": problem["id"], "attempt_id": attempt["id"], "commit": head}


def record_lab(problem_id: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    problem = _problem(problem_id)
    lock_name = f"repo-{hashlib.sha256(problem_id.encode()).hexdigest()[:16]}"
    with store.lock(lock_name) as acquired:
        if not acquired:
            raise RuntimeError(f"repository lock unavailable: {problem_id}")
        repo, _ = _ensure_unlocked(problem)
        job_id = _slug(str(payload.get("job_id") or payload.get("id") or "lab-job"))
        segment = int(payload.get("segment") or 0)
        suffix = f"-segment-{segment:02d}" if segment else ""
        destination = repo / "records" / "labs" / f"{job_id}-{_slug(event)}{suffix}.json"
        store.write_json_atomic(destination, {"event": event, **payload})
        _refresh_problem_projection(repo, problem)
        head = _checkpoint_unlocked(repo, f"Record lab {event}: {job_id}{suffix}")
    return {"problem_id": problem_id, "job_id": job_id, "event": event, "commit": head}


def queue_lab_projection(problem_id: str, event: str, payload: dict[str, Any], *, error: str) -> dict[str, Any]:
    """Durably queue a failed mutable repository projection for repo-sync retry."""
    record = {
        "schema_version": 1,
        "id": hashlib.sha256(json.dumps(
            [problem_id, event, payload], sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest(),
        "problem_id": problem_id,
        "event": event,
        "payload": payload,
        "error": str(error)[:4000],
        "queued_at": store.now_iso(),
    }
    queue = store.STATE / "repository_projection_queue"
    queue.mkdir(parents=True, exist_ok=True)
    with store.lock("repository-projection-queue") as acquired:
        if not acquired:
            raise RuntimeError("repository projection queue lock unavailable")
        destination = queue / f"{record['id']}.json"
        if not destination.exists():
            store.write_json_atomic(destination, record)
    return record


def retry_lab_projections() -> dict[str, Any]:
    queue = store.STATE / "repository_projection_queue"
    legacy = store.STATE / "repository_projection_queue.jsonl"
    if not queue.is_dir() and not legacy.is_file():
        return {"retried": 0, "remaining": 0, "errors": []}
    queue.mkdir(parents=True, exist_ok=True)
    with store.lock("repository-projection-queue") as acquired:
        if not acquired:
            return {"retried": 0, "remaining": 0, "errors": ["projection queue lock unavailable"]}
        pending: list[tuple[Path, dict[str, Any]]] = []
        errors: list[str] = []
        if legacy.is_file():
            legacy_valid = True
            for line_number, line in enumerate(legacy.read_text().splitlines(), 1):
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict) or not str(value.get("id") or ""):
                        raise ValueError("entry is not an identified object")
                    destination = queue / f"{value['id']}.json"
                    if not destination.exists():
                        store.write_json_atomic(destination, value)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    legacy_valid = False
                    errors.append(
                        f"malformed legacy projection retained: line {line_number}: {type(exc).__name__}: {exc}"
                    )
            # Remove the superseded aggregate only after every entry is safely
            # represented as its own atomic receipt. Any malformed line keeps
            # the original byte stream intact for operator recovery.
            if legacy_valid:
                legacy.unlink()
        for path in sorted(queue.glob("*.json")):
            try:
                value = json.loads(path.read_text())
                if isinstance(value, dict):
                    pending.append((path, value))
                else:
                    errors.append(f"malformed projection retained: {path.name}: not an object")
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"malformed projection retained: {path.name}: {type(exc).__name__}: {exc}")
                continue
        retried = 0
        for path, row in pending:
            try:
                record_lab(str(row["problem_id"]), str(row["event"]), dict(row["payload"]))
                retried += 1
                path.unlink()
            except Exception as exc:
                errors.append(f"{path.name}: {type(exc).__name__}: {exc}"[:4000])
        remaining = len(list(queue.glob("*.json"))) + int(legacy.is_file())
    return {"retried": retried, "remaining": remaining, "errors": errors}


def _gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["gh", *args], text=True, capture_output=True, timeout=300)
    if check and proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {(proc.stdout + proc.stderr).strip()[-3000:]}")
    return proc


def _same_github_remote(left: str, right: str) -> bool:
    """Treat GitHub's web URL and Git's conventional .git form as the same remote."""
    return left.strip().removesuffix(".git") == right.strip().removesuffix(".git")


def _sync_problem(problem: dict[str, Any]) -> dict[str, Any]:
    repo_info = ensure(problem)
    repo = Path(repo_info["path"])
    full_name = f"{_github_owner()}/{repo_name(problem['id'])}"
    view = _gh("repo", "view", full_name, "--json", "url,visibility", check=False)
    created = False
    if view.returncode != 0:
        _gh(
            "repo", "create", full_name, "--public",
            "--description", f"Transparent Proof Factory research for {problem.get('title') or problem['id']}",
        )
        created = True
        view = _gh("repo", "view", full_name, "--json", "url,visibility")
    remote = json.loads(view.stdout)
    if str(remote.get("visibility", "")).upper() != "PUBLIC":
        _gh("repo", "edit", full_name, "--visibility", "public", "--accept-visibility-change-consequences")
        view = _gh("repo", "view", full_name, "--json", "url,visibility")
        remote = json.loads(view.stdout)
    if str(remote.get("visibility", "")).upper() != "PUBLIC":
        raise RuntimeError(f"repository did not become public: {full_name}")
    url = str(remote["url"])
    existing = _git(repo, "remote", "get-url", "origin", check=False)
    if existing.returncode == 0 and not _same_github_remote(existing.stdout, url):
        raise RuntimeError(f"origin already points elsewhere for {problem['id']}: {existing.stdout.strip()}")
    if existing.returncode != 0:
        _git(repo, "remote", "add", "origin", url)
    _git(repo, "push", "--set-upstream", "origin", "main")
    return {
        "problem_id": problem["id"], "repository": full_name, "url": url, "visibility": "PUBLIC",
        "created": created, "commit": _git(repo, "rev-parse", "HEAD").stdout.strip(),
    }


def sync_all() -> dict[str, Any]:
    projection_retry = retry_lab_projections()
    synced: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for problem in store.load_problems():
        try:
            synced.append(_sync_problem(problem))
        except Exception as exc:
            errors.append({"problem_id": problem["id"], "error": f"{type(exc).__name__}: {exc}"})
    registry = {
        "schema_version": SCHEMA_VERSION,
        "visibility_policy": "public-research-history",
        "repositories": [{key: value for key, value in row.items() if key != "created"} for row in synced],
        "errors": errors,
        "projection_retry": projection_retry,
    }
    store.write_json_atomic(store.DATA / "problem_repositories.json", registry)
    return {
        "synced": len(synced), "errors": errors, "repositories": synced,
        "projection_retry": projection_retry,
    }


def status() -> dict[str, Any]:
    rows = []
    for problem in store.load_problems():
        repo = workspace(problem["id"])
        initialized = (repo / ".git").is_dir()
        remote = _git(repo, "remote", "get-url", "origin", check=False).stdout.strip() if initialized else ""
        head = _git(repo, "rev-parse", "HEAD", check=False).stdout.strip() if initialized else ""
        rows.append({
            "problem_id": problem["id"], "initialized": initialized, "commit": head,
            "remote": remote, "public_expected": True,
        })
    return {
        "problems": len(rows),
        "initialized": sum(row["initialized"] for row in rows),
        "remotes": sum(bool(row["remote"]) for row in rows),
        "repositories": rows,
    }
