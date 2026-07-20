"""Authenticated, repeatable source provisioning for research workspaces."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceBootstrap:
    problem_id: str
    url: str
    destination: str
    sha256: str
    byte_count: int
    record_count: int | None = None


BOOTSTRAPS = {
    "ramsey-r55": SourceBootstrap(
        problem_id="ramsey-r55",
        url="https://users.cecs.anu.edu.au/~bdm/data/r55_42some.g6",
        destination="sources/r55_42some.g6",
        sha256="067902e853d87b49bcef0d1d4c0e3bbadd238ee18bc65341b079a3ca4780eccb",
        byte_count=47_888,
        record_count=328,
    ),
}


class ResourceProvisionError(RuntimeError):
    """A pinned, required research input could not be acquired or authenticated."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _headers(raw: str) -> dict[str, str]:
    """Return the final HTTP response headers from curl's redirect-aware dump."""
    blocks = [block for block in raw.replace("\r\n", "\n").split("\n\n") if block.startswith("HTTP/")]
    if not blocks:
        return {}
    result: dict[str, str] = {}
    for line in blocks[-1].splitlines()[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip().lower()] = value.strip()
    return result


def _valid_existing(target: Path, spec: SourceBootstrap) -> bool:
    if not target.is_file() or target.stat().st_size != spec.byte_count or _sha256(target) != spec.sha256:
        return False
    if spec.record_count is not None:
        raw = target.read_bytes()
        if not raw.endswith(b"\n") or len(raw.splitlines()) != spec.record_count:
            return False
    return Path(str(target) + ".provenance.json").is_file()


def prepare(problem: dict[str, Any], workspace: Path) -> dict[str, Any] | None:
    """Place pinned source bytes and truthful retrieval metadata in *workspace*.

    This runs outside the model sandbox. The model gets a ready-to-check input
    rather than wasting an epoch on a known network restriction; a source is
    never admitted unless its frozen byte-level discriminator agrees.
    """
    spec = BOOTSTRAPS.get(str(problem.get("id") or ""))
    if spec is None:
        return None
    target = workspace / spec.destination
    target.parent.mkdir(parents=True, exist_ok=True)
    if _valid_existing(target, spec):
        return {"status": "cached", "path": str(target), "sha256": spec.sha256}

    curl = shutil.which("curl")
    if curl is None:
        raise ResourceProvisionError("curl is unavailable for the required source bootstrap")
    with tempfile.TemporaryDirectory(prefix="proof-source-") as raw_dir:
        temporary = Path(raw_dir)
        body = temporary / "body"
        headers_path = temporary / "headers"
        command = [
            curl, "--fail", "--location", "--retry", "3", "--retry-all-errors",
            "--connect-timeout", "15", "--max-time", "120", "--silent", "--show-error",
            "--dump-header", str(headers_path), "--output", str(body), spec.url,
        ]
        completed = subprocess.run(command, text=True, capture_output=True, timeout=150)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[-800:]
            raise ResourceProvisionError(f"required source retrieval failed: {detail}")
        digest = _sha256(body)
        size = body.stat().st_size
        records = len(body.read_bytes().splitlines())
        if digest != spec.sha256 or size != spec.byte_count or (spec.record_count is not None and records != spec.record_count):
            raise ResourceProvisionError(
                f"required source failed frozen admission: sha256={digest}, bytes={size}, records={records}"
            )
        response_headers = _headers(headers_path.read_text(encoding="utf-8", errors="replace"))
        content_type = response_headers.get("content-type")
        inferred = not content_type
        if not content_type:
            # The ANU endpoint omits Content-Type. The graph6 syntax, LF format,
            # and frozen byte discriminator establish this as text data; the raw
            # response headers remain preserved below instead of being rewritten.
            content_type = "text/plain; inferred from validated graph6 record format (header absent)"
        shutil.copyfile(body, target)
        provenance = {
            "schema_version": 1,
            "source_authority": "authoritative_direct",
            "requested_url": spec.url,
            "final_url": spec.url,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "acquisition_method": "host-side curl with retries; frozen byte admission",
            "sha256": digest,
            "byte_count": size,
            "record_count": records,
            "content_type": content_type,
            "content_type_inferred": inferred,
            "response_headers": response_headers,
        }
        Path(str(target) + ".provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return {"status": "retrieved", "path": str(target), "sha256": spec.sha256}
