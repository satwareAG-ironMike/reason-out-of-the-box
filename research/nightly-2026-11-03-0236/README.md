# Round 44 (2026-11-03 02:36): the flash-class firing of the output-policy knob - the ceiling mostly reproduces on its own class (8/11 truncations) and delivery becomes an exact function of instruction obedience: every item whose trace stops enumerating surfaces its answer, and the four items that keep enumerating are all negative cross-check items

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is the
reproducible record: script, gate, prompts, raw responses, scores.

## Question

Is the flash-next class's load ceiling at E = 192 a property of the task (traversing and
surfacing the 192-cell items genuinely needs more than the 2048-token output budget), or of the
model's surface output policy (the class's enumerating trace style consumes the budget, so a
one-line instruction to stop repeating facts reclaims it)? And does the round-42 result on the
27B class (delivery moves, budget not reclaimed, no trace text to manipulate) transfer to the
class the archived ceiling came from?

Motivation, from the record:

- round 23 (the flash-class firing, merged): the (k, E) frontier walk labelled S4 to S6
  (E = 192) `budget_limited`; all 11 E = 192 panel items ran to the 2048-token cap with the
  answer field silent, 25 of 25 delivered answers correct - a surfacing failure, not a
  correctness failure, with the class still enumerating at 192 facts (distractor-mention
  ratio 0.51 to 0.64 cell means, 0.87 panel mean).
