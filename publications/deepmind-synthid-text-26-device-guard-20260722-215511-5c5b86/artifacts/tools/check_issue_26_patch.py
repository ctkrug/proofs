#!/usr/bin/env python3
"""Independent, dependency-free certificate checker for issue #26."""

import argparse
import ast
import pathlib


def find_method(tree: ast.Module) -> ast.FunctionDef:
  for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "BayesianDetector":
      for member in node.body:
        if isinstance(member, ast.FunctionDef) and member.name == "train_best_detector":
          return member
  raise AssertionError("BayesianDetector.train_best_detector not found")


def first_executable_statement(method: ast.FunctionDef) -> ast.stmt:
  statements = method.body
  if (
      statements
      and isinstance(statements[0], ast.Expr)
      and isinstance(statements[0].value, ast.Constant)
      and isinstance(statements[0].value.value, str)
  ):
    statements = statements[1:]
  if not statements:
    raise AssertionError("train_best_detector has no executable statements")
  return statements[0]


def check_guard(source: pathlib.Path) -> None:
  tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
  statement = first_executable_statement(find_method(tree))
  assert isinstance(statement, ast.If), "initial executable statement is not an if"
  comparison = statement.test
  assert isinstance(comparison, ast.Compare), "guard is not a comparison"
  assert len(comparison.ops) == 1 and isinstance(
      comparison.ops[0], ast.NotIn
  ), "guard does not use `not in`"
  assert (
      isinstance(comparison.left, ast.Attribute)
      and isinstance(comparison.left.value, ast.Name)
      and comparison.left.value.id == "torch_device"
      and comparison.left.attr == "type"
  ), "guard does not inspect torch_device.type"
  assert len(comparison.comparators) == 1 and isinstance(
      comparison.comparators[0], ast.Tuple
  ), "allowlist is not a tuple"
  allowlist = tuple(
      element.value
      for element in comparison.comparators[0].elts
      if isinstance(element, ast.Constant)
  )
  assert allowlist == ("cuda", "tpu"), f"unexpected allowlist: {allowlist!r}"
  assert statement.body and isinstance(
      statement.body[0], ast.Raise
  ), "rejection branch does not raise"

  expression = ast.Expression(body=comparison)
  ast.fix_missing_locations(expression)
  compiled = compile(expression, str(source), "eval")
  observed = {
      device: eval(  # pylint: disable=eval-used
          compiled, {}, {"torch_device": type("Device", (), {"type": device})()}
      )
      for device in ("cpu", "cuda", "tpu")
  }
  assert observed == {"cpu": True, "cuda": False, "tpu": False}, observed


def check_tests(test_path: pathlib.Path) -> None:
  tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
  test_class = next(
      (
          node
          for node in tree.body
          if isinstance(node, ast.ClassDef)
          and node.name == "BayesianDetectorDeviceGuardTest"
      ),
      None,
  )
  assert test_class is not None, "focused test class not found"
  methods = {
      node.name: node for node in test_class.body if isinstance(node, ast.FunctionDef)
  }
  assert "test_cpu_rejected_before_processing" in methods
  accelerator_test = methods.get("test_accelerator_type_reaches_training_pipeline")
  assert accelerator_test is not None
  parameter_values = []
  for decorator in accelerator_test.decorator_list:
    if (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "parameters"
    ):
      parameter_values.extend(
          argument.value
          for argument in decorator.args
          if isinstance(argument, ast.Constant)
      )
  assert tuple(parameter_values) == ("cuda", "tpu"), parameter_values


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("source", type=pathlib.Path)
  parser.add_argument("test", type=pathlib.Path)
  args = parser.parse_args()
  try:
    check_guard(args.source)
    check_tests(args.test)
  except (AssertionError, OSError, SyntaxError) as exc:
    print(f"FAIL: {exc}")
    return 1
  print("PASS: exact CPU-reject/CUDA+TPU-accept guard and regression cases verified")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
