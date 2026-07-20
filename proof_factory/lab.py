from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from . import store


SCHEMA_VERSION = 1
RUNNER = store.ROOT / "skills" / "computational-researcher" / "scripts" / "run_experiment.py"
ALLOWED_EXECUTABLES = {
    "python", "python3", "pypy3", "julia", "sage", "lean", "lake",
    "z3", "kissat", "cadical", "glucose", "glucose-syrup", "minisat",
    "gap", "gp", "Singular", "dreadnaut", "geng", "showg", "nauty-geng", "nauty-showg",
    "clingo", "cbc",
}
MAX_SEGMENT_SECONDS = 24 * 3600
MAX_SEGMENTS = 7
MAX_MEMORY_MB = 1100


def _workspace(problem_id: str) -> Path:
    return (store.RESEARCH / problem_id / "workspace").resolve()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validate(spec: dict[str, Any], *, source_path: Path | None = None) -> dict[str, Any]:
    problem_id = str(spec.get("problem_id") or "").strip()
    known = {row["id"] for row in store.load_problems()}
    if problem_id not in known:
        raise ValueError(f"unknown problem_id: {problem_id}")
    workspace = _workspace(problem_id)
    workspace.mkdir(parents=True, exist_ok=True)
    if source_path and not _inside(source_path, workspace / "lab-queue"):
        raise ValueError("job spec must originate inside the problem workspace lab-queue")

    command = spec.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(value, str) and value for value in command):
        raise ValueError("command must be a nonempty argv string list")
    executable = command[0]
    if "/" in executable:
        executable_path = (workspace / executable).resolve() if not Path(executable).is_absolute() else Path(executable).resolve()
        if not _inside(executable_path, workspace) or not executable_path.is_file():
            raise ValueError("custom executable must be a file inside the problem workspace")
    elif executable not in ALLOWED_EXECUTABLES:
        raise ValueError(f"executable not allowlisted: {executable}")
    for value in command[1:]:
        candidate = Path(value)
        if ".." in candidate.parts:
            raise ValueError("command arguments may not traverse outside the workspace")
        if candidate.is_absolute() and not _inside(candidate, workspace):
            raise ValueError("absolute command paths must remain inside the problem workspace")

    segment_seconds = int(spec.get("segment_seconds") or 3600)
    memory_mb = int(spec.get("memory_mb") or 512)
    max_segments = int(spec.get("max_segments") or 1)
    segment = int(spec.get("segment") or 1)
    if segment_seconds < 60 or segment_seconds > MAX_SEGMENT_SECONDS:
        raise ValueError(f"segment_seconds must be 60..{MAX_SEGMENT_SECONDS}")
    if memory_mb < 64 or memory_mb > MAX_MEMORY_MB:
        raise ValueError(f"memory_mb must be 64..{MAX_MEMORY_MB}")
    if max_segments < 1 or max_segments > MAX_SEGMENTS or segment < 1 or segment > max_segments:
        raise ValueError(f"segments must fit 1..{MAX_SEGMENTS}")
    checkpoint = str(spec.get("checkpoint_path") or "").strip()
    if max_segments > 1 and not checkpoint:
        raise ValueError("resumable multisegment jobs require checkpoint_path")
    if checkpoint:
        checkpoint_path = (workspace / checkpoint).resolve()
        if not _inside(checkpoint_path, workspace):
            raise ValueError("checkpoint_path must remain inside the problem workspace")

    normalized = {
        "schema_version": SCHEMA_VERSION,
        "id": str(spec.get("id") or f"lab-{problem_id}-{uuid.uuid4().hex[:12]}"),
        "problem_id": problem_id,
        "name": str(spec.get("name") or "").strip()[:200],
        "hypothesis": str(spec.get("hypothesis") or "").strip()[:4000],
        "expected_signal": str(spec.get("expected_signal") or "").strip()[:4000],
        "source_urls": [str(value)[:1000] for value in spec.get("source_urls", []) if str(value).startswith("http")][:20],
        "command": command,
        "seed": int(spec.get("seed") or 0),
        "segment_seconds": segment_seconds,
        "memory_mb": memory_mb,
        "max_segments": max_segments,
        "segment": segment,
        "checkpoint_path": checkpoint,
        "submitted_at": str(spec.get("submitted_at") or store.now_iso()),
    }
    if not normalized["name"] or not normalized["hypothesis"] or not normalized["expected_signal"]:
        raise ValueError("name, hypothesis, and expected_signal are required")
    return normalized


