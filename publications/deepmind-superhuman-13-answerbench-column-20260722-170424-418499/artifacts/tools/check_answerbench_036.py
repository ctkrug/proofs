#!/usr/bin/env python3
"""Validate the narrowly scoped repair for IMO AnswerBench algebra-036.

Usage:
  python3 tools/check_answerbench_036.py CANDIDATE.csv --reference BASELINE.csv

The reference option establishes that the candidate differs only by insertion of
the missing CSV quote at the reported record.  Without it, the semantic CSV
invariants are still checked.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


HEADER = (
    "Problem ID",
    "Problem",
    "Short Answer",
    "Category",
    "Subcategory",
    "Source",
)
TARGET_ID = "imo-bench-algebra-036"
TARGET_PROBLEM = r"""Find all functions $Y: \mathbb{R} \backslash\{0\} \rightarrow \mathbb{R}$ such that for any non-zero real numbers $a, b$ with $ab \neq -1$, the following equation holds:
\[
a Y\left(a+\frac{1}{b}\right)+b Y(b)+\frac{a}{b}=b Y\left(b+\frac{1}{a}\right)+a Y(a)+\frac{b}{a}
\]
"""
TARGET_ANSWER = r"$Y(x)=A+\frac{B}{x}-x$"
TARGET_TAIL = (TARGET_ANSWER, "Algebra", "Functional Equation", "Iran 2002")
BAD_SEPARATOR = b'\n,"$Y(x)=A+\\frac{B}{x}-x$",Algebra,Functional Equation,Iran 2002'


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def check_csv(path: Path) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or tuple(rows[0]) != HEADER:
        fail(f"header is not the expected six columns: {rows[:1]!r}")
    widths = [(number, len(row)) for number, row in enumerate(rows[1:], start=2) if len(row) != 6]
    if widths:
        fail(f"non-six-column data rows: {widths[:5]!r}")
    target_rows = [row for row in rows[1:] if row[0] == TARGET_ID]
    if len(target_rows) != 1:
        fail(f"expected one {TARGET_ID!r} row, found {len(target_rows)}")
    target = target_rows[0]
    if target[1] != TARGET_PROBLEM:
        fail("target Problem field differs from the reported statement")
    if tuple(target[2:]) != TARGET_TAIL:
        fail(f"target short-answer/category tail is wrong: {target[2:]!r}")
    print(f"PASS: {path}: {len(rows) - 1} data rows, all six columns; {TARGET_ID} is repaired")


def check_one_byte_diff(candidate: Path, reference: Path) -> None:
    repaired = candidate.read_bytes()
    baseline = reference.read_bytes()
    occurrences = baseline.count(BAD_SEPARATOR)
    if occurrences != 1:
        fail(f"reference contains the known malformed separator {occurrences} times, not once")
    offset = baseline.index(BAD_SEPARATOR) + 1
    expected = baseline[:offset] + b'"' + baseline[offset:]
    if repaired != expected:
        fail("candidate is not exactly the one-byte quote insertion at algebra-036")
    print("PASS: candidate differs from reference by only the required quote insertion")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    check_csv(args.candidate)
    if args.reference:
        check_one_byte_diff(args.candidate, args.reference)


if __name__ == "__main__":
    main()
