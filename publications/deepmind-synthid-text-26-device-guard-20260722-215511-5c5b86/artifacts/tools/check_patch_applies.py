#!/usr/bin/env python3
"""Verify a patch against an exact pristine upstream index."""

import argparse
import hashlib
import pathlib
import subprocess


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("repo", type=pathlib.Path)
  parser.add_argument("patch", type=pathlib.Path)
  parser.add_argument("--base", required=True)
  args = parser.parse_args()

  actual_base = subprocess.run(
      ["git", "-C", str(args.repo), "rev-parse", "HEAD"],
      check=True,
      stdout=subprocess.PIPE,
      text=True,
  ).stdout.strip()
  assert actual_base == args.base, (actual_base, args.base)
  subprocess.run(
      [
          "git",
          "-C",
          str(args.repo),
          "apply",
          "--check",
          "--cached",
          str(args.patch.resolve()),
      ],
      check=True,
  )
  digest = hashlib.sha256(args.patch.read_bytes()).hexdigest()
  print(f"PASS: patch {digest} applies to pristine index {actual_base}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
