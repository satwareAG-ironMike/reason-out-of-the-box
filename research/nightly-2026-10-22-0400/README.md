# Round 18 (2026-10-22 04:00): the fixed-budget depth curve on the 27B class

Tracker: issue #65. Branch `research/nightly-2026-10-22-0400` (stacked on the
round-17 branch, so the round-16 and round-17 archives are in-tree as anchor
and cross-class reference). Endpoint: a 27B-class local endpoint (the class
round 16 measured at k = 24; sanitized description, no endpoint value in any
artifact). State: **Executed** (no independent verifier pass this round,
disclosed below). Serves #71 (depth ceiling per (family, endpoint),
budget-controlled) and #78.

## Question

Round 16 measured this class at k = 24 (33 of 33 answered cells correct, the
light-thinker profile with answers in `content`). Round 17 ran the mirror
question on the flash-next class at k = 24/32/48: no turnover, every cell
answered, ceiling cells rescued from the reasoning trace. Round 18 mirrors
round 17 on this class at the identical 36-cell grid (byte-identical prompts,
verified fail-closed before dispatch): **does the flash-next class's clean
deep-level behaviour at the fixed 2048-token budget hold on the 27B-class
endpoint at k = 32 and 48, or does the cross-component arm X turn over there
- and if so, is the turnover an answerability (budget) collapse with answered
cells still correct, or a correctness collapse?** Two joins accompany the
curve: the level-24 cells anchor to the round-16 archive (same class,
temperature-0 rerun) and every cell pairs cross-class to the round-17 archive.

Predictions were declared in the gate (`gate.json`, schema `round18-gate-v1`,
gate_hash `68745581fff326a76d630b5d6523754e4424c89a0478970112f5b31436bc8926`)
before any prompt was spent:

- **P1** every answered cell correct (budget-limited turnover; rounds 6, 15,
  16 and 17 mechanism);
- **P2** answerability non-increasing in k across (24, 32, 48) with at least
  one strict drop at 32 or 48, F1 answering at least as often as X at the
  deepest truncated level;
- **P3** truncated cells die late (median expected-traversal coverage >= 0.8);
- **P4** cross-class answer agreement on every cell both classes answered
  (joined to the round-17 archive on item_id + arm; round 16 vs round 15 at
  k <= 24 gave 33 of 33 agreement, zero discordant pairs).

## Gate (before any prompt was spent)

Generator `generators/ladders.py` sha256 `b0d77efd...` (issue #69 repair, on
main); pools of 300 items per level at seed_base 20261019; the level-24 blob
byte-identical to the round-15/16/17 pin (`cab16fae...`), levels 32 and 48
pinned by the round-17 gate (`3781a95d...`, `f4dee382...`) and re-verified by
this gate. Selection: first 3 usable items per level, chain_path rule verbatim
from rounds 10/11/15/16/17, plus the declared context-safety filter (all
rendered arm prompts <= 45,000 chars) applied identically at every level.
Leak battery (15 direction-blind rules + 2 references, exact label-shuffle
nulls, Bonferroni): no blind rule fires on the matched corpus (best blind
rule 0.75, below the 0.90 bar); the corpus is discriminating (connectivity
!= reachability in exactly the nine R1 cells). Matched-pair invariant: zero
violations, seed-determinism of item construction re-verified.

**Anchor pairing (fail-closed):** the seed policy makes the level-24 items
reproduce round 16's L24 items exactly; the 12 anchor cells verified 12/12 by
prompt sha256 against the in-tree round-16 archive, and `--probe` refuses to
run when that verification fails. The anchor doubles as a temperature-0 rerun
test on the same endpoint class (round 16 spent two attempts on its three
truncated X cells; this round declares no retry on truncation, and the row
`attempts` fields make the asymmetry explicit).

**Cross-class pairing (fail-closed):** all 36 cells verified 36/36 by prompt
sha256 against the in-tree round-17 archive; `--probe` refuses to run when
that verification fails.

## Probe

36 prompts, temperature 0, `max_tokens = 2048` (the budget is the treatment),
two-phase transport per issue #73 (phase-1 walls 8.3 / 6.3 s, estimate
16.7 s/item, concurrency 4 for 34 cells), 900 s per-item deadline, level
budget 1500 s. Declared retry policy (inherited from round 17): **truncation
is a measured outcome and is never retried**; retries are spent only on
transport failures and empty completions. **Total endpoint calls: 37 (36
cells + 1 health check), zero retries, zero transport failures, zero
abandoned cells. Wall 547.6 s.**

## Answer

**Budget turnover, confined to the X arm at k = 24; correctness holds
everywhere.** 29 of 36 cells answered, 29 of 29 correct (per level k = 24 /
32 / 48: 9 / 10 / 10 answered, all correct; per arm F1/R1/F2 each 9/9, X 2/9).
Turnover classification: `budget_turnover` (every answered cell correct, some
levels answer fewer than 12). The directed-traversal oracle matches all 29
answered cells (the traversal signature matches 36/36 cells including the
unanswered ones); undirected connectivity matches 27 (failing exactly the nine
R1 cells); constant-yes and constant-no each match 18; exact McNemar shows
zero discordant pairs in both matched families (p = 1.0).

Predictions: **P1 holds** (29 of 29 answered cells correct); **P2 fails
honestly** - answerability did not decay (0.75 / 0.833 / 0.833 at k = 24 /
32 / 48: it rises from 24 to 32 and is flat at 48, so there is no strict
drop at 32 or 48); the shortfall is entirely the X arm: X answers 0/3 at
k = 24, then 1/3 at k = 32 and 1/3 at k = 48, and at the deepest level F1
(3/3) answers more than X (1/3), the last P2 clause that does hold.
**P3 holds** - all seven truncated cells (all X arm) die at full
expected-traversal coverage (median
coverage 1.0, threshold 0.8): the budget is exhausted exactly where the answer
should land, never in preamble; **P4 holds** - on the 29 cells both classes
answered, 29 of 29 answers agree; paired correctness shows zero discordant
pairs (b = 0, c = 0, exact McNemar p = 1.0).

