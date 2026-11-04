# Round 46 (2026-11-04 02:50): the 27B-class re-fire of the output-policy knob plus the bounded single-pass knob - the ceiling re-confirms class-tied (2/11 truncations), the ban loses one net delivery on this class including a forward item (8/11 vs 9/11), and the bounded permission is the worst mode on delivery and cost (6/11, cost ratio 1.3089 over the ban, and it triggers enumeration on an item the ban delivered)

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is the
reproducible record: script, gate, prompts, raw responses, scores.

## Question

Does the round-44 flash-class knob result (the ceiling is class-tied; under the fixed 2048
output cap, delivery is an exact function of no-repetition obedience; disobedience
concentrates on the negative cross-check arm at depth) transfer to a 27B-class firing of
the same 11 archived E = 192 items - and does a knob that PERMITS bounded enumeration
replace the ban's failure mode without paying for it?

Motivation, from the record:

- round 23 (the flash-class firing, merged): the (k, E) frontier walk labelled S4 to S6
  (E = 192) `budget_limited`: all 11 E = 192 panel items ran to the 2048-token cap with
  the answer field silent - a surfacing failure, not a correctness failure.
- round 42 (a 27B-class firing of this same design, merged): the truncation record did
  not transfer to that class (mode A delivered 10/11); the no-repetition knob moved
  delivery (9/11, all correct) without reclaiming budget (ratio 1.1255), and that
  deployment supplied its trace in the field the inherited scoring channel does not read
  (0 of 30 dispatches with recorded reasoning chars; the record-only census saw 65,678
  trace chars), so the mechanism was unobservable there.
