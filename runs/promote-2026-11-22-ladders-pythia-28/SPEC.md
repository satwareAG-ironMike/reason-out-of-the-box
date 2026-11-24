# PROMOTE: confirmatory ladders run on the pythia-2.8b pin (pre-written before the run)

Owner objective 2026-11-22: fire the confirmatory run and open a PROMOTE PR.
This document is the pre-registration: every parameter below is fixed here, before
any dispatch. The run may not change any of them afterwards
(`rule.json statistics.no_reanalysis`).

## Hypothesis under test

A BASE model with PUBLIC training data produces correct, unique solutions to
procedurally novel ladders tasks beyond its measured trained depth, beating
every evaluable dumb baseline by at least the frozen minimum gap. A clean
negative is an equally valid result; this run optimises for a decisive answer.

## Frozen parameters (from `evaluation/frozen/`, manifest rule `325f8897...`)

- **Family**: ladders (k-hop reachability; grid levels 1, 2, 4, 6, 8)
- **Confirmatory pin**: `pythia-2.8b` = `EleutherAI/pythia-2.8b-deduped`,
  hub revision `7d977fed8c4ce9649816af8cd5fe36a639cbe5b2`, Q4_K_M.
  `instruct`/`rl`/`reasoning_prompt` all false, quantised to Q4_K_M. Served on
  the internal serving host behind the single-server pointer contract (port
  8081, pointer file selects the model; the build digest is recorded at
  scoring time in the tracker ops record, not named in any public file).
- **B3 partner arm**: `pythia-1b` (family's smaller partner, `family_minimum`),
  same item set, same sampler.
- **Calibration arm** (trained depth d_hat): seed base `20260101` (frozen
  `calibration_seed_base`), 40 items per level x 5 levels = 200 items,
  mastery 0.80.
- **Novel band**: seed base `20261122` (run-date fresh seed, never shipped),
  `min_n_confirmatory` = 300 items per cell. Cell set: the grid levels whose
  `level - d_hat` is in the frozen `novel_band_offsets` {1, 2, 3, 4}. The cell
  set is a pure function of the measured d_hat; no choice is made at dispatch.
- **Sampler** (frozen per round, recorded in `sampler.json` before dispatch):
  temperature 0.0, top_p default, max_tokens 256 (one-word answer contract;
  round 81's 8-token first pass is the failure record under `.trash-8tok/`),
  one dispatch at a time, zero-shot, the frozen neutral ladders prompt
  (`verify.py build_prompt`, no reasoning-style instruction).
- **Decision rule**: `min_gap_absolute` 0.10, Wilson 95% cell intervals,
  exact two-sided McNemar on the model-vs-best-baseline discordant pairs,
  pooled Holm-Bonferroni at alpha 0.05 over the confirmatory beyond-depth cell
  set. A cell passes only if the model Wilson lower bound is strictly above
  every evaluable baseline accuracy AND the McNemar p survives Holm.

## Known blockers (pre-registered, reported not waived)

- **B1 corpus nearest-neighbour**: not_evaluable without a corpus backend.
  No corpus slice of the Pile is configured on the serving host, and no
  infini-gram / OlmoTrace instance has been named (owner act #3). A
  baseline that cannot be evaluated blocks the unique claim for the cell;
  it never waives it.
- **Novelty**: without a configured corpus backend the novelty check is
  not_evaluable; the N3 NEGATIVE branch and the POSITIVE `novelty_ok` check
  read not_evaluable over this run's cells.
- Consequence: this run produces the confirmatory d_hat, beyond-depth
  accuracies, the B2/B3 gaps, and a named blocker list. Its verdict is
  OPEN-with-blockers unless and until a corpus slice is named. That is the
  decisive distance report the loop owed.

## Budget and lane

Confirmatory runs are owner-scoped and not part of the weekly compute cap
(research/AGENTS.md): 200 calibration + up to 1200 novel-band prompts on
pythia-2.8b, plus the same novel-band item set on pythia-1b (B3).
Serve-side decode speeds at probe time: 2.8b ~27.6 tok/s, 1b ~77.7 tok/s;
the whole battery is expected to finish in a single night. Self-hosted
endpoint only.

## Execution record (filled after dispatch, forward-only)

- `sampler.json`: sampler + serving build digest, written before the first dispatch
- `calibration-tasks.jsonl`, `calibration.jsonl` (200 rows), `tasks.jsonl` (novel band),
  `raw.jsonl` (pythia-2.8b), `partner-raw.jsonl` (pythia-1b, B3)
- `score.json`: `score.py --score` at the frozen instrument on main
- round ledger line and this directory's README summary follow the score

Owner merges this PR after reading it; the promoted result then feeds docs/
and the README verdict (owner step).
