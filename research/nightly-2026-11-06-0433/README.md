# Round 51 (2026-11-06 04:33): the load floor, where the negative arm answers wrong instead of running out

Firing: 2026-11-06 04:33, pool slot 3/6 (issue #65). Class: a flash-next-class local endpoint
(serving id disclosed only in the commit `Model:` trailer; artifact digest
`c62b81e96826354e`). No metered or hosted provider was used; no search API was used. Status
label: **Executed** (see Limits).

## Question

Registered before dispatch (schema `round51-gate-v1`, frozen in `gate.json`, pinned in the
instrument), blob:

`60b0d62c165f8c2a225a4eeb499e456859c281c4d30b64855c6a4dc3bf247716`

> Where does the per-item output budget cross the 2048 cap on the ladder family at the
> generator's load floor (facts = 2k), and does a trace cut below its own measured natural stop
> still yield a verdict?

Round 50 placed `d*` (the depth at which the family stops delivering) behind one of two doors: a
per-item budget ladder, or a generator that can build deeper items at a fixed prompt size. This
round takes the first door and measures the second.

## Why the load floor is the only walkable family

The shipped generator (`generators/ladders.py`) builds each item from `C` disjoint directed paths
of exactly `k` edges, with `C` drawn uniformly from `2..k+2`, so an item's fact count is `C*k` and
its unique-entity count is `C*(k+1)`. `facts >= 2k` is therefore an invariant, which is exactly
why round 50's constant-prompt band (facts 64-72) cannot reach past `k = 36` and died at `k = 32`:
the pinned load is the *minimum* load at `k = 32` and impossible beyond it.

At the floor, `C = 2` and `facts = 2k` exactly: two disjoint paths of `k` edges each, `2*(k+1)`
entities, the smallest item the generator can produce at that depth. Everything in this round
runs on that subfamily. Measured census over 400 scanned items per level (`--selftest` re-measures
it and refuses if it moves):

| k | items with `facts = 2k` | share of 400 | max entities in any item at that k |
|---|---|---|---|
| 8 | 58 | 14.5% | 90 |
| 16 | 22 | 5.5% | 306 |
| 24 | 14 | 3.5% | 650 |
| 32 | 12 | 3.0% | 1122 |
| 40 | 9 | 2.25% | 1722 |
| 48 | 6 | 1.5% | 2450 |

Two consequences, both pre-registered as design constraints rather than results: the floor family
thins with depth (a selection effect that must be disclosed), and the floor is the only family
whose prompt stays small enough that the 2048-token cap is a statement about the traversal and not
about the input.

## Cells and dispatch plan

Stage 1, 24 dispatches: six cells `F008, F016, F024, F032, F040, F048`; selection rule "first two
gold-yes and first two gold-no in generation order with `facts == 2*k` exactly"; temperature 0,
`max_tokens` 2048. Constant baseline 0.50 per cell (the balanced 2/2 label design).

Stage 2, decided only by stage-1 records and nothing else: on the smallest-seed gold-yes item of
each cell at `k = 24, 32, 40, 48`, re-dispatch the identical prompt twice at rungs
`floor(0.8L/64)*64` and `floor(0.5L/64)*64`, where `L` is that item's measured natural stop. A
candidate that was truncated at the cap is recorded `censored_by_cap` and gets no rung (its own
`L` is not a natural stop). Plus two identical re-dispatches (`k = 40`, `k = 48`) as the issue
#100 self-agreement control, and one 256-token census health call (issue #73): 35 dispatches of
the 40-call cap at most.

Free cross-firing replicate, at zero prompt cost: the `k = 32` floor cell is byte-for-byte round
50's archived `M32` item set (seeds 84261011, 84261050, 84261142, 84261174; prompt digests
pinned), because at `k = 32` the pinned band and the floor coincide. Row N3 asks whether this
firing reproduces round 50's per-item finish state.

Readout policy (issue #94): the answer field only. The trace-recovery rules stay refused after
round 50's calibration failure (0.5652 agreement, and the captured token was the model's own
instruction echo in 10 of 10 disagreements). Trace text is stored for prefix identity and length
only, never as a verdict.

## Instrument

