from __future__ import annotations

import hashlib
import json
import math
import os
import re
import signal
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from . import capacity, events, repositories, schemas, store


SCHEMA_VERSION = 2
_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RUNNER = store.ROOT / "skills" / "computational-researcher" / "scripts" / "run_experiment.py"
ALLOWED_EXECUTABLES = {
    "python", "python3", "pypy3", "julia", "sage", "lean", "lake",
    "z3", "kissat", "cadical", "glucose", "glucose-syrup", "minisat",
    "gap", "gp", "Singular", "dreadnaut", "geng", "showg", "nauty-geng", "nauty-showg",
    "clingo", "cbc",
}
MAX_SEGMENT_SECONDS = 24 * 3600
MAX_DECLARED_SEGMENTS = 100_000
# The experiment harness applies this as RLIMIT_AS (virtual address space), not
# resident memory. Lean maps more than 1.1 GiB while staying below the lab
# service cgroup, so keep physical containment in systemd and permit a 16 GiB
# virtual-address envelope here. Measured 4 and 8 GiB envelopes still failed
# while mapping Mathlib despite bounded resident use.
MAX_MEMORY_MB = 16384
LIFECYCLE_STATES = {
    "queued", "running", "checkpointed", "completed_awaiting_review",
    "validated", "stopped_with_reason",
}
REVIEW_DECISIONS = {"continue", "validate", "promote", "redirect"}
VALIDATION_RECEIPT_SCHEMA_VERSION = 1
EFFICIENCY_FIELDS = {
    "naive_cost", "opportunities_considered", "chosen_reductions",
    "expected_throughput_gain", "soundness_basis", "remains_uncompressed",
}
SPEC_FIELDS = (
    "schema_version", "id", "problem_id", "name", "hypothesis", "expected_signal", "decision_value",
    "efficiency_design", "source_urls", "command", "seed", "segment_seconds", "memory_mb", "max_segments",
    "segment", "pilot_segments", "review_every_segments", "checkpoint_path", "progress_path",
    "continuation_thresholds", "submitted_at", "workspace_git_commit", "input_sha256",
)
OPTIONAL_SPEC_FIELDS = ("mutable_argv_paths", "mutable_argv_initial_sha256", "progress_baseline")


def _workspace(problem_id: str) -> Path:
    return (store.RESEARCH / problem_id / "workspace").resolve()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _state_root() -> Path:
    return store.STATE / "labs" / "jobs"


def _state_path(job_id: str) -> Path:
    if not _SAFE_JOB_ID.fullmatch(job_id):
        raise schemas.SchemaError(f"invalid lab job id: {job_id!r}")
    return _state_root() / f"{job_id}.json"


def _read_state(job_id: str) -> dict[str, Any]:
    path = _state_path(job_id)
    if not path.exists():
        raise ValueError(f"unknown lab job: {job_id}")
    value = schemas.load_json_object(path, kind="lab persisted state")
    schemas.require_current_version(value, kind="lab persisted state", current=SCHEMA_VERSION)
    schemas.require_fields(
        value,
        frozenset((*SPEC_FIELDS, "spec_sha256", "status", "segments", "last_reviewed_segment", "created_at")),
        kind="lab persisted state",
    )
    if value.get("id") != job_id:
        raise schemas.SchemaError(
            f"lab persisted state id {value.get('id')!r} does not match filename job {job_id!r}"
        )
    if not _SAFE_JOB_ID.fullmatch(job_id):
        raise schemas.SchemaError(f"lab persisted state has invalid job id: {job_id!r}")
    if value.get("status") not in LIFECYCLE_STATES:
        raise schemas.SchemaError(f"lab persisted state has invalid lifecycle status: {value.get('status')!r}")
    schemas.require_type(value, "segments", list, kind="lab persisted state")
    _validate_input_hashes(value.get("input_sha256"), kind="lab persisted state")
    if "mutable_argv_paths" in value or "mutable_argv_initial_sha256" in value:
        if "mutable_argv_paths" not in value or "mutable_argv_initial_sha256" not in value:
            raise schemas.SchemaError("lab persisted state must carry both mutable argv fields")
        mutable_paths = _normalize_mutable_argv_paths(
            value["mutable_argv_paths"],
            workspace=_workspace(str(value.get("problem_id") or "")),
            command=value.get("command", []),
        )
        if mutable_paths != value["mutable_argv_paths"]:
            raise schemas.SchemaError("lab persisted state.mutable_argv_paths is not canonical")
        _validate_mutable_initial_hashes(
            value["mutable_argv_initial_sha256"], mutable_paths, kind="lab persisted state",
        )
    expected = str(value.get("spec_sha256") or "")
    if len(expected) != 64 or expected != _spec_sha256(value):
        raise schemas.SchemaError("lab persisted state spec_sha256 mismatch")
    return value


def _write_state(state: dict[str, Any]) -> None:
    state["updated_at"] = store.now_iso()
    _state_root().mkdir(parents=True, exist_ok=True)
    store.write_json_atomic(_state_path(str(state["id"])), state)


def _git_commit(workspace: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workspace, text=True, capture_output=True, timeout=20,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unversioned"


def _git_contains(workspace: Path, revision: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, "HEAD"], cwd=workspace,
        text=True, capture_output=True, timeout=20,
    )
    return proc.returncode == 0


def _input_identity(
    workspace: Path,
    command: list[str],
    *,
    excluded: frozenset[str] = frozenset(),
) -> dict[str, str]:
    identities: dict[str, str] = {}
    for raw in command:
        if len(raw) > 512 or any(char in raw for char in "\n\r\0"):
            continue
        candidate = Path(raw)
        path = candidate if candidate.is_absolute() else workspace / candidate
        try:
            resolved = path.resolve()
        except OSError:
            continue
        try:
            if _inside(resolved, workspace) and resolved.is_file() and not resolved.is_symlink():
                relative = resolved.relative_to(workspace).as_posix()
                if relative not in excluded:
                    identities[relative] = _sha256(resolved)
        except OSError:
            continue
    return dict(sorted(identities.items()))