- round 44 (the flash-class firing, merged): completed the cross-class comparison. The
  ceiling is class-tied (8/11 truncations on the flash class vs 1/11 on the 27B class,
  same 11 prompts), delivery is an exact function of whether the no-repetition
  instruction is obeyed (7/7 obeying items deliver, 4/4 disobedient truncate), and
  disobedience concentrates on the negative cross-check (arm X) items at depth
  (obedience 2/2 at k = 8, 1/2 at k = 12, 0/3 at k = 16). Its next steps named the two
  follow-ups this round runs: the bounded single-pass knob (filed on #71) and the
  27B-class re-fire of the knob. This firing is both, on one 27B-class endpoint.

> Does a one-line surface instruction - `Without repeating any fact, answer with exactly
> one word: yes or no.` (the ban, mode C) and `You may state each fact at most once, then
> answer with exactly one word: yes or no.` (the bounded single-pass knob, mode D) - move
> the cost, delivery and trace structure of the 11 items the flash-class archive recorded
> as cap-truncated at 2048, when they are re-dispatched on a 27B-class endpoint?

The bounded knob is the discriminator round 44 asked for: if the ban's failure mode was
that it forbade the enumeration the cross-check verdicts require, mode D (enumeration
allowed exactly once per fact, no repeats) separates "the instruction forbids the needed
enumeration" from "depth collapses instruction-following". On the 27B class, where the
archived ceiling did not manifest (round 42: 1/11 truncations), mode D reads on cost,
trace structure and obedience rather than delivery rescue.

Published anchor for the elicitation frame: Wang and Zhou 2024 (arXiv 2402.10200, in the
archive, NeurIPS): reasoning is elicited by changes in the surface form of the output,
not created by it.

Literature position (this round's scan, 9 free-API calls, metadata-level: OpenAlex
title-and-abstract search plus one Crossref bibliographic query, abstracts not retrieved):
the nearest published line is token-budget intervention work on how much the model
thinks - Token-Budget-Aware LLM Reasoning (Findings of the ACL 2025, DOI
10.18653/v1/2025.findings-acl.1274) and BORA-BUDGET: Learning When to Think Under a
Token Budget (EMNLP 2026, DOI 10.18653/2026.emnlp-main.408) - plus the
budget-saturation preprints already cited in this record (the coupling tax, arXiv
2605.07686, named in the round-17/18 literature notes; budget-exhaustion
non-convergence, arXiv 2607.21433) and the repo-verified verbosity-control line of the
round-44 scan (arXiv 2407.19825, 2502.18600, 2412.21187, 2511.04108). The exact
phrases "bounded chain of thought" and "at most once" combined with chain of thought
returned zero OpenAlex hits: a one-line bounded-enumeration instruction, applied to
procedurally novel k-hop verification and measured as verdict surfacing before a fixed
output cap, is not measured by any record found in this scan, bounded to the queries run.

## Instrument

`policy_knob_probe.py` (stdlib only). The construction, structural audit, prompt
rendering, readout rules, scoring and attempt mechanics of the merged round-23
instrument (`research/nightly-2026-10-25-0205/frontier_walk_probe.py`) are loaded by
import, not re-implemented; the census transport and the decision machinery are carried
byte-identically from the round-44 instrument, so this firing differs from rounds 42 and
44 only in the serving class and the mode-D arm. The panel is certified digest-true
against the archived round-23 `raw.jsonl` (on main) before anything is dispatched: item
digest, prompt digest and the matched-pair invariants, fail-closed.

Panel: the 11 round-23 records whose archived attempt reached the 2048-token cap with
the answer field silent (finish_reason `length`, content answer null), taken in full -
2 items at S4 (k = 8), 4 at S5 (k = 12), 5 at S6 (k = 16), all at E = 192; 4 gold-yes,
7 gold-no; archived loose-fallback line 8/11 on the same items.

Modes (one line added to the question line; the rule sentence and every fact line stay
byte-identical, asserted on every prompt):

| mode | delta on the question line | calls |
|------|----------------------------|-------|
| A | none (the archived prompt) - replication control for the truncation record | 11 |
| C | `Without repeating any fact, answer with exactly one word: yes or no.` (the ban) | 11 |
| D | `You may state each fact at most once, then answer with exactly one word: yes or no.` (the bounded single-pass knob) | 11 |
| A2 | the mode-A prompt re-dispatched for three deterministic items, one per cell: the identical-prompt self-agreement control (#100) | 3 |
| health | the 256-token chat health call, doubled as the channel census | 1 |

37 of the 40-call cap, `max_tokens` 2048, `temperature` 0.0, concurrency 2. The
ordering knob (round-44 mode B) is not re-run: it failed on both prior firings (the
verdict never leads the answer field) and the 27B-class delivery question it served is
answered by mode A on this class.

The field census of round 40's declared extension runs on every dispatch (completion-
message field names plus the reasoning-supplying field, merge rule `reasoning_content`
if non-empty, else `reasoning`, else none; record-only, the scoring channel stays the
inherited byte-identical one). On this firing the census opens via `reasoning_content`
at the health call, so the text-derived predictions are measurable; if the dispatches
had instead supplied their trace in the `reasoning` field, the P7/P8c floors would have
refused the text-derived claims while the delivery and cost tiers stayed scored - the
round-42 outcome, pre-registered, not an ad hoc narrowing.

The round-42 and round-44 comparison constants are vendored in-file (`ROUND42_REFERENCE`,
`ROUND44_REFERENCE`) with their archive blob digests, extracted programmatically from the
merged archives in this session and re-verified against the archived raw records (the
round-44 obedience split recomputed at the declared 0.1 distractor-ratio threshold);
`--selftest` asserts their internal consistency and carries planted-slip controls for
both references, so both comparisons verify in the post-merge tree.

## Gate

Schema `round46-gate-v1`, frozen before any prompt was spent (blob
`f091f0b126ea35b772d652c76bf79bca280f09c9ee7a60d2cedc839df7da8631`). Prediction rows P1 to P7, P9, N1 and N2 are byte-equal to the
round-42 / round-44 gate, so the three firings score the shared rows on one table; P8
is re-registered for the new mode-D arm (the mode-B row is not run) and P8b / P8c are
new rows: P8 mode D delivers >= 7/11 (the bounded knob does not break delivery on the
class where the ceiling is absent), P8b zero wrong delivered in mode D, P8c the
mode-D text-existence floor (>= 9 records with nonzero recorded reasoning) gating the
mode-D text-derived claims. The mode-D cost and distractor-ratio figures are reported,
not scored (no prior on this class to register against). Decision table (mode C,
byte-equal to rounds 42/44): `policy_artifact` / `surfacing_only` / `policy_immovable`
/ `partial`; secondary mode-D table: `bounded_gain` (D delivers more than C, zero
wrong) / `bounded_parity` (equal, zero wrong) / `bounded_loss` (fewer, or a wrong
delivery).

## How to reproduce

```
python3 research/nightly-2026-11-04-0250/policy_knob_probe.py --selftest
python3 research/nightly-2026-11-04-0250/policy_knob_probe.py --gate --out /tmp/gate.json
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... \
python3 research/nightly-2026-11-04-0250/policy_knob_probe.py \
  --probe --out-dir research/nightly-2026-11-04-0250
python3 research/nightly-2026-11-04-0250/policy_knob_probe.py --analyze \
  --out-dir research/nightly-2026-11-04-0250
```

`--probe` refuses unless the panel certifies digest-true and the endpoint passes the
census health call. Endpoint values are read from the environment and never written to
an artifact; stored model text passes the inherited sanitizer.

## Results

Evidence label: `Executed` (exploratory, small n = 11 panel items, one endpoint, 36
dispatched records plus one health call, zero retries, zero transport errors). Frozen
gate `round46-gate-v1` (blob `f091f0b126ea35b772d652c76bf79bca280f09c9ee7a60d2cedc839df7da8631`),
verdict tier `surfacing_only`, mode-D tier `bounded_loss`. A post-run `--analyze`
reproduces the checks block written at dispatch time; `summary.json` additionally
carries the probe-time transport keys. The census opened via `reasoning_content` on
all 36 dispatches (trace 698 to 6210 chars, P7 and P8c floors 11/11 in every mode), so
the text-derived readouts below are accepted, not refused.

**The ceiling re-confirms class-tied from a third firing (P2/P2b fail as registered).**
Mode A (the byte-identical archived prompt) truncates 2/11 at the 2048 cap against the
archived 11/11, round 42's 1/11 on the 27B class and round 44's 8/11 on the flash
class; both truncations are arm X (S4 k = 8, S6 k = 16). The nine delivered items are
all correct (loose line 11/11, the unprovenanced readout of #94, reference only). The
flash-class replication rows were registered on the shared table and fail here exactly
as the 27B-class behavior predicts.

**The ban is cost-neutral here and loses one net delivery, including a forward item
(P3 holds at 8/11, P4 and P5 fail; P6 fails at 0.0103 against the 0.15 floor).**
Mode C delivers 8/11, all correct, zero wrong; cost ratio C over A is 1.0237. Paired
A vs C: A-only 2, C-only 1, McNemar p = 1.0 (not separable at n = 11). The two items
the ban loses are S5 forward (gold-yes; its C trace enumerates, dr 1.0, 4317 chars)
and S6 X (dr 0.7594); the one item it gains is S4 X, which mode A truncated at 2048
(dr 1.0) and mode C delivered in 405 tokens. Disobedience (dr above the declared 0.1
threshold) is no longer confined to the negative cross-check arm: one of the four
forward items disobeys under C, against 4/4 forward obedience in round 44. All three
mode-C truncations enumerate (dr 0.7594 to 1.0) and two of the eight delivered mode-C
items enumerate too (dr 0.1016, 0.1176): the round-44 exact bijection between
obedience and delivery does not transfer to this class. At the intermediate depth the
loss concentrates: at S5 (k = 12) mode A delivers 4/4, mode C 2/4.

**The bounded single-pass knob is `bounded_loss`: the worst mode on delivery and cost
(P8 fails at 6/11, P8b and P8c hold; the D cost figures are reported, not scored).**
Mode D delivers 6/11, all correct, truncates 5/11; cost ratio D over C is 1.3089 and
D over A 1.3399 - permitting bounded enumeration is the most expensive instruction in
this round, and its mean trace (4618 chars median) and mean distractor ratio (0.3777)
both sit above mode C's. Paired C vs D: C-only 3, D-only 1, p = 0.625. The per-item
structure answers the round-44 discriminator on this class: the permission triggers
enumeration on an item the ban delivered (S5 X: mode C delivered it in 536 tokens at
dr 0.0051, mode D enumerates at dr 0.8923 and truncates at 2048), while the ban loses
a forward item the bounded knob delivers (S5 F: mode C truncates at dr 1.0, mode D
delivers in 380 tokens at dr 0.0). One S6 X item truncates under all three modes (dr
0.9786 / 0.7594 / 0.0909); under mode D its trace is the longest of the round (6210
chars) with a low distractor ratio - the cap can also be consumed by non-enumerating
verification work, a failure mode the round-44 "no item delivered while enumerating,
no obeying item truncated" rule did not anticipate. The honest reading of the #71
discriminator on this firing: the ban's loss is not (only) that it forbids the needed
enumeration - the bounded permission does not recover it, and costs more. The
flash-class reading, where the ban's disobedience concentrated on the cross-check arm
at depth, stays open to a flash firing.

**Controls.** Self-agreement (N2, #100): 3/3 duplicate pairs byte-identical on content
plus reasoning (TARr 1.0) and token-identical too - round 42's completion-token
counter quirk does not recur on this deployment. The vendored round-42 and round-44
reference constants both pass their planted-slip consistency controls (violations
empty in `summary.json`). Transport: 104,689 prompt / 42,785 completion tokens,
~18.8 tokens/s single stream, wall 2298.2 s, 37 of the 40-call cap.

## What it changes

- It completes the knob family's third firing and its first trace-exposed 27B-class
  firing: the class-tied ceiling now reads 1/11 to 2/11 across two 27B deployments
  (rounds 42 and 46) against 8/11 to 11/11 on the flash class (rounds 23 and 44).
- It answers the bounded-knob discriminator (filed on #71) on the 27B class:
  negative. The bounded single-pass knob is `bounded_loss` on this firing - worst
  delivery (6/11) and worst cost (1.3089 over the ban) of the three modes - and it
  demonstrably triggers the enumeration it was meant to bound on one item. The
  flash-class arm of the discriminator (cross-check items at depth) remains the
  sharpest open knob question and needs a flash-class firing of modes A/C/D.
- It refines issue #108 with the third data point of the knob's state-dependent cost
  effect: 0.6756 (flash class, ceiling present, round 44), 1.1255 (27B class,
  ceiling-free, zero-trace-scoring deployment, round 42) and 1.0237 (27B class,
  ceiling-free, trace-exposed deployment, this round); the bounded permission adds
  1.3089 over the ban on the ceiling-free class.
- It adds to issue #105: the 27B class is now measured under both exposure settings
  (this firing exposes `reasoning_content` on 36/36 dispatches; round 42's deployment
  supplied the field the scoring channel does not read), and the obedience-to-delivery
  mapping is shown to be class-specific, not class-invariant.
- It answers the #100 self-agreement control at TARr 1.0 with token identity, and the
  #94 readout contract for the loose line (11/11 under mode A, unprovenanced,
  reference only).

## Disclosure

- `Executed` label: exploratory round, n = 11 items, single endpoint, single firing; the
  verdict is a surface readout for this firing and is not a claim about the class in
  general.
- The comparisons against rounds 42 and 44 are cross-firing, not paired: same panel,
  same prompts, same gate values for the shared rows, different serving class and
  deployment; the per-item joins are within-round (mode A vs C vs D on the same items),
  never across rounds.
- Endpoint values are read from the environment and are not written to any artifact;
  stored model text passes the inherited sanitizer; the serving build is identified only
  in the commit trailer per the public-only rule.
- Round 41 (flash class, 2026-11-01 04:00), round 43 (low-bit build, 2026-11-02 04:00)
  and round 45 (2026-11-03 04:00, runner model-unavailable failure at start) left no
  outtake; this firing is the second recorded 27B-class answer to the knob question,
  and the three-firing comparison (42 / 44 / 46) stays single-firing panels, not a
  repeated-measures design.
- The per-item obedience split is an exploratory post-hoc readout over the archived
  trace (distractor-mention ratio at the declared 0.1 threshold), not a scored
  prediction row.
