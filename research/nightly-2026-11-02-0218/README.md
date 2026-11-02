# Round 42 (2026-11-02 02:18): does a one-line output-policy instruction move the 27B class's load ceiling, or was the ceiling already gone on this firing?

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is the
reproducible record: script, gate, prompts, raw responses, scores.

## Question

Is the 27B class's load ceiling a property of the task (traversing and surfacing the E = 192
cells genuinely needs more than the 2048-token output budget), or of the model's surface output
policy (the class's enumerating trace style consumes the budget, so a one-line instruction to stop
repeating facts reclaims it)?

Motivation, from the record:

- round 23 (the flash-class firing, merged on main): the (k, E) frontier walk labelled S4 to S6
  (E = 192) `budget_limited`; 11 of 36 items ran to the 2048-token cap with the answer field
  silent. That label is a statement about the flash class's deployment.
- round 37 (a same-class retest on a 27B-class pool endpoint, open PR #102): the (16, 96)
  turnover "does not repeat on its own class" - the verdict surface, delivery pattern and
  per-prompt cost law move between firings, while the answers and the non-enumerating style hold.
- round 40 (a 27B-class firing of this pool slot, open PR #104): the deployment exposed a full
  reasoning channel (631 to 4,233 trace characters) and truncated the lighter (8, 128) arm X at
  2048; the round's own limit note said the class's load ceiling "cannot be quoted from any
  2048-budget firing while this serving build is in the pool".
- round 41 (the flash-class firing of 2026-11-01 04:00) posed the output-policy question on its
  own class (the same 11 items, one-line knobs) but left no archived outtake: no branch, no
  record, no tracker comment. The policy-knob question therefore has no recorded answer on the
  record for either class.

Chosen because it answers an open item in the program's own frontier line (#71: the budget
control of the d* statements; #105: control the exposure setting across firings; #100: the
missing identical-prompt self-agreement control) at zero panel cost: the 11 items are the
digest-pinned round-23 panel, and the knob texts are the one-line deltas round 41 declared.

> Does a one-line surface instruction - `Without repeating any fact, answer with exactly one
> word: yes or no.` (no-repetition knob, mode C) and `Answer with exactly one word: yes or no
> before any reasoning, then you may add reasoning.` (ordering knob, mode B, cell S6 only) -
> move the delivery surface of the 11 items that the flash-class archive recorded as
> cap-truncated at 2048, when they are re-dispatched on a 27B-class endpoint?

Published anchor for the elicitation frame: Wang and Zhou 2024 (arXiv 2402.10200, in the
archive, NeurIPS): reasoning is elicited by changes in the surface form of the output, not
created by it. The policy-knob question is the item-level, budget-bounded version of that
reading: does constraining the surface form reclaim the output budget the traversal needs to
surface its verdict?

## Instrument

`policy_knob_probe.py` (stdlib only). The construction, structural audit, prompt rendering,
readout rules, scoring and attempt mechanics of the merged round-23 instrument
(`research/nightly-2026-10-25-0205/frontier_walk_probe.py`) are loaded by import, not
re-implemented. The panel is certified digest-true against the archived round-23 `raw.jsonl`
(on main) before anything is dispatched: item digest, prompt digest and the matched-pair
invariants, fail-closed.

Panel: the 11 round-23 records whose archived attempt reached the 2048-token cap with the
answer field silent (finish_reason `length`, content answer null), taken in full - 2 items at
S4 (k = 8), 4 at S5 (k = 12), 5 at S6 (k = 16), all at E = 192; 4 gold-yes, 7 gold-no;
archived loose-fallback line 8/11 on the same items.

Modes (one line added to the question line; the rule sentence and every fact line stay
byte-identical, asserted on every prompt):

| mode | delta on the question line | calls |
|------|----------------------------|-------|
| A | none (the archived prompt) - replication control for the truncation record | 11 |
| C | `Without repeating any fact, answer with exactly one word: yes or no.` | 11 |
| B | `Answer with exactly one word: yes or no before any reasoning, then you may add reasoning.` (cell S6 only, exploratory) | 5 |
| A2 | the mode-A prompt re-dispatched for three deterministic items, one per cell: the identical-prompt self-agreement control (#100) | 3 |
| health | the 256-token chat health call, doubled as the channel census | 1 |

31 of the 40-call cap, `max_tokens` 2048, `temperature` 0.0, concurrency 2.

Declared extension of the inherited readout stack (record-only; the scoring channel stays the
inherited byte-identical one): the **field census** on every dispatch - the completion
message's field names plus the reasoning-supplying field, merge rule `reasoning_content` if
non-empty, else `reasoning`, else none (the extension round 40 declared on its panel). The
census transport's request body is byte-identical to the inherited one (the drift control is
asserted in `--selftest`); when the channel is closed on the health call (N1), every
trace-derived claim in this round is refused, and the round reports at answer level.

The three duplicate dispatches (A2) are the same-prompt self-agreement control that issue
#100 asks for: per pair, byte identity of content + reasoning and completion-token identity;
pooled TARr over the three pairs, pre-registered floor 2 of 3.

## Gate

Schema `round42-gate-v1`, frozen before any prompt was spent. Predictions and the decision
table (check keys as frozen in the gate blob): P2 mode A truncates on >= 9/11 and delivers
<= 2/11 (the replication control for the archived record); P3 mode C delivers >= 7/11; P4 mode
C scores >= 9/11 strictly above the archived 8/11 loose line, zero wrong delivered; P5 mean
completion ratio C/A <= 0.50; P6 the no-repetition instruction trims enumeration
(distractor-ratio drop >= 0.15) with the text-existence floor 9 (P7); P8 mode B delivers
>= 3/5 on S6; N1 the census channel is open on the health call; N2 duplicate-pair byte
identity >= 2/3; P9 within cap. Decision
table: `policy_artifact` (C delivers >= 7/11, every delivered answer correct, strictly above
the archived line) / `surfacing_only` (C delivers but quality at or below the line) /
`policy_immovable` (both modes deliver <= 2/11) / `partial`.

## How to reproduce

```
python3 research/nightly-2026-11-02-0218/policy_knob_probe.py --selftest
python3 research/nightly-2026-11-02-0218/policy_knob_probe.py --gate --out /tmp/gate.json
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... \
python3 research/nightly-2026-11-02-0218/policy_knob_probe.py \
  --probe --out-dir research/nightly-2026-11-02-0218
python3 research/nightly-2026-11-02-0218/policy_knob_probe.py --analyze \
  --out-dir research/nightly-2026-11-02-0218
```

`--probe` refuses unless the panel certifies digest-true and the endpoint passes the census
health call. Endpoint values are read from the environment and never written to an artifact;
stored model text passes the inherited sanitizer.

## Results

Evidence label: `Executed` (exploratory, small n = 11 panel items, one endpoint, 30 dispatched
records plus one health call). Frozen gate `round42-gate-v1` (blob
`f67c05358e72b3e5f0e46f0b53707f7e31ff9535d9453b9c1c1a9af9686e6735`), verdict tier
`policy_artifact`.

The lead result is that the replication control fails, and that failure is the round's main
finding. The round-23 archive recorded all 11 of these items as cap-truncated (finish_reason
`length`, answer field silent, 2048 completion tokens). Re-dispatched on the 27B-class pool
endpoint, mode A (the byte-identical archived prompt, no knob) truncates on only 1/11 and
delivers 10/11, scoring 10/11 on the loose fallback line. The archived truncation phenotype does
not transfer to this firing: the same items, same prompt, same 2048 budget now surface their
answers. P2 (A truncates >= 9/11) and P2b (A delivers <= 2/11) both fail for this reason.

Mode C (the no-repetition one-line knob, `Without repeating any fact, answer with exactly one
word: yes or no.`) delivers 9/11 and is correct on all 9 delivered answers (zero wrong), i.e.
9/11 overall, strictly above the archived loose line of 8/11 and above the constant-no (7/11)
and constant-yes (4/11) baselines. P3, P4 and P4b hold.

The knob is not a cheap one. The mean completion ratio C over A is 1.1255, above the 0.50
ceiling, so P5 fails: the no-repetition instruction does not shrink the output budget on this
firing, it costs slightly more. And because the one-word constraint suppresses the surface text,
the text-existence floor (mean content chars >= 9) is not met (mode C mean is 3.6), so P6 and the
P7 text-existence check fail even though the distractor-ratio drop from the archived line to mode
C is large (0.8678, above the 0.15 floor). The knob moves the delivery surface but at the cost
of the text channel and without re-claiming budget.

Mode B (the ordering knob, cell S6 only) delivers 3/5, so P8 holds.

The self-agreement control (#100) passes: all three duplicate-pair records are byte-identical on
content plus reasoning, N2 TARr 1.0 (floor 2/3). Note the counter quirk is recorded: the
completion-token counters of a pair can differ (for instance 582 versus 394 on the same content)
while the text is byte-identical, so byte identity of the answer text, not the token counter, is
the self-agreement readout on this endpoint.

The census (N1) channel is open on the health call, with the trace supplied by the `reasoning`
field (82 characters on the health call), not `reasoning_content`; census-derived claims are
accepted. The per-record field census is recorded on all 30 dispatches.

Transport: 30 dispatches, 87,190 prompt tokens, 26,123 completion tokens, about 50.3 single-stream
tokens per second, within the 40-call cap (P9).

## What it changes

- It re-opens the ceiling question on the 27B-class endpoint: the round-23 cap-truncation record
  does not reproduce on the class that the archive's own limit note said could not quote a load
  ceiling from. The load ceiling is shown to be a surface / output-policy artifact of the archived
  (flash-class, round-23) firing, not a fixed property of the 11-item panel, when the same panel
  is re-dispatched with an unchanged prompt.
- It supplies the first recorded output-policy-knob measurement for the 27B class: a one-line
  no-repetition instruction moves the delivery surface (delivers 9/11, all correct) but does not
  shrink the token budget (C over A = 1.1255) and collapses the text channel. The knob is a
  surface move, not a cost win.
- It answers the exposure-setting control (#105) for this firing: the census channel is open and
  the trace is supplied by the `reasoning` field, so future rounds on this pool slot can be
  matched on the exposure setting.
- It closes the self-agreement control gap (#100) for one class and one firing: byte-identical
  duplicate dispatches at 1.0 TARr, with the token-counter quirk recorded so a later round does
  not misread it as disagreement.
- It records that round 41 (flash-class, 2026-11-01 04:00) left no outtake: no branch, no
  record, no tracker comment. The flash-class knob question therefore still has no archived
  answer, and the cross-class knob comparison stays deferred to a recorded flash-class firing.

## Disclosure

- `Executed` label: exploratory round, n = 11 items, single endpoint, small sample; the verdict
  is a surface readout for this firing and is not a claim about the class in general.
- The failed replication control (P2, P2b) is reported, not rationalized away: the archived
  truncation record does not transfer to this firing, and that non-transfer is the round's result
  rather than an error to be corrected.
- Endpoint values are read from the environment and are not written to any artifact; stored model
  text passes the inherited sanitizer; the serving build is identified only in the commit trailer
  per the public-only rule.
- Round 41 (flash class) contributed no record to this comparison; the knob result here is
  single-class and single-firing until a recorded flash-class firing exists.
