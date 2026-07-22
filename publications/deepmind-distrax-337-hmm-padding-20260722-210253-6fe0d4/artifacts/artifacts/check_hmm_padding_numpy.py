"""Independent NumPy oracle for the Distrax HMM padding fix.

This checker intentionally reimplements normalized forward-backward recurrences
with NumPy instead of comparing two calls to the Distrax implementation alone.
It validates only the documented valid prefix; padded output positions are out
of scope.
"""

import json

import distrax
import jax
import jax.numpy as jnp
import numpy as np
from distrax._src.utils import hmm


def _normalize(values):
  # Match Distrax's documented numerical floor while keeping the recurrence
  # itself independent of the JAX implementation.
  values = np.where(values == 0, 0, np.where(values < 1e-15, 1e-15, values))
  denominator = np.sum(values)
  if denominator == 0:
    denominator = 1.0
  return values / denominator, denominator


def _normal_prob(observations, locations, scales):
  centered = (observations[:, None] - locations[None, :]) / scales[None, :]
  return np.exp(-0.5 * centered**2) / (np.sqrt(2.0 * np.pi) * scales)


def _numpy_forward_backward(initial, transition, locations, scales,
                            observations):
  emissions = _normal_prob(observations, locations, scales)
  length = len(observations)
  num_states = len(initial)

  alpha = np.empty((length, num_states), dtype=np.float64)
  alpha[0], normalizer = _normalize(initial * emissions[0])
  log_likelihood = np.log(normalizer)
  for t in range(1, length):
    alpha[t], normalizer = _normalize(
        np.matmul(alpha[t - 1], transition) * emissions[t])
    log_likelihood += np.log(normalizer)

  beta = np.ones((length, num_states), dtype=np.float64)
  for t in range(length - 2, -1, -1):
    beta[t], _ = _normalize(
        np.sum(transition * (emissions[t + 1] * beta[t + 1]), axis=1))

  gamma = np.empty_like(alpha)
  for t in range(length):
    gamma[t], _ = _normalize(alpha[t] * beta[t])
  return alpha, beta, gamma, log_likelihood


def _check_case(case_name, initial, transition, locations, scales,
                observations):
  model = hmm.HMM(
      init_dist=distrax.Categorical(probs=jnp.asarray(initial)),
      trans_dist=distrax.Categorical(probs=jnp.asarray(transition)),
      obs_dist=distrax.Normal(
          loc=jnp.asarray(locations), scale=jnp.asarray(scales)))
  compiled_forward_backward = jax.jit(model.forward_backward)
  observations_jax = jnp.asarray(observations)
  results = []

  for valid_length in (1, 3, len(observations)):
    padded = compiled_forward_backward(
        observations_jax, length=jnp.asarray(valid_length))
    prefix = compiled_forward_backward(observations_jax[:valid_length])
    reference = _numpy_forward_backward(
        initial, transition, locations, scales,
        observations[:valid_length])

    max_errors = []
    for padded_value, prefix_value, reference_value in zip(
        padded[:3], prefix[:3], reference[:3]):
      padded_prefix = np.asarray(padded_value[:valid_length])
      prefix_value = np.asarray(prefix_value)
      np.testing.assert_allclose(
          padded_prefix, prefix_value, rtol=1e-6, atol=1e-6)
      np.testing.assert_allclose(
          padded_prefix, reference_value, rtol=5e-6, atol=1e-7)
      max_errors.append(float(np.max(np.abs(padded_prefix - reference_value))))

    padded_ll = np.asarray(padded[3])
    prefix_ll = np.asarray(prefix[3])
    np.testing.assert_allclose(padded_ll, prefix_ll, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(
        padded_ll, reference[3], rtol=5e-6, atol=1e-7)
    results.append({
        "case": case_name,
        "valid_length": valid_length,
        "max_abs_error_vs_numpy": {
            "alpha": max_errors[0],
            "beta": max_errors[1],
            "posterior": max_errors[2],
            "log_likelihood": float(abs(padded_ll - reference[3])),
        },
    })
  return results


def main():
  cases = (
      (
          "issue_337",
          np.array([0.6, 0.4]),
          np.array([[0.8, 0.2], [0.3, 0.7]]),
          np.array([0.0, 3.0]),
          np.array([0.5, 0.5]),
          np.array([0.05, 2.9, 0.1, 99.0, 99.0]),
      ),
      (
          "three_state_control",
          np.array([0.2, 0.5, 0.3]),
          np.array([
              [0.75, 0.20, 0.05],
              [0.10, 0.70, 0.20],
              [0.15, 0.25, 0.60],
          ]),
          np.array([-1.0, 1.0, 4.0]),
          np.array([0.7, 1.2, 0.9]),
          np.array([-0.8, 1.1, 3.7, 8.0, -6.0]),
      ),
  )
  results = []
  for case in cases:
    results.extend(_check_case(*case))
  print(json.dumps({"status": "pass", "checks": results}, sort_keys=True))


if __name__ == "__main__":
  main()
