"""Host-capacity admission and conservative cleanup for Proof Factory.

Only disposable build residue is eligible for automatic cleanup. Research
records, workspaces, completed toolchains, and published artifacts are not.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from . import config


ROOT_MIN_FREE_BYTES = 8 * 1024**3
CACHE_MIN_FREE_BYTES = 1 * 1024**3
MEMORY_MIN_FREE_BYTES = {"easy": 900 * 1024**2, "hard": 1200 * 1024**2}
TMP_MAX_AGE_SECONDS = 6 * 3600
TMP_EXCLUSIONS = {".X11-unix", ".ICE-unix", ".XIM-unix", ".font-unix"}


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def _available_memory_bytes() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _cache_root() -> Path:
    return config.get_path("PROOF_FACTORY_CACHE_DIR", "/root/.cache/proof-factory")


def _existing_path(path: Path) -> Path:
    """Find a usable filesystem probe without creating anything during checks."""
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _cache_probe() -> Path:
    """Probe the actual build-cache target, including a symlinked subcache."""
    cache = _cache_root()
    for name in ("formal-conjectures", "lean"):
        candidate = cache / name
        if candidate.exists():
            return candidate
    return _existing_path(cache)


def _lab_compute_active() -> bool:
    """Return whether checkpointed lab compute is queued or in a segment.

    The easy lane may invoke a cache-heavy Lean build.  It yields while the
    priority lab worker owns compute, but completed jobs awaiting a human/model
    review do not reserve the host.
    """
    root = config.get_path("PROOF_FACTORY_ROOT", "/root/proof-factory")
    research = root / "research"
    try:
        if next(research.glob("*/workspace/lab-queue/*.json"), None) is not None:
            return True
    except OSError:
        pass
    jobs = root / "state" / "labs" / "jobs"
    try:
        for path in jobs.glob("*.json"):
            try:
                if json.loads(path.read_text()).get("status") == "running":
                    return True
            except (OSError, ValueError, TypeError):
                continue
    except OSError:
        pass
    return False


def _tree_size(path: Path) -> int:
    try:
        if path.is_file() or path.is_symlink():
            return path.lstat().st_size
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink())
    except OSError:
        return 0


def cleanup(*, now: float | None = None) -> dict[str, Any]:
    """Remove stale job temp trees and incomplete elan installs only."""
    now = time.time() if now is None else now
    removed: list[str] = []
    reclaimed = 0
    for entry in _cleanup_candidates(Path("/tmp"), now):
        try:
            size = _tree_size(entry)
            shutil.rmtree(entry) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
            removed.append(str(entry))
            reclaimed += size
        except OSError:
            continue
    elan_home = config.get_path("ELAN_HOME", _cache_root() / "lean" / "elan")
    try:
        incomplete = list((elan_home / "toolchains").glob("*.tmp"))
    except OSError:
        incomplete = []
    for entry in incomplete:
        try:
            size = _tree_size(entry)
            shutil.rmtree(entry) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
            removed.append(str(entry))
            reclaimed += size
        except OSError:
            continue
    return {"removed": removed, "reclaimed_bytes": reclaimed, "cleaned_at": now}


def _cleanup_candidates(tmp: Path, now: float) -> list[Path]:
    try:
        entries = list(tmp.iterdir())
    except OSError:
        return []
    result = []
    for entry in entries:
        if entry.name in TMP_EXCLUSIONS or entry.name.startswith(("systemd-private-", "snap-private-tmp")):
            continue
        try:
            if now - entry.stat().st_mtime >= TMP_MAX_AGE_SECONDS:
                result.append(entry)
        except OSError:
            continue
    return result


def admission(lane: str, *, run_cleanup: bool = True, require_cache: bool = True) -> dict[str, Any]:
    if lane not in MEMORY_MIN_FREE_BYTES:
        raise ValueError("lane must be easy or hard")
    cleanup_result = cleanup() if run_cleanup else None
    root_free = _free_bytes(Path("/"))
    cache_free = _free_bytes(_cache_probe())
    memory_free = _available_memory_bytes()
    reasons: list[str] = []
    if root_free < ROOT_MIN_FREE_BYTES:
        reasons.append(f"root disk reserve is below 8 GiB ({root_free / 1024**3:.1f} GiB free)")
    if require_cache and cache_free < CACHE_MIN_FREE_BYTES:
        reasons.append(f"build-cache volume reserve is below 1 GiB ({cache_free / 1024**3:.1f} GiB free)")
    required_memory = MEMORY_MIN_FREE_BYTES[lane]
    if memory_free < required_memory:
        reasons.append(f"available memory is below the {lane} reserve ({memory_free / 1024**2:.0f} MiB free)")
    lab_compute_active = lane == "easy" and _lab_compute_active()
    if lab_compute_active:
        reasons.append("priority checkpointed lab compute is active; cache-heavy easy work will resume at its review boundary")
    return {"allowed": not reasons, "lane": lane, "reasons": reasons,
            "cache_required": require_cache,
            "root_free_bytes": root_free, "cache_free_bytes": cache_free,
            "memory_available_bytes": memory_free, "memory_required_bytes": required_memory,
            "lab_compute_active": lab_compute_active,
            "cleanup": cleanup_result}
