#!/usr/bin/env python3
"""Submit a checkpointed, shell-free Proof Factory experiment tranche."""

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
    parser.add_argument("--decision-value", required=True)
    parser.add_argument("--efficiency-design", required=True, help="JSON efficiency-design report")
    parser.add_argument("--source-url", action="append", default=[])
    parser.add_argument("--segment-seconds", type=int, default=3600)
    parser.add_argument("--max-segments", type=int, default=1)
    parser.add_argument("--memory-mb", type=int, default=512)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--checkpoint-path", default="")
    parser.add_argument("--progress-path", default="")
    parser.add_argument(
        "--mutable-argv-path", action="append", default=[],
        help="Exact workspace-relative argv path mutated by the job; repeat as needed",
    )
    parser.add_argument(
        "--input-sha256", default="",
        help="JSON object of immutable workspace-relative input hashes (required with mutable argv paths)",
    )
    parser.add_argument("--pilot-segments", type=int, default=1)
    parser.add_argument("--review-every-segments", type=int, default=1)
    parser.add_argument("--min-throughput", type=float, default=0.0)
    parser.add_argument("--max-artifact-growth-bytes", type=int, default=0)
    parser.add_argument("--no-correctness-gate", action="store_true")
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.argv)
    if command[:1] == ["--"]:
        command = command[1:]
    efficiency = json.loads(Path(args.efficiency_design).read_text())
    request = {
        "problem_id": args.problem, "name": args.name, "hypothesis": args.hypothesis,
        "expected_signal": args.expected_signal, "decision_value": args.decision_value,
        "efficiency_design": efficiency, "source_urls": args.source_url,
        "segment_seconds": args.segment_seconds, "max_segments": args.max_segments,
        "memory_mb": args.memory_mb, "seed": args.seed,
        "checkpoint_path": args.checkpoint_path, "progress_path": args.progress_path,
        "pilot_segments": args.pilot_segments, "review_every_segments": args.review_every_segments,
        "continuation_thresholds": {
            "min_throughput_per_second": args.min_throughput,
            "max_artifact_growth_bytes": args.max_artifact_growth_bytes,
            "require_correctness_checks": not args.no_correctness_gate,
        }, "command": command,
    }
    if args.mutable_argv_path:
        request["mutable_argv_paths"] = args.mutable_argv_path
    if args.input_sha256:
        request["input_sha256"] = json.loads(Path(args.input_sha256).read_text())
    result = lab.submit(request)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