`budget_ladder_probe.py`, stdlib only, `--selftest` with 109 checks, all of them able to fail:
independent BFS solver plus the shortcut/isomorphism/gold-flip refusals (issue #67 guards); the
vendored 12-row round-50 reference re-derived from the shipped generator with a planted digest
slip and a planted gold flip; the floor rule checked against a band-tolerance variant that selects
a different item set; generator geometry re-measured live (pool size, per-level maximum entity
counts, `facts = C*k` divisibility, the level-49 raise and the item-by-item scans above it); rung
arithmetic with planted negatives; longest-common-prefix arithmetic; duplicate join keys on the
item rather than the dispatch label (the defect that cost round 50 its self-agreement row); the
instruction-echo control that reads the round-50 capture string as "no"; the sanitizer over RFC
5737 documentation addresses, documentation hostnames and a credential fixture; the issue #105
census merge rule; seven planted firings that produce four distinct gate tiers plus the flag-only
variants; transport, malformed-response and censored-candidate record paths.

Gate rows F1-F5 (predictions and readouts), I1-I2 (the interrupt arms), N1-N3 (census and controls)
with the bands registered in `gate.json`. Tier rule: a delivered wrong answer anywhere means a
capability ceiling (`capability_bound_floor_depth`); otherwise if the positive arm stops
delivering the cap binds on the traversal at every label (`wall_reaches_both_arms`); otherwise if
the negative arm stops delivering the wall is label-split (`label_split_wall`); otherwise nothing
dies inside the measured generator ceiling.

## Finding 1 (zero prompts): the level-49 "generator ceiling" is a collision ceiling on item size, not on depth

`ladders.generate_items(49, ...)` raises `RuntimeError: entity pool exhausted`, and 48 was
therefore the depth this round could reach. Measuring instead item by item, with the raise caught:

| level | scanned | generated | raised | first raise at item | load-floor items found | max entities in a generated item |
|---|---|---|---|---|---|---|
| 48 | 300 | 300 | 0 | - | 3 | 2450 |
| 49 | 300 | 285 | 15 | 16 | 5 | 2500 |
| 50 | 300 | 284 | 16 | 29 | 6 | 2448 |
| 64 | 300 | 178 | 122 | 4 | 1 | 2470 |

The pool is `25 * 9 * 12 = 2700` synthetic names and `ladders._entity` accepts at most 100
rejection tries per name. An item with `C` chains needs `C*(k+1)` fresh names, so an item at
`k = 49` with `C = 50` needs 2550 of the 2700 available names and the sampler dies on the last few
draws; the largest item that *did* generate at level 49 used 2500. The load-floor items need only
`2*(k+1)` names and they keep appearing past the level where the whole-series call dies (5 at 49, 6
at 50, 1 at 64 of the surviving 178).

So: the ceiling is an artifact of asking for a whole series in one call, and the depth door that
round 50 said was closed is open on the floor family. This round stays registered at `k = 48`; the
generator-side fix (skip-on-raise, or a per-item name budget that keeps `C*(k+1)` inside the pool)
is what unlocks `k > 48` for a later round, and it is filed against `generators/`.

## Result

20 dispatches of the 40-call cap (1 health, 16 stage 1, 4 stage 2), zero transport errors, zero
retries, 14,846 prompt tokens, 23,370 completion tokens, 1,093.9 s of dispatch wall. Tier:
**`capability_bound_floor_depth`**, flag `early_commitment_observed`.

| Gate row | Band | Measured | Verdict |
|---|---|---|---|
| F1 positive arm delivers at k = 40, 48 | >= 3 of 4 | 4 of 4 delivered | pass |
| F2 no delivered record wrong anywhere | 0 | 3 wrong | **fail** |
| F3 negative arm delivers at most 3 of 6 at k >= 32 | <= 3 of 6 | 6 of 6 delivered | fail |
| F4 positive-arm length slope | 15..50 tokens/hop | 28.3 | pass |
| F5 label-split cost ratio | reported or refused | reportable, 4 of 4 cells | readout |
| I1 at most 1 of 8 interrupt dispatches delivers | <= 1 of 8 | 2 of 4 dispatched | **fail** |
| I2 interrupted output is a prefix of the delivered one | >= 3 of 4 candidates | 0 of 2 | fail |
| N1 reasoning field open | >= 90% | 20 of 20 | pass |
| N2 both duplicate re-dispatches byte-identical | 2 of 2 | not dispatched | **did not run** |
| N3 k = 32 reproduces round 50's finish states | >= 3 of 4 | 3 of 4 | pass |

Stage 1, 16 records, answer-field readout only:

| k | facts | gold-yes delivered / correct | mean natural stop | gold-no delivered / correct | mean natural stop |
|---|---|---|---|---|---|
| 24 | 48 | 2 / 2 | 718.5 | 2 / 2 | 1556.0 |
| 32 | 64 | 2 / 2 | 915.0 | 2 / 1 | 1556.0 |
| 40 | 80 | 2 / 2 | 1106.0 | 2 / 2 | 1556.0 |
| 48 | 96 | 2 / 2 | 1409.5 | 2 / **0** | 1556.0 |

16 of 16 delivered, `finish_reason` `stop` on every stage-1 record: the 2048 cap binds nowhere on
this family out to `k = 48` (which is what issue #126 predicted for the current builds). 13 of the
16 delivered answers are correct (0.8125, Wilson 95% CI 0.5699..0.9341); the 3 failures are all on
the gold-no (cross-path) arm: both items at `k = 48` and one at `k = 32` answered "yes" to a query
whose two endpoints sit on different paths.

## Finding 2: the wall at the load floor is a wrong answer, not a running-out

Round 50 closed every accuracy loss by non-delivery. At the load floor the shape inverts: nothing
truncates and the arm that breaks is the negative one, at `k = 48` with both items wrong. The tier
rule therefore reads a capability ceiling, the first one this family has produced on the answer
channel with the trace channel closed.

The registered bands expected a delivery wall and got one in the wrong direction: F3 (the negative
arm should stop delivering) fails because the negative arm delivers *everything*, and F2 fails
because what it delivers is wrong. `d*` on this family is an accuracy boundary at `k` between 40
and 48 for cross-path queries, and no `d*` delivery boundary was reached at all.

## Finding 3: the negative arm's output length is pinned at 1556 tokens at every depth

Every one of the eight gold-no records stopped at exactly 1556 completion tokens - at `k = 24`, 32,
40 and 48 alike - while the gold-yes arm grows with depth (718.5, 915.0, 1106.0, 1409.5; F4 slope
28.3 tokens/hop, inside the registered band, between round 50's 31.3 at pinned load and round 6's
80 at growing load). Their trace character counts differ (4201..4940), so this is not one cached
reply: it is the same *length* reached by different traversals.

The cost consequence is measured per cell (F5): the negative arm costs 2.17x, 1.70x, 1.41x and
1.10x the positive arm at `k = 24, 32, 40, 48`. The ratio shrinks with depth not because the
negative arm gets cheaper but because it never gets more expensive: it hits a fixed ceiling while
the positive arm climbs into it. Any budget ladder built on this family must budget the *label*,
not the depth.

## Finding 4: cutting a traversal to 78% of its own natural stop still yields the correct verdict

Stage 2 ran on two of its four registered candidates (`k = 48`: `L = 1310`, rungs 1024 and 640;
`k = 40`: `L = 1153`, rungs 896 and 576; the `k = 24` and `k = 32` candidates were cut off before
dispatch, see Limits). Both 0.8-rungs delivered and both were correct: 532 tokens at rung 1024 for
an item whose undisturbed traversal stops at 1310, and 876 tokens at rung 896 for `L = 1153`. Both
0.5-rungs hit the rung, produced no answer token at all, and were scored as undelivered rather
than wrong. So on this family the verdict is reachable at 78% of the natural stop and unreachable
at 49%, and I1 fails in the informative direction: the wall is not a completeness wall.

The prefix half of the same experiment does not hold, and it is the more important half. The
interrupted output should be a prefix of the same item's delivered output, which is what would make
a budget ladder cost one dispatch per item. It is not: the longest-common-prefix ratio of the two
rungs against the undisturbed output is 0.9509 and 0.0667 for `k = 48` and 0.6243 and 0.9911 for
`k = 40`. The ratios are not ordered by rung, the same prompt dispatched twice at temperature 0 on
the same endpoint diverges at 6.7% of one output and agrees to 99.1% at another depth of another.
`one_dispatch_predicts_rungs` is not claimed and cannot be claimed on this deployment family: an
interrupt ladder has to spend a dispatch per rung it wants to know about.

## Finding 5: a byte-identical prompt changed its finish state between firings

The `k = 32` cell is round 50's `M32` item set with the prompt digests pinned, so it is a free
cross-firing control (N3). It reproduces 3 of 4 finish states, with lengths that do not match:
1646 -> 1556, 988 -> 985, 1001 -> 845, and one flip. Seed 84261050, which round 50 recorded as
`finish_reason: length` at 2048, delivered here at 1556 tokens with `stop`, and it is one of the
three wrong answers. Same prompt bytes, same class, different firing, different arm outcome.

Round 50 recorded its serving-model digest at 12 hex (`4075b5949b2b`); this round records 16
(`c62b81e96826354e`), whose first 12 characters do not match it, so the two firings used different
deployments of the same class and this row is a class-level comparison, not a same-model
replication. The digest width is now fixed at 16 in the instrument so a later round can decide
that question properly (issue #100).

## Cutoff, disclosed

The firing's 90-minute runner window was spent first on an instrument defect: the archived
reference digests had been transcribed at 12 characters while the archive stores 16, so
`certify_reference` refused all 12 rows and refused to dispatch. Nothing was dispatched until that
was repaired by re-extracting the constants programmatically (they are what `certify_reference`
now regenerates from the shipped generator, 12 of 12).

The dispatch then ran in two passes. The first pass was stopped by hand at 6 records so that the
second could carry a wall-clock guard. The resumed pass dispatched the deep cells first (`k = 48,
40, 32, 24`), then stage 2, and was terminated by its 700-second guard while the second duplicate
control was still queued. Not dispatched: the `k = 8` and `k = 16` cells (8 dispatches), the `k =
24` and `k = 32` interrupt candidates (4 dispatches), and both duplicate controls (2 dispatches).
Consequences, stated plainly: I1 and I2 were evaluated on 4 dispatches and 2 candidates instead of
8 and 4; **N2 (the issue #100 self-agreement control) did not run at all**, and `summary.json`
records it as `byte_identical: 0` of 0 joined pairs, which is an absence and not a failure of
agreement; F5 lost the `k = 8` and `k = 16` cells, so the cost-ratio series starts at `k = 24`. The
registered gate (rows, bands, tier rule, blob `60b0d62c`) was not modified to fit the cutoff; the
dispatch order was registered in the gate as deep-first precisely so that a cutoff would cost the
shallow law anchors. `run.log` (local, not published) carries the per-dispatch trail; `summary.json`
and `raw.jsonl` carry the surviving records.

## Limits

- 4 items per cell (2/2 labels); 16 stage-1 records is thin, and one wrong answer moves a cell
  accuracy by 0.5. The 3 wrong answers are 3 different items, not one repeated failure.
- One firing, one deployment (a flash-next-class local endpoint), one class, temperature 0.
- The floor family is a selected subfamily: 1.5% of scanned items at `k = 48`. The items it selects
  are the ones the generator can build with two chains, which is a property of the corpus, not of
  the model.
- The 1556-token pin is 8 observations across 4 depths; nothing here establishes a mechanism.
- The stage-2 readout is 2 candidates and 4 dispatches. The prefix claim is refused, not measured
  at scale.
- `d*` is placed only as an interval (`40 < d* <= 48` on the cross-path arm) at 2 items per level.
- Executed, not Reproduced or Validated: no second firing of this plan ran, and the round's own
  self-agreement control was not dispatched.

## Reproduce

```bash
cd research/nightly-2026-11-06-0433
python3 budget_ladder_probe.py --selftest   # 109 checks, prints the gate blob
python3 budget_ladder_probe.py --gate       # rewrites gate.json, prints the blob
python3 budget_ladder_probe.py --dry-run    # the frozen dispatch plan
python3 budget_ladder_probe.py --rescore    # rebuild gate.json + summary.json from raw.jsonl
```

`--rescore` is the offline path: it reads `raw.jsonl`, refuses if any record carries a gate hash
other than `60b0d62c165f8c2a225a4eeb499e456859c281c4d30b64855c6a4dc3bf247716`, and re-derives every
number in this README from the archived bytes. The endpoint variables are read from the runner
environment and are never written into a file in this directory: artifacts carry
`model_digest` only, and every stored response string passes the sanitizer.
