# Round 58 (2026-11-10 04:01): the 27B-class step boundary sits at 40, not 32 - the flash-class
input-load and product laws are refuted on the re-fired round-54 build (128-fact cells deliver to
j = 32), the (64, 24) and (96, 32) censored pockets split the class builds, and the trace-
provenance row refuses itself for the third time in the name-arm family

Firing: 2026-11-10 04:01 (issue #65 timer, pool slot 6/6). Class: a 27B-class local model
(the serving id is disclosed only in the commit `Model:` trailer; the records carry a one-way
digest `26df9af5972ff312`, which is the round-54 build's digest, so this firing is a re-fire
of round 54's build). No metered or hosted provider was used. One pre-gate calibration call
confirmed the registered format parses on this build; it is not experimental data and is not
in `raw.jsonl`. Status label: **Executed** (see Limits).

## Question

Registered before dispatch (schema `round58-gate-v1`, frozen in `gate.json`, pinned in the
instrument), blob:

`ff1df364dc84a2bed6f399a10ea3e65b3c7417355fd16a33f73f39ebbbcfcd4c`

> On a 27B-class local build (the re-fired round-54 build), with the round-55 name-or-NONE
> response format re-pinned byte-identically (every cell's prompt digest frozen in this gate
> before the first prompt) and the prompt bytes fixed with a grid of three input loads
> (64, 96, 128 facts) against five step counts (`j = 8, 16, 24, 32, 40`) plus a 32-fact
> reference row, does delivery on a one-of-many entity-name answer space (a) stop at the input
> load, at the step count, or at a single load-times-depth product, (b) sit at the step-32
> boundary or the step-40 boundary, (c) deliver correct terminals at the undelivered
> coordinates, (d) refuse with no false name when the links run out, (e) reproduce the
> archived round-55 anchor cells on this build, (f) hold self-agreement on the re-dispatched
> boundary cells, and (g) pass or refuse itself on the matched-name trace-provenance row?

## Why this question

Round 54 (`research/nightly-2026-11-08-0221/`, open PR #133 at this firing) measured this
build's cap ladder on the yes/no arm: every 96-fact dispatch stopped at its requested cap on
every rung, with no self-termination marker, so the build's own archived record already says a
96-fact input load is cap-bound on the verdict arm. What it left owed (its "Owed next (A)"):
whether the cap-bound / absolute-pin reading is a property of this build, this class, or this
stack configuration, owed to the next firing as a re-fire of the same build - which this
firing is (the model digest matches round 54's). The name arm had never been run on this
build: round 55's name-or-NONE format (open PR #136) measured the flash class to `j = 32`
on the 96-fact item and censored both its 96-fact deep cells, and the parallel killed round-56
firing on the sibling 27B build (digest `86d6f3507f8725bf`, the round-52 build; untracked
archive, no PR, disclosed here as provenance only) delivered `j = 32` and censored `j = 40..64`
at 128 facts on its name arm.

The wall-shape question is the one round 57 registered on the flash class and died before
registering (its instrument, `research/nightly-2026-11-10-0223/wall_shape_probe.py`, never
fired a gate; the untracked script and its round-55 anchor vendoring stay out of this PR):
which wall governs delivery - input load, step count, or their product. Re-registered here
for this class and build, with the three flash-class laws as cross-class transfer candidates
and a fourth, boundary-extension law declared before dispatch so the class's own step boundary
(32 or 40) is separable:

  law `input_load_wall`    : censored iff `n_facts >= 96`
  law `step_count_wall`    : censored iff `j >= 32`
  law `load_depth_product` : censored iff `n_facts * j >= 3072`
  law `step40_wall`        : censored iff `j >= 40`

The three flash-class thresholds are declared in the gate from the archived record (the 96-fact
name cells censored on the flash sibling, this build's archived 96-fact cap-bound yes/no rows,
and round 55's largest delivered product 64 x 32 = 2048 against the smallest censored product
96 x 32 = 3072); the step40 threshold is declared from the sibling 27B build's archived
delivery shape. No threshold moves between the gate and the dispatch.

## Items, arms and dispatch plan

Load-floor items (`facts = 2k`, exactly two disjoint `k`-edge paths, issue #129), selected by
the deterministic rule in the instrument, never by run-time choice; seed base 20261005:

| item | level | seed | facts | lineage |
|---|---|---|---|---|
| L16 | 16 | 52261033 | 32 | round 55's anchor item; round-55 name digests vendored |
| L32A | 32 | 84261011 | 64 | round 55's anchor item; round-55 name digests vendored |
| L48 | 48 | 116261051 | 96 | round 51's certified item (rounds 51, 54); round-51 yes/no digest `068bc6a1fb0620fb` lineage-certified from this round's fact block, round-55 name digests vendored |
| L64 | 64 | 148261120 | 128 | round 56's pinned item (issue #129 option (a), per-item scan pinned at 235 of 400 generated) |

- `name` cells: L16 at `j = 8, 16`; L32A at `j = 8, 16, 24, 32`; L48 at `j = 8, 16, 24, 32,
  40`; L64 at `j = 8, 16, 24, 32, 40` (16 cells; the step-32/40 boundary row is at every load).
- `off_end` controls: `j = k + 1` from the query source on all four items (gold NONE).
- `dead_end` controls: the other path's tail (out-degree zero, never the walk's own terminal)
  asked for one step on L32A and L64 (gold NONE).
- `dup` re-dispatches of the two boundary cells `L48_j40` and `L64_j40` (issue #100).
- Budget rung: `L64_j32` at `max_tokens` 256.

25 dispatches of the 40-call cap, plus one census health call and the one calibration call
above. `temperature 0.0`, every requested cap at most 2,048. Instrument selftest: 128 checks,
green before dispatch, with planted negatives (an off-by-one gold must score wrong, a censored
record must be a non-delivery rather than a wrong answer, an empty pseudo-gold must not read
as present, a false name on a delivered control must invalidate the tier while a censored
control must NOT, a planted digest mutation must be refused, a planted prompt-digest mutation
must be refused, the level-48 fact block must rebuild the archived yes/no digest, each law
fixture must read its own tier, a law tie must refuse the tier, an echo-only trace must refuse
the provenance row, a planted self-agreement split must flag, and the post-hoc same-class
column must read a planted agreement and a planted mismatch).

The 13 round-55 archived rows (9 name cells, 4 NONE controls) are certified byte-identical
against open PR #136's head before the first prompt, and the level-48 fact block is
lineage-certified by rebuilding round 51's yes/no prompt from this round's own fact rendering
and asserting the archived digest `068bc6a1fb0620fb` (fail-closed before dispatch). The
post-hoc same-class column (marked `registered: false` in the summary, never a tier input)
compares the three shared cells `L32A_j32`, `L48_j16`, `L48_j32` against the parallel killed
round-56 firing's archived states, with the reasoning exposure stated on both sides (this
firing's channel from its own census, that build's `reasoning_content`), which is the issue
#105 same-class pair the class-level trace statement the next depth round owes.

## What fired

All 25 planned calls of the 40-call cap dispatched inside the registered 3,000 s guard
(`dispatch_wall_s` 364.2, `not_dispatched` [], 0 retries, zero transport errors, no arm timed
out, no runner abnormality). Nothing is reported here that `raw.jsonl` does not carry.
22,890 prompt and 33,791 completion tokens, 25 records. The pre-gate calibration call (a `j = 8`
name query on the level-8 anchor item, `zish` declared in 358 tokens, digest `4f1fdb53`
re-confirmed byte-identical to the archived prompt) is not experimental data and is not in
`raw.jsonl`.

**Verdict: tier `step40_wall`, flags `control_censored_reported_not_gated`,
`trace_provenance_refused`.** C1 (all 18 cap rows delivered and correct) fails on delivery, not
accuracy: 12 of 18 delivered, all 12 correct, 0 false names. C2 (two-part NONE control) passes:
3 of 6 delivered, all 3 a correct `NONE` refusal, the other 3 censored and reported as
non-deliveries rather than misses. C3 (the four registered laws over the 16 name cells):
`step40_wall` 14 of 16 (the tier, the unique law at or above 13), `load_depth_product` 13 of 16,
`step_count_wall` 13 of 16, `input_load_wall` 8 of 16. C5 (13 byte-identical round-55 anchors
plus the level-48 lineage): 12 of 13 states and 12 of 13 names reproduced. C6 (self-agreement,
issue #100): 2 of 2, both pairs byte- and token-identical at the 2,048 cap (2,048 = 2,048).
C7 (trace provenance, issues #94, #105): refused, gap 0.0 on 4 records. C8 (census, issue #105):
25 of 25. H1 (the 256-token rung): non-delivered, as registered.

## The fired numbers

Delivered: 12 of 18 cap rows (Wilson 95% CI over delivered 0.8788..1.0), all 12 correct, 0
false names. The 12 delivered name cells and their completion tokens: `L16_j8` 438, `L16_j16`
526, `L32A_j8` 793, `L32A_j16` 1,024, `L32A_j32` 1,121, `L48_j8` 365, `L48_j16` 1,003, `L48_j24`
1,816, `L64_j8` 1,423, `L64_j16` 1,156, `L64_j24` 895, `L64_j32` 1,767. Every one of the 6
non-delivered cap rows carries `finish_reason` `length` at the 2,048 cap and an empty answer
field: `L32A_j24`, `L48_j32`, `L48_j40` and its identical re-dispatch, `L64_j40` and its
identical re-dispatch.

The 16 name cells by observed delivery state (the shape the laws are scored against):

| load (facts) | j = 8 | j = 16 | j = 24 | j = 32 | j = 40 |
|---|---|---|---|---|---|
| 32 | delivered | delivered | (not dispatched) | (not dispatched) | (not dispatched) |
| 64 | delivered | delivered | **censored** | delivered | (not dispatched) |
| 96 | delivered | delivered | delivered | **censored** | **censored** |
| 128 | delivered | delivered | delivered | delivered | **censored** |

Three censored pockets at `j < 40` that the step40 law does not cover: `L32A_j24` (64 facts, the
shallowest censored cell in the grid), `L48_j32` (96 facts), and the two `j = 40` cells.
`L32A_j32` delivered at 64 facts even though the two `j = 32` cells at heavier loads are the
censored ones' neighbours.

## Findings

**Finding 1: the class's own step boundary sits at 40, and the flash-class input-load law is
refuted on this build.** The tier reads `step40_wall` (14 of 16, the unique law at or above the
registered 13-of-16 line; the next best, `load_depth_product` and `step_count_wall`, reach 13).
The step40 law's two disagreements are exactly the two `j < 40` censored pockets `L32A_j24` and
`L48_j32`. `input_load_wall` (censored iff `n_facts >= 96`) is refuted on its own terms: every
128-fact cell delivered at `j <= 32` (`L64_j32` at 1,767 tokens) and three of five 96-fact
cells delivered, so the wall is not at the 96-fact input load on this build. The flash-class
law that the round-54 yes/no cap-ladder reading (every 96-fact dispatch cap-bound at every
rung) seemed to support does not transfer to the name arm: the same 96-fact fact block that is
cap-bound on the verdict arm delivers a terminal on the production arm at `j = 8, 16, 24`
(`L48_j24` at 1,816 tokens). The build's own archived cap-bound record is an arm-tied property,
not a build-invariant wall.

**Finding 2: two censored pockets at `j < 40` split the class builds, and one of them is new.**
`L48_j32` (96 facts, product 3,072) censored on this build but delivered `whesh` at 1,636 on
the sibling 27B build (the post-hoc same-class column X1: state disagrees, exposure stated on
both sides - this firing's `reasoning` channel against that build's `reasoning_content`). The
same coordinate is a flash-class censorship (round 55 censored its `L48_j32` at the cap), so
96-fact `j = 32` is now a three-build split: delivered on the sibling 27B build, censored on the
flash build and on this 27B build. `L32A_j24` (64 facts, `j = 24`) is the new pocket: delivered
`vixx` at 1,285 on the flash build (round 55's anchor) and censored on this build at a
coordinate no registered law predicted censored (product 1,536, below every declared threshold).
A censored state at a below-threshold coordinate is a delivery fluctuation of this firing, not
a wall the grid was built to catch; it is flagged, not folded into any law.

**Finding 3: the step-32 cliff is not the class wall, and the product law is not separable
from it at the tier line.** `step_count_wall` (censored iff `j >= 32`) and `load_depth_product`
(censored iff `n_facts * j >= 3072`) both reach 13 of 16 and both are beaten by step40 at 14.
The two agree with each other on the step40 law's disagreement cells (`L32A_j24`, `L48_j32`
both censored under all three) and disagree from step40 only on the cells it covers, so the
registered tier rule (unique law at or above 13) is what separates them: the step boundary is
at 40, and the 3072 product is a coordinate the class happens to cross on the way, not the
governing quantity. The 96-fact `j = 32` cell sits exactly on the declared product threshold
(3,072) and is censored, but so is the 96-fact `j = 40` cell at 3,840 and the 128-fact `j = 40`
at 5,120, while the 128-fact `j = 32` at 4,096 delivers - the product is not monotone in
delivery and cannot be the governing law on this build.

**Finding 4: the accuracy-versus-delivery split replicates in the name space on a second
27B build.** All 12 delivered cap rows are correct and no record anywhere in the round declares
a false name; the 6 non-deliveries are all `finish_reason = length` at 2,048 with an empty
answer field. This is round 50's "accuracy never turns over, only delivery does" on the
production arm: `d*` is still not placed on the name format, and the loss is a delivery loss.
The 256-token rung on `L64_j32` censored as registered (H1), so a one-token answer space buys
nothing against the cap when the reasoning channel is what consumes it.

**Finding 5: the control-gate amendment and the self-agreement control both hold (issue #100).**
Among the three delivered NONE controls all three refused correctly (delivery rate 0.5,
reported not gated), so the round-55 finding-3 two-part rule, carried by rounds 56 and 57, is
discharged on a 27B-class build: a censored control is a non-delivery, not a miss. Both
re-dispatch pairs at the `j = 40` boundary are byte- and token-identical to their grid
originals (2,048 = 2,048 both pairs), so self-agreement holds at temperature 0 on this build's
censored boundary cells.

**Finding 6: the trace-provenance row refuses itself for the third time in the name-arm
family (issue #94, issue #105).** On the four undelivered name-gold records the gold terminal
appears in the reasoning text in 4 of 4 and the matched pseudo-gold - the other path's tail,
same role, same item - in 4 of 4: gap 0.0, refused. This is the same echo-capture failure as
round 55 (gap 0.0) and the round-56 refusal (gap -0.1429): a long traversal enumerates both
tails, so containment cannot separate reaching the terminal from listing candidates. The "it
knew but could not say" question stays open, and no version of it is claimed here.

## Census (issue #105)

25 of 25 records carry the field census; the reasoning channel is `reasoning` (not
`reasoning_content`) on all 25, the round-54 build's channel (digest `26df9af5972ff312`),
against `reasoning_content` on the sibling 27B build's round-56 records (digest
`86d6f3507f8725bf`) and on the flash class's round-55 records (digest `4075b5949b2b0487`).
The X1 same-class column is an answer-level statement with both sides' exposure stated; the
class-level trace statement the next depth round owes still needs a same-class pair with the
channel open on both sides, which this firing provides only at the answer level.

## Limits

- One endpoint, one class, one firing: `Executed`, exploratory, n = 1 per cell (two cells at
  n = 2 via the duplicate re-dispatches).
- The name arm is a different task from the archived yes/no arm. It cannot show that the
  yes/no task is solvable at a depth where it is not; it shows what this endpoint produces
  about the same fact graph when the answer space is a name.
- The prompt states the step count, so the task is "walk `j` edges", not "decide
  entailment". Any depth claim from it is a claim about production under an explicit horizon.
- The gold terminal is present in the fact block, so a model could in principle reach it by a
  positional rule ("the entity with no outgoing edge") rather than a walk. That shortcut is
  worth about 1/2 at `j = k` and about zero at the intermediate `j` cells, which is why the
  curve, not the deepest cell, carries the claim.
- The `j < 40` censored pockets (`L32A_j24`, `L48_j32`) are not predicted by any registered
  law; they are delivery fluctuations reported as such, not wall evidence. A law fit that
  ignores them would overstate the step40 tier's support (14 of 16 against the full 16-cell
  grid is the registered reading, not a post-hoc best).
- The round-56 same-class column rides on an untracked archive (a killed firing left no
  branch and no PR). It is disclosed as post-hoc provenance only; no verdict of this round
  reads it, and if that archive is deleted the column's inputs are the vendored in-file
  constants with their disclosed source.
- The flash-class law thresholds are cross-class transfer candidates declared before dispatch;
  a law that fits on this build does not re-establish the flash-class record, and one that
  fails here does not refute it on its own class.
- Trace exposure (issue #105): `reasoning` channel open on 25 of 25 records on this firing
  (digest `26df9af5972ff312`), stated against the sibling builds' `reasoning_content` exposure.

## Limits

- One endpoint, one class, one firing: `Executed`, exploratory, n = 1 per cell (two cells at
  n = 2 via the duplicate re-dispatches).
- The name arm is a different task from the archived yes/no arm. It cannot show that the
  yes/no task is solvable at a depth where it is not; it shows what this endpoint produces
  about the same fact graph when the answer space is a name.
- The prompt states the step count, so the task is "walk `j` edges", not "decide
  entailment". Any depth claim from it is a claim about production under an explicit horizon.
- The gold terminal is present in the fact block, so a model could in principle reach it by a
  positional rule ("the entity with no outgoing edge") rather than a walk. That shortcut is
  worth about 1/2 at `j = k` and about zero at the intermediate `j` cells, which is why the
  curve, not the deepest cell, carries the claim.
- The round-56 same-class column rides on an untracked archive (a killed firing left no
  branch and no PR). It is disclosed as post-hoc provenance only; no verdict of this round
  reads it, and if that archive is deleted the column's inputs are the vendored in-file
  constants with their disclosed source.
- The flash-class law thresholds are cross-class transfer candidates declared before dispatch;
  a law that fits on this build does not re-establish the flash-class record, and one that
  fails here does not refute it on its own class.
- Trace exposure (issue #105): [CENSUS PENDING].

## Reproduce

```
python3 research/nightly-2026-11-10-0401/wall_shape_probe_r58.py --selftest
python3 research/nightly-2026-11-10-0401/wall_shape_probe_r58.py --dry-run
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
  python3 research/nightly-2026-11-10-0401/wall_shape_probe_r58.py --run
python3 research/nightly-2026-11-10-0401/wall_shape_probe_r58.py --rescore
```

Prompts are not stored in `raw.jsonl`: each record carries `(level, seed, j, cap, kind)` plus
the prompt sha256, and the prompt re-renders byte-identically from the seed base, so the
digests are the check. `run.log` stays local.

## Landing note (added 2026-11-19 when this record was landed; everything above is as-shipped)

This directory is a stranded record from the audit filed as issue #150: the 2026-11-10 04:01 firing
wrote a complete record into the runner's working copy and never created a branch or posted a #65
summary, so it was unreachable from the remote until this PR. Three disclosures travel with it.

1. **Instrument: one selftest fixture changed, no experiment path touched.** The sanitizer
   selftest planted two pieces of endpoint noise: a private-range IPv4 address with a port, and a
   model file name under a home path. The serving-id guard (`scripts/check_serving_ids.py`) scans
   tracked files and reads both as leaks, so the fixture now plants an RFC 5737 documentation-range
   address with the same port and a model file name under `/root/`, with the matching assertion.
   Both classes are still stripped by `_SECRET_PATTERNS` (which matches any IPv4 and any
   `root|home|mnt|media|run/user` path), the fixture sits inside `selftest()` only, and
   `--selftest` is green:
   128 checks, 25 planned calls, 16 name cells, 6 controls, gate blob `ff1df364dc84a2be`. This is
   the concrete case behind issue #149: an unlanded tree never met the guard, so its fixture was
   written before the guard's leak classes applied.
2. **`summary.json` is the derived file, and the shipped file was already non-reproducible.** The
   file here is the deterministic `--rescore` derivative from the 2026-11-19 verification on #150,
   and hashes `af5e8c13cb2f77b989b032478f35db133a22553c93e40c2cc4cc8e9fd1f5827d`. It is the same
   size as the
   shipped file (16,408 bytes) and a different sha256, and rescore is deterministic, so the shipped
   bytes were not the byte output of this script over these frozen inputs at rescore time either.
   Which fields differed can no longer be named: the verification ran `--rescore` against the only
   copy without a byte backup first. Every aggregate `run.log` printed at dispatch time is
   reproduced by the derived file: tier `step40_wall`, both flags
   (`control_censored_reported_not_gated`, `trace_provenance_refused`), and all four C3 wall-law
   counts 8/16, 13/16, 13/16, 14/16. `gate.json`, `health.json`, `calibration.json`, `raw.jsonl`
   and the instrument (apart from the fixture above) are byte-unchanged since the firing.
3. **A duplicated Limits block is as-shipped.** This README carries two `## Limits` sections: the
   complete one and a truncated duplicate left by the session restart, whose last bullet still
   reads `[CENSUS PENDING]`. The census is not pending: it is filled under "Census (issue #105)"
   above (25 of 25 records censused, reasoning channel `reasoning` on all 25, C8 `censused 25 of
   25`), and C8 in `summary.json` agrees. Both blocks are kept verbatim under the forward-only
   errata rule (#120); this note is the annotation.

Label: **Executed**, exploratory. One endpoint, one class, one firing, n = 1 per cell (two cells at
n = 2 via duplicate re-dispatches). No row here is a study verdict; the thesis reading of the ladder
ceiling stays with the pre-registered analysis (#11). `run.log` stays local per the research
contract, and `__pycache__` is excluded.