def _spec_sha256(value: dict[str, Any]) -> str:
    identity = {key: value.get(key) for key in SPEC_FIELDS}
    # Lab schema v2 predates resumable-job mutable argv declarations. Preserve
    # the digest of existing v2 records while binding both opt-in fields for
    # every new job that uses the feature.
    for key in OPTIONAL_SPEC_FIELDS:
        if key in value:
            identity[key] = value[key]
    identity.pop("segment", None)
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _validate_input_hashes(value: Any, *, kind: str) -> None:
    if not isinstance(value, dict):
        raise schemas.SchemaError(f"{kind}.input_sha256 must be dict")
    for relative, digest in value.items():
        candidate = Path(relative) if isinstance(relative, str) else Path("..")
        if (
            not isinstance(relative, str) or not relative or candidate.is_absolute()
            or ".." in candidate.parts or candidate.as_posix() != relative
        ):
            raise schemas.SchemaError(f"{kind}.input_sha256 has invalid relative path: {relative!r}")
        if (
            not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise schemas.SchemaError(f"{kind}.input_sha256[{relative!r}] must be lowercase SHA-256")


def _normalize_mutable_argv_paths(
    value: Any,
    *,
    workspace: Path,
    command: list[str],
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("mutable_argv_paths must be a list")
    command_paths: set[str] = set()
    for raw in command[1:]:
        if len(raw) > 512 or any(char in raw for char in "\n\r\0"):
            continue
        candidate = Path(raw)
        path = candidate if candidate.is_absolute() else workspace / candidate
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if _inside(resolved, workspace):
            command_paths.add(resolved.relative_to(workspace).as_posix())

    normalized: list[str] = []
    for raw in value:
        if not isinstance(raw, str) or not raw or len(raw) > 512 or any(char in raw for char in "\n\r\0"):
            raise ValueError("mutable_argv_paths entries must be nonempty path strings")
        candidate = Path(raw)
        if candidate.is_absolute() or ".." in candidate.parts or candidate.as_posix() != raw:
            raise ValueError(f"mutable argv path must be canonical and workspace-relative: {raw!r}")
        path = workspace / candidate
        resolved = path.resolve()
        if not _inside(resolved, workspace):
            raise ValueError(f"mutable argv path must remain inside the workspace: {raw!r}")
        relative = resolved.relative_to(workspace).as_posix()
        if relative != raw:
            raise ValueError(f"mutable argv path must resolve without aliases: {raw!r}")
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f"mutable argv path must be absent or a regular non-symlink file: {raw!r}")
        if relative not in command_paths:
            raise ValueError(f"mutable argv path is not an exact command argument: {raw!r}")
        if relative in normalized:
            raise ValueError(f"duplicate mutable argv path: {raw!r}")
        normalized.append(relative)
    return sorted(normalized)


def _mutable_identity(workspace: Path, paths: list[str]) -> dict[str, str]:
    identities: dict[str, str] = {}
    workspace_resolved = workspace.resolve()
    for relative in paths:
        path = workspace_resolved / relative
        resolved = path.resolve()
        if (
            not _inside(resolved, workspace_resolved)
            or resolved.relative_to(workspace_resolved).as_posix() != relative
            or path.is_symlink()
            or (path.exists() and not path.is_file())
        ):
            raise ValueError(f"mutable argv path is no longer a regular file: {relative}")
        identities[relative] = _sha256(path) if path.is_file() else "absent"
    return identities


def _validate_mutable_initial_hashes(value: Any, paths: list[str], *, kind: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != set(paths):
        raise schemas.SchemaError(f"{kind}.mutable_argv_initial_sha256 must cover exactly mutable_argv_paths")
    for relative, digest in value.items():
        if digest != "absent" and (
            not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise schemas.SchemaError(
                f"{kind}.mutable_argv_initial_sha256[{relative!r}] must be lowercase SHA-256 or 'absent'"
            )
    return dict(sorted(value.items()))


def _validate_progress_baseline(value: Any, *, kind: str) -> dict[str, float | int]:
    if not isinstance(value, dict):
        raise schemas.SchemaError(f"{kind}.progress_baseline must be an object")
    completed = value.get("completed_units")
    artifact_bytes = value.get("reported_artifact_bytes")
    if (
        isinstance(completed, bool) or not isinstance(completed, (int, float))
        or not math.isfinite(float(completed)) or float(completed) < 0
    ):
        raise schemas.SchemaError(f"{kind}.progress_baseline.completed_units must be finite and nonnegative")
    if isinstance(artifact_bytes, bool) or not isinstance(artifact_bytes, int) or artifact_bytes < 0:
        raise schemas.SchemaError(f"{kind}.progress_baseline.reported_artifact_bytes must be a nonnegative int")
    return {
        "completed_units": float(completed),
        "reported_artifact_bytes": artifact_bytes,
        "artifact_bytes": artifact_bytes,
    }


def _capture_progress_baseline(workspace: Path, relative: str) -> dict[str, float | int]:
    if not relative:
        return {"completed_units": 0.0, "reported_artifact_bytes": 0, "artifact_bytes": 0}
    path = workspace / relative
    if not path.is_file():
        return {"completed_units": 0.0, "reported_artifact_bytes": 0, "artifact_bytes": 0}
    value = schemas.load_json_object(path, kind="lab initial progress record")
    return _validate_progress_baseline({
        "completed_units": value.get("completed_units"),
        "reported_artifact_bytes": value.get("artifact_bytes"),
    }, kind="lab spec")


def _validate_efficiency(value: Any, *, substantial: bool) -> dict[str, Any]:
    if not substantial and not value:
        return {}
    if not isinstance(value, dict):
        if substantial:
            raise ValueError("substantial lab jobs require efficiency_design")
        return {}
    missing = sorted(field for field in EFFICIENCY_FIELDS if not value.get(field))
    if missing:
        raise ValueError(f"efficiency_design missing: {', '.join(missing)}")
    opportunities = value.get("opportunities_considered")
    if not isinstance(opportunities, list) or len(opportunities) < 3:
        raise ValueError("efficiency_design must document at least three compression opportunities")
    return {
        "naive_cost": str(value["naive_cost"])[:4000],
        "opportunities_considered": [str(item)[:1000] for item in opportunities][:30],
        "chosen_reductions": str(value["chosen_reductions"])[:4000],
        "expected_throughput_gain": str(value["expected_throughput_gain"])[:2000],
        "soundness_basis": str(value["soundness_basis"])[:4000],
        "remains_uncompressed": str(value["remains_uncompressed"])[:4000],
    }


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

    mutable_paths = _normalize_mutable_argv_paths(
        spec.get("mutable_argv_paths"), workspace=workspace, command=command,
    )
    mutable_set = frozenset(mutable_paths)
    explicit_input_hashes = spec.get("input_sha256")
    automatic_input_hashes = _input_identity(workspace, command, excluded=mutable_set)
    mutable_initial: dict[str, str] = {}
    progress_baseline: dict[str, float | int] = {}
    if mutable_paths:
        if not isinstance(explicit_input_hashes, dict):
            raise ValueError(
                "mutable argv declarations require explicit input_sha256 hashes for protected code and corpus inputs"
            )
        _validate_input_hashes(explicit_input_hashes, kind="lab spec")
        overlap = sorted(mutable_set.intersection(explicit_input_hashes))
        if overlap:
            raise ValueError(f"paths cannot be both mutable and immutable inputs: {', '.join(overlap)}")
        missing_or_wrong = sorted(
            relative for relative, digest in automatic_input_hashes.items()
            if explicit_input_hashes.get(relative) != digest
        )
        if missing_or_wrong:
            raise ValueError(
                "explicit input_sha256 must bind every existing non-mutable argv file: "
                + ", ".join(missing_or_wrong)
            )
        # Extra hashes are encouraged for inputs reached through a config or
        # manifest rather than passed directly on argv. Verify them now as well
        # as before every segment so a submission cannot contain invented pins.
        for relative, digest in explicit_input_hashes.items():
            unresolved = workspace / relative
            path = unresolved.resolve()
            if (
                not _inside(path, workspace) or not path.is_file() or unresolved.is_symlink()
                or _sha256(path) != digest
            ):
                raise ValueError(f"explicit immutable input hash does not match a regular workspace file: {relative}")
        if source_path is None:
            if "mutable_argv_initial_sha256" in spec:
                raise ValueError("mutable_argv_initial_sha256 is engine-generated and may not be supplied")
            if "progress_baseline" in spec:
                raise ValueError("progress_baseline is engine-generated and may not be supplied")
            mutable_initial = _mutable_identity(workspace, mutable_paths)
            progress_baseline = _capture_progress_baseline(
                workspace, str(spec.get("progress_path") or "").strip(),
            )
        else:
            mutable_initial = _validate_mutable_initial_hashes(
                spec.get("mutable_argv_initial_sha256"), mutable_paths, kind="lab persisted spec",
            )
            progress_baseline = _validate_progress_baseline(spec.get("progress_baseline"), kind="lab persisted spec")
    elif "mutable_argv_initial_sha256" in spec or "progress_baseline" in spec:
        raise ValueError("mutable argv initial state requires mutable_argv_paths")

    segment_seconds = int(spec.get("segment_seconds") or 3600)
    memory_mb = int(spec.get("memory_mb") or 512)
    max_segments = int(spec.get("max_segments") if spec.get("max_segments") is not None else 1)
    segment = int(spec.get("segment") or 1)
    review_every = int(spec.get("review_every_segments") or 1)
    pilot_segments = int(spec.get("pilot_segments") or 1)
    if segment_seconds < 60 or segment_seconds > MAX_SEGMENT_SECONDS:
        raise ValueError(f"segment_seconds must be 60..{MAX_SEGMENT_SECONDS}")
    if memory_mb < 64 or memory_mb > MAX_MEMORY_MB:
        raise ValueError(f"memory_mb must be 64..{MAX_MEMORY_MB}")
    if max_segments < 0 or max_segments > MAX_DECLARED_SEGMENTS:
        raise ValueError(f"max_segments must be 0 (open continuation) or <= {MAX_DECLARED_SEGMENTS}")
    if segment < 1 or (max_segments and segment > max_segments):
        raise ValueError("segment is outside the declared tranche")
    if review_every < 1 or pilot_segments < 1:
        raise ValueError("pilot_segments and review_every_segments must be positive")

    checkpoint = str(spec.get("checkpoint_path") or "").strip()
    progress_path = str(spec.get("progress_path") or "").strip()
    substantial = max_segments == 0 or max_segments > 1 or segment_seconds > 3600
    if substantial and (not checkpoint or not progress_path):
        raise ValueError("substantial jobs require checkpoint_path and progress_path")
    for label, relative in (("checkpoint_path", checkpoint), ("progress_path", progress_path)):
        if relative:
            path = (workspace / relative).resolve()
            if not _inside(path, workspace):
                raise ValueError(f"{label} must remain inside the problem workspace")

    thresholds = spec.get("continuation_thresholds") or {}
    if substantial and not isinstance(thresholds, dict):
        raise ValueError("substantial jobs require continuation_thresholds")
    normalized_thresholds = {
        "min_throughput_per_second": max(0.0, float(thresholds.get("min_throughput_per_second") or 0.0)),
        "max_artifact_growth_bytes": max(0, int(thresholds.get("max_artifact_growth_bytes") or 0)),
        "require_correctness_checks": bool(thresholds.get("require_correctness_checks", substantial)),
    }
    decision_value = str(spec.get("decision_value") or "").strip()
    if substantial and not decision_value:
        raise ValueError("substantial jobs require a predeclared decision_value")
    efficiency = _validate_efficiency(spec.get("efficiency_design"), substantial=substantial)

    normalized = {
        "schema_version": SCHEMA_VERSION,
        "id": str(spec.get("id") or f"lab-{problem_id}-{uuid.uuid4().hex[:12]}"),
        "problem_id": problem_id,
        "name": str(spec.get("name") or "").strip()[:200],
        "hypothesis": str(spec.get("hypothesis") or "").strip()[:4000],
        "expected_signal": str(spec.get("expected_signal") or "").strip()[:4000],
        "decision_value": decision_value[:4000],
        "efficiency_design": efficiency,
        "source_urls": [str(value)[:1000] for value in spec.get("source_urls", []) if str(value).startswith("http")][:20],
        "command": command,
        "seed": int(spec.get("seed") or 0),
        "segment_seconds": segment_seconds,
        "memory_mb": memory_mb,
        "max_segments": max_segments,
        "segment": segment,
        "pilot_segments": pilot_segments,
        "review_every_segments": review_every,
        "checkpoint_path": checkpoint,
        "progress_path": progress_path,
        "continuation_thresholds": normalized_thresholds,
        "submitted_at": str(spec.get("submitted_at") or store.now_iso()),
        "workspace_git_commit": str(spec.get("workspace_git_commit") or _git_commit(workspace)),
        "input_sha256": explicit_input_hashes if explicit_input_hashes is not None else automatic_input_hashes,
    }
    if mutable_paths:
        normalized["mutable_argv_paths"] = mutable_paths
        normalized["mutable_argv_initial_sha256"] = mutable_initial
        normalized["progress_baseline"] = progress_baseline
    if not normalized["name"] or not normalized["hypothesis"] or not normalized["expected_signal"]:
        raise ValueError("name, hypothesis, and expected_signal are required")
    if not _SAFE_JOB_ID.fullmatch(normalized["id"]):
        raise ValueError(f"invalid lab job id: {normalized['id']}")
    _validate_input_hashes(normalized["input_sha256"], kind="lab spec")
    normalized["spec_sha256"] = _spec_sha256(normalized)
    return normalized


def _load_persisted_spec(path: Path, *, source_path: Path | None = None) -> dict[str, Any]:
    """Load a queued spec without synthesizing fields for historical schemas.

    Lab v1 did not bind the full continuation/efficiency contract. It remains
    viewable in durable state but cannot be executed or accepted as if it were v2.
    """
    raw = schemas.load_json_object(path, kind="lab persisted spec")
    schemas.require_current_version(raw, kind="lab persisted spec", current=SCHEMA_VERSION)
    schemas.require_fields(raw, frozenset((*SPEC_FIELDS, "spec_sha256")), kind="lab persisted spec")
    _validate_input_hashes(raw.get("input_sha256"), kind="lab persisted spec")
    if "mutable_argv_paths" in raw or "mutable_argv_initial_sha256" in raw:
        if "mutable_argv_paths" not in raw or "mutable_argv_initial_sha256" not in raw:
            raise schemas.SchemaError("lab persisted spec must carry both mutable argv fields")
    expected = str(raw.get("spec_sha256") or "")
    if len(expected) != 64 or expected != _spec_sha256(raw):
        raise schemas.SchemaError("lab persisted spec spec_sha256 mismatch")
    normalized = _validate(raw, source_path=source_path)
    if normalized != raw:
        raise schemas.SchemaError("lab persisted spec is not in canonical current-schema form")
    return normalized


def submit(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate(spec)
    queue = _workspace(normalized["problem_id"]) / "lab-queue"
    queue.mkdir(parents=True, exist_ok=True)
    destination = queue / f"{normalized['id']}.json"
    if destination.exists() or _state_path(normalized["id"]).exists():
        raise ValueError(f"duplicate lab job: {normalized['id']}")
    store.write_json_atomic(destination, normalized)
    state = {
        **normalized,
        "status": "queued",
        "segments": [],
        "last_reviewed_segment": 0,
        "created_at": store.now_iso(),
    }
    _write_state(state)
    repositories.record_lab(normalized["problem_id"], "submitted", normalized)
    return {"status": "queued", "spec": str(destination), **normalized}


def _verify_immutable_inputs(spec: dict[str, Any], workspace: Path, state: dict[str, Any] | None = None) -> None:
    current_commit = _git_commit(workspace)
    if (
        spec["workspace_git_commit"] != "unversioned"
        and current_commit != spec["workspace_git_commit"]
        and not _git_contains(workspace, spec["workspace_git_commit"])
    ):
        raise ValueError(
            f"submitted revision is no longer an ancestor: {spec['workspace_git_commit']}, current {current_commit}"
        )
    for relative, expected in spec.get("input_sha256", {}).items():
        path = (workspace / relative).resolve()
        if not _inside(path, workspace) or not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"immutable input changed or disappeared: {relative}")
    mutable_paths = spec.get("mutable_argv_paths", [])
    if mutable_paths:
        previous_segments = (state or {}).get("segments", [])
        recovery = (state or {}).get("mutable_argv_recovery")
        if (
            isinstance(recovery, dict)
            and recovery.get("segment") == spec.get("segment")
            and isinstance(recovery.get("recovered_sha256"), dict)
        ):
            expected_mutable = recovery["recovered_sha256"]
        else:
            expected_mutable = (
                previous_segments[-1].get("mutable_argv_after_sha256")
                if previous_segments else spec["mutable_argv_initial_sha256"]
            )
        current_mutable = _mutable_identity(workspace, mutable_paths)
        if current_mutable != expected_mutable:
            raise ValueError("mutable argv input changed outside the recorded segment chain")


def _append_record(record: dict[str, Any]) -> None:
    ledger = store.STATE / "labs" / "jobs.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _recover_running_specs() -> list[str]:
    recovered: list[str] = []
    for running in store.RESEARCH.glob("*/workspace/lab-queue/*.running.json"):
        source = running.with_name(running.name.replace(".running.json", ".json"))
        os.replace(running, source)
        try:
            raw = json.loads(source.read_text())
            state = _read_state(str(raw["id"]))
            state["status"] = "checkpointed"
            state["recovery_note"] = "in-flight segment recovered after worker interruption; exact segment will replay"
            mutable_paths = state.get("mutable_argv_paths", [])
            if mutable_paths:
                previous_segments = state.get("segments", [])
                prior_expected = (
                    previous_segments[-1].get("mutable_argv_after_sha256")
                    if previous_segments else state["mutable_argv_initial_sha256"]
                )
                recovery = {
                    "recorded_at": store.now_iso(),
                    "segment": int(state.get("segment") or 1),
                    "prior_expected_sha256": prior_expected,
                    "recovered_sha256": _mutable_identity(
                        _workspace(str(state["problem_id"])), mutable_paths,
                    ),
                    "reason": "worker interruption left no completed segment record; replay must recheck progress",
                }
                state["mutable_argv_recovery"] = recovery
                state.setdefault("mutable_argv_recovery_receipts", []).append(recovery)
            _write_state(state)
            recovered.append(str(raw["id"]))
        except Exception:
            recovered.append(source.stem)
    return recovered


def queued_specs() -> list[Path]:
    return sorted(store.RESEARCH.glob("*/workspace/lab-queue/*.json"), key=lambda path: path.stat().st_mtime)


def _requires_build_cache(raw: dict[str, Any]) -> bool:
    command = [str(value).lower() for value in raw.get("command", [])]
    return any(token in value for value in command for token in ("lean", "lake", "formal-conjectures"))


def _tree_bytes(root: Path) -> int:
    """Measure regular-file bytes without following cache or external symlinks."""
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _progress(
    workspace: Path,
    spec: dict[str, Any],
    previous: dict[str, Any],
    duration: float,
    *,
    measured_growth_bytes: int = 0,
) -> tuple[dict[str, Any], list[str]]:
    if not spec["progress_path"]:
        measured = max(0, int(measured_growth_bytes))
        return {"complete": True, "completed_units": 1, "total_units": 1,
                "correctness_checks_passed": True, "decision_value_active": True,
                "artifact_bytes": measured, "artifact_growth_bytes": measured,
                "measured_artifact_growth_bytes": measured}, []
    path = workspace / spec["progress_path"]
    try:
        value = schemas.load_json_object(path, kind="lab progress record")

        def number(field: str) -> float:
            item = value.get(field)
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise schemas.SchemaError(f"lab progress record.{field} must be a number")
            result = float(item)
            if not math.isfinite(result) or result < 0:
                raise schemas.SchemaError(f"lab progress record.{field} must be finite and nonnegative")
            return result

        def boolean(field: str) -> bool:
            item = value.get(field)
            if not isinstance(item, bool):
                raise schemas.SchemaError(f"lab progress record.{field} must be bool")
            return item

        completed = number("completed_units")
        total = number("total_units")
        reported_artifact_bytes = value.get("artifact_bytes")
        if isinstance(reported_artifact_bytes, bool) or not isinstance(reported_artifact_bytes, int):
            raise schemas.SchemaError("lab progress record.artifact_bytes must be int")
        if reported_artifact_bytes < 0:
            raise schemas.SchemaError("lab progress record.artifact_bytes must be nonnegative")
        declared_complete = boolean("complete")
        correctness_passed = boolean("correctness_checks_passed")
        decision_value_active = boolean("decision_value_active")
    except (OSError, schemas.SchemaError) as exc:
        return {}, [f"progress record missing or invalid: {exc}"]

    prior_completed = float(previous.get("completed_units") or 0)
    prior_bytes = int(previous.get("reported_artifact_bytes", previous.get("artifact_bytes") or 0))
    delta = completed - prior_completed
    throughput = delta / max(duration, 0.001)
    reported_growth = reported_artifact_bytes - prior_bytes
    independently_measured_growth = max(0, int(measured_growth_bytes))
    effective_growth = max(0, reported_growth, independently_measured_growth)
    progress = {
        "path": spec["progress_path"],
        "sha256": _sha256(path),
        "completed_units": completed,
        "total_units": total,
        "delta_units": delta,
        "throughput_per_second": throughput,
        "artifact_bytes": reported_artifact_bytes,
        "reported_artifact_bytes": reported_artifact_bytes,
        "reported_artifact_growth_bytes": max(0, reported_growth),
        "measured_artifact_growth_bytes": independently_measured_growth,
        "artifact_growth_bytes": effective_growth,
        "complete": declared_complete,
        "correctness_checks_passed": correctness_passed,
        "decision_value_active": decision_value_active,
        "message": str(value.get("message") or "")[:2000],
    }
    failures: list[str] = []
    limits = spec["continuation_thresholds"]
    if total <= 0:
        failures.append("total units must be positive")
    if total > 0 and declared_complete != (completed >= total):
        failures.append("declared completion disagrees with completed and total units")
    if completed > total and total > 0:
        failures.append("completed units exceed total units")
    if delta <= 0 and not progress["complete"]:
        failures.append("completed units did not increase")
    if reported_growth < 0:
        failures.append("reported artifact bytes decreased")
    if limits["min_throughput_per_second"] and throughput < limits["min_throughput_per_second"]:
        failures.append("measured throughput fell below the declared continuation threshold")
    if limits["max_artifact_growth_bytes"] and progress["artifact_growth_bytes"] > limits["max_artifact_growth_bytes"]:
        failures.append("artifact growth exceeded the declared per-segment threshold")
    if limits["require_correctness_checks"] and not progress["correctness_checks_passed"]:
        failures.append("declared correctness checks did not pass")
    if not progress["decision_value_active"]:
        failures.append("progress record says the predeclared decision value is no longer active")
    return progress, failures


def _emit_segment_event(spec: dict[str, Any], status: str, record: dict[str, Any]) -> dict[str, Any]:
    kind = "lab_completed" if status in {"completed_awaiting_review", "stopped_with_reason"} else "lab_segment_completed"
    return events.enqueue(
        spec["problem_id"], kind,
        evidence=(
            f"lab job {spec['id']} segment {record.get('segment', spec['segment'])} entered {status}; "
            f"progress={json.dumps(record.get('progress', {}), sort_keys=True)[:2500]}"
        ),
        source=f"state/labs/jobs/{spec['id']}.json",
    )


def _run_monitored_segment(
    command: list[str],
    *,
    workspace: Path,
    env: dict[str, str],
    timeout_seconds: int,
    workspace_bytes_before: int,
    filesystem_used_before: int,
    max_growth_bytes: int,
) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run one segment while enforcing live root-reserve and declared growth gates."""
    proc = subprocess.Popen(
        command,
        cwd=workspace,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout_seconds
    monitor_failure = ""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            monitor_failure = "segment wrapper exceeded its wall-clock envelope"
        try:
            stdout, stderr = proc.communicate(timeout=max(0.1, min(5.0, remaining)))
            return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr), monitor_failure
        except subprocess.TimeoutExpired:
            # Filesystem allocation is an O(1), producer-independent live
            # signal. It conservatively charges concurrent growth on the same
            # filesystem rather than trusting an experiment-authored counter.
            growth = max(
                0,
                shutil.disk_usage(workspace).used - filesystem_used_before,
                _tree_bytes(workspace) - workspace_bytes_before,
            )
            if capacity._free_bytes(Path("/")) < capacity.ROOT_MIN_FREE_BYTES:
                monitor_failure = "root free space fell below the live reserve during the segment"
            elif max_growth_bytes and growth > max_growth_bytes:
                monitor_failure = "measured artifact growth exceeded the declared threshold during the segment"
            elif remaining > 0:
                continue
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = proc.communicate()
        return subprocess.CompletedProcess(command, proc.returncode or 124, stdout, stderr), monitor_failure


def worker_once() -> dict[str, Any]:
    with store.lock("lab-worker", nonblocking=True) as acquired:
        if not acquired:
            return {"status": "busy"}
        recovered = _recover_running_specs()
        queue = queued_specs()
        if not queue:
            return {"status": "idle", "recovered": recovered}
        source: Path | None = None
        deferred: list[dict[str, Any]] = []
        for candidate in queue:
            try:
                candidate_raw = json.loads(candidate.read_text())
            except Exception:
                candidate_raw = {}
            # Cache-dependent formalization jobs retain the cache reserve. A
            # blocked Lean job must not head-of-line block an independent
            # Python/SAT job whose artifacts live on the healthy root disk.
            policy = capacity.admission("hard", require_cache=_requires_build_cache(candidate_raw))
            if policy["allowed"]:
                source = candidate
                capacity_policy = policy
                break
            deferred.append({"job": str(candidate), "capacity_policy": policy})
        if source is None:
            return {"status": "deferred", "reason": "host capacity reserve", "deferred_jobs": deferred}
        running = source.with_suffix(".running.json")
        os.replace(source, running)
        try:
            spec = _load_persisted_spec(running, source_path=source)
            workspace = _workspace(spec["problem_id"])
            state = _read_state(spec["id"])
            _verify_immutable_inputs(spec, workspace, state)
            if state.get("status") not in {"queued", "checkpointed"}:
                raise schemas.SchemaError(
                    f"lab job {spec['id']} is not executable from state {state.get('status')!r}"
                )
            state["status"] = "running"
            state["running_segment"] = spec["segment"]
            _write_state(state)
            mutable_before = _mutable_identity(workspace, spec.get("mutable_argv_paths", []))
            output_root = workspace / "lab-runs" / spec["id"] / f"segment-{spec['segment']:06d}"
            output_root.mkdir(parents=True, exist_ok=True)
            total_label = "open" if spec["max_segments"] == 0 else str(spec["max_segments"])
            command = [
                sys.executable, str(RUNNER), "--name", f"{spec['name']} segment {spec['segment']}/{total_label}",
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
            workspace_bytes_before = _tree_bytes(workspace)
            filesystem_used_before = shutil.disk_usage(workspace).used
            started = store.parse_iso(store.now_iso())
            proc, monitor_failure = _run_monitored_segment(
                command,
                workspace=workspace,
                env=env,
                timeout_seconds=spec["segment_seconds"] + 120,
                workspace_bytes_before=workspace_bytes_before,
                filesystem_used_before=filesystem_used_before,
                max_growth_bytes=spec["continuation_thresholds"]["max_artifact_growth_bytes"],
            )
            finished = store.parse_iso(store.now_iso())
            duration = max(0.0, (finished - started).total_seconds()) if started and finished else 0.0
            checkpoint_path = workspace / spec["checkpoint_path"] if spec["checkpoint_path"] else None
            checkpoint_exists = bool(checkpoint_path and checkpoint_path.is_file())
            previous = (
                state.get("segments", [])[-1].get("progress", {})
                if state.get("segments") else spec.get("progress_baseline", {})
            )
            measured_growth = max(0, _tree_bytes(workspace) - workspace_bytes_before)
            progress, threshold_failures = _progress(
                workspace, spec, previous, duration, measured_growth_bytes=measured_growth,
            )
            if monitor_failure:
                threshold_failures.append(monitor_failure)
            if spec["checkpoint_path"] and not checkpoint_exists and not progress.get("complete"):
                threshold_failures.append("checkpoint file missing")
            record = {
                "recorded_at": store.now_iso(), "job_id": spec["id"], "problem_id": spec["problem_id"],
                "segment": spec["segment"], "max_segments": spec["max_segments"],
                "returncode": proc.returncode, "duration_seconds": duration,
                "checkpoint_exists": checkpoint_exists,
                "checkpoint_sha256": _sha256(checkpoint_path) if checkpoint_exists else "",
                "progress": progress, "threshold_failures": threshold_failures,
                "runner_result": proc.stdout[-12000:], "runner_error": proc.stderr[-4000:],
                "output_root": str(output_root.relative_to(workspace)),
            }
            if spec.get("mutable_argv_paths"):
                record["mutable_argv_before_sha256"] = mutable_before
                record["mutable_argv_after_sha256"] = _mutable_identity(
                    workspace, spec["mutable_argv_paths"],
                )
            if proc.returncode not in {0, 124}:
                threshold_failures.append(f"segment process returned {proc.returncode}")
            if proc.returncode == 124 and not checkpoint_exists:
                threshold_failures.append("timed-out segment has no resumable checkpoint")

            if threshold_failures:
                lifecycle = "stopped_with_reason"
            elif progress.get("complete"):
                lifecycle = "completed_awaiting_review"
            else:
                last_reviewed = int(state.get("last_reviewed_segment") or 0)
                since_review = spec["segment"] - last_reviewed
                pilot_due = last_reviewed == 0 and spec["segment"] >= spec["pilot_segments"]
                periodic_due = last_reviewed > 0 and since_review >= spec["review_every_segments"]
                tranche_limit = pilot_due or periodic_due
                declared_end = bool(spec["max_segments"] and spec["segment"] >= spec["max_segments"])
                lifecycle = "completed_awaiting_review" if tranche_limit or declared_end else "checkpointed"

            state.setdefault("segments", []).append(record)
            state["status"] = lifecycle
            state["running_segment"] = None
            state["latest_progress"] = progress
            state["stop_reason"] = "; ".join(threshold_failures)
            next_spec: dict[str, Any] | None = None
            if lifecycle == "checkpointed":
                spec["segment"] += 1
                spec["spec_sha256"] = _spec_sha256(spec)
                state["segment"] = spec["segment"]
                state["spec_sha256"] = spec["spec_sha256"]
                next_spec = spec
            else:
                archive = workspace / "lab-archive"
                archive.mkdir(parents=True, exist_ok=True)
                store.write_json_atomic(archive / f"{spec['id']}.json", {**spec, "final_record": record})
            event = _emit_segment_event(spec, lifecycle, record)
            record["research_event_id"] = event["id"]
            _write_state(state)
            _append_record({**record, "status": lifecycle})
            repositories.record_lab(spec["problem_id"], lifecycle, {**spec, **record})
            # Publish executable work only after the event, state, append-only
            # ledger, and repository receipt are durable. A late failure can no
            # longer leave a stopped job queued.
            if next_spec is not None:
                store.write_json_atomic(source, next_spec)
            return {"status": lifecycle, **record}
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            failed_id = running.stem.replace(".running", "")
            failed_problem = ""
            try:
                failed_spec = store.read_json(running, {})
                if isinstance(failed_spec, dict):
                    failed_id = str(failed_spec.get("id") or failed_id)
                    failed_problem = str(failed_spec.get("problem_id") or "")
            except Exception:
                pass
            try:
                state = _read_state(failed_id)
                state["status"] = "stopped_with_reason"
                state["stop_reason"] = error
                _write_state(state)
            except Exception:
                # An incompatible historical state is retained byte-for-byte for
                # viewing; the append-only record and event carry the rejection.
                pass
            if failed_problem:
                try:
                    events.enqueue(failed_problem, "lab_completed", evidence=f"lab job {failed_id} stopped: {error}",
                                   source=f"state/labs/jobs/{failed_id}.json")
                except Exception:
                    pass
            record = {"recorded_at": store.now_iso(), "job_id": failed_id, "problem_id": failed_problem,
                      "status": "stopped_with_reason", "error": error}
            _append_record(record)
            source.unlink(missing_ok=True)
            rejected = running.parent.parent / "lab-rejected"
            rejected.mkdir(parents=True, exist_ok=True)
            shutil.move(str(running), str(rejected / running.name))
            return record
        finally:
            running.unlink(missing_ok=True)


def worker_tranche(*, max_segments: int | None = None) -> dict[str, Any]:
    """Run bounded segments continuously until the next real review/stop boundary.

    ``max_segments`` remains available for tests and explicitly bounded operator
    calls.  The production ``--drain`` path deliberately leaves it unset: each
    segment retains its own resource limits, while an arbitrary activation cap
    must not create idle gaps before the predeclared review tranche is due.
    """
    results: list[dict[str, Any]] = []
    while max_segments is None or len(results) < max_segments:
        result = worker_once()
        results.append(result)
        if result.get("status") != "checkpointed":
            break
    return {
        "status": results[-1].get("status") if results else "idle",
        "segments_run": len([row for row in results if row.get("segment")]),
        "results": results,
    }


def _validated_lab_receipt(state: dict[str, Any], relative: str) -> tuple[dict[str, Any], str]:
    """Verify an independently produced receipt against the completed job and current artifacts."""
    workspace = _workspace(str(state["problem_id"]))
    candidate = Path(str(relative or ""))
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        raise schemas.SchemaError("validation receipt must be a relative workspace path")
    path = (workspace / candidate).resolve()
    if not _inside(path, workspace) or not path.is_file() or path.is_symlink():
        raise schemas.SchemaError("validation receipt must be a regular file inside the workspace")
    receipt = schemas.load_json_object(path, kind="lab validation receipt")
    schemas.require_current_version(
        receipt, kind="lab validation receipt", current=VALIDATION_RECEIPT_SCHEMA_VERSION,
    )
    schemas.require_fields(receipt, frozenset({
        "schema_version", "job_id", "segment", "progress_sha256", "result", "validator",
        "checker_path", "checker_sha256", "checked_artifacts", "independence_basis", "created_at",
        "checker_command", "checker_exit_code", "checker_stdout_sha256", "checker_result_path",
        "checker_result_sha256", "execution_record_path", "execution_record_sha256",
        "validation_job_id",
    }), kind="lab validation receipt")
    if isinstance(receipt["segment"], bool) or not isinstance(receipt["segment"], int):
        raise schemas.SchemaError("lab validation receipt.segment must be int")
    if receipt["job_id"] != state["id"] or receipt["segment"] != state["segment"]:
        raise schemas.SchemaError("lab validation receipt is not bound to the completed job segment")
    if receipt["result"] != "passed":
        raise schemas.SchemaError("lab validation receipt result is not passed")
    progress_relative = state.get("latest_progress", {}).get("path")
    if not isinstance(progress_relative, str) or not progress_relative:
        raise schemas.SchemaError("completed lab state has no final progress path")
    progress_path = (workspace / progress_relative).resolve()
    if (
        Path(progress_relative).is_absolute() or ".." in Path(progress_relative).parts
        or not _inside(progress_path, workspace) or not progress_path.is_file() or progress_path.is_symlink()
    ):
        raise schemas.SchemaError("final progress record is not a regular workspace file")
    current_progress_sha256 = _sha256(progress_path)
    if (
        receipt["progress_sha256"] != state.get("latest_progress", {}).get("sha256")
        or current_progress_sha256 != receipt["progress_sha256"]
    ):
        raise schemas.SchemaError("lab validation receipt does not bind the final progress record")
    if not isinstance(receipt["validator"], str) or not receipt["validator"].strip():
        raise schemas.SchemaError("lab validation receipt.validator must be nonempty")
    if not isinstance(receipt["independence_basis"], str) or not receipt["independence_basis"].strip():
        raise schemas.SchemaError("lab validation receipt.independence_basis must be nonempty")
    if not store.parse_iso(receipt["created_at"] if isinstance(receipt["created_at"], str) else ""):
        raise schemas.SchemaError("lab validation receipt.created_at must be an ISO timestamp")

    checker_relative = receipt["checker_path"]
    if not isinstance(checker_relative, str):
        raise schemas.SchemaError("lab validation receipt.checker_path must be a relative path")
    checker = (workspace / checker_relative).resolve()
    if (
        Path(checker_relative).is_absolute() or ".." in Path(checker_relative).parts
        or not _inside(checker, workspace) or not checker.is_file() or checker.is_symlink()
    ):
        raise schemas.SchemaError("lab validation checker must be a regular workspace file")
    if receipt["checker_sha256"] != _sha256(checker):
        raise schemas.SchemaError("lab validation checker hash mismatch")
    if receipt["checker_sha256"] in set(state.get("input_sha256", {}).values()):
        raise schemas.SchemaError("lab validation checker must differ from the experiment inputs")

    checker_command = receipt["checker_command"]
    if (
        not isinstance(checker_command, list) or not checker_command
        or not all(isinstance(item, str) and item for item in checker_command)
        or checker_relative not in checker_command
    ):
        raise schemas.SchemaError("lab validation receipt.checker_command must name the checker exactly")
    if isinstance(receipt["checker_exit_code"], bool) or receipt["checker_exit_code"] != 0:
        raise schemas.SchemaError("lab validation checker exit code must be integer zero")

    validation_job_id = receipt["validation_job_id"]
    if not isinstance(validation_job_id, str) or validation_job_id == state["id"]:
        raise schemas.SchemaError("lab validation receipt requires a distinct validation job id")
    validation_state = _read_state(validation_job_id)
    validation_segments = validation_state.get("segments", [])
    validation_last = validation_segments[-1] if validation_segments else {}
    if (
        validation_state.get("problem_id") != state["problem_id"]
        or validation_state.get("status") not in {"completed_awaiting_review", "validated"}
        or validation_state.get("command") != checker_command
        or validation_last.get("returncode") != 0
        or validation_last.get("threshold_failures")
        or not validation_state.get("latest_progress", {}).get("complete")
        or not validation_state.get("latest_progress", {}).get("correctness_checks_passed")
    ):
        raise schemas.SchemaError("declared validation job did not complete the checker successfully")
    if validation_state.get("input_sha256", {}).get(checker_relative) != receipt["checker_sha256"]:
        raise schemas.SchemaError("validation job input identity does not bind the checker bytes")

    execution_relative = receipt["execution_record_path"]
    if not isinstance(execution_relative, str):
        raise schemas.SchemaError("lab validation receipt.execution_record_path must be a relative path")
    execution_path = (workspace / execution_relative).resolve()
    if (
        Path(execution_relative).is_absolute() or ".." in Path(execution_relative).parts
        or not _inside(execution_path, workspace) or not execution_path.is_file() or execution_path.is_symlink()
        or receipt["execution_record_sha256"] != _sha256(execution_path)
    ):
        raise schemas.SchemaError("lab validation execution record is absent or hash-mismatched")
    execution = schemas.load_json_object(execution_path, kind="lab validation execution record")
    schemas.require_current_version(execution, kind="lab validation execution record", current=1)
    schemas.require_fields(execution, frozenset({
        "schema_version", "id", "name", "hypothesis", "expected_signal", "command", "cwd", "seed",
        "timeout_seconds", "memory_limit_mb", "memory_limit_enforced", "started_at", "finished_at",
        "duration_seconds", "returncode", "timed_out", "python", "platform", "git_commit",
        "source_urls", "input_artifacts", "peak_child_memory_rusage", "peak_child_memory_unit", "artifacts",
    }), kind="lab validation execution record")
    expected_output_root = str(validation_last.get("output_root") or "").rstrip("/") + "/"
    execution_inputs = execution.get("input_artifacts") if isinstance(execution.get("input_artifacts"), dict) else {}
    if (
        not execution_relative.startswith(expected_output_root)
        or execution.get("command") != checker_command
        or execution.get("cwd") != str(workspace)
        or isinstance(execution.get("returncode"), bool) or execution.get("returncode") != 0
        or execution.get("timed_out") is not False
        or execution_inputs.get(str(checker)) != receipt["checker_sha256"]
    ):
        raise schemas.SchemaError("lab validation execution record did not run the declared checker successfully")
    stdout = execution_path.parent / "stdout.txt"
    execution_artifacts = execution.get("artifacts") if isinstance(execution.get("artifacts"), dict) else {}
    if (
        not stdout.is_file() or stdout.is_symlink()
        or receipt["checker_stdout_sha256"] != _sha256(stdout)
        or execution_artifacts.get("stdout.txt") != receipt["checker_stdout_sha256"]
    ):
        raise schemas.SchemaError("lab validation stdout is absent or hash-mismatched")

    result_relative = receipt["checker_result_path"]
    if not isinstance(result_relative, str):
        raise schemas.SchemaError("lab validation receipt.checker_result_path must be a relative path")
    result_path = (workspace / result_relative).resolve()
    if (
        Path(result_relative).is_absolute() or ".." in Path(result_relative).parts
        or not _inside(result_path, workspace) or not result_path.is_file() or result_path.is_symlink()
        or receipt["checker_result_sha256"] != _sha256(result_path)
    ):
        raise schemas.SchemaError("lab validation checker result is absent or hash-mismatched")

    artifacts = receipt["checked_artifacts"]
    if not isinstance(artifacts, dict) or not artifacts:
        raise schemas.SchemaError("lab validation receipt.checked_artifacts must be a nonempty object")
    for artifact_relative, expected in artifacts.items():
        if not isinstance(artifact_relative, str) or not isinstance(expected, str):
            raise schemas.SchemaError("lab validation artifact paths and hashes must be strings")
        artifact = (workspace / artifact_relative).resolve()
        if (
            Path(artifact_relative).is_absolute() or ".." in Path(artifact_relative).parts
            or not _inside(artifact, workspace) or not artifact.is_file() or artifact.is_symlink()
            or len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected)
        ):
            raise schemas.SchemaError(f"invalid lab validation artifact: {artifact_relative!r}")
        if _sha256(artifact) != expected:
            raise schemas.SchemaError(f"lab validation artifact hash mismatch: {artifact_relative}")
    if artifacts.get(result_relative) != receipt["checker_result_sha256"]:
        raise schemas.SchemaError("lab validation checker result must be included among checked artifacts")
    return receipt, _sha256(path)


def apply_review(
    job_id: str,
    decision: str,
    *,
    reason: str,
    reviewer: str = "operator",
    validation_receipt: str = "",
) -> dict[str, Any]:
    decision = str(decision).strip()
    if decision not in REVIEW_DECISIONS:
        raise ValueError(f"review decision must be one of {sorted(REVIEW_DECISIONS)}")
    if not str(reason).strip():
        raise ValueError("review reason is required")
    state = _read_state(job_id)
    if state.get("status") not in {"completed_awaiting_review", "stopped_with_reason"}:
        raise ValueError(f"job {job_id} is not awaiting review or stopped")
    review = {"decision": decision, "reason": str(reason)[:4000], "reviewer": str(reviewer)[:200],
              "reviewed_at": store.now_iso(), "segment": int(state.get("segment") or 1)}
    if decision in {"validate", "promote"}:
        receipt, receipt_sha256 = _validated_lab_receipt(state, validation_receipt)
        review["validation_receipt"] = validation_receipt
        review["validation_receipt_sha256"] = receipt_sha256
        review["independent_validator"] = receipt["validator"]
    state.setdefault("reviews", []).append(review)
    workspace = _workspace(str(state["problem_id"]))
    queued_spec: dict[str, Any] | None = None
    if decision == "continue":
        if state.get("status") != "completed_awaiting_review":
            raise ValueError("a stopped lab job cannot continue; submit a new audited job or redirect it")
        if not state.get("checkpoint_path"):
            raise ValueError("cannot continue a job without a checkpoint")
        latest = state.get("latest_progress") if isinstance(state.get("latest_progress"), dict) else {}
        last_segment = state.get("segments", [])[-1] if state.get("segments") else {}
        if (
            not latest.get("correctness_checks_passed")
            or not latest.get("decision_value_active")
            or last_segment.get("threshold_failures")
        ):
            raise ValueError("lab continuation gates are not satisfied")
        state["last_reviewed_segment"] = int(state.get("segment") or 1)
        state["segment"] = int(state.get("segment") or 1) + 1
        if state.get("max_segments") and state["segment"] > int(state["max_segments"]):
            state["max_segments"] = state["segment"] + int(state.get("review_every_segments") or 1) - 1
        # Remain truthfully checkpointed until the next executable queue item is
        # atomically published after the authoritative review ledger is durable.
        state["status"] = "checkpointed"
        state["spec_sha256"] = _spec_sha256(state)
        queued_spec = {key: state[key] for key in (*SPEC_FIELDS, *OPTIONAL_SPEC_FIELDS, "spec_sha256") if key in state}
    elif decision in {"validate", "promote"}:
        if not state.get("latest_progress", {}).get("complete"):
            raise ValueError("only a complete experiment can be validated or promoted")
        state["status"] = "validated"
        state["promotion_requested"] = decision == "promote"
    else:
        state["status"] = "stopped_with_reason"
        state["stop_reason"] = str(reason)[:4000]
    _write_state(state)
    _append_record({"recorded_at": store.now_iso(), "job_id": job_id, "problem_id": state["problem_id"],
                    "status": state["status"], "review": review})
    if queued_spec is not None:
        queue = workspace / "lab-queue"
        queue.mkdir(parents=True, exist_ok=True)
        try:
            store.write_json_atomic(queue / f"{job_id}.json", queued_spec)
        except Exception as exc:
            state["status"] = "stopped_with_reason"
            state["stop_reason"] = f"review accepted but continuation queue publication failed: {type(exc).__name__}: {exc}"
            _write_state(state)
            _append_record({
                "recorded_at": store.now_iso(), "job_id": job_id, "problem_id": state["problem_id"],
                "status": state["status"], "error": state["stop_reason"],
            })
            raise
        state["status"] = "queued"
        _write_state(state)
        _append_record({
            "recorded_at": store.now_iso(), "job_id": job_id, "problem_id": state["problem_id"],
            "status": "queued", "transition": "reviewed checkpoint published for continuation",
        })
    projection_warning = ""
    try:
        repositories.record_lab(str(state["problem_id"]), state["status"], {"id": job_id, "review": review})
    except Exception as exc:
        projection_warning = f"{type(exc).__name__}: {exc}"
        repositories.queue_lab_projection(
            str(state["problem_id"]), state["status"], {"id": job_id, "review": review},
            error=projection_warning,
        )
        _append_record({
            "recorded_at": store.now_iso(), "job_id": job_id, "problem_id": state["problem_id"],
            "status": "repository_projection_pending", "error": projection_warning,
        })
    return {
        "status": state["status"], "job_id": job_id, "review": review,
        **({"repository_projection_warning": projection_warning} if projection_warning else {}),
    }


def retune_review_interval(job_id: str, review_every_segments: int, *, reason: str,
                           actor: str = "operator") -> dict[str, Any]:
    """Change review cadence only at a durable safety boundary and retain an audit record."""
    interval = int(review_every_segments)
    if interval < 1:
        raise ValueError("review_every_segments must be positive")
    if not str(reason).strip():
        raise ValueError("retuning requires a reason")
    state = _read_state(job_id)
    if state.get("status") != "completed_awaiting_review":
        raise ValueError("review cadence may change only at a completed-awaiting-review boundary")
    progress = state.get("latest_progress") if isinstance(state.get("latest_progress"), dict) else {}
    if not progress.get("correctness_checks_passed") or not progress.get("decision_value_active", True):
        raise ValueError("review cadence cannot expand after a correctness or decision-value failure")
    old = int(state.get("review_every_segments") or 1)
    change = {
        "changed_at": store.now_iso(), "actor": str(actor)[:200], "field": "review_every_segments",
        "old": old, "new": interval, "reason": str(reason)[:4000],
        "at_segment": int(state.get("segment") or 1),
    }
    state["review_every_segments"] = interval
    state["spec_sha256"] = _spec_sha256(state)
    state.setdefault("configuration_changes", []).append(change)
    _write_state(state)
    record = {
        "recorded_at": store.now_iso(), "job_id": job_id, "problem_id": state["problem_id"],
        "status": "configuration_updated", "configuration_change": change,
        "spec_sha256": state["spec_sha256"],
    }
    _append_record(record)
    repositories.record_lab(str(state["problem_id"]), "configuration_updated", record)
    return {"status": state["status"], "job_id": job_id, "configuration_change": change,
            "spec_sha256": state["spec_sha256"]}


def status(problem_id: str | None = None) -> dict[str, Any]:
    states: list[dict[str, Any]] = []
    for path in sorted(_state_root().glob("*.json")):
        value = store.read_json(path, None)
        if not isinstance(value, dict) or (problem_id and value.get("problem_id") != problem_id):
            continue
        try:
            current = _read_state(path.stem)
            current["schema_compatible"] = True
            states.append(current)
        except (ValueError, schemas.SchemaError) as exc:
            # Historical records remain inspectable, but no mutation/acceptance
            # path uses this permissive display view.
            visible = dict(value)
            visible["schema_compatible"] = False
            visible["schema_error"] = str(exc)[:1000]
            states.append(visible)
    counts = {name: sum(1 for row in states if row.get("status") == name) for name in sorted(LIFECYCLE_STATES)}
    return {
        "counts": counts,
        "jobs": states[-50:],
        "queued": [str(path) for path in queued_specs()],
        "limits": {
            "allowed_executables": sorted(ALLOWED_EXECUTABLES),
            "max_segment_seconds": MAX_SEGMENT_SECONDS,
            "max_declared_segments": MAX_DECLARED_SEGMENTS,
            "open_continuation_value": 0,
            "max_memory_mb": MAX_MEMORY_MB,
            "shell": False,
            "policy": "bounded segments with measured review tranches; no universal overall wall-clock stop",
        },
    }


def public_summary() -> dict[str, Any]:
    report = status()
    visible = []
    newest = sorted(
        report["jobs"],
        key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")),
        reverse=True,
    )[:10]
    for row in newest:
        visible.append({
            "id": row.get("id"), "problem_id": row.get("problem_id"), "name": row.get("name"),
            "status": row.get("status"), "segment": row.get("segment"),
            "completed_units": row.get("latest_progress", {}).get("completed_units"),
            "total_units": row.get("latest_progress", {}).get("total_units"),
            "stop_reason": row.get("stop_reason"), "updated_at": row.get("updated_at"),
        })
    return {"counts": report["counts"], "jobs": visible}