The round's information is the cross-class comparison on the identical grid at
the identical budget (this class vs the flash-next class of round 17, 36/36
cells prompt-paired):

- **The disagreement is exactly the seven truncated X cells.** Round 17
  answered all nine X cells (every one via the reasoning fallback at the 2048
  ceiling); this class answered two (L32-2 via the reasoning fallback,
  L48-2 via `content` at 509 tokens) and truncated the other seven (three at
  k = 24, two at k = 32, two at k = 48, all at 2048 tokens with no yes/no in
  either field). On the 29 cells both classes answered, agreement is 100%.
- **This class is far more token-efficient where it answers.** Mean
  completion tokens per arm (mean over the arm's nine cells, truncated cells
  censored at 2048), this class vs round 17: F1 657 vs 1106, F2 745 vs 1141,
  R1 453 vs 1717 (3.8x shorter on the reverse-reachability arm), X 1877 vs
  2048. Reasoning rescues: 1 of 29 answered
  cells here vs 17 of 36 in round 17; the light-thinker profile of round 16
  extends to k = 48.
- **The positive arms still answer cheap-early, more cheaply than round 17.**
  Among answered F1/F2 cells with a natural stop, completion tokens fit
  -61.9 + 22.0 * k (Pearson r = 0.879, 18 cells) vs round 17's -50.8 +
  33.1 * k (r = 0.845): about a third slower growth per hop. Full-chain
  recitation (all interior nodes named) is 2 of 36 cells (round 17: 9/36,
  round 16: 5/36).
- **The single reasoning rescue commits mid-trace:** the L32-2 X yes/no sits
  at 0.4014 of the reasoning stream (median and max both 0.4014, the only
  cell with a defined commit fraction).
- **Anchor rerun (cell-paired to round 16, same class):** 12 of 12 answers
  agree, outcomes identical, completion tokens equal on all twelve pairs
  (e.g. 424 = 424, 576 = 576, 2048 = 2048). Temperature-0 rerun
  reproducibility on this class is exact at the answer level and exact at the
  token level (stronger than round 17's approximate token agreement).
- **The k = 24 X shortfall is a rerun of round 16's own result:** round 16's
  three truncated X cells truncate again on this endpoint (2048 = 2048), now
  with the declared single attempt; the X cells that do answer at k = 32/48
  are cells round 17 also answered, and all seven X cells answered by round 17
  that this class truncated are the only cross-class delta in the whole grid.

## Adjacent literature

No new literature pass this round (the round-17 framing stands: the coupling
tax, arXiv:2605.07686, names the shared-budget mechanism this grid measures
per arm; arXiv:2607.21433 characterizes the budget-exhaustion split the X arm
at k = 24 sits in). The cross-class token-efficiency contrast at equal
correctness is the new datum; the cross-component arm X is where the two
classes diverge at the fixed budget.

## Disclosure and limits

No independent verifier pass: state **Executed**, not Reproduced. n = 9 per
arm and n = 3 items per level: exploratory, not confirmatory. The reasoning
fallback parser scores one of the 29 answered cells (L32-2 X); the rescued
token is the LAST yes/no in a still-running trace, which is a convention, not
a transcript of the model's final word (arXiv:2605.07686 is the adjacent
warning; rounds 15/16 showed the rescue property does not transfer across
classes, and this round shows the answerability it enables does not either).
The anchor pins one endpoint of one class: results remain one endpoint per
class, quantized local deployment, undisclosed training data; not H1
evidence. Cross-class pairing assumes the same flash-next endpoint was served
in round 17 (class identity by runner assignment, not re-verified in this
round). The P4 agreement is over the intersection: the seven cells only round
17 answered are excluded from it. Prompt load and depth stay coupled at these
levels (#71 option 2 open). Levels 32/48 had no cell-paired prior on this
class.

## Reproduce

```
python3 research/nightly-2026-10-22-0400/crossclass_depth_curve.py --selftest
python3 research/nightly-2026-10-22-0400/crossclass_depth_curve.py --gate    # compare gate_hash
python3 research/nightly-2026-10-22-0400/crossclass_depth_curve.py --analyze
```

`--probe` needs a served endpoint via `NIGHTLY_BASE_URL` / `NIGHTLY_MODEL_ID`
/ `NIGHTLY_API_KEY` (never written to artifacts) and the round-16 and round-17
archives present in-tree (`research/nightly-2026-10-21-0400/`,
`research/nightly-2026-10-22-0200/`); it refuses to run when either the 12/12
anchor-pairing or the 36/36 cross-class pairing verification fails. Files:
`gate.json` (pre-registration record including both pairing verifications),
`raw.jsonl` (36 records, sanitized raw responses), `summary.json` (aggregates
incl. predictions, turnover rule, anchor, cross-class join, token law,
mid-stream commitment), `transport.json` (dispatch note). Artifact sha256 at
round close: `raw.jsonl` `a82a2c5b3cb67651047bea5615c31d026b920711908c37c9700c18142bbeef02`,
`summary.json` `9bf814f971fa7de9f4223e3b7bd4eb61578aefcb575819e27d0aff6fcb6401c5`,
`gate.json` `b66142f4f79c0b6b861a5ef63f9588706def24055f0dbbfc864a3f3f63dcf3a0`,
`transport.json` `0b5bd987a326da653d761b2fa2de3b98da297b0ae9441db59fc72eecdd2eebaa`.
