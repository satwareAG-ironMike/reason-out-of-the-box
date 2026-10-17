# generators

## Purpose

Task generators for study-design Condition 2 (novel, contamination-audited tasks,
issue #4): digit matrices (Webb-style Raven analogues), compositional ladders
(Faith-and-Fate style), ARC-style grid transforms. Generators are stdlib-only
Python with a `--selftest` negative control, matching `scripts/` house style.

## Ownership

Agent-maintained; design decisions recorded here and in the CHANGELOG. Families
land one PR at a time (Baby Steps).

## Local Contracts

- Family 1 `digit_matrices.py`: cell = d-tuple of digits; each component follows
  its own row-wise rule from the fixed pool (constant, progression,
  distribution_of_3, xor, or, and); depth level d = number of simultaneous
  component rules (Webb's "1-4 simultaneous rules" mapped onto tuple components -
  design decision 2026-10-05). Answer format: 8 options (Raven ACMS/Webb
  convention); missing cell fixed at (2,2).
- Family 2 `ladders.py` (subtype `hop_chain`): universal transitivity rule +
  shuffled atomic facts over synthetic entity strings + yes/no query; depth k =
  shortest directed path length of the queried pair. Construction (component
  isomorphism, issue #67 fix): the facts are C >= 2 disjoint directed paths, each
  of exactly k edges over fresh entities; the query is always (head of one path,
  tail of one path); answer "yes" iff both endpoints lie on the same path. Because
  every component is isomorphic (same length, same endpoint roles), no surface
  feature of the query endpoints separates the two answer classes, so no item has
  a shortcut and none stays unreachable; the selftest re-derives both invariants by
  independent BFS plus a four-rule surface battery (issue #67 acceptance criterion
  2). `audit_ladder_leaks.py` makes the leak measurement repeatable (feature
  battery, conjunction search, stumps, bounded-search baselines, independent-BFS
  solvability; constant features reported but never gated). Gate calibration (issue #71
  criterion 4): the derivation-shortcut statistic must be read against a level-matched
  permutation null (re-draw the query pair from the item's own entity set). Measured
  2026-10-17: null shortcut rate 0% at k=1 and 9-12% at k>=2, while the shipped corpus
  measures 0 shortcuts in 1,500 items. A fixed 0.55 threshold sits about 5x above that band
  and would not flag a genuine 10% leak, so gate thresholds are level-matched to the null
  plus a margin, not constants (`research/nightly-2026-10-17-0200/ladder_depth_load.py`).
  Subtypes `mult_mult`
  and `dp_puzzle` (issue #4 list) are pending.
- Solvability is generation-time policy: for every component, exactly one rule of
  the pool must reproduce both demonstration rows jointly; non-identifiable
  samples are rejected. The selftest re-derives uniqueness from the emitted item.
- Depth grid across families (reconciles "3 families x 5 depths" with the
  per-family knobs in `docs/study-design.md`): digit matrices levels 1-4;
  compositional ladders k in {1, 2, 4, 6, 8} hops; ARC-style 1-5 composed
  transforms. The study runs d*+1..d*+4 around the audit ceiling d*.
- Ladder load is coupled to depth, and the coupling is quadratic: facts per item equal
  `C * k` with `C` drawn uniformly from `[2, k+2]`, so mean load is `k^2/2 + 2k` and the
  within-level span is `2k` to `k(k+2)` (measured 2026-10-17: level 8 spans 16-80 facts, a
  5x range). The level axis is therefore also a load axis, and accuracy measured across
  levels is confounded until `C` (or total facts) is held fixed. A `(k, C)` factorial is
  required before `d*+1..d*+4` can be read as a depth band (issue #71 criterion 2;
  `research/nightly-2026-10-17-0200/`).
- Seed policy: base seed is public (date-based, e.g. 20261005), post-dating model
  cutoffs; per-item seed = seed_base + 1_000_000 * level + item_index; every item
  carries `seed` and `seed_hash = sha256("family|level|seed")[:16]`; manifests
  record count, seed_base, content sha256, and the seed-hash-chain sha256.
  Reproducibility: regeneration from the seed must be byte-identical.
- Item files: `items/<family>/l<level>.jsonl` + `l<level>.manifest.json`, one JSON
  object per line, sorted keys, compact separators, no em/en dashes. Items and
  seeds are public (public-only rule).

## Work Guidance

- New family: separate module, same CLI shape (`--selftest`, `--generate`,
  `--manifest`), selftest must cover determinism, solvability, format, and a
  negative-control mutation before merge.
- Reuse external generator infrastructure where the study names it
  (2404.07353, ARC-GEN 2511.00162) instead of re-implementing.
- Human-solvability smoke check (>= 3 independent humans per family, issue #4)
  gates the M2 go/no-go, not the generator merge; keep it open in issue #4.

## Verification

- `python3 generators/digit_matrices.py --selftest`
- `python3 generators/ladders.py --selftest`
- regeneration hash stability: `--generate ... --out f` twice, `sha256sum f` equal;
  manifest `sha256` field equals the file hash
- repo parity: `scripts/check_links.py`, dash scan, CHANGELOG entry

## Child DOX Index

| Path | Scope | File |
|------|-------|------|
| `items/` (repo root) | generated task items + per-level manifests, public seeds, machine-readable counts | - |
