#!/usr/bin/env python3
"""Independently check the AnswerBench repair as one exact byte replacement.

Usage:
  python checkers/check_exact_geometry_004_patch_bytes.py BASELINE_V2.csv CANDIDATE_V2.csv

This intentionally does not use a CSV parser or import the semantic checker.
It validates a materially different encoding: the candidate byte stream must
equal the pinned baseline after one unique, context-bound replacement.
"""

from __future__ import annotations

import sys
from pathlib import Path


OLD = (
    b'imo-bench-geometry-004,"Let $n$ cities lie on the circumference of a circular lake. '
    b'Exactly half of the triangles formed by connecting any three of these cities are '
    b'acute-angled triangles. Find the value of $n$ for which this is possible.\n"'
    b',45752,Geometry,combinatorial_geometry,Sharygin 2009'
)
NEW = OLD.replace(b',45752,Geometry', b',"4, 5",Geometry')


def verify(baseline: bytes, candidate: bytes) -> None:
    if baseline.count(OLD) != 1:
        raise AssertionError("baseline does not contain the unique expected corrupted record")
    if candidate != baseline.replace(OLD, NEW, 1):
        raise AssertionError("candidate is not the exact one-record byte replacement")
    if candidate.count(NEW) != 1 or OLD in candidate:
        raise AssertionError("candidate does not contain exactly one corrected record")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    baseline_path, candidate_path = map(Path, sys.argv[1:])
    verify(baseline_path.read_bytes(), candidate_path.read_bytes())
    print("PASS: candidate equals baseline under one unique context-bound byte replacement")


if __name__ == "__main__":
    main()
