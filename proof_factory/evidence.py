"""Fail-closed, per-attempt evidence manifests and validation receipts.

The workspace is a mutable research surface.  This module records the files an
attempt actually added or changed, plus every explicitly claimed evidence file,
in an immutable manifest.  Mutable projections (dashboards, aggregate indexes,
and similar derived state) are labelled separately and are never accepted as
claimed evidence.

The module deliberately has no dependency on the research agent.  Callers take
a snapshot before an attempt, then finalize and validate it after the attempt::

    before = capture_workspace_snapshot(workspace)
    manifest = create_attempt_manifest(
        workspace, attempt_id, before,
        claimed_evidence_paths=["proof.lrat", "check.py"],
        mutable_projection_patterns=["status.json"],
    )
    receipt = create_evidence_receipt(manifest)

Both manifest and receipt are JSON, so a scheduler, contribution gate, or CI job
can consume them without importing this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from . import schemas


SCHEMA_VERSION = 1
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _relative_path(value: str | os.PathLike[str]) -> str:
    """Return one canonical relative POSIX path or reject ambiguous scope."""
    raw = str(value).replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or raw == "." or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"evidence path must be a normalized relative path: {value}")
    return path.as_posix()


def _scoped_file(workspace: Path, relative: str) -> Path:
    """Resolve a regular file without permitting symlinks or workspace escape."""
    candidate = workspace / relative
    current = workspace
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"evidence path uses a symlink: {relative}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(f"evidence path escapes workspace: {relative}") from exc
    return resolved


def _is_mutable(relative: str, patterns: tuple[str, ...]) -> bool:
    path = PurePosixPath(relative)
    return any(path.match(pattern) for pattern in patterns)


def _validate_manifest_schema(value: dict[str, Any]) -> None:
    schemas.require_fields(value, frozenset({
        "schema_version", "kind", "attempt_id", "created_at", "workspace",
        "mutable_projection_patterns", "claimed_evidence_paths", "artifact_count",
        "artifacts", "content_sha256",
    }), kind="attempt evidence manifest")
    if value.get("kind") != "proof-factory-attempt-delta-manifest":
        raise schemas.SchemaError(f"invalid attempt evidence manifest kind: {value.get('kind')!r}")
    attempt_id = schemas.require_type(value, "attempt_id", str, kind="attempt evidence manifest")
    if not _SAFE_ID.fullmatch(attempt_id):
        raise schemas.SchemaError(f"invalid attempt evidence manifest attempt_id: {attempt_id!r}")
    if not schemas.require_type(value, "workspace", str, kind="attempt evidence manifest"):
        raise schemas.SchemaError("attempt evidence manifest.workspace must be nonempty")
    if not schemas.require_type(value, "created_at", str, kind="attempt evidence manifest"):
        raise schemas.SchemaError("attempt evidence manifest.created_at must be nonempty")
    patterns = schemas.require_type(
        value, "mutable_projection_patterns", list, kind="attempt evidence manifest",
    )
    claimed = schemas.require_type(value, "claimed_evidence_paths", list, kind="attempt evidence manifest")
    artifacts = schemas.require_type(value, "artifacts", list, kind="attempt evidence manifest")
    count = schemas.require_type(value, "artifact_count", int, kind="attempt evidence manifest")
    if count < 0 or count != len(artifacts):
        raise schemas.SchemaError("attempt evidence manifest artifact_count mismatch")
    if not all(isinstance(item, str) for item in (*patterns, *claimed)):
        raise schemas.SchemaError("attempt evidence manifest paths and patterns must be strings")
    try:
        normalized_patterns = [_relative_path(item) for item in patterns]
        normalized_claimed = [_relative_path(item) for item in claimed]
    except (TypeError, ValueError) as exc:
        raise schemas.SchemaError(str(exc)) from exc
    if len(set(normalized_patterns)) != len(normalized_patterns):
        raise schemas.SchemaError("attempt evidence manifest has duplicate projection patterns")
    if len(set(normalized_claimed)) != len(normalized_claimed):
        raise schemas.SchemaError("attempt evidence manifest has duplicate claimed paths")
    seen_paths: set[str] = set()
    indexed_claims: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise schemas.SchemaError(f"attempt evidence manifest artifact {index} must be an object")
        schemas.require_fields(
            artifact, frozenset({"path", "role", "change", "claimed_evidence"}),
            kind=f"attempt evidence manifest artifact {index}",
        )
        if not isinstance(artifact["path"], str):
            raise schemas.SchemaError(f"attempt evidence manifest artifact {index}.path must be str")
        try:
            relative = _relative_path(artifact["path"])
        except (TypeError, ValueError) as exc:
            raise schemas.SchemaError(str(exc)) from exc
        if relative in seen_paths:
            raise schemas.SchemaError(f"attempt evidence manifest has duplicate artifact path: {relative}")
        seen_paths.add(relative)
        if artifact.get("role") not in {"mutable_projection", "immutable_artifact"}:
            raise schemas.SchemaError(f"attempt evidence manifest artifact {index} has invalid role")
        if artifact.get("change") not in {"added", "modified", "deleted", "unchanged"}:
            raise schemas.SchemaError(f"attempt evidence manifest artifact {index} has invalid change")
        if not isinstance(artifact.get("claimed_evidence"), bool):
            raise schemas.SchemaError(
                f"attempt evidence manifest artifact {index}.claimed_evidence must be bool"
            )
        if artifact["claimed_evidence"]:
            indexed_claims.add(relative)
        change = artifact["change"]
        required_metadata = (
            ("after",) if change == "added" else
            ("before",) if change == "deleted" else
            ("before", "after")
        )
        for field in required_metadata:
            metadata = artifact.get(field)
            if not isinstance(metadata, dict):
                raise schemas.SchemaError(
                    f"attempt evidence manifest artifact {index}.{field} must be an object"
                )
            if metadata.get("kind") == "file":
                digest = metadata.get("sha256")
                size = metadata.get("size")
                if (
                    not isinstance(digest, str) or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest)
                    or isinstance(size, bool) or not isinstance(size, int) or size < 0
                ):
                    raise schemas.SchemaError(
                        f"attempt evidence manifest artifact {index}.{field} has invalid file metadata"
                    )
            elif metadata.get("kind") == "symlink":
                if not isinstance(metadata.get("target"), str):
                    raise schemas.SchemaError(
                        f"attempt evidence manifest artifact {index}.{field} has invalid symlink metadata"
                    )
            else:
                raise schemas.SchemaError(
                    f"attempt evidence manifest artifact {index}.{field} has invalid metadata kind"
                )
    if indexed_claims != set(normalized_claimed):
        raise schemas.SchemaError("attempt evidence manifest claimed evidence index mismatch")
    content = dict(value)
    expected = str(content.pop("content_sha256", ""))
    if (
        len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected)
        or _json_sha256(content) != expected
    ):
        raise schemas.SchemaError("attempt evidence manifest content hash mismatch")


def load_attempt_manifest(path: Path | str) -> dict[str, Any]:
    """Strictly load a current-schema evidence manifest."""
    return schemas.validate_loaded(
        path, kind="attempt evidence manifest", current=SCHEMA_VERSION,
        validator=_validate_manifest_schema,
    )


def _validate_receipt_schema(value: dict[str, Any]) -> None:
    schemas.require_fields(value, frozenset({
        "schema_version", "kind", "attempt_id", "checked_at", "manifest_path",
        "manifest_file_sha256", "manifest_content_hash_valid", "workspace", "status",
        "errors", "artifact_count", "claimed_evidence_count", "mutable_projection_count", "checks",
    }), kind="evidence receipt")
    if value.get("kind") != "proof-factory-evidence-receipt":
        raise schemas.SchemaError(f"invalid evidence receipt kind: {value.get('kind')!r}")
    attempt_id = schemas.require_type(value, "attempt_id", str, kind="evidence receipt")
    if not _SAFE_ID.fullmatch(attempt_id):
        raise schemas.SchemaError(f"invalid evidence receipt attempt_id: {attempt_id!r}")
    for field in ("checked_at", "manifest_path", "workspace"):
        if not schemas.require_type(value, field, str, kind="evidence receipt"):
            raise schemas.SchemaError(f"evidence receipt.{field} must be nonempty")
    if value.get("status") not in {"valid", "invalid"}:
        raise schemas.SchemaError(f"invalid evidence receipt status: {value.get('status')!r}")
    if not isinstance(value.get("manifest_content_hash_valid"), bool):
        raise schemas.SchemaError("evidence receipt.manifest_content_hash_valid must be bool")
    for field in ("errors", "checks"):
        schemas.require_type(value, field, list, kind="evidence receipt")
    if not all(isinstance(error, str) and error for error in value["errors"]):
        raise schemas.SchemaError("evidence receipt.errors must contain nonempty strings")
    for field in ("artifact_count", "claimed_evidence_count", "mutable_projection_count"):
        count = schemas.require_type(value, field, int, kind="evidence receipt")
        if count < 0:
            raise schemas.SchemaError(f"evidence receipt.{field} must be nonnegative")
    if value["artifact_count"] != len(value["checks"]):
        raise schemas.SchemaError("evidence receipt artifact_count mismatch")
    claimed_count = 0
    mutable_count = 0
    immutable_valid = True
    for index, check in enumerate(value["checks"]):
        if not isinstance(check, dict):
            raise schemas.SchemaError(f"evidence receipt check {index} must be an object")
        schemas.require_fields(
            check,
            frozenset({"path", "role", "change", "claimed_evidence", "scope_valid", "exists", "hash_matches", "valid"}),
            kind=f"evidence receipt check {index}",
        )
        if check.get("role") not in {"mutable_projection", "immutable_artifact"}:
            raise schemas.SchemaError(f"evidence receipt check {index} has invalid role")
        if not isinstance(check.get("path"), str):
            raise schemas.SchemaError(f"evidence receipt check {index}.path must be str")
        try:
            _relative_path(check["path"])
        except ValueError as exc:
            raise schemas.SchemaError(str(exc)) from exc
        if check.get("change") not in {"added", "modified", "deleted", "unchanged"}:
            raise schemas.SchemaError(f"evidence receipt check {index} has invalid change")
        for field in ("claimed_evidence", "scope_valid", "exists", "valid"):
            if not isinstance(check.get(field), bool):
                raise schemas.SchemaError(f"evidence receipt check {index}.{field} must be bool")
        if check.get("hash_matches") is not None and not isinstance(check.get("hash_matches"), bool):
            raise schemas.SchemaError(f"evidence receipt check {index}.hash_matches must be bool or null")
        claimed_count += int(check["claimed_evidence"])
        mutable_count += int(check["role"] == "mutable_projection")
        if check["role"] == "immutable_artifact":
            immutable_valid = immutable_valid and check["valid"]
    if value["claimed_evidence_count"] != claimed_count:
        raise schemas.SchemaError("evidence receipt claimed_evidence_count mismatch")
    if value["mutable_projection_count"] != mutable_count:
        raise schemas.SchemaError("evidence receipt mutable_projection_count mismatch")
    manifest_hash = schemas.require_type(value, "manifest_file_sha256", str, kind="evidence receipt")
    if len(manifest_hash) != 64 or any(char not in "0123456789abcdef" for char in manifest_hash):
        raise schemas.SchemaError("evidence receipt.manifest_file_sha256 must be lowercase SHA-256")
    if value["status"] == "valid" and (
        value["errors"] or not value["manifest_content_hash_valid"] or not immutable_valid
    ):
        raise schemas.SchemaError("valid evidence receipt contains errors or an invalid manifest hash")


def load_evidence_receipt(path: Path | str) -> dict[str, Any]:
    """Strictly load a current-schema evidence receipt."""
    return schemas.validate_loaded(
        path, kind="evidence receipt", current=SCHEMA_VERSION,
        validator=_validate_receipt_schema,
    )


def capture_workspace_snapshot(workspace: Path | str) -> dict[str, dict[str, Any]]:
    """Hash every regular workspace file; there is intentionally no file cap.

    Symlinks are represented but not followed or hashed.  A claimed symlink is
    rejected when the attempt manifest is created.
    """
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise ValueError(f"workspace is not a directory: {root}")
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = {"kind": "symlink", "target": os.readlink(path)}
        elif path.is_file():
            snapshot[relative] = {
                "kind": "file",
                "sha256": _sha256(path),
                "size": path.stat().st_size,
            }
    return snapshot


def create_attempt_manifest(
    workspace: Path | str,
    attempt_id: str,
    before_snapshot: Mapping[str, Mapping[str, Any]],
    *,
    claimed_evidence_paths: Iterable[str | os.PathLike[str]] = (),
    mutable_projection_patterns: Iterable[str] = (),
    manifest_root: Path | str | None = None,
    created_at: str | None = None,
) -> Path:
    """Create one immutable delta manifest and return its path.

    The manifest includes all added, modified, and deleted paths, and also every
    claimed evidence file even when that file predated the attempt.  Creating a
    second manifest for the same attempt is an error rather than an overwrite.
    """
    if not _SAFE_ID.fullmatch(attempt_id):
        raise ValueError(f"invalid attempt id: {attempt_id}")
    root = Path(workspace).resolve()
    after = capture_workspace_snapshot(root)
    before = {_relative_path(key): dict(value) for key, value in before_snapshot.items()}
    claimed = tuple(sorted({_relative_path(path) for path in claimed_evidence_paths}))
    patterns = tuple(sorted({_relative_path(pattern) for pattern in mutable_projection_patterns}))

    claimed_metadata: dict[str, dict[str, Any]] = {}
    for relative in claimed:
        if _is_mutable(relative, patterns):
            raise ValueError(f"mutable projection cannot be claimed as evidence: {relative}")
        path = _scoped_file(root, relative)
        if not path.is_file():
            raise ValueError(f"claimed evidence file does not exist: {relative}")
        claimed_metadata[relative] = after[relative]

    changed = {
        relative
        for relative in set(before) | set(after)
        if before.get(relative) != after.get(relative)
    }
    included = sorted(changed | set(claimed))
    artifacts: list[dict[str, Any]] = []
    for relative in included:
        old = before.get(relative)
        new = after.get(relative)
        if old is None:
            change = "added"
        elif new is None:
            change = "deleted"
        elif old != new:
            change = "modified"
        else:
            change = "unchanged"
        role = "mutable_projection" if _is_mutable(relative, patterns) else "immutable_artifact"
        row: dict[str, Any] = {
            "path": relative,
            "role": role,
            "change": change,
            "claimed_evidence": relative in claimed_metadata,
        }
        if old is not None:
            row["before"] = old
        if new is not None:
            row["after"] = new
        artifacts.append(row)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "proof-factory-attempt-delta-manifest",
        "attempt_id": attempt_id,
        "created_at": created_at or _now_iso(),
        "workspace": str(root),
        "mutable_projection_patterns": list(patterns),
        "claimed_evidence_paths": list(claimed),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    manifest["content_sha256"] = _json_sha256(manifest)

    parent = Path(manifest_root).resolve() if manifest_root else root.parent / "evidence"
    parent.mkdir(parents=True, exist_ok=True)
    attempt_dir = parent / attempt_id
    attempt_dir.mkdir(mode=0o755)  # exist_ok=False is the immutability guard.
    destination = attempt_dir / "delta-manifest.json"
    try:
        with destination.open("x") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        destination.chmod(0o444)
    except Exception:
        try:
            attempt_dir.rmdir()
        except OSError:
            pass
        raise
    return destination


def validate_attempt_manifest(
    manifest_path: Path | str,
    *,
    workspace: Path | str | None = None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    """Validate manifest integrity and every artifact against the live workspace."""
    path = Path(manifest_path).resolve()
    manifest = load_attempt_manifest(path)
    root = Path(workspace or manifest.get("workspace", "")).resolve()
    errors: list[str] = []
    expected_content_hash = str(manifest.get("content_sha256") or "")
    content = dict(manifest)
    content.pop("content_sha256", None)
    content_hash_valid = bool(expected_content_hash) and _json_sha256(content) == expected_content_hash
    if not content_hash_valid:
        errors.append("manifest content hash mismatch")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported schema version: {manifest.get('schema_version')}")
    if workspace is not None and root != Path(str(manifest.get("workspace") or "")).resolve():
        errors.append("validation workspace differs from manifest workspace")

    checks: list[dict[str, Any]] = []
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
        errors.append("manifest artifacts must be a list")
    if manifest.get("artifact_count") != len(artifacts):
        errors.append("manifest artifact count mismatch")
    raw_patterns = manifest.get("mutable_projection_patterns")
    if not isinstance(raw_patterns, list):
        raw_patterns = []
        errors.append("manifest mutable projection patterns must be a list")
    try:
        patterns = tuple(_relative_path(value) for value in raw_patterns)
    except ValueError as exc:
        patterns = ()
        errors.append(str(exc))
    raw_claimed = manifest.get("claimed_evidence_paths")
    if not isinstance(raw_claimed, list):
        raw_claimed = []
        errors.append("manifest claimed evidence paths must be a list")
    try:
        claimed_paths = {_relative_path(value) for value in raw_claimed}
    except ValueError as exc:
        claimed_paths = set()
        errors.append(str(exc))
    seen_paths: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append("manifest contains a non-object artifact")
            continue
        relative = str(artifact.get("path") or "")
        role = str(artifact.get("role") or "")
        change = str(artifact.get("change") or "")
        check: dict[str, Any] = {
            "path": relative,
            "role": role,
            "change": change,
            "claimed_evidence": bool(artifact.get("claimed_evidence")),
            "scope_valid": False,
            "exists": False,
            "hash_matches": None,
            "valid": False,
        }
        try:
            relative = _relative_path(relative)
            target = _scoped_file(root, relative)
            check["scope_valid"] = True
        except ValueError as exc:
            errors.append(str(exc))
            checks.append(check)
            continue

        if relative in seen_paths:
            errors.append(f"duplicate artifact path: {relative}")
        seen_paths.add(relative)
        expected_role = "mutable_projection" if _is_mutable(relative, patterns) else "immutable_artifact"
        if role != expected_role:
            errors.append(f"artifact role does not match projection policy: {relative}")
        if bool(artifact.get("claimed_evidence")) != (relative in claimed_paths):
            errors.append(f"claimed evidence index mismatch: {relative}")
        if change not in {"added", "modified", "deleted", "unchanged"}:
            errors.append(f"invalid artifact change type: {relative}")

        expected = artifact.get("after") if isinstance(artifact.get("after"), dict) else None
        if change == "deleted":
            check["exists"] = target.exists()
            check["valid"] = not target.exists()
            if target.exists() and role != "mutable_projection":
                errors.append(f"deleted immutable artifact reappeared: {relative}")
        elif target.is_file() and not target.is_symlink() and expected and expected.get("kind") == "file":
            check["exists"] = True
            check["actual_sha256"] = _sha256(target)
            check["expected_sha256"] = expected.get("sha256")
            check["hash_matches"] = check["actual_sha256"] == check["expected_sha256"]
            check["valid"] = bool(check["hash_matches"])
            if not check["valid"] and role != "mutable_projection":
                errors.append(f"immutable artifact hash mismatch: {relative}")
        else:
            if role != "mutable_projection":
                errors.append(f"immutable artifact is unavailable: {relative}")

        if artifact.get("claimed_evidence") and role == "mutable_projection":
            check["valid"] = False
            errors.append(f"claimed evidence is a mutable projection: {relative}")
        checks.append(check)

    for relative in sorted(claimed_paths - seen_paths):
        errors.append(f"claimed evidence missing from artifact ledger: {relative}")

    immutable_checks = [row for row in checks if row["role"] != "mutable_projection"]
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "kind": "proof-factory-evidence-receipt",
        "attempt_id": manifest.get("attempt_id"),
        "checked_at": checked_at or _now_iso(),
        "manifest_path": str(path),
        "manifest_file_sha256": _sha256(path),
        "manifest_content_hash_valid": content_hash_valid,
        "workspace": str(root),
        "status": "valid" if not errors and all(row["valid"] for row in immutable_checks) else "invalid",
        "errors": errors,
        "artifact_count": len(checks),
        "claimed_evidence_count": sum(bool(row["claimed_evidence"]) for row in checks),
        "mutable_projection_count": sum(row["role"] == "mutable_projection" for row in checks),
        "checks": checks,
    }
    return receipt


def create_evidence_receipt(
    manifest_path: Path | str,
    *,
    workspace: Path | str | None = None,
    receipt_path: Path | str | None = None,
    checked_at: str | None = None,
) -> Path:
    """Validate an attempt and exclusively write its machine-readable receipt."""
    manifest = Path(manifest_path).resolve()
    receipt = validate_attempt_manifest(manifest, workspace=workspace, checked_at=checked_at)
    destination = Path(receipt_path).resolve() if receipt_path else manifest.parent / "evidence-receipt.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    destination.chmod(0o444)
    return destination
