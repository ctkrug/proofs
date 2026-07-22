#!/usr/bin/env python3
"""Adversarial controls for both geometry-004 patch checkers.

Usage:
  python checkers/test_geometry_004_checkers.py V1.csv BASELINE_V2.csv CANDIDATE_V2.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import check_exact_geometry_004_patch_bytes as byte_checker
import verify_answerbench_geometry_004 as semantic_checker


def must_reject(label: str, action: object) -> None:
    try:
        action()  # type: ignore[operator]
    except AssertionError:
        return
    raise AssertionError(f"negative control unexpectedly accepted: {label}")


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    v1_path, baseline_path, candidate_path = map(Path, sys.argv[1:])
    v1 = semantic_checker.read_csv(v1_path)
    baseline = semantic_checker.read_csv(baseline_path)
    candidate = semantic_checker.read_csv(candidate_path)
    baseline_bytes = baseline_path.read_bytes()
    candidate_bytes = candidate_path.read_bytes()

    semantic_checker.verify(v1, baseline, candidate)
    byte_checker.verify(baseline_bytes, candidate_bytes)

    must_reject(
        "unchanged v2",
        lambda: semantic_checker.verify(v1, baseline, baseline),
    )

    changed_number_theory = [row.copy() for row in candidate]
    by_id = semantic_checker.index_by_id(changed_number_theory)
    by_id[semantic_checker.NUMBER_THEORY_ID][2] = "tampered"
    must_reject(
        "number_theory-048 changed",
        lambda: semantic_checker.verify(v1, baseline, changed_number_theory),
    )

    must_reject(
        "unrelated trailing byte",
        lambda: byte_checker.verify(baseline_bytes, candidate_bytes + b"\n"),
    )
    must_reject(
        "unquoted comma corrupts target arity",
        lambda: byte_checker.verify(
            baseline_bytes, candidate_bytes.replace(b'"4, 5"', b"4, 5", 1)
        ),
    )

    print("PASS: positive candidate accepted and four adversarial controls rejected")


if __name__ == "__main__":
    main()
