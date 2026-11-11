# Round 59 (2026-11-11 03:18): no delivery wall on the flash class, it stops itself at 1,557 tokens, and every failure at j >= 40 is a wrong position on the right path (tier `controls_invalid`)

Firing: 2026-11-11 03:18 (issue #65 timer, pool slot 1/6). Class: a flash-next-class local model (the
serving id is disclosed only in the commit `Model:` trailer; artifact digest `c62b81e96826354e`). No
metered or hosted provider was used; no search API was used. Status label: **Executed** (see Limits).

## Question

Registered before dispatch (schema `round59-gate-v1`, frozen in `gate.json`, pinned in the
instrument), blob:

`f9a2c845875524c816efb4739ec1e7ac01056dc7ae641ad9c9b22ade924cdacf`

> On a flash-class endpoint, over one load-floor item per level at 32, 64, 96 and 128 facts and step
> counts `j = 8, 16, 24, 32, 40` (and `j = 48` on the 128-fact item), which single registered law
> predicts the delivery wall on at least 14 of the 17 name cells: input load (`n_facts >= 96`), step
> count (`j >= 32`), the load-times-depth product (`n_facts * j >= 3072`), or a deeper step-count
> wall (`j >= 40`)? And does an order-based trace readout (is the gold terminal the *last* entity
> named in the reasoning text, against the matched pseudo-gold) survive where containment refused at
> gap 0.0?

## Why this question, and what it buys that the archived grids cannot

Three consecutive firings registered or fired this grid and none of them landed it. Round 57
(2026-11-10 02:00) registered exactly this four-law question and died before its first dispatch;
round 58 (2026-11-10 04:00) fired it on a 27B-class endpoint and its record was killed before any
commit (`research/nightly-2026-11-10-0401/` is local provenance, not a repo artifact). This round is
the first landed dispatch of the grid, on the flash class, with the law thresholds and the tier line
frozen in `gate.json` before the first call.

The four laws are not rhetorical variants; they disagree on specific cells, and the archived flash
grid could not tell them apart. Round 55 (`research/nightly-2026-11-09-0301/`, open as PR #136, gate
blob `eadf84d55d10b649c952a29a350437a8658c837fb62c6f39356c508378a151a4`) censored exactly one name
cell, `L48_j32`, at 96 facts and `j = 32`. All four laws predict that cell as censored and predict
every delivered round-55 cell as delivered, so round 55's wall is uninformative: load, step count and
product all fit one point. The cells this grid adds are precisely the discriminating ones:

| cell | facts | `j` | load law | step-count law | product law | step-40 law |
|---|---|---|---|---|---|---|
| `L32A_j32` | 64 | 32 | delivered | censored | delivered | delivered |
| `L48_j8` | 96 | 8 | censored | delivered | delivered | delivered |
| `L48_j24` | 96 | 24 | censored | delivered | delivered | delivered |
| `L64_j24` | 128 | 24 | censored | delivered | censored | delivered |
| `L64_j32` | 128 | 32 | censored | censored | censored | delivered |
| `L48_j40` | 96 | 40 | censored | censored | censored | censored |

The second reason for the grid is the 27B comparison. On the killed round-58 27B firing the wall is
not a clean line at all: it censored `L32A_j24` (64 facts, `j = 24`) while delivering `L48_j24`
(96 facts, `j = 24`) on the same class, and it censored `L48_j40` while delivering `L64_j32`. That is
a pocket, and the instrument scores pockets (`pockets()`: a censored cell every law predicts as
delivered) rather than averaging them away. `X1` reports the state agreement against those 16
coordinates and is explicitly unregistered and post-hoc, because the archive it compares against
carries no commit and no PR.

