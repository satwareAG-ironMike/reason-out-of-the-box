# Round 52 (2026-11-07 03:19): the load-floor wall on a 27B class - the cross-path boundary is class-shared, the mode is class-split, and the 1,556 pin is not reproduced

Firing: 2026-11-07 03:19 (session start), pool slot 4/6 (issue #65). Class: a 27B-class local
endpoint (serving id disclosed only in the commit `Model:` trailer; artifact digest
`86d6f3507f8725bf`). No metered or hosted provider was used; no search API was used. Status
label: **Executed** (see Limits).

## Question

Registered before dispatch (schema `round52-gate-v1`, frozen in `gate.json`, pinned in the
instrument), blob:

`0b0e8d777c7ac97047f70ea33eafb05f23ffc3e424f2a6d4c945fe1d2603b550`

> On the load-floor ladder family (facts = 2k), does a 27B-class local endpoint reproduce the
> reference firing's wall (the k = 48 cross-path answer flip, and the negative arm pinned at
> 1556 completion tokens), and are identical-prompt re-dispatches byte-identical on this class
> (the issue #100 self-agreement control the reference firing owed)?

The 2026-11-06 04:33 firing (flash-next class) measured this family at the generator's load floor
out to k = 48: 16 of 16 delivered (nothing truncates), 13 of 16 correct, all three failures
cross-path (both k = 48 items answered yes to a query whose endpoints sit on different paths),
and every gold-no record stopped at exactly 1,556 completion tokens at every depth. Its issue
#100 self-agreement control never dispatched. Two questions followed: is the k = 48 cross-path
break a capability artifact of the small class, or does it hold across classes; and is the
1,556 pin a class property, a firing-state property, or a deployment artifact?

## Pairing design

This round re-dispatches the reference firing's items byte-identically (prompt digests pinned)
on a different class:

- k = 24, 40, 48: 12 items, digests pinned to the reference firing's archived grid records.
- k = 32: 4 items, the digest-pinned M32 item set of round 50, which the reference firing
  re-dispatched: the k = 32 cell is a two-firing lineage point (round 50 flash, reference flash,
  this firing 27B).
- k = 16: 4 items, a same-construction anchor only. The reference firing did not dispatch
  k = 16, and round 50's M16 band row is a different item (facts = 64 against the floor's 32),
  so this cell pairs by construction with lineage cited by digest, not by archived outcome.
- k = 48 extras: the two unselected floor items, both gold-no, so the cross-path arm at the
  cliff depth carries four items (2 paired + 2 extra).
- Duplicates: two k = 48 items re-dispatched once (the gold-no item the reference firing
  answered wrong, 116261051, and the smallest-seed gold-yes item, 116261338): the issue #100
  control.

