#!/usr/bin/env python3
"""Reproduce issue #13 and adversarially test the proposed narrow checker.

This is a baseline experiment, not an edit to the released dataset.  It builds
the one-byte repair only inside a temporary directory, parses it with Python's
standard-library RFC-style CSV reader, and exercises positive and negative
controls against ``check_answerbench_036.py``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


TARGET_ID = "imo-bench-algebra-036"
TARGET_ANSWER = r"$Y(x)=A+\frac{B}{x}-x$"
ANSWER_BYTES = b'"$Y(x)=A+\\frac{B}{x}-x$"'


def parse(path: Path, *, strict: bool) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle, strict=strict))


def run_checker(checker: Path, *args: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(checker), *(str(arg) for arg in args)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def normalize_output(output: str, temporary_root: Path) -> str:
    return output.replace(str(temporary_root), "<temporary-directory>").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("checker", type=Path)
    parser.add_argument(
        "--candidate",
        type=Path,
        help="also require this materialized candidate to equal the derived repair",
    )
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()

    baseline_bytes = args.baseline.read_bytes()
    baseline_rows = parse(args.baseline, strict=False)
    strict_baseline_error = ""
    try:
        parse(args.baseline, strict=True)
    except csv.Error as error:
        strict_baseline_error = str(error)
    require(strict_baseline_error != "", "strict parser unexpectedly accepted malformed baseline")
    require(len(baseline_rows[0]) == 6, "baseline header must declare six columns")
    widths = Counter(map(len, baseline_rows[1:]))
    require(widths == Counter({6: 399, 5: 1}), f"unexpected widths: {widths}")
    malformed = [row for row in baseline_rows[1:] if len(row) != 6]
    require(len(malformed) == 1 and malformed[0][0] == TARGET_ID, "wrong malformed row")
    require(TARGET_ANSWER in malformed[0][1], "reported answer is not merged into Problem")

    # The answer token itself is unique.  The preceding byte must be the comma
    # currently swallowed by the open quoted Problem field.  Closing that field
    # immediately before the comma is therefore the local one-byte repair.
    require(baseline_bytes.count(ANSWER_BYTES) == 1, "answer token is not unique")
    answer_start = baseline_bytes.index(ANSWER_BYTES)
    comma_offset = answer_start - 1
    require(baseline_bytes[comma_offset : answer_start] == b",", "no separator comma")
    repaired_bytes = baseline_bytes[:comma_offset] + b'"' + baseline_bytes[comma_offset:]

    candidate_sha256 = None
    if args.candidate is not None:
        candidate_bytes = args.candidate.read_bytes()
        require(candidate_bytes == repaired_bytes, "materialized candidate differs from derived repair")
        candidate_rows = parse(args.candidate, strict=True)
        require(all(len(row) == 6 for row in candidate_rows), "candidate does not have six columns")
        candidate_target = [row for row in candidate_rows[1:] if row[0] == TARGET_ID]
        require(
            len(candidate_target) == 1 and candidate_target[0][2] == TARGET_ANSWER,
            "candidate does not restore the exact short answer",
        )
        candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()

    controls: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="answerbench-036-") as temporary:
        root = Path(temporary)
        repaired = root / "repaired.csv"
        repaired.write_bytes(repaired_bytes)
        repaired_rows = parse(repaired, strict=True)
        require(all(len(row) == 6 for row in repaired_rows), "repair did not restore six columns")
        target = [row for row in repaired_rows[1:] if row[0] == TARGET_ID]
        require(len(target) == 1 and target[0][2] == TARGET_ANSWER, "answer not restored exactly")

        malformed_result = run_checker(args.checker, args.baseline)
        require(malformed_result.returncode != 0, "checker accepted malformed baseline")
        controls["malformed_baseline_rejected"] = {
            "returncode": malformed_result.returncode,
            "output": normalize_output(malformed_result.stdout, root),
        }

        repaired_result = run_checker(args.checker, repaired, Path("--reference"), args.baseline)
        # ``run_checker`` treats every argument as a Path so the flag remains a
        # literal argv token and no shell participates.
        require(repaired_result.returncode == 0, repaired_result.stdout)
        controls["one_byte_repair_accepted"] = {
            "returncode": repaired_result.returncode,
            "output": normalize_output(repaired_result.stdout, root).splitlines(),
        }

        if args.candidate is not None:
            candidate_result = run_checker(
                args.checker, args.candidate, Path("--reference"), args.baseline
            )
            require(candidate_result.returncode == 0, candidate_result.stdout)
            controls["materialized_candidate_accepted"] = {
                "returncode": candidate_result.returncode,
                "output": normalize_output(candidate_result.stdout, root).splitlines(),
            }

        wrong_answer = root / "wrong-answer.csv"
        wrong_token = b'"$Y(x)=A+\\frac{C}{x}-x$"'
        wrong_answer.write_bytes(repaired_bytes.replace(ANSWER_BYTES, wrong_token, 1))
        wrong_result = run_checker(args.checker, wrong_answer)
        require(wrong_result.returncode != 0, "checker accepted wrong answer")
        controls["wrong_answer_rejected"] = {
            "returncode": wrong_result.returncode,
            "output": normalize_output(wrong_result.stdout, root),
        }

        unrelated = root / "unrelated-edit.csv"
        original_id = b"imo-bench-algebra-001"
        changed_id = b"imo-bench-algebra-X01"
        require(repaired_bytes.count(original_id) == 1, "control ID is not unique")
        unrelated.write_bytes(repaired_bytes.replace(original_id, changed_id, 1))
        semantic_only = run_checker(args.checker, unrelated)
        require(semantic_only.returncode == 0, "semantic-only control unexpectedly failed")
        exact_diff = run_checker(args.checker, unrelated, Path("--reference"), args.baseline)
        require(exact_diff.returncode != 0, "exact-diff guard accepted an unrelated edit")
        controls["unrelated_edit"] = {
            "semantic_only_returncode": semantic_only.returncode,
            "with_reference_returncode": exact_diff.returncode,
            "with_reference_output": normalize_output(exact_diff.stdout, root),
        }

    result = {
        "source_commit": "96fa6c4cc3a9bb7450ee7b6773b659d3a030dace",
        "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "baseline_bytes": len(baseline_bytes),
        "data_rows": len(baseline_rows) - 1,
        "baseline_width_counts": {str(width): count for width, count in sorted(widths.items())},
        "malformed_problem_id": malformed[0][0],
        "strict_baseline_error": strict_baseline_error,
        "inserted_quote_offset": comma_offset,
        "repaired_sha256": hashlib.sha256(repaired_bytes).hexdigest(),
        "repaired_bytes": len(repaired_bytes),
        "repaired_all_six_columns": True,
        "repaired_target_short_answer": TARGET_ANSWER,
        "materialized_candidate": str(args.candidate) if args.candidate is not None else None,
        "materialized_candidate_sha256": candidate_sha256,
        "controls": controls,
        "scope": "the 400 data records in the pinned upstream CSV only",
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