The third reason is issue #94. The trace-provenance row has refused three times in a row on this
family (round 50's recovery rule captured by the model's own instruction-to-self echo at 0.5652;
round 55's containment gap 0.0; round 58's containment gap 0.0) because containment cannot separate
"reached the terminal" from "enumerated the candidate tails". This round registers the readout as an
order test, `C7`: among the name-gold records that produced no terminal and carry a non-empty
reasoning channel, the rate at which the gold terminal is the *last* entity named in the reasoning
text, minus the same rate for the matched pseudo-gold (the other path's tail, same item, same role).
Containment is still computed and reported, but only as legacy comparability with rounds 50, 55 and
58, and it gates nothing.

## Items, arms and dispatch plan

Load-floor items (`facts = 2k`, exactly two disjoint `k`-edge paths, issue #129's reachable family),
seed base 20261005, selected by the deterministic load-floor rule in the instrument, never by run
time choice:

| item | level | seed | facts | lineage |
|---|---|---|---|---|
| L16 | 16 | 52261033 | 32 | archived load-floor seed, asserted before dispatch |
| L32A | 32 | 84261011 | 64 | archived load-floor seed, asserted before dispatch |
| L48 | 48 | 116261051 | 96 | the item rounds 51, 53, 54 and 55 dispatched byte-identically |
| L64 | 64 | 148261120 | 128 | level-64 per-item scan, re-derived in `--selftest`: 400 candidate seeds, 235 items generated, 165 entity-pool raises, first raise at scan index 4, exactly one load-floor item at scan index 115 (issue #129 option (a)) |

`L48` is the certification anchor: the instrument rebuilds round 51's *yes/no* prompt from the same
rule and fact block and asserts its sha256 against the archived digest `068bc6a1fb0620fb` before any
dispatch, so the name-form prompts on that item provably carry the same fact bytes as the archived
records. The level-64 pin is asserted the same way before the first prompt.

- 17 `name` cells: "start at SRC and follow the direct links for exactly `j` steps; answer with
  exactly one entity name, or NONE if the links run out". Gold from an independent BFS in the
  instrument. Shallow-to-deep order within each item, deepest items last.
- 6 `NONE` controls, dispatched first: `L32A_deadend` and `L64_deadend` (one step from an
  out-degree-zero tail; at level 32 the tail is the other path's, at level 64 it is the query path's
  own), and `j = k + 1` off-end controls `L16_offend` 17, `L32A_offend` 33, `L48_offend` 49,
  `L64_offend` 65.
- budget rung `L64_j32_c256`: the `j = 32` query on the 128-fact item at `max_tokens` 256, the
  registered predicted non-delivery carried from the archived budget rungs.
- 2 `dup` re-dispatches, `L48_j40` and `L64_j40` (issue #100 self-agreement control).

26 calls of the 40-call cap, plus one health call at cap 256 and one calibration call before the
gate was frozen (a `j = 2` name query on a level-8 load-floor item at cap 512; `brep` asked, `brep`
answered, never experimental data and never in `raw.jsonl`). `temperature` 0.0, every requested cap
at most 2,048, dispatch wall-clock guard 1,800 s. Instrument selftest: 127 checks, green before
dispatch, including planted negatives (an off-by-one gold must be scored wrong, a censored record
must be a non-delivery rather than a wrong answer, an empty pseudo-gold must not read as present, a
constant token cost must not pass `C9`, a planted tie at the tier line must read
`laws_not_separable`, a law set that fits every cell must not be called a wall, each of the four
tiers must land under planted record sets, and the issue #137 row guard must reject each of its five
planted defects).

## Gate rows (registered, thresholds frozen before dispatch)

| row | measures | threshold |
|---|---|---|
| `C1` | shallow name reproduction at the four archived flash-class coordinates | 3 of 4 correct |
| `C2` | NONE controls: zero false names among delivered controls, at least 3 of 6 controls delivered | gated |
| `C3` | the four wall laws against the 17 name cells, and the pocket detector | unique law at 14 of 17 |
| `C4` | accuracy versus delivery: no false name, no undetermined answer, every non-delivery cap-bound | gated |
| `C5` | delivery-state agreement with the landed flash-class round 55 at the 9 shared coordinates | 6 of 9, 0 name contradictions |
| `C6` | the two byte-identical re-dispatch pairs agree on answer and completion tokens | 2 of 2 |
| `C7` | order-based trace provenance, gold terminal last named minus pseudo-gold last named | 0.50 gap over at least 3 records |
| `C8` | message-field census on every dispatched record (issue #105) | all dispatched records |
| `C9` | Spearman rank of completion tokens against `j`, `n_facts` and `n_facts * j` | abs(rho) >= 0.60 for one quantity |
| `H0` | health call census (cap 256) | reported |
| `H1` | the 256-token rung on `L64_j32` produces no terminal | non-delivered |
| `X1` | post-hoc state agreement with the killed round-58 27B grid at 16 coordinates | reported, not gated |

Tier rule, frozen: `dispatch_incomplete` if any planned cell was not dispatched; else
`controls_invalid` if the gated part of `C2` fails; else `accuracy_turnover` if `C4` fails; else the
unique wall law at or above 14 of 17 name cells; else `laws_not_separable` if two or more laws reach
the line; else `no_wall_law`.

## What fired

| cell | k | j | facts | cap | completion tokens | finish | delivered | declared | gold | scored | trace chars | last entity named |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `L32A_deadend` | 32 | 1 | 64 | 2048 | 271 | stop | yes | NONE | NONE | correct | 1043 | quixg |
| `L64_deadend` | 64 | 1 | 128 | 2048 | 185 | stop | yes | NONE | NONE | correct | 687 | brelt |
| `L16_offend` | 16 | 17 | 32 | 2048 | 1360 | stop | yes | NONE | NONE | correct | 4000 | stand |
| `L32A_offend` | 32 | 33 | 64 | 2048 | 1556 | stop | yes | NONE | NONE | correct | 4000 | sterk |
| `L48_offend` | 48 | 49 | 96 | 2048 | 1557 | stop | yes | spog | NONE | wrong name | 4000 | ven |
| `L64_offend` | 64 | 65 | 128 | 2048 | 1558 | stop | yes | - | NONE | no answer | 4000 | frut |
| `L16_j8` | 16 | 8 | 32 | 2048 | 576 | stop | yes | stacklt | stacklt | correct | 1751 | stacklt |
| `L16_j16` | 16 | 16 | 32 | 2048 | 1292 | stop | yes | brond | brond | correct | 3911 | brond |
| `L32A_j8` | 32 | 8 | 64 | 2048 | 726 | stop | yes | thrend | thrend | correct | 2166 | thrend |
| `L32A_j16` | 32 | 16 | 64 | 2048 | 779 | stop | yes | crux | crux | correct | 2411 | crux |
| `L32A_j24` | 32 | 24 | 64 | 2048 | 1558 | stop | yes | vixx | vixx | correct | 4000 | vixx |
| `L32A_j32` | 32 | 32 | 64 | 2048 | 1557 | stop | yes | sterk | sterk | correct | 4000 | spurk |
| `L48_j8` | 48 | 8 | 96 | 2048 | 1221 | stop | yes | trackst | trackst | correct | 3650 | trackst |
| `L48_j16` | 48 | 16 | 96 | 2048 | 1557 | stop | yes | flixm | flixm | correct | 4000 | flackg |
| `L48_j24` | 48 | 24 | 96 | 2048 | 1557 | stop | yes | whek | whek | correct | 4000 | strackm |
| `L48_j32` | 48 | 32 | 96 | 2048 | 1557 | stop | yes | whesh | whesh | correct | 4000 | whesh |
| `L48_j40` | 48 | 40 | 96 | 2048 | 1556 | stop | yes | NONE | knudnd | wrong name | 4000 | crog |
| `L64_j8` | 64 | 8 | 128 | 2048 | 289 | stop | yes | crilt | crilt | correct | 972 | crilt |
| `L64_j16` | 64 | 16 | 128 | 2048 | 1557 | stop | yes | crep | crep | correct | 4000 | crudrk |
| `L64_j24` | 64 | 24 | 128 | 2048 | 1558 | stop | yes | clixg | clixg | correct | 4000 | zet |
| `L64_j32` | 64 | 32 | 128 | 2048 | 1557 | stop | yes | knalt | knalt | correct | 4000 | spam |
| `L64_j40` | 64 | 40 | 128 | 2048 | 1558 | stop | yes | trudsh | frixm | wrong name | 4000 | drosh |
| `L64_j48` | 64 | 48 | 128 | 2048 | 1557 | stop | yes | cruk | blackt | wrong name | 4000 | crosh |
| `L64_j32_c256` | 64 | 32 | 128 | 256 | 256 | length | no | - | knalt | no answer | 1070 | knudt |
| `L48_j40_dup` | 48 | 40 | 96 | 2048 | 1557 | stop | yes | spog | knudnd | wrong name | 4000 | thrudlt |
| `L64_j40_dup` | 64 | 40 | 128 | 2048 | 1556 | stop | yes | NONE | frixm | wrong name | 4000 | prap |

Dispatch: 26 of 26 planned calls of the 40-call cap, 1800.523 s dispatch phase against a sum of 1,790.737 s over the 26 calls (the registered 1,800 s dispatch guard fired after the last cell and cut nothing: `not_dispatched` is empty), 24124 prompt and 31868 completion tokens, 0 retries, zero transport errors, no arm timed out. One health call at cap 256 (census fields content, reasoning_content, role, reasoning field `reasoning_content`, 60 tokens) and one calibration call before the gate was frozen (154 tokens, gold `brep`, answered `brep`) sit outside the grid: 28 endpoint calls in total of the 40-call cap. The frozen gate blob is `f9a2c845875524c816efb4739ec1e7ac01056dc7ae641ad9c9b22ade924cdacf` and every one of the 26 records carries it.


## Result

**Tier `controls_invalid`, flags `self_agreement_split`.** The tier is fail-closed on the NONE controls and this report honors it, which means the round's wall-law number is a reported readout and not a verdict.

- `C1` shallow reproduction at the four archived flash-class coordinates: 4 of 4, pass.
- `C2` NONE controls: 6 of 6 controls delivered, 4 refused with `NONE`, 2 control failures (L48_offend, L64_offend), gated part `false_names`, fail.
- `C3` wall laws over the 17 name cells: step40_wall 14 of 17, load_depth_product 11 of 17, step_count_wall 11 of 17, input_load_wall 6 of 17, unique law at the line 14 of 17 is `step40_wall`, pockets 0; the row's own criterion is met, and the tier rule ranks `C2` above it.
- `C4` accuracy versus delivery: 14 of 17 name cells correct, 3 failed name cells (L48_j40, L64_j40, L64_j48; the instrument counts the `NONE` at `L48_j40` as a false name because a name exists there), 0 non-deliveries, 0 cap-bound, delivery 1.0 at `j <= 16` against 1.0 at `j >= 32` (drop 0.0), fail: this is an accuracy turnover, not a delivery-bound loss.
- `C5` the archived flash-class column (round 55, different build): 8 of 9 shared coordinates agree in state, extensions past the archived grid `L48_j32`, regressions none, name contradictions 0, pass.
- `C6` the two byte-identical re-dispatch pairs: 0 of 2 agree, fail.
- `C7` order-based trace provenance: 0 qualifying records, so the row is inadmissible and no containment number is computable either; fail without measuring.
- `C8` census: 26 records, 26 carrying the field census, 26 with an open reasoning channel (`reasoning_content`), pass.
- `C9` Spearman over the 17 name cells: `j` 0.6767, `n_facts` 0.3984, `n_facts * j` 0.6922, best abs rho 0.6922, pass.
- `H1` the 256-token rung on `L64_j32`: 256 tokens, `finish_reason length`, no terminal, pass.
- `X1` (post-hoc, unregistered) against the killed round-58 27B archive: 12 of 16 coordinates agree in state; build extensions `L32A_j24`, `L48_j32`, `L48_j40`, `L64_j40`; regressions none.

## Findings

1. **The four registered laws are delivery laws, and on this build delivery never breaks.** All 17 name cells and 5 of the 6 `NONE` controls produced an answer field with `finish_reason = stop`; 16 of the 26 records (11 of the 17 name cells, both re-dispatches and three controls) completed inside a three-token band 1,556 to 1,558, the largest completion anywhere under the 2,048 cap is 1,558, and 17 records sit at the 4,000 character store cap the sanitizer puts on reasoning text. The only cap-bound record in the whole firing is the 256-token rung (`H1` pass: 256 tokens, `length`, no terminal), and `C3` reports zero pockets. So the wall this grid was built to measure is absent: `input_load_wall` fits 6 of 17 name cells, `step_count_wall` and `load_depth_product` 11 each, `step40_wall` 14. What the grid found instead is round 49's signature on a new build: this class stops by itself at about 1,557 completion tokens at 32, 64, 96 and 128 facts alike, so the 2,048 cap never binds and the archived flash-class cap-bound readings the four laws were derived from (round 55's `L48_j32` and `L32A_offend`, both at 2,048) are properties of that build, not of the class. `C9` says the same thing from the cost side: rank correlation 0.6767 with `j` and 0.6922 with `n_facts * j` against 0.3984 with `n_facts` alone, i.e. under the self-imposed stop the fact block is close to free and `j` is what the model spends.

2. **What gives way at `j >= 40` is the position index, not the output budget.** Every one of the 14 name cells at `j <= 32` answered correctly, at 32, 64, 96 and 128 facts alike (`L64_j32` 1,557 tok correct, `L48_j32` 1,557 tok correct, `L64_j24` 1,558 tok correct); none of the 3 cells at `j >= 40` did. Each failure is a node *of the asked path at a different index*, checked against the item by the instrument: `trudsh` at `L64_j40` is the 38th step of the query path against an asked 40 (off by 2); `cruk` at `L64_j48` is the 1st step against an asked 48 (off by 47); `spog`, named twice (`L48_j40_dup` against an asked 40, and `L48_offend` where the links have run out at 49), is the 48th and last step of that same path. The traversal lands on the right chain and reports the wrong place on it, and the error grows with the asked depth: off-by-2 at 40, jump to the endpoint at 40 and 49, jump to the start at 48. The build also fabricates: `L64_offend` answered `cruuk`, which is not in the item's 130-name vocabulary at all and is one insertion away from `cruk`, which is. A refusal at a coordinate where a name exists (`L48_j40`, gold `knudnd`, answered `NONE`) is the same defect read the other way.

3. **Reproducibility breaks exactly where accuracy breaks (issue #100).** Both byte-identical re-dispatch pairs split at `temperature` 0.0: `L48_j40` `NONE` 1,556 tok against `L48_j40_dup` `spog` 1,557 tok, and `L64_j40` `trudsh` 1,558 tok against `L64_j40_dup` `NONE` 1,556 tok; `C6` reads 0 of 2 and the flag `self_agreement_split` is set. At `j <= 32` the same prompt on the same item produced a correct name in every cell dispatched, while the archived round-55 re-dispatch pairs reproduced, one in answer and tokens and one as an identical non-answer at 2,048. The instability is therefore specific to the failing regime: at `j = 40` this build can refuse a name it produced on the previous call of the same prompt, and can produce a wrong name it refused on the previous call. Consequence for the program: a single dispatch at `j >= 40` is not a measurement, and the depth of the cliff is not pinned by this firing; the cliff is somewhere in `(32, 40]` and the cells in between were never dispatched here.

4. **The tier is `controls_invalid`, and the round's most quotable number is not its verdict.** The gated part of `C2` is "no control fails to refuse": 4 of 6 controls refused correctly (`L32A_deadend` 271 tok, `L64_deadend` 185 tok, `L16_offend` 1,360 tok, `L32A_offend` 1,556 tok), `L48_offend` named `spog` where the links have run out, and `L64_offend` named the fabricated `cruuk`. Two control failures invalidate the tier, so no wall-law claim is made even though `C3`'s own criterion is met: `step40_wall` is the only law at the registered line, 14 of 17 against 6, 11, 11 for the other three. Its three disagreements are precisely the three cells where the answer is wrong, i.e. the law has the right *coordinates* and the wrong predicted *failure mode*. `C4` would have read `accuracy_turnover` (3 name cells failed, 0 non-deliveries, 0 cap-bound, delivery 1.00 at `j <= 16` and 1.00 at `j >= 32`, drop 0.00: `L48_j40` refused where a name exists, `L64_j40` and `L64_j48` named other nodes). The registered order makes `C2` the verdict and `C4` the diagnosis, and a gate that can put a met row criterion behind a control gate is worth naming as a protocol fact rather than smoothing over: the tier and `C3` disagree here by design.

5. **Issue #94's order readout never got its data, and that is worth more than a gap of 0.0.** `C7` admits only name-gold records that produced no terminal and carry a non-empty reasoning channel. On this firing all 17 name cells produced a terminal (`NONE` is a produced answer), so `n = 0`, the row is inadmissible, and the containment legacy numbers are equally uncomputable. Rounds 50, 55 and 58 refused the same row at gap 0.0 because containment could not separate "reached the terminal" from "enumerated the candidate tails"; this firing does not even reach that test, because the `j >= 40` failures are wrong answers rather than withheld answers. The surfacing question moves: on this build at this depth there is nothing stuck under the surface, the surface is full and what is on it is the wrong position.

6. **Same class, different build: the column extends, the capability does not.** `C5` reads 8 of 9 state agreement with the landed flash-class round 55 grid with 0 name contradictions and no regression to a censored state; the single extension is `L48_j32`, censored at 2,048 there and `stop` at 1,557 with the correct name `whesh` here. `X1`, post-hoc and unregistered against the killed round-58 27B archive, reads 12 of 16, with four build extensions (`L32A_j24`, `L48_j32`, `L48_j40`, `L64_j40`: censored at 2,048 there, `stop` here) of which two are wrong answers here. "Delivered" means an answer field exists, and at `j >= 40` that is not a capability claim: this build gets further out of the token budget and lands on the wrong node, which is the cleanest evidence in this program that a delivery-state comparison across builds cannot be read as a depth comparison.



## Limits

- This firing is the 2026-11-11 02:00 timer slot (slot 1/6). Its runner wrote no completion record
  and the tracker carried no round 59 line before this directory: the firing was cut at its 90 minute
  wall-clock cap and the agent session continued from its own in-progress state. That matters for the
  record only in one verifiable way: the instrument fix (an archived anchor gold, `sterkt` against the
  item's `sterk`) landed before the freeze, `gate.json` is dated 05:44 and the first dispatch 05:45,
  so the frozen gate predates every record here, and all 26 records carry the frozen blob, so
  `raw.jsonl` holds no pre-fix residue. The directory keeps its own firing clock (`0318`), which is
  why it does not match the slot.
- The stored reasoning text is capped at 4,000 characters per record and 17 of the 26 records sit at
  that cap, so `C7`'s "last entity named" is the last named inside the stored prefix. A fired order
  readout needs a wider store or a measure that survives truncation; this firing never reached that
  question because nothing withheld its answer.
- No cell was dispatched at `32 < j < 40` on any item, so the cliff found here is bounded by the grid
  and not measured by it.
- One endpoint, one class, one firing: `Executed`, exploratory, n = 1 per cell (two cells at n = 2),
  and at `j = 40` even n = 2 disagrees with itself.
- The serving build of this firing is not the build round 55 dispatched. Its artifact digest
  `c62b81e96826354e` differs from round 55's `4075b5949b2b0487`, from round 52 and round 56's
  `86d6f3507f8725bf` and from the round 54 and round 58 build `26df9af5972ff312`, so every archived
  comparison in `C5` and `X1` is same-class, different-build, and is disclosed as such in the gate
  certification (`build_matches_archived: false`).
- The killed-firing archives are disclosed provenance, not repo artifacts: `research/nightly-2026-11-
  09-0417/` (round 56), `research/nightly-2026-11-10-0223/` (round 57) and
  `research/nightly-2026-11-10-0401/` (round 58) exist only on the maintainer workstation; their
  rounds 56, 57 and 58 never produced a commit or a PR. Every number taken from them is labelled as
  such in this directory (`R58_STATES` in the instrument), `X1` is registered `registered: false`,
  and no tier input reads them.
- The level-64 column is new: no landed round has ever dispatched a 128-fact item, so `L64_*` has no
  committed comparator at all, and `X1` compares it only against an uncommitted archive.
- The prompt states the step count, so the task is "walk `j` edges", not "decide entailment". Any
  depth claim from it is a claim about production under an explicit horizon.
- The gold terminal is present in the fact block, so a positional rule ("emit the entity with no
  outgoing edge") is available at `j = k`. It is worth about 1/2 at `j = k` (two tails per item) and
  about zero at the intermediate `j` cells, which is why the curve, not the deepest cell, carries the
  claim.
- Trace text on this deployment is supplied by `reasoning_content` (census: fields `content`,
  `reasoning_content`, `role` on the health call and on every record). Issue #105: every trace claim
  here is same-class and same-firing, both sides exposed.
- The serving id is not written anywhere in this directory; records carry a one-way digest.

## Reproduce

```
python3 research/nightly-2026-11-11-0318/wall_transfer_probe_r59.py --selftest
python3 research/nightly-2026-11-11-0318/wall_transfer_probe_r59.py --dry-run
python3 research/nightly-2026-11-11-0318/wall_transfer_probe_r59.py --calibrate
python3 research/nightly-2026-11-11-0318/wall_transfer_probe_r59.py --run
python3 research/nightly-2026-11-11-0318/wall_transfer_probe_r59.py --rescore
python3 research/nightly-2026-11-11-0318/wall_transfer_probe_r59.py --check-readme
```

`--rescore` rewrites `summary.json` from `gate.json` plus `raw.jsonl` alone, and the committed
`summary.json` is that rescored file, so re-running it reproduces the artifact byte-identically (the
dispatch phase wall clock and the retry count are carried forward from the firing, and the rest is
rebuilt: `dispatch_source` says which). `--check-readme` is the issue #137 guard run over this
directory: it fails on a quoted row id that this gate does not define, on a blob pin that differs
from the compact sorted-key sha256 of `gate.json`, on a raw record carrying a different blob, and on
a cited 64 hex blob that is neither this gate's nor a certified archive's.

Prompts are not stored in `raw.jsonl`: each record carries `(level, seed, j, cap, kind)` plus the
prompt sha256, and the prompt re-renders byte-identically from the seed base, so the digests are the
check. `run.log` stays local.