- round 42 (open PR #107, a 27B-class firing of this same design): the truncation record did
  not transfer to that class (mode A delivered 10/11); mode C delivered 9/11 all correct but
  cost slightly more than mode A (ratio 1.1255 against the 0.50 ceiling) and that deployment
  stored no trace text at all on its dispatches, so the mechanism (what the knob does to the
  enumeration) was unobservable there.
- round 41 (the flash-class firing of 2026-11-01 04:00) posed this question on this class and
  left no archived outtake; round 42 therefore closed with the cross-class knob comparison
  "deferred to a recorded flash-class firing". This round is that firing.

> Does a one-line surface instruction - `Without repeating any fact, answer with exactly one
> word: yes or no.` (no-repetition knob, mode C) and `Answer with exactly one word: yes or no
> before any reasoning, then you may add reasoning.` (ordering knob, mode B, cell S6 only) -
> move the delivery surface of the 11 items that the flash-class archive recorded as
> cap-truncated at 2048, when they are re-dispatched on a flash-next-class endpoint?

Published anchor for the elicitation frame: Wang and Zhou 2024 (arXiv 2402.10200, in the
archive, NeurIPS): reasoning is elicited by changes in the surface form of the output, not
created by it. The policy-knob question is the item-level, budget-bounded version of that
reading: does constraining the surface form reclaim the output budget the traversal needs to
surface its verdict?

Literature position (this round's scan, 8 free-API calls, abstract-level unless marked): the
nearest published line is verbosity-control prompting measured as an accuracy-versus-cost
trade-off, not as surfacing under a fixed output cap - Concise Thoughts (arXiv 2407.19825,
whose record carries the journal reference Information Sciences 2026, DOI
10.1016/j.ins.2026.123939; CCoT there is "Constrained-CoT"), Chain of Draft (arXiv
2502.18600, preprint), the overthinking line (arXiv 2412.21187, preprint) and a
prompting-side constraint suppression of overthinking (arXiv 2511.04108, preprint,
metadata-level). The seam this program occupies, bounded to the queries run: a format
instruction as an intervention on whether a verdict surfaces before the output budget runs
out, on procedurally novel items.

## Instrument

`policy_knob_probe.py` (stdlib only). The construction, structural audit, prompt rendering,
readout rules, scoring and attempt mechanics of the merged round-23 instrument
(`research/nightly-2026-10-25-0205/frontier_walk_probe.py`) are loaded by import, not
re-implemented; the census transport and the decision machinery are carried verbatim from the
round-42 instrument so the two firings differ only in the serving class. The panel is certified
digest-true against the archived round-23 `raw.jsonl` (on main) before anything is dispatched:
item digest, prompt digest and the matched-pair invariants, fail-closed.

Panel: the 11 round-23 records whose archived attempt reached the 2048-token cap with the
answer field silent (finish_reason `length`, content answer null), taken in full - 2 items at
S4 (k = 8), 4 at S5 (k = 12), 5 at S6 (k = 16), all at E = 192; 4 gold-yes, 7 gold-no;
archived loose-fallback line 8/11 on the same items.

Modes (one line added to the question line; the rule sentence and every fact line stay
byte-identical, asserted on every prompt):

| mode | delta on the question line | calls |
|------|----------------------------|-------|
| A | none (the archived prompt) - same-class replication control for the truncation record | 11 |
| C | `Without repeating any fact, answer with exactly one word: yes or no.` | 11 |
| B | `Answer with exactly one word: yes or no before any reasoning, then you may add reasoning.` (cell S6 only, exploratory) | 5 |
| A2 | the mode-A prompt re-dispatched for three deterministic items, one per cell: the identical-prompt self-agreement control (#100) | 3 |
| health | the 256-token chat health call, doubled as the channel census | 1 |

31 of the 40-call cap, `max_tokens` 2048, `temperature` 0.0, concurrency 2.

The field census of round 40's declared extension runs on every dispatch (completion-message
field names plus the reasoning-supplying field, merge rule `reasoning_content` if non-empty,
else `reasoning`, else none; record-only, the scoring channel stays the inherited
byte-identical one). On this firing the channel is supplied by `reasoning_content` - the field
the inherited scoring channel records - so unlike the round-42 deployment the trace text
itself is inside the archive and the text-derived predictions are measurable, not refused.

The round-42 comparison constants are vendored in-file (`ROUND42_REFERENCE`) with their
archive blob digests, transcribed programmatically from the round-42 `summary.json` and
re-verified against its `raw.jsonl` (delivered/truncated counts recomputed there, not read
from prose); `--selftest` asserts their internal consistency and carries planted-slip
controls, so the cross-class comparison verifies in the post-merge tree while PR #107 is
still open.

## Gate

Schema `round44-gate-v1`, frozen before any prompt was spent, prediction values byte-equal to
the round-42 gate so the two firings are scored on the same table (blob
`8bbbb25c4955751c0950a37d28c2f487fbfb7f80deac6500c90501bd45e4556c`). Predictions: P1 panel
digests reproduce the archive; P2 mode A truncates on >= 9/11 and P2b delivers <= 2/11 (the
same-class replication control, the prediction round 42 could not pass cross-class); P3 mode C
delivers >= 7/11; P4 mode C scores >= 9/11 strictly above the archived 8/11 loose line with
P4b zero wrong delivered; P5 mean completion ratio C over A <= 0.50 (budget re-claim); P6 the
no-repetition instruction trims trace enumeration (mode A minus mode C distractor-ratio drop
>= 0.15) behind the P7 text-existence floor (>= 9 mode-C records with nonzero recorded
reasoning); P8 mode B delivers >= 3/5; N1 census channel open on the health call; N2
duplicate-pair byte identity >= 2/3; P9 within the call cap. Decision table: `policy_artifact`
(C delivers >= 7/11, every delivered answer correct, strictly above the archived line) /
`surfacing_only` (C delivers but quality at or below the line) / `policy_immovable` (both
modes deliver <= 2/11) / `partial`.

## How to reproduce

```
python3 research/nightly-2026-11-03-0236/policy_knob_probe.py --selftest
python3 research/nightly-2026-11-03-0236/policy_knob_probe.py --gate --out /tmp/gate.json
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... \
python3 research/nightly-2026-11-03-0236/policy_knob_probe.py \
  --probe --out-dir research/nightly-2026-11-03-0236
python3 research/nightly-2026-11-03-0236/policy_knob_probe.py --analyze \
  --out-dir research/nightly-2026-11-03-0236
```

`--probe` refuses unless the panel certifies digest-true and the endpoint passes the census
health call. Endpoint values are read from the environment and never written to an artifact;
stored model text passes the inherited sanitizer.

## Results

Evidence label: `Executed` (exploratory, small n = 11 panel items, one endpoint, 30 dispatched
records plus one health call, zero retries, zero transport errors). Frozen gate
`round44-gate-v1` (blob `8bbbb25c4955751c0950a37d28c2f487fbfb7f80deac6500c90501bd45e4556c`),
verdict tier `surfacing_only`. A post-run `--analyze` reproduces the checks block written at
dispatch time; `summary.json` additionally carries the probe-time transport keys.

**The same-class replication control nearly holds and says the ceiling is class-tied.**
Mode A (the byte-identical archived prompt) truncates 8/11 at the 2048 cap against the
archived 11/11 - short of the P2 floor of 9 by one item (P2 and P2b fail at 8/11 and 3/11).
The three items that escaped are the shortest traversals of the panel (two S5 forward items
at 297 and 298 tokens and one S5 cross item at 1027), all three delivered correctly (mode A
delivered-correct 3/3, loose line 9/11). Set against round 42's 1/11 truncations on the 27B
class, the truncation phenotype is overwhelmingly a property of the flash class (8/11 vs
1/11), with a modest firing-level drift inside it (8/11 vs 11/11).

**The knob moves delivery, nested and exact, but not above the registered quality line.**
Mode C delivers 7/11 (P3 holds at the floor), a strict superset of mode A's three (A-only
gains: none; C gains: 4), with all seven delivered answers correct and zero wrong (P4b
holds). The strict delivered score 7/11 does not exceed the archived 8/11 loose line (P4
fails, `modeC_beats_archived_loose_line` false), nor beat the 7/11 constant-no baseline, so
the decision table lands on `surfacing_only`, not round 42's `policy_artifact`. Paired
delivery A vs C: b = 0, c = 4, exact McNemar p = 0.125 (directional, not separable at
n = 11). For reference only (the unprovenanced readout, #94): mode C's traces read 11/11
correct under the same loose fallback rule under which the archive reads 8/11; the registered
comparison stays strict-delivered vs the archived line.

**The mechanism, measurable for the first time in this program: delivery is an exact
function of instruction obedience, and obedience is polarity- and depth-dependent.** The
census channel is open on all 30 dispatches via `reasoning_content` (the field the inherited
scoring channel records, unlike the round-42 zero-trace deployment), the P7 text-existence
floor passes (11/11 mode-C records with recorded reasoning, median 2495 chars), and the P6
manipulation check passes: the mode A minus mode C distractor-ratio drop is 0.3467 (floor
0.15). Per item the split is exact: every one of the 7 mode-C items that obeys the
no-repetition instruction suppresses enumeration (trace distractor ratio 0.000 to 0.048) and
delivers its correct verdict in 262 to 931 tokens; every one of the 4 items that disobeys
keeps enumerating (ratio 0.936 to 1.000) and truncates at 2048. No item delivered while
enumerating; no obeying item truncated. The four disobedient items are all negative
cross-component (arm X) queries: all 4 forward (arm F) items obey at every depth, X
obedience is 2/2 at k = 8, 1/2 at k = 12 and 0/3 at k = 16. The residual ceiling concentrates
precisely where the verdict requires the exhaustive cross-check the instruction asked the
model to stop doing.

**The cost picture: partial re-claim on this firing, the opposite sign from round 42.** The
mean completion ratio C over A is 0.6756: above the P5 ceiling of 0.50 (P5 fails) because the
four disobedient items still burn the full budget, but a genuine re-claim on average, and a
large one on the movable subset (delivered mode-C items cost 262 to 931 tokens where the same
items cost up to 2048 under mode A). Round 42 measured 1.1255 on a firing whose ceiling had
already dissolved: the direction of the knob's cost effect depends on whether the ceiling is
present on the firing, which is itself a class-plus-firing property.

**The ordering knob is not followed (P8 fails).** Mode B delivers 2/5 (floor 3), both
forward items, none with the verdict leading the answer field (0/5 `answer_leading`): asked
to answer before reasoning, this deployment emits its enumeration in the reasoning channel
first anyway and the one-word content arrives, when it arrives, at the end.

**Controls.** Self-agreement (N2, #100): 3/3 duplicate pairs byte-identical on content plus
reasoning (TARr 1.0), and token-identical too on this deployment - the completion-token
counter quirk round 42 reported is a deployment property, not an endpoint-family law. The
vendored round-42 reference constants pass their planted-slip consistency controls
(`round42_reference.violations` empty). Transport: 87,190 prompt / 43,604 completion tokens,
about 43.5 tokens/s single stream, wall 1015.8 s, 31 of the 40-call cap.

## What it changes

- It completes the cross-class knob comparison round 42 deferred: the ceiling is class-tied
  (truncations 8/11 on the flash class vs 1/11 on the 27B class for the same 11 prompts), so
  the round-23 `budget_limited` label describes the flash class, and re-firing it reproduces
  at one item of slack.
- It refines issue #108: "the knob moves the delivery surface but does not re-claim the
  budget" was measured on a firing whose ceiling had dissolved; on a firing where the ceiling
  is present, the same one-line instruction re-claims about a third of the mean budget
  (0.6756) and all of the budget on the items it moves. The honest durable claim is that the
  knob's cost effect is state-dependent, not that the knob never re-claims.
- It adds the sharpest mechanism statement available at n = 11: under a fixed output cap,
  delivery is an exact function of whether the no-repetition instruction is obeyed
  (7/7 obeying items deliver, 4/4 disobedient items truncate), and disobedience concentrates
  on negative cross-check items at depth (0/3 at k = 16). The task/policy dichotomy is not a
  dichotomy: the policy moves the traversal wherever the traversal is feed-forward, and the
  residual ceiling sits exactly where the verdict requires the enumeration the policy forbids.
- It answers #105's exposure control for this firing (census open via `reasoning_content`),
  and shows the #100 self-agreement control passing at TARr 1.0 with token identity, which
  re-attributes round 42's counter quirk to its deployment.

## Disclosure

- `Executed` label: exploratory round, n = 11 items, single endpoint, single firing; the
  verdict is a surface readout for this firing and is not a claim about the class in general.
- The comparison against round 42 is cross-firing, not paired: same panel, same prompts,
  same gate values, different serving class and deployment; the per-item joins below are
  within-round (mode A vs mode C on the same items), never across rounds.
- Endpoint values are read from the environment and are not written to any artifact; stored
  model text passes the inherited sanitizer; the serving build is identified only in the
  commit trailer per the public-only rule.
- Round 41 (flash class, 2026-11-01 04:00) and round 43 (2026-11-02 04:00) left no outtake;
  this firing is the first recorded flash-class answer to the knob question and the
  round-42-vs-round-44 comparison stays two single-firing panels, not a repeated-measures
  design.
