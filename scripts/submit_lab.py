#!/usr/bin/env python3
"""Submit a bounded, shell-free Proof Factory simulation-lab job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proof_factory import lab  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--expected-signal", required=True)
    parser.add_argument("--source-url", action="append", default=[])
    parser.add_argument("--segment-seconds", type=int, default=3600)
    parser.add_argument("--max-segments", type=int, default=1)
    parser.add_argument("--memory-mb", type=int, default=512)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--checkpoint-path", default="")
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.argv)
    if command[:1] == ["--"]:
        command = command[1:]
    result = lab.submit({
        "problem_id": args.problem, "name": args.name, "hypothesis": args.hypothesis,
        "expected_signal": args.expected_signal, "source_urls": args.source_url,
        "segment_seconds": args.segment_seconds, "max_segments": args.max_segments,
        "memory_mb": args.memory_mb, "seed": args.seed,
        "checkpoint_path": args.checkpoint_path, "command": command,
    })
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
