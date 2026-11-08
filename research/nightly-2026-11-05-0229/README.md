# Round 48 (2026-11-05 02:29): the test-retest re-fire of the round-46 27B-class knob battery - the round-46 readout (class-tied ceiling 2/11, ban 8/11 at cost ratio 1.0237, bounded knob bounded_loss 6/11 at 1.3089) re-dispatched on a new 27B-class firing: the ceiling band holds (1/11), the bounded knob flips to bounded_gain (10/11), and the census exposure state has flipped to the round-42 `reasoning` state

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is the
reproducible record: script, gate, prompts, raw responses, scores.

## Question

Does the round-46 27B-class knob readout - the class-tied ceiling (mode A truncates
2/11 against the archived 11/11 and the flash class's 8/11), the ban's delivery
(8/11 all correct, cost ratio 1.0237 over mode A: the ban is cost-neutral on the
ceiling-free 27B class) and the bounded single-pass knob's `bounded_loss` (6/11
delivered, cost ratio 1.3089 over the ban: the permission demonstrably triggered the
enumeration it bounds on one item) - repeat on a NEW 27B-class firing of the same 11
archived E = 192 items? And is this firing the same serving state as the archived one,
or a new state of the class: the round-46 deployment exposed its trace via
`reasoning_content`, the round-42 deployment via `reasoning`, and the census health
call decides which side of that exposure boundary this firing sits on.

Motivation, from the record:

- round 33 (the test-retest pattern this round applies): re-dispatching an
  archived grid on the class that produced it separates within-firing byte
  stability from cross-firing drift - "all seven repeatability predictions pass and
  32 of 36 completions are token-identical three days later", and the cross-class
  cost-law gap read "noise-bounded". The knob family has no such re-fire yet:
  rounds 42, 44 and 46 are three different firings, but no 27B-class firing has
  been repeated, so the class-tied ceiling statement (27B: 1/11 to 2/11 truncations
  vs 8/11 to 11/11 on the flash class) rests on two 27B firings of different
  deployment states (round 42 zero-trace-scoring, round 46 trace-exposed).
- round 46's disclosure named the open question: "the flash-class arm of the
  discriminator (cross-check items at depth) remains the sharpest open knob
  question and needs a flash-class firing of modes A/C/D". This firing is a 27B-class
  slot, so the flash arm stays open; the re-fire question on the 27B class is the
  next cheapest step in the knob family and sharpens the #105 exposure-control
  record: it asks whether the exposure state (which message field carries the trace)
  is a stable class property or a firing-state property.
- issue #100 (self-agreement control): the three duplicate mode-A dispatches
  (one per cell) run again, so the firing's decoding determinism is read beside the
  repeat rows.

> Re-dispatch the round-46 battery - mode A (the archived prompt, 11), mode C
> (`Without repeating any fact, answer with exactly one word: yes or no.`, 11),
> mode D (`You may state each fact at most once, then answer with exactly one word:
> yes or no.`, 11), plus 3 duplicate mode-A dispatches and 1 census health call (37
> of the 40-call cap, `max_tokens` 2048, `temperature` 0.0, concurrency 2) - and
> score the five re-fire rows against the two archived 27B-class firings (rounds 42
> and 46): R1 the mode-A truncation count stays inside the 27B-class band
> (<= 3/11), R2 the ban delivers >= 8/11 with zero wrong, R3 the ban's cost ratio
> C over A stays inside [0.90, 1.25], R4 the bounded knob does not beat the ban
> (<= 7/11), R5 the bounded permission costs >= 1.10 times the ban; R6, the
> firing-identity readout, counts the dispatch records byte-identical to the
> archived round-46 firing.

## Instrument

`policy_knob_probe.py` (stdlib only). The construction, structural audit, prompt
rendering, readout rules, scoring and attempt mechanics of the merged round-23
instrument (`research/nightly-2026-10-25-0205/frontier_walk_probe.py`) are loaded
by import, not re-implemented; the census transport and the decision machinery are
carried byte-identically from the round-46 instrument, so this firing differs from
round 46 only in the firing state and the new R rows. The panel is certified
digest-true against the archived round-23 `raw.jsonl` (on main) before anything is
dispatched; the archived round-46 `raw.jsonl` blob is pinned by digest
(`certify_reference`, fail-closed) and is the join target for R6.

