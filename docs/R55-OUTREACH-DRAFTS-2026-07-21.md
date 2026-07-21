# R(5,5) alignment outreach: verified contacts, packet contract, and unsent drafts

Prepared 2026-07-21. **Nothing in this document has been sent.** These drafts describe independent
verification infrastructure and scoped negative experiments, not a new Ramsey graph, a new bound, a
proof that the 656 supplied graphs are complete, or peer review. Before sending, publish the dedicated
packet described below, replace its provisional pin if the packet commit changes, and confirm every
listed checksum from a clean clone.

## Verified recipients and contact routes

- **Thibault Gauthier.** Current affiliation: Czech Technical University in Prague, Czech Institute of
  Informatics, Robotics and Cybernetics (CIIRC). The official CIIRC directory lists
  `thibault.gauthier@cvut.cz`; the AITP 2025 program and his R(5,5) abstract independently identify CTU
  and the generalized SAT-gluing project. Sources: [CIIRC staff record](https://www.ciirc.cvut.cz/people/people-list/?uid=gauththi),
  [AITP program](https://aitp-conference.org/2025/), and
  [author abstract](https://aitp-conference.org/2025/abstract/AITP_2025_paper_3.pdf).
- **John Mackey and the CMU student group.** Send to `jmackey@andrew.cmu.edu`, the address on Mackey's
  official Carnegie Mellon Computer Science directory page. The group's conference abstract names
  Jacob Braginsky, Shreyas Yellenki, Lipeng (Jack) Zhu, John Mackey, and Zachary Battleman; it reports
  313 symmetry-reduced SAT encodings and 141 certified UNSAT cases for an R(5,5)-good
  `srg(45,22,10,11)`. Sources: [CMU directory](https://csd.cmu.edu/people/faculty/john-mackey) and
  [group abstract hosted by the FAU combinatorics conference](https://www.math.fau.edu/combinatorics/abstracts/braginsky-57-access.pdf).
- **BigCompute / Cahlen Humphreys.** The project's own About page identifies Cahlen Humphreys as its
  operator. **No email address was confirmed from a first-party source. Do not guess one.** Best
  confirmed routes are [GitHub `@cahlen`](https://github.com/cahlen) and
  [X `@cahlenhumphreys`](https://x.com/cahlenhumphreys); use a GitHub issue/discussion or direct
  message only if Charlie chooses. Sources: [BigCompute About](https://bigcompute.science/about/),
  [R(5,5) experiment](https://bigcompute.science/experiments/ramsey-r55-lower-bound/), and its
  [independent verifier](https://github.com/cahlen/idontknow/blob/main/scripts/experiments/ramsey-r55/verify_independent.py).

## Exact packet contract

The existing public evidence snapshot is pinned to repository commit
[`2b7c417e303f78189baaddee400a3f30110c1e8e`](https://github.com/ctkrug/proofs-ramsey-r55/tree/2b7c417e303f78189baaddee400a3f30110c1e8e).
Its retained-artifact checksum inventory is
[`artifacts/MANIFEST.sha256`](https://raw.githubusercontent.com/ctkrug/proofs-ramsey-r55/2b7c417e303f78189baaddee400a3f30110c1e8e/artifacts/MANIFEST.sha256),
whose SHA-256 is `8cc98a600544578be0e20e82ab4206054ad5bec0c4a8546a08dc97638cb7de5e`.
The final outreach packet should live at `outreach/r55-alignment-20260721/` in this repository and contain
`README.md`, `MANIFEST.sha256`, and the three path lists below. Its README must repeat the non-claims in
the opening paragraph, identify Python/GCC/CaDiCaL/Z3/nauty/NetworkX/drat-trim and AI assistance, and
give clean-clone replay commands. **The current prefix-49 embedding-census files postdate the retained
artifact inventory, so the existing inventory alone is not a sufficient final outreach packet. Do not
send these drafts until the dedicated packet manifest is committed and its immutable URL is substituted
for `[PACKET_URL]`.**

### Packet A: generalized-gluing alignment

Include the following exact material from the pinned snapshot:

- `artifacts/two_orbit_slices/distance_{01..05,07..21}/unsat.drat`: 20 checked burden-zero DRAT
  proofs, with the paired CNFs, independent origin ledgers, checker output, and per-family summaries.
- `artifacts/two_orbit_burden_one/distance_{01..05,07..21}/unsat_{a,b}.drat`: 40 checked burden-one
  DRAT proofs from two independent encoders, plus the 40 retained LRAT conversions under
  `artifacts/two_orbit_burden_one_lrat/`.
- `artifacts/two_orbit_certified_sweep_report.json`, SHA-256
  `9d8ec9a46cf74bdeab70fd39aebe0bd71c09badee163e69813c1ba67b84a55a8`.
- `artifacts/two_orbit_burden_one_exact_report.json`, SHA-256
  `993adc7236b0c7a241b9d17457b28e144e745e7c2d890bae17ef9c81dcbf689f`.
- `artifacts/two_orbit_burden_one_adversarial_audit.json`, SHA-256
  `0026e4d53f31b2fb8409bb52a0090035306cd6366e4a59c527bbc35b316167ff`.
- `artifacts/two_orbit_slice_exact_report.json`, SHA-256
  `0456c5764898ab28d248d20912f26fd6708cac5d283151e1673110ce73690627`, and
  `artifacts/two_orbit_slice_adversarial_audit.json`, SHA-256
  `38f2b91ca963760dc1fed0107be7fef0c40d41d3fd7da2a7104103447c6b36c8`.
- The corresponding `scripts/run_two_orbit_*`, `scripts/audit_two_orbit_*`,
  `checkers/two_orbit_*`, and pinned `tools/drat-trim/` paths enumerated in the retained checksum
  inventory.

Scope statement: these 60 certificates classify 20 cyclic two-orbit families around one published
K43 seed at minimum burden two. They do not cover arbitrary gluing configurations and do not change
`43 <= R(5,5) <= 46`.

### Packet B: CMU SRG alignment

Include the authenticated supplied corpus, dual embedding implementations, and current checkpoint:

- `sources/r55_42some.g6`, SHA-256
  `067902e853d87b49bcef0d1d4c0e3bbadd238ee18bc65341b079a3ca4780eccb`.
- `artifacts/authenticated_corpus_report.json`, SHA-256
  `0d9b1801434edcc12f34e73cea6c98d911f0e0c6f0884f8f03d96a46eca1344c`.
- `scripts/run_known_class_embedding_census.py`, SHA-256
  `d571103060c50a82bc6b7d41c7affabc4062ef975750da397bacf93ae81623dc`;
  `scripts/enumerate_core_embeddings_bitset.py`, SHA-256
  `01b3953b1db6a65737e4fb4ee176a88b7c8c8ed26a374c410cf274fe2500739a`; and
  `scripts/enumerate_core_embeddings_networkx.py`, SHA-256
  `c4491591b16394e11d3bf0b907eea8c65a73308e8a2a366e5d594532c7010aaf`.
- `checkers/validate_known_class_embedding_census.py`, SHA-256
  `dfb690a33faca857255303c8923d99263ea98c85a862adad0c53778926b4c07b`.
- `artifacts/known-class-embedding-census/output/manifest.jsonl`, 49 rows, SHA-256
  `52fbdafb4b03decd835a62848e6e558ef720124a58c5176463e5ac5b17645a70`;
  `checkpoint.json`, SHA-256
  `45bcdd67bd68c3749a2b6a54985f7b81e2d8e79b07c1c7a472b3311bdc9a03dd`; and
  `progress.json`, SHA-256
  `f8213733c0b6cf255157a1d25e1eb92761c6cea5abccf82b65821065355753ba`.

Scope statement: the pinned census is an exact 49-of-656 checkpoint, not a full-corpus result. The
bitset and NetworkX streams agree on every completed host; the packet must be regenerated and repinned
if the full census supersedes this checkpoint before outreach.

### Packet C: BigCompute reproduction alignment

Include the corpus-authentication core and the two-orbit packet as a sample of the receipt format:

- `sources/r55_42some.g6` and `artifacts/authenticated_corpus_report.json` with the hashes in Packet B.
- `scripts/run_corpus_gate.py`, SHA-256
  `ea8cc894bcc0597aac9eb459cead427fd5282082f35e3a27b5dda299c2065d23`.
- `checkers/checker_a.py`, SHA-256
  `b7f28adfec792139acce538ca879b775a0180467763b413e1a464672acddd259`, and
  `checkers/checker_b.c`, SHA-256
  `40f719bb36f8d7d3db3a4b949dce8b20abd49499f57f7d5b651b718658014d2e`.
- All of Packet A, demonstrating the CNF/proof/checker-log/hash-manifest convention proposed for an
  independent replay of BigCompute's 656 extension instances.

Scope statement: this packet does not claim to reproduce BigCompute's 656/656 run. BigCompute's public
verifier generates and checks each DRAT proof and then deletes it; the proposed collaboration is to
run a separately pinned reproduction that retains the generated CNFs, proofs, checker logs, corpus
mapping, and complete manifest.

## Unsent draft 1: Thibault Gauthier

**To:** `thibault.gauthier@cvut.cz`  
**Subject:** R(5,5) SAT certificate-format alignment

Hello Dr. Gauthier,

I’m Charlie Krug, and I have been building an open, AI-assisted proof-factory around independently checkable computational work on R(5,5). We are not claiming a new graph or bound; our current results are scoped negative experiments and verification infrastructure. The pinned packet at [PACKET_URL] includes 60 checked DRAT certificates and independent unsymmetrized decisions for 20 cyclic two-orbit families, together with corpus-authentication and embedding-census tooling. I read your AITP strategy for generalizing gluing subproblems and was especially interested in the plan to reuse one abstracted UNSAT result across many concrete configurations. Our certificates do not cover those gluing cases, but the manifest, dual encoders, and replay receipts may be useful plumbing for a compatible independent check. What exact machine-readable representation do you plan to use for an abstracted configuration, its blocking-clause coverage claim, and the underlying SAT refutation? In particular, would DIMACS plus DRAT or LRAT and a separate coverage manifest fit your HOL4 verification path, or is there another certificate boundary we should target? If useful, I would be glad to adapt our packet format or contribute bounded compute to reproduce one representative gluing case under your preferred contract.

Best,  
Charlie Krug

## Unsent draft 2: John Mackey and the CMU group

**To:** `jmackey@andrew.cmu.edu`  
**Subject:** Artifact alignment for the SRG(45,22,10,11) R(5,5) search

Hello Dr. Mackey,

I’m Charlie Krug, working on an open, AI-assisted verification system for computational R(5,5) experiments. I saw the CMU group’s report of 313 symmetry-reduced SAT encodings for an R(5,5)-good `srg(45,22,10,11)`, including 141 certified UNSAT cases. We do not have a Ramsey breakthrough; what we can offer is an authenticated copy of the supplied 328-plus-complements corpus, independent graph checkers, 60 checked two-orbit DRAT certificates, and a dual-implementation embedding-census pipeline. The exact materials and their hashes are pinned at [PACKET_URL], with the current census explicitly labeled as a 49-of-656 checkpoint rather than a completed classification. Would your group be willing to share the case-index map for the 313 encodings and one representative CNF/certificate pair? More specifically, what certificate and coverage format would make an independent replay most useful to you: per-case DIMACS plus DRAT/LRAT, a proof of the symmetry-reduced case cover, or both? We could return a hash-manifested replay with exact solver/checker versions and preserve any failure at the first mismatching case. If another artifact would better complement your current work, I would appreciate a pointer and would keep any conclusions within the checked scope.

Best,  
Charlie Krug

## Unsent draft 3: BigCompute / Cahlen Humphreys

**To:** **unconfirmed; no first-party email found** — use [GitHub `@cahlen`](https://github.com/cahlen) or [X `@cahlenhumphreys`](https://x.com/cahlenhumphreys) if Charlie approves  
**Subject:** Independent, retained-artifact replay of the 656 R(5,5) extensions

Hi Cahlen,

I’m Charlie Krug, and I have been building an open, AI-assisted proof-factory for reproducible work on R(5,5). I appreciated that the BigCompute write-up now states the exact limitation of the 656/656 extension result and publishes a CPU verifier with optional DRAT checking. We are not claiming a new graph or bound; our useful contribution is independent corpus authentication, dual graph checkers, hash-manifested evidence receipts, 60 checked two-orbit DRAT certificates, and compute for a clean reproduction. The exact current packet is pinned at [PACKET_URL]. I noticed that `verify_independent.py` checks each generated DRAT proof and then deletes it, which makes the result easy to rerun but leaves less material for byte-for-byte cross-audit. Do you already have a retained mapping from each of the 656 corpus records to its exact DIMACS instance, DRAT proof, checker output, and SHA-256 manifest? If not, would a separately generated packet with those five pieces per instance be useful, and should we preserve your binary ordering or key everything back to McKay’s original graph6 record and complement flag? We would be happy to run that bounded reproduction and report the first discrepancy rather than silently normalizing it.

Best,  
Charlie Krug

## Send checklist

- Replace `[PACKET_URL]` with one immutable commit URL to the completed dedicated packet; never use a
  branch URL.
- From a clean clone, run `sha256sum -c outreach/r55-alignment-20260721/MANIFEST.sha256` and all
  documented replay commands.
- Update Packet B to the validated full-corpus result if it completes before sending; do not mix a
  later result with the provisional commit or hashes above.
- Keep the no-breakthrough, no-bound-change, incomplete-656, AI/tool-disclosure, and scoped-coverage
  language intact.
- Charlie reviews and sends; automation sends nothing.
