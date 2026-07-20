# Erdős #647 — first discovery target

Official source: <https://www.erdosproblems.com/647>

Let `tau(n)` be the divisor count. Find an explicit `n > 24`, if one exists, such that
`max_{m<n}(m + tau(m)) ≤ n + 2`.

A candidate is unusually easy to verify relative to most open problems:

1. compute every `tau(m)` for `1 ≤ m < n` with an exact sieve;
2. compute the maximum and its witnesses;
3. check the displayed inequality;
4. rerun an independently implemented factorization-based checker;
5. check OEIS/current literature before claiming novelty.

The main research work is to derive an efficient search or structural filter. Searching farther
without recording the exact range, algorithm, source revision, and hash is not a result.
