"""Typed, fail-closed access to Proof Factory's non-secret configuration.

Configuration is deliberately read on every call.  Tests, operator tooling, and
long-lived review processes can therefore change an environment value without
having to reload this module.  Secret credentials remain in their existing,
service-scoped credential file and are not listed or validated here.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Final
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when an explicitly configured value is unsafe or malformed."""


_MISSING: Final = object()
_TRUE: Final = frozenset({"1", "true", "yes", "on"})
_FALSE: Final = frozenset({"0", "false", "no", "off"})
_HEX_32 = re.compile(r"[0-9a-fA-F]{32}")
_HEX_40 = re.compile(r"[0-9a-fA-F]{40}")
_HEX_64 = re.compile(r"[0-9a-fA-F]{64}")


def _raw(name: str, default: object = _MISSING) -> str:
    value = os.environ.get(name)
    if value is None:
        if default is _MISSING:
            raise ConfigurationError(f"required configuration is missing: {name}")
        value = str(default)
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ConfigurationError(f"{name} contains a forbidden control character")
    return value


def get_text(
    name: str,
    default: str | None = None,
    *,
    allow_empty: bool = False,
    choices: set[str] | frozenset[str] | None = None,
) -> str:
    """Read a string value now, optionally restricting it to exact choices."""
    value = _raw(name, default if default is not None else _MISSING).strip()
    if not value and not allow_empty:
        raise ConfigurationError(f"{name} must not be empty")
    if choices is not None and value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ConfigurationError(f"{name} must be one of: {allowed}")
    return value


def get_bool(name: str, default: bool) -> bool:
    """Read a strict boolean; unrecognised spellings fail closed."""
    value = _raw(name, "true" if default else "false").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigurationError(f"{name} must be a boolean (true/false, yes/no, on/off, or 1/0)")


