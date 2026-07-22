Best live route: submit a one-cell upstream PR after replaying the checker. Upstream issue [#14](https://github.com/google-deepmind/superhuman/issues/14) remains open with no comments; current `main` retains `45752`.

Sourced facts:
- Pinned upstream `main` `96fa6c4…` has v2 SHA-256 `275877…b21cf9`.
- Parsed rows: geometry-004 Short Answer is `45752`; number_theory-048 is `ab≤e³`.
- Deprecated [v1 CSV](https://github.com/google-deepmind/superhuman/blob/main/imobench/answerbench.csv) has geometry-004 `4, 5`.
- v2 introduced `45752`; later v2 changes did not touch it.
- Upstream requires a CLA and PR review.

Cheapest discriminator: run [verify_answerbench_geometry_004.py](/root/proof-factory/research/deepmind-superhuman-14-geometry-answer/workspace/checkers/verify_answerbench_geometry_004.py) on pinned baseline versus candidate. It requires exactly one semantic-cell change: `geometry-004`, column 3, `45752 → 4, 5`; it explicitly protects number_theory-048 and all other data.

Controls:
- Positive in-memory one-cell control passed.
- Identical-current-file negative control correctly failed.
- Complexity is linear over 400 records; no large search applies. Safe reduction is a full-file identity comparison except the single approved cell.

Failure mode to retain: the current CSV has a six-column header but one unrelated pre-existing malformed five-field row (`imo-bench-algebra-036`). Do not normalize it in this narrow fix; preserve its baseline structure. “Six-column schema” should be interpreted as preserving the target record/header and making no unrelated changes.

Reusable evidence and replay instructions are in [source-discriminator-2026-07-22.md](/root/proof-factory/research/deepmind-superhuman-14-geometry-answer/workspace/notes/source-discriminator-2026-07-22.md).

Stop condition: checker passes against a freshly fetched pinned upstream baseline and the PR diff is one cell. Then the external acceptance path is upstream CLA + maintainer review.

Principal should independently re-fetch/hash the source before PR creation, verify the checker output, and reject any change to number_theory-048 or formatting-wide rewrite. Current uncertainty is only whether maintainers want an added independent geometry derivation; provenance is strong but is not itself such a derivation.
