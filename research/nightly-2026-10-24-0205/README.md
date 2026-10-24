# Round 21 (2026-10-24 02:05): the constant-load depth arm, measured at last, under three readouts

Nightly firing 2026-10-24 02:05 (tracker [#65](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65),
round 21; slot 2 of the local pool, a flash-next-class local endpoint, sanitized description with
no endpoint value in any artifact). Serves issue [#71](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/71)
(criterion 2 and option 2: depth separated from prompt-length load, the binding next instrument)
and issue [#94](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/94) (score every
cell under a content-only arm beside the fallback arms). State: **Executed** (no independent second
implementation reproduced this round; disclosed per `docs/agent-execution.md`).

## Question

At a **fixed number of facts** (E = 24), does answerability or accuracy on the component-isomorphic
hop-chain family turn over as hop depth k grows through {2, 3, 4, 6, 8, 12} - and does each of the
three readouts (delivered answer, archived loose fallback, strict trace commitment) tell the same
story?

Picked for three reasons. First, every grid shipped so far (rounds 6, 9..19) couples prompt load
and depth: the generator's fact count grows with k, so the depth axis of the d\* procedure was never
measured free of the load axis; the round-17 measurement comment on #71 names option 2 ("fixed
facts, varying hops") as the binding next instrument. Second, this exact arm was designed once -
round 8 (2026-10-17 04:00, branch `research/nightly-2026-10-17-0400`, PR #75) - and its probe died
on endpoint transport failure after 15 of 40 dispatched prompts; the measurement has never
existed. Third, round 19 showed that on this endpoint class the recorded answerability of the
negative arms was reasoning-fallback rescue, so a constant-load curve read only through the
archived parser would repeat that loading; issue #94 asks for the harness to carry both arms, and
this round is the first run where the readout stack is declared before dispatch rather than
re-scored post-hoc.

## Method

`constant_load_depth.py` (stdlib only). Independence: it imports nothing from `generators/` and
re-implements the component-isomorphic construction (issue #67 repair, PR #69), the BFS solver, the
structural verifier and the permutation-calibrated leak gate from the round-8 script with its own
entity-name pools, so a shared bug cannot hide a leak. The shipped corpus on `main` is not used.

Declared grid, seed-frozen (`seed_base 20261024`): arm L constant load E = 24 facts,
k in {2, 3, 4, 6, 8, 12}, C = 24/k disjoint directed paths, 6 items per depth (3 yes, 3 no) =
36 prompts; `max_tokens = 2048`, `temperature = 0.0`, one sample per item, no exemplars, no chain
of thought requested. Health probe first, then two-phase dispatch (two sequential throughput cells,
then concurrency chosen from the measured rate), incremental fsync'd `raw.jsonl`, `--resume`
refusing unless every stored record carries the current gate hash. There is no cell pairing: this
construction shares no prompt with any archived round; comparisons to rounds 15..19 are
same-construction, cited by generator digest.

Readout stack (issue #94's harness request, declared before dispatch):

| Readout | Rule |
|---------|------|
| `content_only` | last standalone yes/no in the answer field - the delivered answer |
| `loose_fallback` | the archived rounds 10..18 convention: content, else last yes/no in the reasoning field |
| `delivered_or_strict` | content answer if present, else the strict trace commitment |

The strict commitment rule and the echo-phrase test are vendored **verbatim** from round 19
(`research/nightly-2026-10-23-0200/surfacing_budget_curve.py`, PR #93) and `--selftest` asserts
their documented behaviours, so the rule cannot drift silently from the round this grid must stay
comparable to (no cross-round file dependency in the post-merge tree). The vendored rule was also
re-run against the round-19 archive in this session before dispatch: it reproduces round 19's
headline control exactly - 13 of 36 records kept, all 13 agreeing with gold, and the reasoning-token
readout scoring 24/36, identical to the constant-"no" baseline (24 of 36 gold labels are "no").

## Gate (before any prompt was spent)

Gate `d39ceb84` (schema `round21-gate-v1`), selftest green. Corpus blob `5113bdabf99f`; every
candidate of every cell passed the independent structural audit (each weak component a directed
path of exactly k edges, query head-to-tail, stored answer equal to an unbounded BFS). The
permutation-calibrated leak battery (exact label-shuffle nulls, 400 permutations, family-wise
alpha 0.05) runs on the whole 40-item candidate pool per cell, never on the selected six: no cell
flagged (best blind-rule accuracy 0.70 against a calibrated threshold of 0.725; p >= 0.247).
Constant load is visible in the construction: mean prompt length 946.5..952.7 characters at every
depth (0.7% spread), E = 24 edges at all six depths.

Predictions declared in the gate: P1 prompt-token load constancy (max/min mean prompt tokens <=
1.12); P2 no depth turnover under `content_only` (no depth classified collapsed or budget-limited
by the round-8 trichotomy, Wilson 95% floor 0.60); P3 the token law flattens at constant load
(mean completion tokens at k = 12 <= 2x the mean at k = 2); P4a every `delivered_or_strict` answer
correct; P4b when the answer field is silent, the loose fallback token is "no" in at least 2/3 of
cells (the #94 skew replicated at constant load).

## Probe

36 prompts + 1 health probe = 38 endpoint calls in total (one further health call ran during the
gate-verified `--resume` that rebuilt `summary.json` after an analysis-side patch; see
`transport.json`), `max_tokens = 2048`, zero cell retries, one attempt per cell. Health ok in
1.7 s; two-phase dispatch: two sequential k = 2 cells (walls 4.3 s and 10.3 s, ~474 tok/s
estimate), then the remaining 34 at concurrency 1 (total measured wall 698.4 s; per-depth mean
walls 7.8..44.0 s). Every cell was answered in the answer field
(`answered_in_answer_field` 36 of 36); max completion 725 tokens (35% of the budget).

## Answer

**No turnover at constant load, and the delivered answer carries it.** All 36 cells answered in
the answer field and all 36 correct, at every depth k in {2, 3, 4, 6, 8, 12}, under all three
readouts (the loose and strict arms never had to be consulted: every content field carried the
answer). Round-8's trichotomy classifies every depth `maintained` (Wilson 95% lower bound 0.6097
for 6/6, above the 0.60 floor): **d\* >= 12 on (repaired construction, constant load E = 24,
flash-next class, budget 2048)** - no turnover within the declared grid, stated on the delivered
answer, not on trace rescue.

| k | n | correct | mean completion tok | mean prompt tok | status |
|---|---|---------|---------------------|-----------------|--------|
| 2 | 6 | 6 | 238.0 | 434.8 | maintained |
| 3 | 6 | 6 | 322.7 | 437.5 | maintained |
| 4 | 6 | 6 | 412.2 | 436.3 | maintained |
| 6 | 6 | 6 | 432.3 | 437.5 | maintained |
| 8 | 6 | 6 | 456.3 | 438.3 | maintained |
| 12 | 6 | 6 | 529.2 | 440.8 | maintained |

Predictions: **P1 pass** (mean prompt tokens max/min 1.0138; the tokenizer sees the constant
load). **P2 pass** (no collapsed, no budget-limited depth under `content_only`). **P3 fail**:
mean completion tokens at k = 12 are 2.2235x the k = 2 mean - the token law is *not* primarily
load-driven: +29.1 tokens per hop at constant prompt load, close to the ~33 tokens/hop measured
at coupled load (round 18), so what depth costs is generation, not (within this grid)
correctness. **P4a pass** (`delivered_or_strict` 36/36, trivially via content). **P4b vacuous**:
zero cells where the answer field was silent, so the #94 fallback skew had nothing to bite on;
the skew is a coupled-load phenomenon (k = 24 with ~264 facts), not a depth phenomenon at E = 24.

Against the coupled-load archive this relocates the ceiling. On this class at k = 24 (load
coupled, ~240-288 facts), round 19 measured 0 of 6 negative-arm cells delivering any answer at
budgets up to 2048. At constant E = 24, hop depth alone leaves the delivered answer perfect to
k = 12 - so the r19 surfacing failure is a joint prompt-load x budget effect, not depth per se,
and the answerability curve for #71 should be re-stated as: turnover needs the load axis. The
corrected budget replay (see `transport.json` for the estimate correction) quantifies how much
lower the delivery ladder sits at constant load: 4/36 answers would surface at an estimated
256-token cut, 29/36 at 512, 36/36 at 1024 (max measured completion 725).

Traversal signature at constant load: all 18 gold-yes items name the full queried chain in
ordered order (`coverage_ratio` = 1.0). Honesty limit: arm L's yes and no items are different
items (head-to-tail same path vs cross-component pairs), so this grid carries no per-item matched
pair; the traversal-vs-connectivity discrimination claims stay with the matched-pair family
(rounds 10, 11, 15, 16).

Fallback-token provenance (declared, though unused for scoring since content never went silent):
the last reasoning-field yes/no sits terminal in 33 of 36 records (median commit fraction 0.9916),
mid-trace in 3, and none is an instruction echo; terminal tokens agree with gold in 24 of 33.

## Adjacent literature (free scholarly APIs, abstract-level, 2026-10-24)

- Dziri et al., "Faith and Fate: Limits of Transformers on Compositionality", NeurIPS 2023
  (arXiv 2305.18654; already archived) - the depth-decay frame this k-sweep tests, with depth
  co-varying with surface form rather than isolated.
- Kohli et al., "Loop, Think, & Generalize: Implicit Reasoning in Recurrent-Depth Transformers",
  arXiv 2604.07822 (accepted COLM 2026 per the arXiv comment record) - closest structural
  analogue: depth extrapolation measured with input format held fixed across hop counts, the same
  load-decoupling move, from-scratch models; vanilla transformers fail depth extrapolation.
- Chen et al. (Anthropic), "Reasoning Models Don't Always Say What They Think", arXiv 2505.05410 -
  the companion to Turpin et al. 2023: CoT reveal rates often below 20% even for hints the model
  uses; bounds what hidden-trace readouts can detect, so low trace surfacing is a baseline, not
  depth evidence.
- Han et al., "The Quantization Trap: Breaking Linear Scaling Laws in Multi-Hop Reasoning",
  arXiv 2602.13595 (preprint) - names quantization and model scale as multi-hop moderators; a
  confound our quantized local endpoints share and cannot rule out per-endpoint.

All four IDs were confirmed against arXiv records in this session (batched id_list call after the
scan subagent's OpenAlex-first pass). A candidate for "degradation tracks input length, not
depth" could not be confirmed and is cited nowhere.

## Disclosure and limits

- Small n: 6 items per depth on one endpoint class; exploratory, labeled per
  `docs/agent-execution.md`. State **Executed**, not Reproduced or Validated.
- One quantized local deployment, undisclosed training data; not H1 evidence.
- No cell pairing to archived rounds (new construction); same-construction lineage cited by the
  gate corpus blob.
- Budget replay uses a character-proportional position estimate; it is approximate and reported as
  such (never a measured token count). The per-record `est_content_answer_tokens` field in
  `raw.jsonl` carries the pre-fix estimate (it omitted the reasoning-prefix offset); the committed
  analyze code recomputes the corrected estimate from the archived attempt fields, and
  `transport.json` discloses the difference. The probe run itself crashed AFTER all 36 cells were
  recorded (a results-store line missing from the ported two-phase transport); the measurement
  path was untouched, `--selftest` was re-run green and `summary.json` regenerated at the final
  HEAD under the gate-hash-guarded resume, zero extra prompts (issue #73's resume contract doing
  its job, per the lesson from round 19's interrupted firing).
- The 2026-10-23 04:00 firing (round 20) died without producing a record; this round's summary
  comment on #65 states the gap. Round numbering follows the runner count.

## Reproduce

```
python3 research/nightly-2026-10-24-0205/constant_load_depth.py --selftest
python3 research/nightly-2026-10-24-0205/constant_load_depth.py --gate
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
  python3 research/nightly-2026-10-24-0205/constant_load_depth.py --probe
python3 research/nightly-2026-10-24-0205/constant_load_depth.py --analyze
```

The script reads the endpoint from the environment and writes no endpoint value anywhere; stored
model text passes a sanitizer for URLs, IP addresses and absolute paths.