Panel: the 11 round-23 records whose archived attempt reached the 2048-token cap
with the answer field silent (finish_reason `length`, content answer null), taken
in full - 2 items at S4 (k = 8), 4 at S5 (k = 12), 5 at S6 (k = 16), all at E = 192;
4 gold-yes, 7 gold-no; archived loose-fallback line 8/11 on the same items.

Modes (one line added to the question line; the rule sentence and every fact line
stay byte-identical, asserted on every prompt):

| mode | delta on the question line | calls |
|------|----------------------------|-------|
| A | none (the archived prompt) - replication control for the truncation record | 11 |
| C | `Without repeating any fact, answer with exactly one word: yes or no.` (the ban) | 11 |
| D | `You may state each fact at most once, then answer with exactly one word: yes or no.` (the bounded single-pass knob) | 11 |
| A2 | the mode-A prompt re-dispatched for three deterministic items, one per cell: the identical-prompt self-agreement control (#100) | 3 |
| health | the 256-token chat health call, doubled as the channel census | 1 |

37 of the 40-call cap, `max_tokens` 2048, `temperature` 0.0, concurrency 2.

The field census of round 40's declared extension runs on every dispatch
(completion-message field names plus the reasoning-supplying field, merge rule
`reasoning_content` if non-empty, else `reasoning`, else none; record-only, the
scoring channel stays the inherited byte-identical one). The census health call
decides the firing's exposure state: if the channel is supplied by `reasoning`
(round-42 style), the P7/P8c floors refuse the text-derived claims while the
delivery and cost tiers stay scored - the pre-registered narrowing, not an ad hoc
one; the R rows (truncation counts, deliveries, cost ratios, byte identity) do not
read the trace text and stay scored in either exposure state.

The round-44 and round-46 comparison constants are vendored in-file
(`ROUND44_REFERENCE`, `ROUND46_REFERENCE`) with their archive blob digests,
extracted programmatically from the merged archives in this session and
re-verified against the archived raw records (the cost ratios recomputed from the
embedded means); `--selftest` asserts their internal consistency and carries
planted-slip controls for both, so both comparisons verify in the post-merge tree.

## Gate

Schema `round48-gate-v1`, frozen before any prompt was spent. The shared rows P1
to P9, N1 and N2 are byte-equal to the round-46 gate, so the four firings (42, 44,
46, 48) score the shared rows on one table. The re-fire rows R1 to R6 are new:
R1 mode A truncates <= 3/11 (the 27B-class band: round 42 1/11, round 46 2/11,
against 8/11 and 11/11 on the flash class), R2 mode C delivers >= 8/11 with zero
wrong, R3 the cost ratio C over A stays inside [0.90, 1.25] (1.1255 in round 42,
1.0237 in round 46), R4 mode D delivers <= 7/11 (6/11 in round 46), R5 the cost
ratio D over C >= 1.10 (1.3089 in round 46), R6 at least 20 of the 36 dispatch
records byte-identical to the archived round-46 firing (firing-identity readout,
not a tier row). Repeat decision table: `repeated` (all of R1-R5 hold) /
`partial` (3-4 of R1-R5) / `divergent` (0-2 of R1-R5).

## How to reproduce

```
python3 research/nightly-2026-11-05-0229/policy_knob_probe.py --selftest
python3 research/nightly-2026-11-05-0229/policy_knob_probe.py --gate --out /tmp/gate.json
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... \
python3 research/nightly-2026-11-05-0229/policy_knob_probe.py \
  --probe --out-dir research/nightly-2026-11-05-0229
python3 research/nightly-2026-11-05-0229/policy_knob_probe.py --analyze \
  --out-dir research/nightly-2026-11-05-0229
```

`--probe` refuses unless the panel certifies digest-true, the archived round-46
blob certifies its embedded digest, and the endpoint passes the census health
call. Endpoint values are read from the environment and never written to an
artifact; stored model text passes the inherited sanitizer.

## Results

Evidence label: `Executed` (exploratory, small n = 11 panel items, one endpoint, 36
dispatched records plus one health call, zero retries, zero transport errors). Frozen
gate `round48-gate-v1` (blob
`294ed5bda21d516de4fff44507d1c1e2c4f3017d4014f58bf676242e9a032817`), verdict tier
`policy_artifact`, mode-D tier `bounded_gain`, repeat tier `partial` (4 of 5 of R1-R5).
A post-run `--analyze` reproduces the checks block written at dispatch time (empty
diff); `summary.json` additionally carries the probe-time transport keys.

**The readout repeats as a within-class band statement on a NEW firing (repeat tier
`partial`, 4/5; R4 alone diverges).** R1 holds at 1/11: mode A truncates a single
item (the third S6 X, 2048) against the registered <= 3/11 band - the 27B-class
firings of this design now read 1/11 (round 42), 2/11 (round 46) and 1/11 (this
firing) against 8/11 and 11/11 on the flash class, so the class-tied ceiling holds
on a third 27B firing. R2 holds at 9/11 with zero wrong: the ban delivers 9/11 all
correct, strictly above the archived 8/11 loose-fallback line, which re-establishes
the shared table's top tier `policy_artifact` (the round-42 readout: 9/11 all
correct). R3 holds at 1.0982 inside [0.90, 1.25]: the ban's cost ratio C over A is
the fourth data point of the state-dependent cost ledger - 1.1255 (round 42,
ceiling-free 27B, zero-trace-scoring deployment), 0.6756 (round 44, ceiling-present
flash class), 1.0237 (round 46, ceiling-free 27B, trace-exposed) and 1.0982 (this
firing, ceiling-free 27B, `reasoning`-exposed): the ban stays cost-neutral on the
ceiling-free 27B class and re-claims budget only where the ceiling is present. R4
fails at 10/11 against the registered <= 7/11: the bounded knob is the BEST
delivery mode on this firing (10/11 all correct, 1 truncated, cost ratio 1.2325
over mode A) and beats the ban by one item (paired C vs D: C-only 0, D-only 1,
p = 1.0), so the round-46 `bounded_loss` readout does not repeat on this class. R5 holds at
1.1224: the cost direction of the bounded knob DID repeat - the permission is the
most expensive instruction in both firings (1.3089 over the ban in round 46,
1.1224 here).