def submit(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate(spec)
    queue = _workspace(normalized["problem_id"]) / "lab-queue"
    queue.mkdir(parents=True, exist_ok=True)
    destination = queue / f"{normalized['id']}.json"
    if destination.exists():
        raise ValueError(f"duplicate lab job: {normalized['id']}")
    store.write_json_atomic(destination, normalized)
    return {"status": "queued", "spec": str(destination), **normalized}


def _append_record(record: dict[str, Any]) -> None:
    ledger = store.STATE / "labs" / "jobs.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def queued_specs() -> list[Path]:
    return sorted(store.RESEARCH.glob("*/workspace/lab-queue/*.json"), key=lambda path: path.stat().st_mtime)


def worker_once() -> dict[str, Any]:
    with store.lock("lab-worker", nonblocking=True) as acquired:
        if not acquired:
            return {"status": "busy"}
        queue = queued_specs()
        if not queue:
            return {"status": "idle"}
        source = queue[0]
        running = source.with_suffix(".running.json")
        os.replace(source, running)
        try:
            raw = json.loads(running.read_text())
            spec = _validate(raw, source_path=source)
            workspace = _workspace(spec["problem_id"])
            output_root = workspace / "lab-runs" / spec["id"] / f"segment-{spec['segment']:02d}"
            output_root.mkdir(parents=True, exist_ok=True)
            command = [
                sys.executable, str(RUNNER),
                "--name", f"{spec['name']} segment {spec['segment']}/{spec['max_segments']}",
                "--hypothesis", spec["hypothesis"], "--expected-signal", spec["expected_signal"],
                "--timeout", str(spec["segment_seconds"]), "--memory-mb", str(spec["memory_mb"]),
                "--seed", str(spec["seed"]), "--output-root", str(output_root),
            ]
            for url in spec["source_urls"]:
                command += ["--source-url", url]
            command += ["--", *spec["command"]]
            env = {key: value for key, value in os.environ.items() if key in {
                "HOME", "PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR",
            }}
            env["PROOF_EXPERIMENT_MAX_SECONDS"] = str(MAX_SEGMENT_SECONDS)
            proc = subprocess.run(
                command, cwd=workspace, env=env, text=True, capture_output=True,
                timeout=spec["segment_seconds"] + 120,
            )
            checkpoint_exists = bool(spec["checkpoint_path"] and (workspace / spec["checkpoint_path"]).is_file())
            record = {
                "recorded_at": store.now_iso(), "job_id": spec["id"], "problem_id": spec["problem_id"],
                "segment": spec["segment"], "max_segments": spec["max_segments"],
                "returncode": proc.returncode, "checkpoint_exists": checkpoint_exists,
                "runner_result": proc.stdout[-12000:], "runner_error": proc.stderr[-4000:],
            }
            _append_record(record)
            should_resume = proc.returncode == 124 and checkpoint_exists and spec["segment"] < spec["max_segments"]
            if should_resume:
                spec["segment"] += 1
                store.write_json_atomic(source, spec)
                status = "requeued"
            else:
                archive = workspace / "lab-archive"
                archive.mkdir(parents=True, exist_ok=True)
                store.write_json_atomic(archive / f"{spec['id']}.json", {**spec, "final_record": record})
                status = "completed" if proc.returncode == 0 else "stopped"
            return {"status": status, **record}
        except Exception as exc:
            record = {
                "recorded_at": store.now_iso(), "job_id": running.stem, "status": "invalid",
                "error": f"{type(exc).__name__}: {exc}",
            }
            _append_record(record)
            rejected = running.parent.parent / "lab-rejected"
            rejected.mkdir(parents=True, exist_ok=True)
            shutil.move(str(running), str(rejected / running.name))
            return record
        finally:
            running.unlink(missing_ok=True)


def status() -> dict[str, Any]:
    ledger = store.STATE / "labs" / "jobs.jsonl"
    records = []
    if ledger.exists():
        for line in ledger.read_text().splitlines()[-50:]:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return {
        "queued": [str(path) for path in queued_specs()],
        "recent_records": records,
        "limits": {
            "allowed_executables": sorted(ALLOWED_EXECUTABLES),
            "max_segment_seconds": MAX_SEGMENT_SECONDS,
            "max_segments": MAX_SEGMENTS,
            "max_memory_mb": MAX_MEMORY_MB,
            "shell": False,
        },
    }
