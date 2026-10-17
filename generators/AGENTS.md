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
  2). Subtypes `mult_mult` and `dp_puzzle` (issue #4 list) are pending.
- Leak gate `audit_ladder_leaks.py`: permutation-calibrated, not an absolute floor.
  The null is the exact hit-count distribution of the best rule in the audited
  hypothesis class under label permutation (binomial weights over the bitmask
  class, no Monte Carlo); a rule is gated only when it beats the class's own
  constant rule AND clears that null at `NULL_ALPHA = 0.05`. `CHANCE_MAX = 0.55`
  survives only as a reported legacy floor (`legacy_threshold_leaks`), never as the
  decision. Features constant across an item set carry no label information and are
  reported, never gated. Level 1 is a `lookup_control`: at k=1 `direct_fact` is the
  task itself, so level 1 is excluded from the gate and from C5 depth evidence;
  ladder depth evidence starts at k=2. `min_detectable_accuracy` per level states
  the smallest rule accuracy that could have flipped the gate, so every `no_leak`
  verdict ships with its detection power. `--audit-generated --count N --seed-base S`
  is the fresh-seed replication path; `--json` writes the full report to stdout.
  `no_leak` is a statement about the tested class only, and the class is known to be
  incomplete: the undirected component-membership feature (query source and query
  target in the same connected component of the fact graph, ignoring edge direction)
  reproduces the gold label at accuracy 1.0000 on all 300 shipped items at every
  ladder level, and the 18-feature class contains no relational feature. Widening the
  class to relational features is open work, tracked on issue #67; until then the
  shipped corpus is clean under the tested class and leaky under connectivity.
- Fixtures `generators/fixtures/`: the pinned pre-fix issue #67 items (every 8th
  line of the l2/l8 files at 49ee823) committed as the negative control for the gate
  and the probe. `--audit-fixtures` asserts the gate FIRES on them: exit 0 means
  detection power demonstrated, exit 4 means the gate failed to detect a documented
  leak. These items carry the leak and are superseded; they never enter a study run,
  a pilot, or the main experiment. Provenance and extraction rule:
  `issue67_prefix.manifest.json`.