**The mode-D tier flips with the firing state, not with the class.** Round 46 read
`bounded_loss` (6/11 delivered, worst of the three modes, the permission triggered
the enumeration it bounds on an item the ban delivered); this firing reads
`bounded_gain` (10/11 delivered, best of the three modes). The item-level structure
is one-directional against round 46's mixed one (paired C vs D: C-only 0, D-only 1,
p = 1.0): the permission reclaims the one item the ban lost - the second S5 X,
where the ban truncates at 2048 and the bounded knob delivers in 1,588 tokens - and
loses nothing (the third S6 X truncates in both the ban and the bounded knob at
2048, where mode A delivered it in 974). The mechanism-level read (whether the
permission triggered enumeration) is refused on this firing: the trace text sits in
the field the scoring channel does not record, so the text-derived claims are
refused by the P7/P8c floors and the flip is a delivery-level statement, not a
mechanism statement. The bounded-knob discriminator (filed on #71) is therefore a
firing-state property on the 27B class: it needs the flash-class A/C/D firing to
close, which this round could not run (a 27B-class slot was assigned).

**The census exposure state flipped between the two 27B-class firings (the #105
third exposure state; P7/P8c refused as pre-registered).** The census opens via
`reasoning` on the health call (N1 holds, source `reasoning` - the round-42
outcome) instead of `reasoning_content` (the round-46 outcome), and the message
field set changed with it (this firing: `audio`, `content`, `function_call`,
`reasoning`, `refusal`, `role`; round 46: `content`, `reasoning_content`,
`role`), which marks a different serving revision of the same public model class.
Every dispatch records its trace in the `reasoning` field (census: mode A 672 to
4,506 chars, median 1,898; mode C 665 to 4,882, median 1,649; mode D 1,140 to
4,994, median 2,561) while the inherited scoring channel - byte-identical to the
round-23 transport, which reads `reasoning_content` only - records 0 trace chars
on all 36 dispatches, so P7 and P8c fail at 0/11 and the text-derived readouts
(distractor ratios, the obedience split, the P6 manipulation check) are refused,
the pre-registered narrowing, not an ad hoc one. The 27B class is now measured
under all three exposure states (round 42 zero-trace-scoring, round 46
`reasoning_content`, this firing `reasoning`), and the exposure state is a
property of the serving state, not of the class. R6 records the consequence:
0/36 dispatch records byte-identical to the archived round-46 firing (3/36
content-identical), so the repeat rows are a cross-firing class statement, not a
within-firing restatement.

**The shared-table flash-class rows fail exactly as the 27B-class behavior
predicts.** P2/P2b (the flash-class replication floors: >= 9/11 truncations,
<= 2/11 deliveries) fail at 1/11 and 10/11; P5 (the flash-class budget-re-claim
ceiling of 0.50) fails at 1.0982; P6 fails behind the refused P7 floor. P3, P4,
P4b, P8, P8b, N1, N2 and P9 hold. `all_registered_predictions_met` is false, as
on every 27B-class firing of the shared table: the flash-class rows are not
expected to hold on this class.

**Controls.** Self-agreement (N2, #100): 2/3 duplicate pairs byte-identical
(TARr 0.6667; the >= 2 floor holds) but 0/3 token-identical - on two pairs the
answer word is stable while the billed trace length drifts (S4: 993 vs 797
completion tokens; S5: 1,473 vs 596), and the S6 pair diverges on the answer
itself: the mode-A original delivered "no" in 596 tokens on a 1,659-char trace,
the duplicate dispatch truncated at 2048 on a 4,341-char trace with no answer.
Within-firing trace non-determinism on this deployment state, against the
token-identical rounds 42/44/46 (TARr 1.0) and the within-firing byte stability
round 38 recorded. The vendored round-44 and round-46 reference constants both
pass their planted-slip consistency controls (`violations` empty in
`summary.json`). Transport: 104,689 prompt / 33,564 completion tokens, ~67.9
tokens/s single stream (3.6x the round-46 slot rate of 18.77), wall 508.7 s,
37 of the 40-call cap.

## What it changes

- It completes the 27B-class knob-family record with the third firing and its
  first test-retest re-fire: the class-tied ceiling now holds across three 27B
  firings (1/11, 2/11 and 1/11 truncations on the same 11 items) against 8/11 to
  11/11 on the flash class, and the ban's cost-neutral ratio now has three
  ceiling-free 27B data points (1.1255, 1.0237, 1.0982) against the
  ceiling-present flash firing's 0.6756.
- It flips the mode-D tier on the 27B class (`bounded_loss` in round 46 to
  `bounded_gain` this firing, with the cost direction intact: the bounded
  permission is the most expensive instruction in both firings) and refines the
  #71 bounded-knob discriminator: on the 27B class it is a firing-state
  property, not a class property, and the flash-class arm (the sharpest open
  knob question from round 46) remains the firing that would close it.
- It adds the third 27B-class exposure state to #105 (the class is now measured
  under zero-trace-scoring, `reasoning_content` and `reasoning` exposure) and
  shows the exposure state can flip between firings of the same public model
  class, with the serving revision marked by the message field set; the
  pre-registered P7/P8c refusal path ran exactly as registered.
- It refines issue #100: self-agreement is a firing-state quantity - 3/3
  byte- AND token-identical on rounds 42/44/46, 2/3 byte-identical (answer-word
  level) with 0/3 token-identical and one pair diverging on the answer on this
  firing; within-firing trace non-determinism is the new record.

## Disclosure

- `Executed` label: exploratory round, n = 11 panel items, single endpoint, single
  firing; the verdict is a surface readout for this firing and is not a claim about
  the class in general.
- The comparisons against rounds 42, 44 and 46 are cross-firing, not paired: same
  panel, same prompts, same gate values for the shared rows, different serving
  state; the per-item joins are within-round (mode A vs C vs D on the same items),
  never across rounds. The R-row bands are registered against the two archived
  27B-class firings, so a pass is a within-class band statement at n = 3 firings,
  not a class law.
- Endpoint values are read from the environment and are not written to any
  artifact; stored model text passes the inherited sanitizer; the serving build is
  identified only in the commit trailer per the public-only rule.
- Round 45 (2026-11-03 04:00) and round 47 (2026-11-04 04:00) left no outtake:
  both recorded "Model unavailable" runner-start errors on the assigned slot class
  (the flash-next-class low-bit build, absent at firing time) and died before the
  agent started. The dedup baseline for this round is the last round-summary
  comment that did land (round 46).
