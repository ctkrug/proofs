#!/usr/bin/env python3
"""Clone current upstream, replay issue #37 patch, and run both validators."""

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import py_compile
import subprocess
import tempfile


REMOTE = "https://github.com/google-deepmind/ai-foundations.git"


def run(argv: list[str], *, cwd: Path, expected_returncode: int = 0) -> subprocess.CompletedProcess:
  result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
  if result.returncode != expected_returncode:
    raise AssertionError(
        f"{argv!r} returned {result.returncode}, expected {expected_returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
  return result


def sha256(path: Path) -> str:
  return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--expected-commit", required=True)
  parser.add_argument("--patch", type=Path, required=True)
  parser.add_argument("--checker", type=Path, required=True)
  args = parser.parse_args()

  workspace = Path.cwd().resolve()
  patch = args.patch.resolve()
  checker = args.checker.resolve()
  report = {
      "expected_commit": args.expected_commit,
      "patch": {"path": str(args.patch), "sha256": sha256(patch)},
      "checker": {"path": str(args.checker), "sha256": sha256(checker)},
  }

  with tempfile.TemporaryDirectory(prefix=".issue37-replay-", dir=workspace) as temporary:
    clone = Path(temporary) / "ai-foundations"
    run(["git", "clone", "--depth", "1", "--branch", "main", REMOTE, str(clone)], cwd=workspace)
    head = run(["git", "rev-parse", "HEAD"], cwd=clone).stdout.strip()
    if head != args.expected_commit:
      raise AssertionError(f"head changed: expected {args.expected_commit}, observed {head}")
    report["observed_commit"] = head

    baseline = run(["python3", str(checker), str(clone)], cwd=workspace, expected_returncode=1)
    for expected in (
        "FAIL: Python feedback reference",
        "FAIL: notebook typed reference solution",
        "produced 460928; expected 461440",
    ):
      if expected not in baseline.stderr:
        raise AssertionError(f"baseline did not contain {expected!r}: {baseline.stderr}")
    report["baseline_negative_control"] = {
        "returncode": baseline.returncode,
        "stderr": baseline.stderr.strip().splitlines(),
    }

    run(["git", "apply", "--check", str(patch)], cwd=clone)
    run(["git", "apply", str(patch)], cwd=clone)
    run(["git", "diff", "--check"], cwd=clone)
    # `git diff` omits untracked files; intent-to-add makes the newly added
    # regression test visible without staging its contents.
    run(
        [
            "git",
            "add",
            "--intent-to-add",
            "ai_foundations/feedback/course_4/counting_parameters/test_reference_implementations.py",
        ],
        cwd=clone,
    )
    diff = run(["git", "diff", "--binary", "--full-index"], cwd=clone).stdout.encode()
    patch_bytes = patch.read_bytes()
    if diff != patch_bytes:
      diagnostic = "".join(
          difflib.unified_diff(
              patch_bytes.decode().splitlines(keepends=True),
              diff.decode().splitlines(keepends=True),
              fromfile="saved-patch",
              tofile="replayed-diff",
          )
      )
      raise AssertionError(
          "replayed diff differs from patch: "
          f"diff={hashlib.sha256(diff).hexdigest()} patch={hashlib.sha256(patch_bytes).hexdigest()}\n"
          f"{diagnostic}"
      )
    report["replayed_diff_sha256"] = hashlib.sha256(diff).hexdigest()

    notebook = clone / "course_4/gdm_lab_4_5_reflection_on_trainable_parameters.ipynb"
    json.loads(notebook.read_text(encoding="utf-8"))
    python_files = (
        clone / "ai_foundations/feedback/course_4/counting_parameters/reference_implementations.py",
        clone / "ai_foundations/feedback/course_4/counting_parameters/test_reference_implementations.py",
        checker,
    )
    for path in python_files:
      py_compile.compile(str(path), doraise=True)
    regression_source = python_files[1].read_text(encoding="utf-8").splitlines()
    overlong = [(number, len(line)) for number, line in enumerate(regression_source, 1) if len(line) > 80]
    if overlong:
      raise AssertionError(f"new regression test has lines over 80 columns: {overlong}")

    regression = run(
        ["python3", "ai_foundations/feedback/course_4/counting_parameters/test_reference_implementations.py"],
        cwd=clone,
    )
    independent = run(["python3", str(checker), str(clone)], cwd=workspace)
    run(["git", "apply", "--reverse", "--check", str(patch)], cwd=clone)
    report["regression_test"] = {
        "returncode": regression.returncode,
        "stdout": regression.stdout.strip(),
        "stderr": regression.stderr.strip().splitlines(),
    }
    report["independent_checker"] = {
        "returncode": independent.returncode,
        "stdout": independent.stdout.strip(),
        "stderr": independent.stderr.strip(),
    }
    report["static_checks"] = {
        "git_apply_check": "pass",
        "git_diff_check": "pass",
        "exact_patch_identity": "pass",
        "notebook_json": "pass",
        "python_compile": "pass",
        "new_test_max_line_length_80": "pass",
        "reverse_apply_check": "pass",
    }

  print(json.dumps(report, indent=2, sort_keys=True))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
