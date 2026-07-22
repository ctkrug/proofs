#!/usr/bin/env python3
"""Run the issue #26 tests against the exact method body without ML deps.

The upstream detector module imports the full PyTorch/JAX training stack. These
branch tests need none of it: this runner extracts and compiles the unmodified
``BayesianDetector.train_best_detector`` AST into a minimal class, then loads
the proposed upstream test module normally. Only absl-py and mock are needed.
"""

import argparse
import ast
import importlib.util
import pathlib
import sys
import types
import typing
import unittest

def load_detector_class_from_text(source_text: str, filename: str) -> type:
  tree = ast.parse(source_text, filename=filename)
  method = None
  for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "BayesianDetector":
      method = next(
          (
              member
              for member in node.body
              if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
              and member.name == "train_best_detector"
          ),
          None,
      )
      break
  if method is None:
    raise ValueError("BayesianDetector.train_best_detector was not found")

  isolated_class = ast.ClassDef(
      name="BayesianDetector",
      bases=[],
      keywords=[],
      body=[method],
      decorator_list=[],
  )
  module = ast.fix_missing_locations(
      ast.Module(body=[isolated_class], type_ignores=[])
  )
  namespace = {
      "Any": typing.Any,
      "Optional": typing.Optional,
      "Sequence": typing.Sequence,
      "Union": typing.Union,
      "logits_processing": types.SimpleNamespace(
          SynthIDLogitsProcessor=object
      ),
      "np": types.SimpleNamespace(
          ndarray=object, logspace=lambda *args, **kwargs: object()
      ),
      "torch": types.SimpleNamespace(device=object),
  }
  compiled = compile(module, filename, "exec")
  exec(compiled, namespace)  # pylint: disable=exec-used
  detector_class = namespace["BayesianDetector"]
  detector_class.process_raw_model_outputs = classmethod(lambda cls, **kwargs: None)
  detector_class.train_best_detector_given_g_values = classmethod(
      lambda cls, **kwargs: None
  )
  return detector_class


def load_detector_class(source_path: pathlib.Path) -> type:
  return load_detector_class_from_text(
      source_path.read_text(encoding="utf-8"), str(source_path)
  )


def load_test_module(test_path: pathlib.Path, detector_class: type):
  package = types.ModuleType("synthid_text")
  package.__path__ = []
  detector_module = types.ModuleType("synthid_text.detector_bayesian")
  detector_module.BayesianDetector = detector_class
  package.detector_bayesian = detector_module
  sys.modules["synthid_text"] = package
  sys.modules["synthid_text.detector_bayesian"] = detector_module

  spec = importlib.util.spec_from_file_location(
      "issue_26_detector_bayesian_test", test_path
  )
  if spec is None or spec.loader is None:
    raise ValueError(f"Could not load test module {test_path}")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("source", type=pathlib.Path)
  parser.add_argument("test", type=pathlib.Path)
  args = parser.parse_args()

  detector_class = load_detector_class(args.source)
  test_module = load_test_module(args.test, detector_class)
  suite = unittest.defaultTestLoader.loadTestsFromModule(test_module)
  result = unittest.TextTestRunner(verbosity=2).run(suite)
  return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
  raise SystemExit(main())