Pairing is fail-closed: all 22 pinned prompts (16 reference-firing rows, 4 of which are also
round 50's M32 anchors, plus 2 extra floor items) and 4 construction anchors must regenerate
byte-identically from the shipped generator before any prompt is spent, or the instrument
refuses to dispatch. It certified 22 of 22 and 4 of 4 before dispatch, and `--rescore` re-runs
the certification offline. The reference archives live in open PRs, so the pins are in-file
constants (the round 50/51 pattern): the post-merge tree re-certifies from the constants alone.

## Instrument

`cross_class_floor_probe.py`, stdlib only, `--selftest` with 73 checks, all of them able to
fail: independent BFS solver plus the shortcut/isomorphism/gold-flip refusals (issue #67
guards); the pinned prompt template re-derived from the shipped generator with a planted
template slip; the selection rule checked against an independent scan and against a
band-tolerance variant that selects a different item set (the variant picks round 50's M24 band
items); series determinism and the shipped-file identity assertion; the pairing certification
with planted digest, gold, seed-set, M32-anchor and extra-item slips; the exact McNemar against
hand-computed binomial values; the Wilson interval pinned to the reference firing's 13/16 CI;
the gate blob pin; the issue #105 census merge rule; the sanitizer over RFC 5737 documentation
addresses, documentation hostnames and credential fixtures assembled from fragments; the
duplicate join keyed on the item rather than the cell label (the defect that cost the reference
firing its self-agreement row); and the transport, malformed-response and censored record
paths. The selftest caught a ported-BFS defect (a dropped queue append in the weak-component
guard) before any prompt was spent.

Gate rows P1-P5 (predictions and readouts), N1-N3 (census and controls) with the bands
registered in `gate.json`. Tier rule: N3 uncertified -> `refused_no_dispatch` (fatal
pre-dispatch); P1 fail -> `cross_path_cliff_class_invariant`; P1 pass ->
`cross_path_cliff_flash_specific`. Flags: `negative_arm_pin_reproduced` (P2 fail),
`wall_is_label_split` (any gold-no truncation), `self_agreement_holds_at_temperature_0` (N2
pass).

Readout policy (issue #94): the answer field only. The trace-recovery rules stay refused after
round 50's calibration failure (0.5652 agreement). Trace text is stored for prefix identity and
length only. The cross-class comparison is an answer-level claim with both sides' trace exposure
stated (issue #105): reference firing `reasoning_content` open on 20 of 20 records, 16-hex model
digest `c62b81e96826354e`; this firing `reasoning_content` open on 24 of 24, digest
`86d6f3507f8725bf`.

## Result

25 dispatches of the 40-call cap (1 health, 20 grid, 2 extra, 2 dup), zero transport errors,
zero retries, 16,672 prompt tokens, 27,673 completion tokens, 2,624.9 s of record wall at
concurrency 2. Tier: **`cross_path_cliff_class_invariant`**, flags
`wall_is_label_split`, `self_agreement_holds_at_temperature_0`.

| Gate row | Band | Measured | Verdict |
|---|---|---|---|
| P1 k = 48 gold-no correct (2 paired + 2 extra) | >= 3 of 4 | 1 of 4 (3 of 4 censored at the cap) | **fail** |
| P2 gold-no distinct stops, paired levels | >= 3 distinct, delivered >= 5 | refused (4 delivered; those 4 are distinct: 763, 1222, 1775, 1806) | refused |
| P3 positive-arm slope | 15..50 tokens/hop | 20.9 | pass |
| P4 label-split cost ratio | reported or refused | reported, 3 of 5 cells (1.3705, 2.1162, 3.0322) | readout |
| P5 cross-class join (zero prompts) | reported | joined 16 of 16, digest-identical; McNemar b = 0, c = 1, p = 1.0 over 12 delivered pairs | readout |
| N1 reasoning field open (issue #105) | >= 90% | 24 of 24 | pass |
| N2 duplicate re-dispatches byte-identical (issue #100) | 2 of 2 | 2 of 2 (and token-identical) | pass |
| N3 pairing certification | 22 of 22 + 4 of 4 anchors | 22 of 22 + 4 of 4, pre-dispatch | pass |

Stage 1, 20 records, answer-field readout only (stops in completion tokens; the reference
firing's per-item stops in parentheses):

| k | gold-yes delivered / correct (this firing) | reference firing | gold-no delivered / correct (this firing) | reference firing |
|---|---|---|---|---|
| 16 | 2 / 2 (345, 336) | not dispatched | 2 / 2 (475, 446) | not dispatched |
| 24 | 2 / 2 (464, 474) | 2 / 2 (771, 666) | 2 / 2 (763, 1222) | 2 / 2 (1556, 1556) |
| 32 | 2 / 2 (604, 577) | 2 / 2 (985, 845) | 2 / 2 (1806, 1775) | 2 / 1 (1556, 1556) |
| 40 | 2 / 2 (715, 731) | 2 / 2 (1153, 1059) | 0 / 0 (both censored at 2048) | 2 / 2 (1556, 1556) |
| 48 | 2 / 2 (840, 1250) | 2 / 2 (1310, 1509) | 0 / 0 (both censored at 2048) | 2 / 0 (1556, 1556) |

Extras (k = 48, gold-no): 116261303 delivered correct at 1,731; 116261347 censored at 2,048.
18 of 18 delivered answers are correct (Wilson 95% CI over delivered 0.8241..1.0; over all 24
records 18/24, CI 0.551..0.88). All six non-deliveries are gold-no records at k = 40 and
k = 48, every one of them `finish_reason` `length` at the 2,048 cap.

## Finding 1: the k = 48 cross-path boundary is class-shared; the mode of the wall is class-split

Neither class gets the k = 48 cross-path arm right. The reference firing delivered both items
and got both wrong (answered yes to a cross-path query, natural stop 1,556). This firing
delivered one of four and got it right; the other three never delivered at all: 116261051 and
116261076 (the reference firing's two wrong items) and 116261347 ran to the 2,048 cap with no
answer token, while 116261303 finished at 1,731 with the correct no.

The tier rule therefore reads `cross_path_cliff_class_invariant`, and the registered parenthetical
("delivered wrong cross-path answers at k = 48 on both classes") is the part that does not
apply to this firing: on the 27B class the wall is non-delivery, not error. What is invariant is
the boundary itself (no class clears the k = 48 cross-path arm), and what splits by class is the
mechanism: the small class commits a wrong verdict at a natural stop, the larger class
enumerates past the cap. `d*` on the cross-path arm is placed as an interval at 48 on both
classes (2 items per class on the reference side, 4 on this side), and the label-split flag
`wall_is_label_split` fires for the first time on this family.

## Finding 2: the 1,556 pin is not reproduced on this class

Every delivered gold-no stop on this class is different, and none of them is 1,556: 475, 446
(k = 16), 763, 1222 (k = 24), 1806, 1775 (k = 32), 1,731 (the delivered k = 48 extra). At the
four registered paired levels the row is refused (only 4 of 8 delivered), but the 4 delivered
stops there (763, 1222, 1775, 1806) are 4 distinct values, and the negative arm grows with
depth (mean 460.5 -> 992.5 -> 1,790.5) instead of sitting on a constant. The pin is therefore
not a family property; it is either a flash-class property or a firing-state property, and this
round cannot separate those (the reference class is not re-dispatched here).

The cost surface splits the same way, in the opposite direction: the label-split ratio on this
class *grows* with depth (1.3705 at k = 16, 2.1162 at k = 24, 3.0322 at k = 32; k = 40 and
k = 48 unreportable, their negatives censored), while on the reference firing it *shrinks*
(2.1656 -> 1.1039) because its negative arm never grew past the pin. The positive arm, by
contrast, is cheaper on this class at every paired depth (mean delta over the 8 paired yes items
-330.4 completion tokens; slope 20.9 against 28.3 tokens/hop), and the k = 16 anchor shows the
same pattern from below (336.0 yes vs 460.5 no).

## Finding 3: the zero-truncation claim does not transfer to the ladder family on this class

Issue #126 recorded a monotone collapse of the 2,048 truncation wall to zero on both classes
across four firings, on the E = 192 knob panel. On the ladder family at the load floor the wall
is back: 6 of 6 gold-no records at k = 40 and k = 48 (including one extra) are censored at the
cap on this class, while the positive arm on the same firing delivers 10 of 10 with `stop`.
The zero-truncation statement holds for the panel it was measured on and for the reference
firing's ladder run, and does not generalize to this class on this family: the cap binds on
exactly one label, which is what the `wall_is_label_split` flag now records for the family.

## Finding 4: self-agreement holds at temperature 0 on this class, including on the censored pair

Both duplicate re-dispatches (the issue #100 control the reference firing owed) are
byte-identical to their grid original in content and trace, and token-identical: 116261338 at
840 = 840, and 116261051 at 2,048 = 2,048 with the cap-cut trace reproduced byte-for-byte. The
flag `self_agreement_holds_at_temperature_0` therefore fires on this class. The contrast with
the reference class is a firing-state fact, not a class law: the 2026-11-07 04:00 firing
(parallel round, flash-next class, same item set) re-dispatched 116261051 and got the same
1,556 tokens with different traces and answers (`no` then `yes`); the class-level determinism
claim needs a same-class pair on both sides (issue #105) and is not made here.

## Finding 5: the one cross-class discordance is the item the small class got wrong

The P5 join is 16 of 16 with all prompt digests verified. Over the 12 delivered matched pairs,
McNemar gives b = 0, c = 1 (p = 1.0): 84261050 (k = 32 gold-no) is the only item whose verdict
changed class, and it changed in the 27B class's favor (reference firing answered yes, wrong;
this firing answered no, correct, at 1,775). The four excluded pairs are precisely the k = 40
and k = 48 gold-no items this firing did not deliver; their exclusion is the Finding 1 result,
not a join artifact.

## Cutoff, disclosed

The firing's dispatch phase ran to completion: 25 of 25 planned calls dispatched inside the
registered 1,800 s dispatch budget (the final call started inside the budget and landed
outside it; nothing was cut). The instrument then crashed in its own summary write (a
`NameError` in `run_dispatch`, a defect in this round's port, not in the transport), after all
24 records were already fsynced to `raw.jsonl`. The defect was repaired and `--rescore` rebuilt
`gate.json` and `summary.json` offline at zero prompt cost; `run.log` (local, not published)
carries the traceback and the per-dispatch trail. The registered gate (rows, bands, tier rule,
blob `0b0e8d77`) was not modified to fit anything.

## Limits

- 2 items per cell (4 on the k = 48 cross-path arm including extras); one delivery flips the
  P1 boundary, and the tier rests on 3 of 4 censored versus 0 of 2 wrong on the reference side.
- One firing, one deployment (a 27B-class local endpoint, digest `86d6f3507f8725bf`), one
  class, temperature 0, concurrency 2. The reference side is a different class on a different
  firing (flash-next class, digest `c62b81e96826354e`): this is a cross-class comparison, not a
  replication of either firing.
- P2 was refused under-powered (4 of 8 delivered at the paired levels). The "pin not
  reproduced" statement rests on 7 distinct delivered negative stops (6 paired-cell plus the
  delivered extra) and the absence of 1,556 among them; no mechanism is established for either
  class.
- The censored no records cost 2,048 tokens each: the negative arm's true traversal length on
  this class is unknown (>= 2,048), so the P4 ratio cannot be completed at k = 40 and k = 48.
- The McNemar rests on 12 delivered pairs; the 4 excluded pairs are the finding, but the
  matched-pair design cannot express a delivered-against-censored contrast.
- Executed, not Reproduced or Validated: no second firing of this plan ran.

## Reproduce

```bash
cd research/nightly-2026-11-07-0319
python3 cross_class_floor_probe.py --selftest   # 73 checks, prints the gate blob
python3 cross_class_floor_probe.py --gate       # rewrites gate.json, prints the blob
python3 cross_class_floor_probe.py --dry-run    # the frozen dispatch plan
python3 cross_class_floor_probe.py --rescore    # rebuild gate.json + summary.json from raw.jsonl
```

`--rescore` is the offline path: it reads `raw.jsonl`, refuses if any record carries a gate hash
other than the frozen blob, re-runs the pairing certification, and re-derives every number in
this README from the archived bytes. The endpoint variables are read from the runner
environment and are never written into a file in this directory: artifacts carry `model_digest`
only, and every stored response string passes the sanitizer.
