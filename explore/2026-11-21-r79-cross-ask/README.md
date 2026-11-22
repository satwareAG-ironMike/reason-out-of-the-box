# Round 79: cross-ask family, #139/#94/#145 trigger fixes (exploratory)

Moved to the exploratory lane by owner objective 2026-11-21; was prepared as
`research/nightly-2026-11-21-0400`.

## Question

Does the cross-ask family survive the three trigger fixes shipped this round in one
`gate.json`?

- **#145 `censored_not_a_miss`**: censored arm cells (finish_reason length, no delivery
  inside the budget) are excluded from the contrast denominator and reported as
  `censored_at_cap`, not counted as misses; the competence verdict no longer inherits
  the output budget.
- **#139 `control_own_budget`**: the NONE-gold control (`over_end`) carries its own
  `CONTROL_MAX_TOKENS = 512` budget, not the deep cells' `max_tokens`; a control
  exhausted at its own budget ships `not_delivered`, not a censored-miss.
- **#94 `fallback_provenance`**: the reasoning-fallback token's first-occurrence position
  in the trace is recorded and classified `own-channel` vs `donor-block`; a token sourced
  from the restored donor block is not the model's own reasoning provenance.

## Run

- Endpoint: `qwen38-flash-next` (public name only, self-hosted, no metered key).
- `--selftest`: 159 of 159 checks green (151 base + 7 planted-slip fixtures).
- 28 records dispatched sequentially (issue #73, #141).
- `--rescore`: exits 0, `summary.json` sha256 `6119340eb48b`.
- Primary verdict: `X2_tail_shortcut` = `selection_beyond_tail`, arm X delivered the
  draft tail 0 of 3.
- The `over_end` control shipped `not_delivered` under its own 512-token budget, as
  the #139 fix requires.
- Censored arm cells (finish_reason length, no delivery in the 2048 cap) read
  `censored_at_cap` and are excluded from the contrast denominator, as the #145 fix
  requires.

## Scoring

The frozen judge (`evaluation/frozen/`, issue #194) scores this round's raw records. The
round is exploratory; no confirmatory cell is produced. `score.json` will be written at
the first frozen-judge PR merge.

## Ledger

`explore/LEDGER.md` row r79: `OPEN, exploratory`. Distance moved: registers the
cross-ask arm; does not move the beyond-depth gap.
