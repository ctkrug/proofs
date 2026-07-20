#!/usr/bin/env python3
"""Run one bounded experiment without a shell and emit a reproducibility record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--name", required=True)
    result.add_argument("--hypothesis", required=True)
    result.add_argument("--expected-signal", required=True)
    result.add_argument("--timeout", type=int, default=900)
    result.add_argument("--seed", type=int, default=0)
    result.add_argument("--memory-mb", type=int, default=2048)
    result.add_argument("--source-url", action="append", default=[])
    result.add_argument("--output-root", type=Path, default=Path(".proof-experiments"))
    result.add_argument("command", nargs=argparse.REMAINDER)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        raise SystemExit("an argv command is required after --")
    maximum = int(os.environ.get("PROOF_EXPERIMENT_MAX_SECONDS", "10800"))
    if args.timeout < 1 or args.timeout > maximum:
        raise SystemExit(f"timeout must be between 1 and {maximum} seconds")
    if args.memory_mb < 64 or args.memory_mb > 32768:
        raise SystemExit("memory-mb must be between 64 and 32768")

    experiment_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    output_dir = args.output_root.resolve() / experiment_id
    output_dir.mkdir(parents=True, exist_ok=False)
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    started_at = now_iso()
    start = time.monotonic()
    timed_out = False
    env_keys = {"HOME", "PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    env = {key: value for key, value in os.environ.items() if key in env_keys}
    env.update({
        "PYTHONHASHSEED": str(args.seed),
        "PROOF_EXPERIMENT_SEED": str(args.seed),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    })
    source_hashes: dict[str, str] = {}
    for value in command:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        try:
            resolved = candidate.resolve()
            if resolved.is_file() and resolved.stat().st_size <= 50 * 1024 * 1024:
                source_hashes[str(resolved)] = digest(resolved)
        except OSError:
            continue
    for name in ("requirements.txt", "pyproject.toml", "uv.lock", "poetry.lock", "Cargo.lock", "lake-manifest.json"):
        candidate = Path.cwd() / name
        if candidate.is_file():
            source_hashes[str(candidate.resolve())] = digest(candidate)
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path.cwd(), env=env, text=True,
            stderr=subprocess.DEVNULL, timeout=5,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        git_commit = ""

    def limits() -> None:
        memory_bytes = args.memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    returncode = 124
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                command,
                cwd=Path.cwd(),
                env=env,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                preexec_fn=limits if sys.platform.startswith("linux") else None,
            )
            returncode = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if process is not None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)

    record = {
        "schema_version": 1,
        "id": experiment_id,
        "name": args.name,
        "hypothesis": args.hypothesis,
        "expected_signal": args.expected_signal,
        "command": command,
        "cwd": str(Path.cwd()),
        "seed": args.seed,
        "timeout_seconds": args.timeout,
        "memory_limit_mb": args.memory_mb,
        "memory_limit_enforced": sys.platform.startswith("linux"),
        "started_at": started_at,
        "finished_at": now_iso(),
        "duration_seconds": round(time.monotonic() - start, 3),
        "returncode": returncode,
        "timed_out": timed_out,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git_commit": git_commit,
        "source_urls": args.source_url,
        "input_artifacts": source_hashes,
        "peak_child_memory_rusage": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "peak_child_memory_unit": "bytes" if sys.platform == "darwin" else "kilobytes",
        "artifacts": {
            "stdout.txt": digest(stdout_path),
            "stderr.txt": digest(stderr_path),
        },
    }
    metadata_path = output_dir / "experiment.json"
    metadata_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"experiment_dir": str(output_dir), **record}, indent=2, ensure_ascii=False))
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
