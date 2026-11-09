# Round 55 (2026-11-09 03:01): the ladder answers in a name space it cannot guess - 27 of 27 delivered names correct to j = 48 on the certified k = 48 item, and every NONE control refuses

Firing: 2026-11-09 03:01 (issue #65 timer, pool slot 2/6). Class: a flash-next-class local model
(the serving id is disclosed only in the commit `Model:` trailer; artifact digest `4075b5949b2b0487`). No
metered or hosted provider was used; no search API was used. Status label: **Executed** (see Limits).

## Question

Registered before dispatch (schema `round55-gate-v1`, frozen in `gate.json`, pinned in the
instrument), blob:

`eadf84d55d10b649c952a29a350437a8658c837fb62c6f39356c508378a151a4`

> With the prompt bytes fixed and only the step count `j` moved inside one load-floor ladder item,
> does a one-of-many entity-name answer space (a) deliver correct terminals at shallow `j` where no
> constant rule and no connectivity shortcut could, (b) hold to `j = k` on the certified `k = 48`
> item, (c) refuse correctly when the links run out, and (d) leave a trace signal that passes a
> matched-name provenance control?

## Why this question, and what it buys that the yes/no numbers cannot

Every ladder accuracy number in this repository is a yes/no number, and that answer space is weak in
two known ways. First, a constant rule scores 0.50 on it and the shipped corpus is leaky under
undirected component membership, which reproduces the gold label at 1.0000 at every level
(`generators/AGENTS.md`, issue #77); issue #94 records the same problem for the probe readout ("at
`k = 24` its accuracy equals the constant-`no` baseline"). Second, membership and production are
different demands: to answer "does a precedes b" the model has to decide a relation, while to answer
"name the entity exactly `j` steps from `a`" it has to emit one name out of the 2,700-name pool,
which neither a constant rule nor the connectivity shortcut can do. The name space is also the space
the closest published multi-hop benchmark uses (Sinha et al. 2019, CLUTRR, arXiv:1908.06177,
EMNLP 2019, archived in `archive/INDEX.md` round 20: kinship relations between characters, so a
correct answer is a name and an incorrect one is a wrong name, not a coin flip).

Round 50 (`research/nightly-2026-11-06-0259/`, merged as #128) separated depth from input load by
selecting items inside a fixed fact band *across* items, and found that accuracy never turns over
while delivery does: 23/23 delivered answers correct, five non-deliveries, all at the 2,048 cap. It
could not separate computation from surfacing because its trace-recovery rule was captured by the
model's own echo of the question (calibration 0.5652) - an echo that contains the verdict words. A
name answer has no such echo, so this round re-attempts that separation with a matched control.

The instrument holds the load fixed a second way, inside one item: every cell of an item dispatches
the same rule sentence and the same shuffled fact block, and the only thing that changes between two
cells is the integer `j`. Depth is then isolated from input load by construction, not by band
matching.

## Items, arms and dispatch plan

Load-floor items (`facts = 2k`, exactly two disjoint `k`-edge paths, issue #129's reachable family),
seed base 20261005, selected by the deterministic load-floor rule in the instrument, never by run
time choice:

| item | level | seed | facts | lineage |
|---|---|---|---|---|
| L8 | 8 | 36261005 | 16 | round 6's archived anchor seed family |
| L16 | 16 | 52261033 | 32 | load-floor scan |
| L32A | 32 | 84261011 | 64 | load-floor scan |
| L32B | 32 | 84261050 | 64 | second 32 item, two cells |
| L48 | 48 | 116261051 | 96 | the item rounds 51, 53 and 54 dispatched byte-identically |

`L48` is the certification anchor: the instrument rebuilds round 51's *yes/no* prompt from the same
rule and fact block and asserts its sha256 against the archived digest `068bc6a1fb0620fb` before any
dispatch (selftest check 2, green), so the name-form prompts on that item provably carry the same
fact bytes as the archived records whose answer field the earlier rounds never got.

- `name` cells: "start at SRC and follow the direct links for exactly `j` steps; answer with exactly
  one entity name, or NONE if the links run out". Gold from an independent BFS in the instrument.
- `off_end` controls: `j = k + 1`, gold NONE (five cells).
- `dead_end` controls: a path tail asked for one step, gold NONE (two cells).
- budget rung: the `j = 48` query at `max_tokens 256`, to see whether a one-token answer space is
  still censored by the cap.
- `dup` re-dispatches of `L32A_j32` and `L48_j48`: the issue #100 self-agreement control.

29 calls of the 40-call cap plus one census health call; one calibration call before the gate was
frozen (a `j = 8` name query on L32A, never experimental data). `temperature 0.0`, every requested
cap at most 2,048. Instrument selftest: 34 checks, green before dispatch, with planted negatives (an
off-by-one gold must be scored wrong, a censored record must be a non-delivery rather than a wrong
answer, an empty pseudo-gold must not read as present, and the tier rule must land on each of its
four tiers under planted record sets).

## What fired

| cell | k | j | cap | completion tokens | finish | delivered | declared | gold | scored | trace chars |
|---|---|---|---|---|---|---|---|---|---|---|
| `L8_j1` | 8 | 1 | 2048 | 100 | stop | yes | stonsh | stonsh | correct | 378 |
| `L8_j2` | 8 | 2 | 2048 | 135 | stop | yes | brep | brep | correct | 501 |
| `L8_j4` | 8 | 4 | 2048 | 263 | stop | yes | crup | crup | correct | 822 |
| `L8_j8` | 8 | 8 | 2048 | 383 | stop | yes | zish | zish | correct | 1206 |
| `L8_offend` | 8 | 9 | 2048 | 398 | stop | yes | NONE | NONE | correct | 1283 |
| `L32A_deadend` | 32 | 1 | 2048 | 204 | stop | yes | NONE | NONE | correct | 813 |
| `L48_deadend` | 48 | 1 | 2048 | 1002 | stop | yes | NONE | NONE | correct | 2901 |
| `L16_j2` | 16 | 2 | 2048 | 145 | stop | yes | brixt | brixt | correct | 564 |
| `L16_j8` | 16 | 8 | 2048 | 441 | stop | yes | stacklt | stacklt | correct | 1343 |
| `L16_j16` | 16 | 16 | 2048 | 529 | stop | yes | brond | brond | correct | 1509 |
| `L16_offend` | 16 | 17 | 2048 | 974 | stop | yes | NONE | NONE | correct | 2775 |
| `L32A_j2` | 32 | 2 | 2048 | 128 | stop | yes | stonnd | stonnd | correct | 480 |
| `L32A_j8` | 32 | 8 | 2048 | 528 | stop | yes | thrend | thrend | correct | 1831 |
| `L32A_j16` | 32 | 16 | 2048 | 437 | stop | yes | crux | crux | correct | 1301 |
| `L32A_j24` | 32 | 24 | 2048 | 1285 | stop | yes | vixx | vixx | correct | 3652 |
| `L32B_j8` | 32 | 8 | 2048 | 704 | stop | yes | strark | strark | correct | 1992 |
| `L48_j2` | 48 | 2 | 2048 | 161 | stop | yes | plost | plost | correct | 601 |
| `L48_j8` | 48 | 8 | 2048 | 1096 | stop | yes | trackst | trackst | correct | 3116 |
| `L48_j16` | 48 | 16 | 2048 | 883 | stop | yes | flixm | flixm | correct | 2870 |
| `L48_j32` | 48 | 32 | 2048 | 2048 | length | no | - | whesh | no answer | 4000 |
| `L32A_j32` | 32 | 32 | 2048 | 951 | stop | yes | sterk | sterk | correct | 2485 |
| `L32A_offend` | 32 | 33 | 2048 | 2048 | length | no | - | NONE | no answer | 4000 |
| `L32B_j32` | 32 | 32 | 2048 | 1515 | stop | yes | drist | drist | correct | 4000 |
| `L32B_offend` | 32 | 33 | 2048 | 1903 | stop | yes | NONE | NONE | correct | 4000 |
| `L48_j48` | 48 | 48 | 2048 | 2048 | length | no | - | spog | no answer | 4000 |
| `L48_offend` | 48 | 49 | 2048 | 2048 | length | no | - | NONE | no answer | 4000 |
| `L48_j48_c256` | 48 | 48 | 256 | 256 | length | no | - | spog | no answer | 980 |
| `L32A_j32_dup` | 32 | 32 | 2048 | 951 | stop | yes | sterk | sterk | correct | 2485 |
| `L48_j48_dup` | 48 | 48 | 2048 | 2048 | length | no | - | spog | no answer | 4000 |

Dispatch: 29 of 29 planned calls of the 40-call cap, 504.441 s wall, 18695 prompt and 25612 completion tokens, 0 retries, `not_dispatched` [], zero transport errors, no arm timed out. The 8 earliest cells were written by a dispatch process killed mid-round (the shell that launched it exited); `--run` resumed by label, every record carries the same gate blob, and the 29 rows are the complete plan. Census (issue #105): the reasoning-supplying field is `reasoning_content`, open on the health call and on all 29 records.

## Result

**Tier `controls_invalid`, flags `delivery_bound_loss`, `trace_provenance_refused`.** The tier is fail-closed and this report honors it: the C2 control gate reads 5 of 7 against a registered 6 of 7. What the two misses are, and are not, is the round's main finding: both are non-deliveries at the 2,048 cap (`finish_reason` `length`, empty answer field: `L32A_offend`, `L48_offend`), and the false-name rate among the controls that did answer is 0 of 5. No record anywhere in the run declares a wrong name.

- C1 shallow name competence: 4 of 4, pass. - C2 NONE controls: 5 of 7, fail (0 false names, 2 censored). - C3 deep in-band cells: 3 of 4, verdict `no_ceiling` (`L48_j48` is a non-delivery, not a wrong name). - C4 delivery 1.0 at `j <= 8` vs 0.5 at `j >= 24`, drop 0.5: delivery-bound. - C5 self-agreement: 2 of 2 pairs, pass (the `L48` pair agrees degeneratedly: both censored at 2,048 with no answer field). - C6 trace provenance: gold-in-trace 0.6667 vs matched pseudo-gold-in-trace 0.6667 on 3 undelivered name records, gap 0.0, refused.

Across the 22 name-gold records: 18 delivered, 18 of 18 delivered correct, 0 wrong, 4 undelivered (`L48_j32`, `L48_j48`, `L48_j48_c256`, `L48_j48_dup`).

## Findings

1. **The name space is not guessable and the endpoint clears it everywhere it answers.** All
   18 delivered name cells are correct, including `j = 16` 529 tok delivered correct, `j = 24` 1285 tok delivered correct, `j = 32` 951 tok delivered correct, `j = 32` 1515 tok delivered correct.
   The gold terminal is one name out of the generator's 2,700-name pool, and the only shortcut the
   item shape offers is "emit an out-degree-zero tail", worth about 1/2 at `j = k` (two tails per
   item) and about nothing at the intermediate `j`. A base-rate or connectivity explanation cannot
   produce this pattern, which is exactly the evidence the two-way yes/no space cannot supply
   (issue #94, `k = 24` accuracy equal to the constant-`no` baseline; issue #77, component
   membership reproducing the gold label at 1.0000).
2. **Accuracy never turns over; delivery does, and the turn is a load-times-depth surface.**
   Delivery is 1.00 at `j <= 8` and 0.50 at `j >= 24` (C4). The four non-deliveries are the
   `j = 32` and `j = 48` cells on the 96-fact item plus the two 96- and 64-fact off-end controls.
   Depth alone does not censor: `L32B_j32` at 64 facts delivers in 1,515 tokens and `L32A_j32` in
   951, while `L48_j32` at 96 facts is censored at 2,048. That is the same shape round 50 found at
   its H32 cell (3x load at depth), now in a response format whose answer is a single token: the
   cost is in getting the verdict out, and it scales with the fact block as well as with `j`.
3. **Round 6's tokens-per-hop law does not survive the name format either.** Tokens-to-answer run
   `j = 1` 100 tok delivered correct, `j = 8` 383 tok delivered correct, `j = 16` 437 tok delivered correct, `j = 32` 951 tok delivered correct - a visible trace of
   2,485 characters at `j = 32` on the 64-fact item, about 78 characters per hop against round 50's
   20.9 tokens per hop at constant load in the verdict format. A one-name answer does not force the
   traversal to be written out, so the format changes the cost curve, not just the answer space.
4. **The refusals are honest; the control gate is what broke.** 5 of
   7 NONE controls answered, and every one of them refused: `j = 9` 398 tok delivered correct, `j = 17` 974 tok delivered correct, `j = 33` 1903 tok delivered correct
   plus both dead-end controls (`L32A_deadend` 204 tokens, `L48_deadend` 1,002 tokens, asked to walk
   one step from a name with no outgoing link). Zero false names. The gate nonetheless reads
   `controls_invalid` because it counts a censored control as a miss. That is a protocol gap worth
   naming: a refusal control needs a two-part score (false-name rate among delivered controls, and
   control delivery rate), or the controls have to sit at depths whose delivery rate is known. As
   registered, a delivery failure invalidates capability claims it does not bear on.
5. **The trace containment signal fails its matched control, so the surfacing question stays open
   (issue #94).** On the 3 undelivered name records the gold terminal appears in the
   reasoning text in 0.6667 of them and the matched pseudo-gold (the other path's
   tail, same role, same item) in 0.6667: gap 0.0, below the
   registered 0.50, so the row refuses itself and no "it knew but could not say" claim is made here.
   Round 50's recovery rule died by echo capture (0.5652, an echo containing the verdict words);
   this row dies differently, because a long traversal enumerates both tails, so containment cannot
   separate "reached the terminal" from "listed the candidates". Trace containment is not a
   provenance test in either format.
6. **Self-agreement holds on the deliverable half (issue #100).** `L32A_j32` and its re-dispatch are
   identical in completion tokens (951) and declared name. `L48_j48` and its re-dispatch are both
   censored at 2,048 with identical token counts, which is reproducibility of a non-answer, not of a
   decision. Round 54's byte-identical `L48` fact block was reused here under the archived yes/no
   digest `068bc6a1fb0620fb`, so round 51's wrong `k = 48` verdict and this round's censored
   `j = 48` name query are the same 96 facts and the same class: on this item the 48-step traversal
   was never surfaced in either format, while the same facts answer correctly at `j` up to 16.

## Limits

- One endpoint, one class, one firing: `Executed`, exploratory, n = 1 per cell (two cells at n = 2).
- The name arm is a different task from the archived yes/no arm. It cannot show that the yes/no task
  is solvable at `k = 48`; it shows what this endpoint can produce about the same fact graph when
  the answer space is a name. Like round 53's `enumerate` arm, it is a task variant, not a repair.
- The prompt states the step count, so the task is "walk `j` edges", not "decide entailment". Any
  depth claim from it is a claim about production under an explicit horizon.
- The gold terminal is present in the fact block, so a model could in principle reach it by a
  positional rule ("the entity with no outgoing edge") rather than a walk. That shortcut is worth
  about 1/2 at `j = k` (two tails per item) and about zero at the intermediate `j` cells, which is
  why the curve, not the deepest cell, carries the claim.
- Trace text on this deployment is supplied by `reasoning_content` (census: fields `content`,
  `reasoning_content`, `role` on the health call and on every record). Issue #105: every trace claim
  here is same-class and same-firing, both sides exposed.
- The serving id is not written anywhere in this directory; records carry a one-way digest.

## Reproduce

```
python3 research/nightly-2026-11-09-0301/name_depth_probe.py --selftest
python3 research/nightly-2026-11-09-0301/name_depth_probe.py --dry-run
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
  python3 research/nightly-2026-11-09-0301/name_depth_probe.py --run
python3 research/nightly-2026-11-09-0301/name_depth_probe.py --rescore
```

Prompts are not stored in `raw.jsonl`: each record carries `(level, seed, j, cap, kind)` plus the
prompt sha256, and the prompt re-renders byte-identically from the seed base, so the digests are the
check. `run.log` stays local.
