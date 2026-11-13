# Nightly round 63: does the k > 48 name-walk panel discriminate the two wall readings on the 27B class?

| Field | Value |
|-------|-------|
| Question | Does the k > 48 name-walk panel (issue #129) discriminate the two wall readings on the 27B class, as registered by the round-61 gate row P1? Full wording in `gate.json`. |
| Gate blob | `8ae5029d565181681e3d47cf2cabfe691f1985370999fd0eaa8e9d12e4704950` (sha256 of `gate.json`, `blob` key omitted) |
| Contract | Rate-gated panel dispatch on a healthy 27B-class endpoint: 8 planned cells (two dead-end NONE controls, the four registered P1 endpoint cells, one byte-identical re-dispatch pair, one anchor liveness cell), `max_tokens` 2048, temperature 0.0, 3 pre-gate calls (two 256-token census plus one full-cap calibration dispatch on the anchor cell), measured rate 123.4 tok/s against the frozen plan thresholds, call cap 40, 11 calls used |
| Fired | 2026-11-13, gate frozen pre-dispatch; dispatch 8 of 8 cells, 97.5 s wall, 0 retries, 0 transport errors, 0 not_dispatched; 11 calls counting the 3 pre-gate and the health call |
| Verdict | `panel_delivered`, flags `endpoint_censored_at_cap` (three of four P1 cells) and `dup_pair_diverges` (the k = 50 endpoint pair); P1: 1 of 4 endpoint cells delivered, the length-generalization reading (T1-T3) survives on the 27B class; scorecard: E1 pass, E2 pass, R1 both refused, P1 1 of 4, N3 certified |

## Why

The round-61 gate registered this panel as P1, owed to the next healthy 27B-class firing:
on the four endpoint cells past the old generator ceiling (k = 48/49/50/64 at each item's
deepest step, cap 2048, name arm), at least 3 of 4 delivering the correct terminal makes
the measured ladder wall an output-budget and output-policy artifact (the issue #126
reading); at most 1 of 4 delivering (censor at the cap or a position error on the right
path, the round-59 shape) keeps the length-generalization reading (T1-T3) alive on the 27B
class. The 27B-class yes/no arm already censors at k = 48 (round 52), the name arm had
never fired at depth on the class, and round 61 added only the first shallow data point
(E1 at j = 8, correct, 1123 tokens under a starved load).

The standing rule this round applies: gate panel-scale commitments on a pre-dispatch rate
measurement. This endpoint was healthy (no co-fired load this firing): two 256-token
census calls at about 82 tok/s and one full-cap calibration dispatch on the anchor cell
at 123.4 tok/s, far above the frozen 10 tok/s threshold, so the full 8-cell plan was
selected over the trimmed 6-cell plan.

## Items and lineage

Items were generated from the pinned generator `generators/ladders.py` with per-item
generation (issue #129: the whole-series call dies at k = 49 on the entity pool; the
load-floor items keep generating past it) and the seed policy of the shipped
`generate_items` (seed base 20261005, seed = base + 2_000_000 * level + index), so every
item is byte-identical to what the shipped generator produces for its seed.

| Cell | level | facts | start | `j` | kind | gold | seed | lineage |
|------|-------|-------|-------|-----|------|------|------|---------|
| `A48_j48` | 48 | 96 | `glag` | 48 | name | `spog` | 116261051 | archived k = 48 anchor item (rounds 51 through 54), re-certified before dispatch (N3): regenerates with the archived yes/no digest `068bc6a1fb0620fb` |
| `A49_j49` | 49 | 98 | `konn` | 49 | name | `studnd` | 118261016 | first load-floor item at level 49 (round 61's new item, same seed) |
| `B50_j50` | 50 | 100 | `grudk` | 50 | name | `prish` | 120261132 | first load-floor item at level 50 (new this round) |
| `C64_j64` | 64 | 128 | `smixg` | 64 | name | `brelt` | 148261120 | first load-floor item at level 64 (new this round) |
| `B50_j50_dup` | 50 | 100 | `grudk` | 50 | dup | `prish` | 120261132 | byte-identical re-dispatch of the k = 50 endpoint cell (issue #100); prompt digest equals the original's |
| `A48_j8` | 48 | 96 | `glag` | 8 | name | `trackst` | 116261051 | the round-61 E1 coordinate; a cross-firing duplicate of that record and a within-firing duplicate of the pre-gate calibration dispatch on the same prompt |
| `A49_deadend` | 49 | 98 | `studnd` | 1 | dead-end NONE control | NONE | 118261016 | one step by design (round-60 lesson: off-end controls at depth inherit truncation); asks the first step from a path tail, where no successor exists |
| `C64_deadend` | 64 | 128 | `brelt` | 1 | dead-end NONE control | NONE | 148261120 | same control on the k = 64 item |

The pseudo-gold (the other path's tail, in the item's vocabulary) sits in every item's
fact list, so no cell can be passed by recognizing the gold.

## Fired

Pre-gate (all recorded in `measure.json`, none experimental): two census calls (69
completion tokens each, about 82 tok/s) and the calibration dispatch on the anchor cell
(1113 completion tokens in 9.0 s, 123.4 tok/s, declared `trackst`, stop). Measured rate
123.4 tok/s selected the full plan against the frozen thresholds (10 tok/s full, 5 tok/s
trimmed). Gate `round63-gate-v1` frozen at the measured rate; N3 certified before any
prompt was spent. Dispatch: 8 cells, two workers, 97.5 s wall inside the frozen 3000 s
budget, temperature 0.0, cap 2048 on every cell, 0 retries, 0 transport errors.

| Cell | declared | gold | correct | finish | completion tokens | wall |
|------|----------|------|---------|--------|-------------------|------|
| `A49_deadend` | `none` | NONE | yes | stop | 1,026 | 15.9 s |
| `C64_deadend` | `none` | NONE | yes | stop | 1,268 | 18.9 s |
| `A48_j48` | (none) | `spog` | no | length | 2,048 | 27.9 s |
| `A49_j49` | (none) | `studnd` | no | length | 2,048 | 31.8 s |
| `B50_j50` | `prish` | `prish` | yes | stop | 1,956 | 28.1 s |
| `C64_j64` | (none) | `brelt` | no | length | 2,048 | 29.0 s |
| `B50_j50_dup` | (none) | `prish` | no | length | 2,048 | 25.6 s |
| `A48_j8` | `trackst` | `trackst` | yes | stop | 306 | 3.8 s |

The three censored endpoint cells stopped at exactly 2,048 completion tokens with an
empty visible answer channel; on this serving stack the reasoning channel precedes the
answer and consumed the whole budget (trace census: 5,454 / 5,561 / 5,664 characters).
In all four censored traces the gold terminal appears in the trace text, so the answer
channel is empty while the trace restates the fact list (the round-50 / round-60
provenance gap, now at depth on this class).

## Result

- P1 (the registered discriminator): 1 of 4 endpoint cells delivered the correct
  terminal (the k = 50 item at j = 50, 1,956 tokens). Three of four censored at the
  cap. The frozen rule resolves at the 1-of-4 branch: **the length-generalization
  reading (T1 through T3) survives on the 27B class**, and the output-budget and
  output-policy artifact reading (the issue #126 reading, which required 3 of 4
  deliveries) is not supported on this class at these depths. The evaluation is
  certified: all four endpoint cells recorded and both controls valid.
- R1 (dead-end controls, validity gate): both refused correctly (1,026 and 1,268
  tokens). The NONE-gold readout is certified for this firing, which is what makes the
  P1 count admissible.
- E1 (anchor liveness): the k = 48 anchor item still delivers the correct 8th walk name
  (`trackst`, 306 tokens) on this firing. Cross-firing against round 61's E1 record on
  the identical prompt: 306 tokens here against 1,123 there, and 1,113 on this firing's
  own pre-gate calibration dispatch. The completion-token count of a fixed prompt at
  temperature 0 is not stable across firings, and is not even stable within a firing on
  this deployment (finding 4).
- E2 (census, issue #105): the census answers the two-fact transitivity query correctly
  and the trace is exposed in a non-empty channel. This firing's channel is the
  `reasoning` field (239 characters in the census; 8 of 8 raw records carry it),
  whereas the round-61 27B-class firing exposed `reasoning_content`. The exposure
  setting is a deployment property, and any cross-deployment trace claim must state
  both sides (finding 5).
- N3: certified pre-dispatch (seed 116261051, archived yes/no digest `068bc6a1fb0620fb`).
- The issue #100 self-agreement pair diverges: the byte-identical re-dispatch of the
  k = 50 endpoint was censored at the cap while the original delivered at 1,956 tokens
  (finding 3).

## Findings

1. The wall on the 27B class is not an output-budget or output-policy artifact at these
   depths. Under the registered rule, at most 1 of 4 endpoint deliveries keeps the
   length-generalization reading alive: the task stays trivial (T4, two-path BFS in NC1,
   128 facts at k = 64) while the terminal cannot be reliably surfaced inside the 2,048
   token budget at j = 48/49/64. The issue #126 zero-truncation record (flash builds)
   does not transfer to the 27B-class name arm at depth on this deployment; the two
   readings now have a class split in the record.
2. Delivery at the terminal is non-monotone in depth at n = 1: the deepest panel item
   (k = 64, j = 64, 128 facts) is censored, the k = 48 and k = 49 items are censored, and
   the k = 50 item (j = 50, 100 facts, 1,956 tokens) delivers. A single trial per cell
   cannot separate a monotone depth effect from run noise; the panel shape is reported,
   not fitted.
3. The byte-identical re-dispatch flips a delivery at the cap (issue #100): the k = 50
   endpoint's original delivered at 1,956 tokens and its duplicate was censored at
   2,048 with an empty answer channel. On this serving stack (a multi-token-prediction
   engine at temperature 0.0) the completion length of a fixed prompt is a property of
   the run, and a run that lands inside the budget delivers while a slightly longer run
   of the same prompt does not. Self-agreement on this class and depth holds for the
   declared answer when both sides deliver, and fails for the delivery outcome when the
   length sits near the cap.
4. Completion-token counts at temperature 0 are not reproducible on this deployment.
   The same anchor prompt produced 1,123 tokens on the round-61 firing, 1,113 on this
   firing's calibration dispatch, and 306 on the dispatch-phase re-dispatch of the same
   cell (3.6x within one firing). The token-per-hop cost laws of rounds 6 and 50
   (80 per hop, then 20.9 / 31.3) are order-of-magnitude statements on this stack, not
   byte-level predictions.
5. The trace-exposure census (issue #105) states this firing's setting: the reasoning
   channel is the `reasoning` field on 8 of 8 raw records, against `reasoning_content`
   on the round-61 27B-class firing. Two 27B-class deployments (different serving
   stacks, different endpoints) expose the trace through different channel fields; the
   channel name is a deployment property, and a class-level trace statement still needs
   a same-class pair with the channel exposed on both sides.
6. Accuracy on delivered cells never turns over: every delivered name in this firing is
   correct (the k = 50 terminal, the anchor at j = 8, both NONE controls, 6 of 6),
   consistent with rounds 50/55/59/60. The loss is a delivery loss, entirely at the
   2,048 cap.

## Limits

- One endpoint, n = 1 per cell, one firing: small-n exploratory by construction, and the
  label is `Executed` (no independent second implementation, no pre-registered decision
  table covering this experimental tier).
- The P1 discriminator is a registered count rule (3 of 4 / 1 of 4 / 2 of 4), not a
  statistical test; the 1-of-4 outcome resolves the registered branch, but a single
  censored cell is a run-length accident and not a depth law (finding 2).
- Finding 4 (token-count variance) is stated from three measurements on two firings;
  it is a serving-stack property, not a class property, and no byte-level prediction is
  made from it.
- The trace channel field name (finding 5) is reported for this deployment pair; a
  class-level trace claim remains out of reach per the issue #105 contract.

## Verification notes (literature)

No new literature call this firing: the theory rows T1 through T4 are carried from the
round-61 gate, work-record verified on 2026-11-12 (OpenAlex: title, authors, year; no
quote taken; the T2 NoPE-versus-RoPE caveat is on record). This round is the
experimental dispatch the round-61 gate registered; the theory block is context, not a
new claim.

## Reproduce

- `python3 name_walk_panel_r63.py --selftest` (102 deterministic checks: frozen gate
  schema, both plans, item lineage and issue #67 guards, the P1 count rule against
  synthetic record sets, the plan-selection thresholds, the dup-pair and censored-cell
  flags, sanitizer fixtures)
- `python3 name_walk_panel_r63.py --measure` (pre-gate: two 256-token census calls and
  the full-cap calibration dispatch on the anchor cell; writes `measure.json` with the
  measured rate and the plan selection)
- `python3 name_walk_panel_r63.py --freeze --panel r63` (derives the gate against
  `measure.json`; the frozen `gate.json` in this directory is the contract and is never
  rewritten by a run; the panel must equal the plan the measured rate selected)
- `python3 name_walk_panel_r63.py --run --panel r63` (health call plus the dispatch;
  incremental `raw.jsonl` writes; writes `health.json` and `summary.json`)
- `python3 name_walk_panel_r63.py --rescore` (rescores from `raw.jsonl` and
  `health.json` against the frozen blob; idempotent)
- `python3 name_walk_panel_r63.py --check-readme` (issue #137 row-and-blob guard over
  this README)

`raw.jsonl` and `health.json` carry a machine-only 16-hex model digest for verification
and are excluded from human-readable surfaces, per `research/AGENTS.md`. Every raw
record carries the gate blob. Evidence label: `Executed`; the small-n exploratory
caveat is in Limits.