def get_int(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Read a base-ten integer with explicit inclusive bounds."""
    raw = _raw(name, default).strip()
    if not re.fullmatch(r"[+-]?\d+", raw):
        raise ConfigurationError(f"{name} must be a base-ten integer")
    value = int(raw, 10)
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{name} must be at most {maximum}")
    return value


def get_path(name: str, default: str | Path, *, absolute: bool = True) -> Path:
    """Read a filesystem path without requiring it to exist."""
    path = Path(get_text(name, str(default)))
    if absolute and not path.is_absolute():
        raise ConfigurationError(f"{name} must be an absolute path")
    return path


def get_https_url(name: str, default: str = "", *, allow_empty: bool = False) -> str:
    """Read an HTTPS endpoint, rejecting credentials and non-network URLs."""
    value = get_text(name, default, allow_empty=allow_empty)
    if not value and allow_empty:
        return ""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ConfigurationError(f"{name} must be an HTTPS URL without embedded credentials")
    return value.rstrip("/")


VALIDATION_PROFILES = frozenset({
    "all", "capacity", "intake", "lab", "lane", "publish", "review", "runtime", "scout", "strategy", "watchdog",
})


def validate_environment(profile: str = "all") -> None:
    """Validate settings consumed by one service profile, isolating optional integrations."""
    if profile not in VALIDATION_PROFILES:
        raise ConfigurationError(f"unknown validation profile: {profile}")
    get_path("PROOF_FACTORY_ROOT", "/root/proof-factory")
    if profile in {"all", "capacity", "lab", "lane", "watchdog"}:
        get_path("PROOF_FACTORY_CACHE_DIR", "/root/.cache/proof-factory")
    if profile in {"all", "lane"}:
        get_path("PROOF_USAGE_CACHE_PATH", "/root/project-factory/state/usage_cache.json")
        get_bool("PROOF_OPERATOR_RUN", False)
        get_text("PROOF_FACTORY_PUBLISH_CMD", "", allow_empty=True)
    if profile in {"all", "lane", "scout", "strategy"}:
        get_path("CODEX_BIN", "/root/.local/bin/codex")
        get_text(
            "PROOF_CODEX_SANDBOX", "danger-full-access",
            choices={"read-only", "workspace-write", "danger-full-access"},
        )
        get_bool("PHOENIX_ENABLED", False)
        get_bool("PHOENIX_CAPTURE_TEXT", True)
        get_int("PHOENIX_TEXT_LIMIT", 6000, minimum=0, maximum=1_000_000)
        endpoint = get_https_url("PHOENIX_ENDPOINT", "", allow_empty=True)
        if get_bool("PHOENIX_ENABLED", False) and not endpoint:
            raise ConfigurationError("PHOENIX_ENDPOINT is required when PHOENIX_ENABLED is true")
        get_text("PHOENIX_PROJECT", "proof-factory")
    if profile in {"all", "lane"}:
        for name, default, maximum in (
            ("PROOF_EASY_TIMEOUT_SEC", 3600, 86_400),
            ("PROOF_HARD_TIMEOUT_SEC", 7200, 86_400),
            ("PROOF_EASY_DELEGATE_TIMEOUT_SEC", 600, 86_400),
            ("PROOF_HARD_DELEGATE_TIMEOUT_SEC", 1200, 86_400),
            ("PROOF_JSON_REPAIR_TIMEOUT_SEC", 180, 3600),
        ):
            get_int(name, default, minimum=1, maximum=maximum)
    if profile in {"all", "scout"}:
        get_int("PROOF_SCOUT_TIMEOUT_SEC", 3600, minimum=1, maximum=86_400)
    if profile in {"all", "strategy"}:
        get_int("PROOF_STRATEGY_TIMEOUT_SEC", 3600, minimum=1, maximum=86_400)
    if profile in {"all", "intake", "lab", "lane", "publish", "scout", "strategy"}:
        get_text("PROOF_REPO_GITHUB_OWNER", "ctkrug")
        get_text("PROOF_REPO_GIT_NAME", "ctkrug")
        get_text("PROOF_REPO_GIT_EMAIL", "ctkrug4501@gmail.com")
        get_int("PROOF_REPO_MAX_FILE_BYTES", 50 * 1024 * 1024, minimum=1024, maximum=10 * 1024**3)
    if profile in {"all", "review", "runtime"}:
        namespace = get_text("PROOF_RUNTIME_KV_NAMESPACE_ID", "", allow_empty=True)
        if namespace and not _HEX_32.fullmatch(namespace):
            raise ConfigurationError("PROOF_RUNTIME_KV_NAMESPACE_ID must be a 32-digit hexadecimal id")
    if profile in {"all", "lane"}:
        get_path("ELAN_HOME", "/root/.cache/proof-factory/lean/elan")
        revision = get_text("PROOF_FACTORY_FORMAL_CONJECTURES_REVISION", "", allow_empty=True)
        if revision and not _HEX_40.fullmatch(revision):
            raise ConfigurationError("PROOF_FACTORY_FORMAL_CONJECTURES_REVISION must be a full 40-digit commit id")
        manifest = get_text("PROOF_FACTORY_FORMAL_CONJECTURES_MANIFEST_SHA256", "", allow_empty=True)
        if manifest and not _HEX_64.fullmatch(manifest):
            raise ConfigurationError("PROOF_FACTORY_FORMAL_CONJECTURES_MANIFEST_SHA256 must be a SHA-256 digest")
        get_int("PROOF_FACTORY_LEAN_BOOTSTRAP_MIN_FREE_KIB", 8 * 1024 * 1024, minimum=1024)
        get_int("LEAN_NUM_THREADS", 1, minimum=1, maximum=64)
    if profile in {"all", "watchdog"}:
        get_bool("PROOF_EASY_EXPECTED", True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    profile = "all"
    if args[:1] == ["validate"]:
        args = args[1:]
    if args[:1] == ["--profile"] and len(args) == 2:
        profile = args[1]
        args = []
    if args:
        print("usage: python -m proof_factory.config [validate] [--profile PROFILE]", file=sys.stderr)
        return 2
    try:
        validate_environment(profile)
    except ConfigurationError as exc:
        print(f"invalid Proof Factory configuration: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
