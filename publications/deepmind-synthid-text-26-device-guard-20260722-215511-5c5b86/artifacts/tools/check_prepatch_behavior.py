#!/usr/bin/env python3
"""Confirm that the pinned pristine source exhibits issue #26."""

import argparse
import subprocess
import types

from run_focused_device_guard_tests import load_detector_class_from_text


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("repo")
  parser.add_argument("--ref", required=True)
  args = parser.parse_args()
  source_path = "src/synthid_text/detector_bayesian.py"
  source = subprocess.run(
      ["git", "-C", args.repo, "show", f"{args.ref}:{source_path}"],
      check=True,
      stdout=subprocess.PIPE,
      text=True,
  ).stdout
  detector = load_detector_class_from_text(source, f"{args.ref}:{source_path}")
  processed = ("train_g", "train_m", "train_l", "cv_g", "cv_m", "cv_l")
  sentinel = (object(), 0.0)
  detector.process_raw_model_outputs = classmethod(
      lambda cls, **kwargs: processed
  )
  detector.train_best_detector_given_g_values = classmethod(
      lambda cls, **kwargs: sentinel
  )

  cpu_result = detector.train_best_detector(
      tokenized_wm_outputs=[],
      tokenized_uwm_outputs=[],
      logits_processor=None,
      tokenizer=None,
      torch_device=types.SimpleNamespace(type="cpu"),
  )
  assert cpu_result is sentinel, "pristine CPU path unexpectedly rejected"
  for accelerator in ("cuda", "tpu"):
    try:
      detector.train_best_detector(
          tokenized_wm_outputs=[],
          tokenized_uwm_outputs=[],
          logits_processor=None,
          tokenizer=None,
          torch_device=types.SimpleNamespace(type=accelerator),
      )
    except ValueError as exc:
      assert "unstable on CPUs" in str(exc)
    else:
      raise AssertionError(f"pristine {accelerator} path unexpectedly accepted")
  print("PASS: pristine CPU is accepted while CUDA and TPU are rejected")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
