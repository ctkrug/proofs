#!/usr/bin/env python3
"""Dependency-free regression discriminator for ai-foundations issue #37.

Usage:
  python checkers/layernorm_count_discriminator.py /path/to/ai-foundations

It independently loads the Python feedback reference and the notebook's typed
reference-solution cells, then checks that a transformer block is the sum of
attention, MLP, and two complete LayerNorm components. The two fixtures use
the curriculum's existing test hyperparameters and have fixed, hand-derived
expected totals, so the former `2 * embedding_dim` bug fails in both sources.
"""

import ast
import json
import runpy
import sys
from pathlib import Path


FIXTURES = (
    ({"embedding_dim": 256, "mlp_dim": 384}, 461440),
    ({"embedding_dim": 128, "mlp_dim": 512}, 198272),
)


def notebook_reference_functions(notebook: Path) -> dict:
  """Execute only the four typed parameter-count reference cells."""
  cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
  namespace: dict = {}
  names = (
      "parameter_count_layer_norm",
      "parameter_count_attention",
      "parameter_count_mlp",
      "parameter_count_transformer_block",
  )
  for name in names:
    marker = f"def {name}(hyperparams: dict[str, int])"
    matches = []
    for cell in cells:
      source = "".join(cell.get("source", []))
      if (
          cell.get("cell_type") == "code"
          and marker in source
          and "parameter_count = ..." not in source
      ):
        matches.append(source)
    if len(matches) != 1:
      raise AssertionError(
          f"expected one typed notebook cell for {name}, found {len(matches)}"
      )
    tree = ast.parse(matches[0])
    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(definitions) != 1:
      raise AssertionError(f"expected one function definition for {name}")
    module = ast.Module(body=definitions, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(notebook), "exec"), namespace)
  return namespace


def assert_reference(label: str, namespace: dict) -> None:
  block = namespace["parameter_count_transformer_block"]
  attention = namespace["parameter_count_attention"]
  mlp = namespace["parameter_count_mlp"]
  layer_norm = namespace["parameter_count_layer_norm"]
  for hyperparams, direct_oracle in FIXTURES:
    observed = block(hyperparams)
    compositional_oracle = (
        attention(hyperparams) + mlp(hyperparams) + 2 * layer_norm(hyperparams)
    )
    assert compositional_oracle == direct_oracle, (
        label,
        hyperparams,
        compositional_oracle,
    )
    assert observed == direct_oracle, (
        f"{label}: {hyperparams} produced {observed}; expected {direct_oracle} "
        "(attention + MLP + two gamma/beta LayerNorms)"
    )


def main(argv: list[str]) -> int:
  if len(argv) != 2:
    print(f"usage: {argv[0]} /path/to/ai-foundations", file=sys.stderr)
    return 2
  root = Path(argv[1])
  python_reference = (
      root
      / "ai_foundations/feedback/course_4/counting_parameters/reference_implementations.py"
  )
  notebook = root / "course_4/gdm_lab_4_5_reflection_on_trainable_parameters.ipynb"
  assert python_reference.is_file(), python_reference
  assert notebook.is_file(), notebook
  checks = (
      ("Python feedback reference", lambda: runpy.run_path(str(python_reference))),
      ("notebook typed reference solution", lambda: notebook_reference_functions(notebook)),
  )
  failures = []
  for label, load in checks:
    try:
      assert_reference(label, load())
    except (AssertionError, KeyError, SyntaxError) as error:
      failures.append(str(error))
  if failures:
    print("FAIL: " + "\nFAIL: ".join(failures), file=sys.stderr)
    return 1
  print("PASS: both references count two complete LayerNorm components")
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv))
