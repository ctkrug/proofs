#!/usr/bin/env python3
"""Verify the proposed one-cell AnswerBench v2 correction.

Usage:
  python checkers/verify_answerbench_geometry_004.py V1.csv BASELINE_V2.csv CANDIDATE_V2.csv

The first two inputs must be the unmodified, commit-pinned upstream CSVs.  A
successful run means that both versions parse with the expected schema profile,
v1 independently supplies the corrected answer, and the candidate preserves
the v2 structure while changing only geometry-004's Short Answer from 45752 to
``4, 5``.  It also explicitly guards the current number_theory-048 answer.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


HEADER = ["Problem ID", "Problem", "Short Answer", "Category", "Subcategory", "Source"]
GEOMETRY_ID = "imo-bench-geometry-004"
NUMBER_THEORY_ID = "imo-bench-number_theory-048"
CURRENT_GEOMETRY_ANSWER = "45752"
CORRECTED_GEOMETRY_ANSWER = "4, 5"
CURRENT_NUMBER_THEORY_ANSWER = " $\\left\\{ (a,b):ab\\leq e^{3}\\right\\}$"
KNOWN_V2_ARITY_EXCEPTION = "imo-bench-algebra-036"


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0] != HEADER:
        raise AssertionError(f"{path}: header is not the expected six-column header")
    ids = [row[0] for row in rows[1:]]
    if len(ids) != len(set(ids)):
        raise AssertionError(f"{path}: Problem ID values must remain unique")
    return rows


def assert_schema_profile(rows: list[list[str]], *, version: str) -> None:
    """Check the released schema without normalizing its known v2 defect."""
    malformed = [(row[0], len(row)) for row in rows[1:] if len(row) != 6]
    expected = [] if version == "v1" else [(KNOWN_V2_ARITY_EXCEPTION, 5)]
    if malformed != expected:
        raise AssertionError(
            f"{version}: unexpected non-six-field records: {malformed}; expected {expected}"
        )


def index_by_id(rows: list[list[str]]) -> dict[str, list[str]]:
    return {row[0]: row for row in rows[1:]}


def verify(
    v1: list[list[str]], baseline: list[list[str]], candidate: list[list[str]]
) -> None:
    """Raise AssertionError unless candidate is the exact intended patch."""
    assert_schema_profile(v1, version="v1")
    assert_schema_profile(baseline, version="v2")
    assert_schema_profile(candidate, version="v2")
    old = index_by_id(v1)
    if len(old[GEOMETRY_ID]) != 6:
        raise AssertionError("v1 geometry-004 must have six CSV fields")
    if old[GEOMETRY_ID][2] != CORRECTED_GEOMETRY_ANSWER:
        raise AssertionError("v1 does not supply geometry-004 answer '4, 5'")
    if len(baseline) != len(candidate):
        raise AssertionError("candidate changes the number of CSV records")
    base, cand = index_by_id(baseline), index_by_id(candidate)
    if base.keys() != cand.keys():
        raise AssertionError("candidate changes the Problem ID set")
    if {key: len(value) for key, value in base.items()} != {
        key: len(value) for key, value in cand.items()
    }:
        raise AssertionError("candidate changes a record's CSV field count")
    if len(base[GEOMETRY_ID]) != 6 or len(cand[GEOMETRY_ID]) != 6:
        raise AssertionError("geometry-004 must retain all six CSV fields")
    if base[GEOMETRY_ID][2] != CURRENT_GEOMETRY_ANSWER:
        raise AssertionError("baseline is not the reported v2 geometry-004 state")
    if cand[GEOMETRY_ID][2] != CORRECTED_GEOMETRY_ANSWER:
        raise AssertionError("geometry-004 Short Answer is not exactly '4, 5'")
    if base[NUMBER_THEORY_ID][2] != CURRENT_NUMBER_THEORY_ANSWER:
        raise AssertionError("baseline number_theory-048 value is unexpected")
    if cand[NUMBER_THEORY_ID][2] != CURRENT_NUMBER_THEORY_ANSWER:
        raise AssertionError("number_theory-048 must not change")

    changed = [
        (problem_id, column)
        for problem_id in base
        for column, (old, new) in enumerate(zip(base[problem_id], cand[problem_id]))
        if old != new
    ]
    if changed != [(GEOMETRY_ID, 2)]:
        raise AssertionError(f"candidate must change only geometry-004 Short Answer; got {changed}")


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    v1_path, baseline_path, candidate_path = map(Path, sys.argv[1:])
    v1 = read_csv(v1_path)
    baseline = read_csv(baseline_path)
    candidate = read_csv(candidate_path)
    verify(v1, baseline, candidate)
    print(
        "PASS: v1 corroborates '4, 5'; exactly one semantic v2 CSV cell changed; "
        "released schema profile and number_theory-048 are preserved"
    )


if __name__ == "__main__":
    main()
