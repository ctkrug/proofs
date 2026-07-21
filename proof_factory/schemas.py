"""Shared fail-closed helpers for durable JSON schema boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping


class SchemaError(ValueError):
    """A durable record does not satisfy the schema claimed by its producer."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise SchemaError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json_object(path: Path | str, *, kind: str) -> dict[str, Any]:
    """Read one JSON object, rejecting missing files, invalid JSON, and duplicate keys."""
    source = Path(path)
    try:
        raw = source.read_text()
    except OSError as exc:
        raise SchemaError(f"cannot read {kind}: {source}: {exc}") from exc
    return parse_json_object(raw, kind=kind, source=str(source))


def parse_json_object(raw: str, *, kind: str, source: str = "inline") -> dict[str, Any]:
    """Parse one JSON object while rejecting duplicate keys and non-objects."""
    def reject_constant(token: str) -> None:
        raise SchemaError(f"non-finite JSON number: {token}")

    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, SchemaError) as exc:
        raise SchemaError(f"invalid {kind} JSON: {source}: {exc}") from exc
    return require_object(value, kind=kind)


def require_object(value: Any, *, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{kind} must be a JSON object")
    return value


def require_current_version(value: Mapping[str, Any], *, kind: str, current: int) -> int:
    version = value.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise SchemaError(f"{kind} schema_version must be an integer")
    if version != current:
        raise SchemaError(
            f"unsupported {kind} schema_version {version}; current schema_version is {current}"
        )
    return version


def require_migratable_version(
    value: Mapping[str, Any], *, kind: str, oldest: int, current: int,
) -> int:
    version = value.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise SchemaError(f"{kind} schema_version must be an integer")
    if not oldest <= version <= current:
        raise SchemaError(
            f"unsupported {kind} schema_version {version}; supported versions are {oldest}..{current}"
        )
    return version


def require_fields(value: Mapping[str, Any], fields: set[str] | frozenset[str], *, kind: str) -> None:
    missing = sorted(field for field in fields if field not in value)
    if missing:
        raise SchemaError(f"{kind} missing required fields: {', '.join(missing)}")


def require_type(value: Mapping[str, Any], field: str, expected: type | tuple[type, ...], *, kind: str) -> Any:
    item = value.get(field)
    # bool is an int subclass, but durable numeric and version fields should not accept it.
    if expected is int and isinstance(item, bool):
        raise SchemaError(f"{kind}.{field} must be int")
    if not isinstance(item, expected):
        if isinstance(expected, tuple):
            label = " or ".join(item_type.__name__ for item_type in expected)
        else:
            label = expected.__name__
        raise SchemaError(f"{kind}.{field} must be {label}")
    return item


def validate_loaded(
    path: Path | str,
    *,
    kind: str,
    current: int,
    validator: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    value = load_json_object(path, kind=kind)
    require_current_version(value, kind=kind, current=current)
    validator(value)
    return value
