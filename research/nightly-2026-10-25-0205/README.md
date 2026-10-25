# Round 23 (2026-10-25 02:05): the (k, E) frontier walk

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is the
reproducible record: script, gate, prompts, raw responses, scores.

## Question

Where is the ceiling of a flash-next-class local endpoint as a function of BOTH hop depth k and
prompt load E, and is the failure at the joint corner a surfacing collapse (the output budget runs
out before a verdict is committed) or a correctness collapse (a wrong verdict is committed)?

Motivation, from the archive:

- round 21 (PR #95): depth at constant load, E = 24, k in {2,3,4,6,8,12}, this class: 36/36
  delivered in the answer field and 36/36 correct, no turnover, `d* >= 12`.
- round 22 (PR #96): load at constant depth, k = 4, E in {24..240}, 27B class: 36/36 delivered and
  correct, and output did not grow with the irrelevant facts (0.97x; a strategy switch away from
  enumeration above ~100 facts).
- round 19 (PR #93): the coupled construction on THIS class, k = 24 with E = 264: 0 of 6
  negative-arm cells delivered an answer at any budget up to 2048.

So a ceiling exists on this class, and neither axis alone, inside the grids tried, reaches it.
Issue #71 asks for the two-dimensional restatement ("a frontier in (k, E)") and names the cells
this round walks.

## Instrument

`frontier_walk_probe.py` (stdlib only). Construction: C disjoint directed paths of exactly k edges
over fresh entity names, one rule sentence (transitivity of `precedes`), E = k x C facts in shuffled
order, one query per prompt, answer required as exactly one word. Gold from an unbounded BFS that is
independent of the generator, plus a structural audit (component edge and node counts, path shape,
no branching, query source a head and query target a tail, label agrees with BFS).

Matched pair (issue #78 acceptance criterion 1): every dispatched graph is asked TWO questions over
the identical fact list, identical entity names, identical fact count and the identical queried
source; only the queried target varies.

- arm F: forward query, gold yes, k hops along one path.
- arm X: cross-component query, gold no, the target is the tail of a different path, chosen
  deterministically from the item digest.

`pair_violations()` asserts this on every dispatched pair, and `--selftest` carries the planted
non-matched control (a variant built from another item's facts, from a different cell of the walk).

Declared walk (fixed before any measurement, seed base 20261024); consecutive cells differ in
exactly one axis, asserted in `--selftest`:

| cell | k | C (paths) | E (facts) | transition from previous |
|------|---|-----------|-----------|--------------------------|
| S1 | 4 | 6 | 24 | origin |
| S2 | 4 | 24 | 96 | load x4 |
| S3 | 8 | 12 | 96 | depth x2 |
| S4 | 8 | 24 | 192 | load x2 |
| S5 | 12 | 16 | 192 | depth x1.5 |
| S6 | 16 | 12 | 192 | depth x1.33 |

Readout stack, declared before dispatch (issue #94): `content_only` (last standalone yes/no in the
answer field), `loose_fallback` (the archived convention of rounds 10 to 22: content, else the last
yes/no in the reasoning field), `delivered_or_strict` (content, else round 19's strict trace
commitment rule). Provenance of every fallback token is classified (`instruction_echo`, `terminal`,
`mid_trace`).

## Anchors (why this walk is a continuation, not a new grid)

The construction re-uses rounds 21 and 22: same seed base, same name pools, same seed formula
`SEED_BASE + 1_000_000*k + 10_000*C + index`, same 40-candidate pool, same selection rule. Therefore
S1 IS round 21's k = 4 level (and round 22's E = 24 level) and S2 IS round 22's E = 96 level. The
pool blobs and the six arm-F prompt digests are hardcoded pins (`A1_*`, `A2_*` in the script) and
`--gate` and `--probe` refuse when they do not match:

- A1, cell S1, pool blob `11ab33acc9ea42fd...`, three prompts, archived answers yes with 351, 360,
  385 completion tokens (round 21, this class) and 304, 340, 293 (round 22, the other class).
- A2, cell S2, pool blob `8adaedb0c0376d72...`, three prompts, archived answers yes with 984, 1006,
  987 completion tokens (round 22, the 27B class).

`--selftest` tampers with a blob and asserts the anchor check fails, so the fail-closed property is
tested and not merely asserted.

## Selection rule

Fixed in advance: candidates in seed order; the first three GOLD-YES candidates of each cell become
the arm-F members of the three dispatched pairs, each paired with its deterministic arm-X variant.
Every candidate and every variant must pass the structural audit, and every pair must pass the
shared-content assertion, before the cell is built at all.

## Leak gate

Permutation-calibrated battery (blind traversal-free lexical rules over the query endpoints and
fact positions, single features and conjunctions, exact label-shuffle nulls, 400 permutations,
family-wise alpha 0.05), run on the 40-candidate pool and on the paired pool of each cell, never on
the selected pairs. Gate `f324feda` (schema `round23-gate-v1`): no cell flagged on either pool.
Disclosed edge: the S2 candidate pool reaches an observed maximum of 0.725 exactly at its calibrated
threshold 0.725 (p = 0.11); the flag rule is strictly greater, and this pool is byte-identical to
round 22's E = 96 pool, which reported the same edge.

## How to reproduce

```
python3 research/nightly-2026-10-25-0205/frontier_walk_probe.py --selftest
python3 research/nightly-2026-10-25-0205/frontier_walk_probe.py --gate --out /tmp/gate.json
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
python3 research/nightly-2026-10-25-0205/frontier_walk_probe.py \
  --probe --out-dir research/nightly-2026-10-25-0205
python3 research/nightly-2026-10-25-0205/frontier_walk_probe.py --analyze \
  --out-dir research/nightly-2026-10-25-0205
```

`--probe` refuses unless the leak gate is clean AND both anchors match AND the endpoint passes a
256-token chat health call. Endpoint values are read from the environment and never written to an
artifact; stored model text passes a sanitizer for URLs, IP addresses and absolute paths.
`--resume` re-uses archived cells only under the identical gate hash.

Endpoint calls used: 36 grid prompts + 1 health = 37 of the 40-call cap, `max_tokens = 2048`,
`temperature = 0.0`, concurrency 2 (chosen from the measured single-stream rate of 58.2 tok/s),
dispatch wall 762.8 s, zero retries, zero transport errors, zero abandoned cells.

## Results

Round-8 trichotomy per cell (Wilson 95 %, floor 0.60), on the delivered answer:

| cell | k | E | correct / n (content_only) | content-silent | length-truncated | mean completion tokens | mean prompt tokens | status |
|------|---|---|----------------------------|----------------|------------------|------------------------|--------------------|--------|
| S1 | 4 | 24 | 6/6 | 0 | 0 | 445.5 | 438.0 | maintained |
| S2 | 4 | 96 | 6/6 | 0 | 0 | 930.0 | 1448.5 | maintained |
| S3 | 8 | 96 | 6/6 | 0 | 0 | 1177.3 | 1446.8 | maintained |
| S4 | 8 | 192 | 4/6 | 2 | 2 | 1245.2 | 2899.8 | inconclusive |
| S5 | 12 | 192 | 2/6 | 4 | 4 | 1675.0 | 2895.7 | budget_limited |
| S6 | 16 | 192 | 1/6 | 5 | 5 | 1772.2 | 2899.2 | budget_limited |

1. **The frontier is inside the walk.** First non-maintained cell S4 (k = 8, E = 192). Maintained
   region under `content_only`: E <= 96 at k = 4 and k = 8 (`maintained_by_k {4: 96, 8: 96}`,
   `maintained_by_edges {24: 4, 96: 8}`).
2. **Surfacing, not correctness.** 25 of 25 delivered answers are correct and there is not one wrong
   answer in the grid; all 11 failures are `length` truncations at exactly 2048 tokens with the answer
   field silent.
3. **The readout arms diverge.** `content_only` 25 answered / 25 correct, `delivered_or_strict` 28 /
   28, `loose_fallback` 36 / 33. The three answers only the loose convention rescues are arm F items,
   gold yes, whose last trace yes/no is `no` and whose provenance class is `instruction_echo` (the
   token sits inside the prompt's own "yes or no" phrase). The strict rule refuses all three and
   accepts three genuine commitments, all correct. 7 of 36 records carry an echo as their last trace
   token. Among the 11 content-silent cells the fallback token is "no" in 10 (0.909; constant-"no"
   baseline 0.50).
4. **No enumeration switch on this class.** Mean completion at S6 is 3.98x S1 (round 22 measured
   0.97x at E = 240 on the 27B class). Distractor-mention ratio 1.00, 0.83, 1.00 at E <= 96 and 0.51,
   0.63, 0.64 at E = 192: enumeration is trimmed but never abandoned, and it is what consumes the
   budget. Ordered chain coverage on gold-yes items follows: 1.00, 1.00, 1.00, 1.00, 0.82, 0.75.
5. **Matched-pair discordance.** 18 pairs: 10 both correct, 4 arm F correct with its own arm X partner
   silent, 1 in the reverse direction, 3 both silent. Exact McNemar p = 0.375, so the direction
   (arm X silent 7 times, arm F 4 times) is consistent with round 19's fragile-negative-arm reading
   and cannot be separated from noise at this n.
6. **Predictions** (declared in gate `f324feda` before any prompt): P1 fail (prompt-token ratio 6.62x
   passes, strict monotonicity does not: S3 is 1.7 tokens, 0.12 %, below S2 at the same fact count,
   because entity-name length is random), P2a pass, P2b pass, P3 pass (3.98x), P4 fail (b = 4 but
   c = 1, declared c = 0), P5 pass (25/25), P6 pass (0.909, non-vacuous), P7 pass (6/6 anchors).
7. **Token model, censored and therefore descriptive.** Fit on the six cell means: +137.7 tokens per
   hop, +5.65 tokens per fact, interaction -0.447, r2 0.959, with 11 of 36 cells censored at the 2048
   cap. The interaction term is an artifact of truncation; the defensible statement is geometric: the
   ceiling is a censoring surface in (k, E, budget).
8. **Budget replay** (character-proportional estimate recomputed from archived fields, not a measured
   count): 1/36 answers would surface at 256 tokens, 9/36 at 512, 14/36 at 1024, 25/36 at 2048, and
   every surfaced estimate is correct.

## What this changes

- Issue #71: the ceiling on this class is placed within one grid step (maintained at (8, 96), not
  maintained at (8, 192)); the next instrument bisects load at fixed depth (k = 8, E in {112, 128,
  160}) and adds k = 12 and k = 16 at E = 96. All d* and E* statements must be reported as (k, E,
  budget) surfaces at budget 2048: `budget_limited` bounds surfacing under the protocol cap, not
  competence.
- Issue #94: first round where the arms disagree, and the disagreement is the echo class; proposed
  readout contract for the pilot is `content_only` primary, `delivered_or_strict` the only rescue,
  `loose_fallback` reported and never scored.
- Issue #78: the shared-content polarity pair works and is asserted, but separating the
  fragile-negative-arm claim needs at least 40 pairs, which is a generator-side ask.

## Disclosure

Six cells, three matched pairs per cell, one endpoint class: exploratory. Evidence label **Executed**
(no independent verifier pass, not covered by the pre-registered decision table). One quantized local
deployment with undisclosed training data; not H1 evidence. The 2048-token output cap is part of
every ceiling stated above. Endpoint identity is not fingerprinted in the archive by design, so
"the same class as rounds 15, 17, 19 and 21" is a slot inference. Two implementation bugs were
caught by the anchor and analysis checks before the record was finalized: the name pools and two
anchor prompt digests had first been transcribed from truncated output and did not reproduce the
archived blobs (the fail-closed anchor refused them), and a status field was read from the token rows
instead of the classification rows in the transition block (round 22's recorded failure class, now
asserted by `--selftest` item 14). No prompt was spent before the anchors matched.