- Model-side probe `probe_ladder_shortcut.py` (issue #67): matched-pair shortcut
  probe. 4 cells x 10 items = 40 experimental prompts, fixed budget: pre-fix l2,
  post-fix l2, pre-fix l8, post-fix l8, paired by seed (the instrument asserts seed
  identity, so the two arms of a level differ only in construction). Zero-shot,
  temperature 0, one fixed neutral template, one decoding seed, no traversal or
  chain-of-thought instruction; the item `rule` field is withheld from the prompt
  because study-design forbids task-specific prompt tokens. Primary metric is
  balanced accuracy (the cells are base-rate imbalanced, so every constant baseline
  sits at exactly 0.5), scored against three a-priori baselines fixed in advance
  (majority, direct_fact, leak signature) and an exact fair-coin answering null; the
  verdict rule is encoded in the instrument and never chosen after seeing output.
  Calibration calls are capped at 3, use seeds asserted outside the 40, take the
  worst-case chain length of each arm, and are never experimental data. The endpoint
  base URL is read from `NIGHTLY_BASE_URL` only and never written into an artifact.
  Resilience is part of the contract (issue #67 round 5: attempt 1 lost 21 paid answers
  to a mid-run socket timeout): records are appended and fsynced one by one, a stalled
  item is retried once under a global budget (`MAX_RETRIES_TOTAL = 8`,
  `RETRY_BACKOFF_S = 20`, client timeout 600s), a still-failed item is recorded as
  `finish_reason="client_error"` and invalid rather than ending the run, and `--resume`
  reuses answered items while re-asking failed ones. Resume validates every stored record
  against the prompt this run would send before rewriting the raw file. The manifest
  reports `endpoint_attempts`, `retries_used`, `retry_budget`,
  `items_reused_from_prior_attempt` and `items_recorded_as_client_error`.
  The instrument ran once (`runs/nightly-2026-10-16-0200`, verdict
  `traversal_consistent`, all 4 cells strong) and is frozen for that run: do not edit it
  against that run's artifacts. Two known defects are recorded rather than fixed in place:
  the per-cell `leak_sig_agreement` and `direct_agreement` fields hold baseline-vs-gold
  accuracy, not model-vs-baseline agreement (model-vs-baseline is computed by
  `runs/nightly-2026-10-16-0200/analyze_run.py`), and the fixture arm is degenerate because
  its leak signature equals the gold label on every item, so it is a capability control and
  not a shortcut discriminator. The verdict means "not explained by the tested shortcut
  signatures": it does not separate directed traversal from undirected component clustering,
  because component membership reproduces the gold label at 1.0000 on the shipped corpus.
- Solvability is generation-time policy: for every component, exactly one rule of
  the pool must reproduce both demonstration rows jointly; non-identifiable
  samples are rejected. The selftest re-derives uniqueness from the emitted item.
- Depth grid across families (reconciles "3 families x 5 depths" with the
  per-family knobs in `docs/study-design.md`): digit matrices levels 1-4;
  compositional ladders k in {1, 2, 4, 6, 8} hops (k=1 is the lookup control, not
  depth evidence); ARC-style 1-5 composed transforms. The study runs d*+1..d*+4
  around the audit ceiling d*.
- Seed policy: base seed is public (date-based, e.g. 20261005), post-dating model
  cutoffs; per-item seed = seed_base + M * level + item_index, M = 1_000_000 for
  digit matrices and 2_000_000 for ladders; every item carries `seed` and `seed_hash`,
  whose implemented form differs by family and must not be assumed uniform:
  `digit_matrices.py` uses `sha256("<family>|<level>|<seed>")[:16]`, `ladders.py` uses
  `sha256("<family>|<task_type>|<level>|<seed>")[:16]` (verified against 300 of 300 items
  at every level of both families); manifests record count, seed_base,
  content sha256, and the seed-hash-chain sha256. Reproducibility: regeneration from
  the seed must be byte-identical.
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
- Instrument selftests must contain a control that plants the very defect the
  instrument claims to detect, so detection power is asserted, not assumed.
- Fixture items are negative controls: they never enter a study run, a pilot, or a
  model-facing experiment outside the probe's shortcut-present arm.
- Run artifacts (manifests, raw responses, reports) live in `runs/`, never under
  `generators/`.

## Verification

- `python3 generators/digit_matrices.py --selftest`
- `python3 generators/ladders.py --selftest`
- `python3 generators/audit_ladder_leaks.py --selftest` (10 controls, planted leak
  plus label-shuffle null)
- `python3 generators/audit_ladder_leaks.py --audit-fixtures` (exit 0 required: the
  gate fires on the pinned issue #67 leak; exit 4 means detection power is lost)
- `python3 generators/audit_ladder_leaks.py --audit-shipped` (shipped corpus: exit 0
  required at every depth level; `--json` carries `min_detectable_accuracy` per level)
- `python3 generators/probe_ladder_shortcut.py --selftest` (13 control groups, group 13
  plants a mid-run socket timeout and asserts the run survives, the retry budget is
  capped, failures are recorded rather than dropped, and `--resume` neither re-asks an
  answered item nor reuses a failed one)
- `python3 generators/probe_ladder_shortcut.py --dry-run` (40 prompts and the
  prompt hash, no endpoint call)
- regeneration hash stability: `--generate ... --out f` twice, `sha256sum f` equal;
  manifest `sha256` field equals the file hash
- repo parity: `scripts/check_links.py`, dash scan, CHANGELOG entry

## Child DOX Index

| Path | Scope | File |
|------|-------|------|
| `items/` (repo root) | generated task items + per-level manifests, public seeds, machine-readable counts | - |
| `generators/fixtures/` | pinned pre-fix issue #67 ladder items, negative control for the gate and the probe; never study input | [issue67_prefix.manifest.json](fixtures/issue67_prefix.manifest.json) |
