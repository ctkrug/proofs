"""Regression discriminator for Distrax issue #337.

Run against the source tree being evaluated, e.g.:
  PYTHONPATH=/path/to/distrax python artifacts/hmm_padding_discriminator.py
"""

import numpy as np
import distrax
import jax.numpy as jnp
from distrax._src.utils import hmm


def main():
  model = hmm.HMM(
      init_dist=distrax.Categorical(probs=jnp.array([0.6, 0.4])),
      trans_dist=distrax.Categorical(
          probs=jnp.array([[0.8, 0.2], [0.3, 0.7]])),
      obs_dist=distrax.Normal(
          loc=jnp.array([0.0, 3.0]), scale=jnp.array([0.5, 0.5])),
  )
  observations = jnp.array([0.05, 2.9, 0.1, 99.0, 99.0])
  valid_length = jnp.array(3)

  _, beta_padded, gamma_padded, ll_padded = model.forward_backward(
      observations, length=valid_length)
  _, beta_prefix, gamma_prefix, ll_prefix = model.forward_backward(
      observations[:valid_length])

  np.testing.assert_allclose(beta_padded[:valid_length], beta_prefix,
                             rtol=1e-6, atol=1e-6)
  np.testing.assert_allclose(gamma_padded[:valid_length], gamma_prefix,
                             rtol=1e-6, atol=1e-6)
  np.testing.assert_allclose(ll_padded, ll_prefix, rtol=1e-6, atol=1e-6)


if __name__ == "__main__":
  main()
