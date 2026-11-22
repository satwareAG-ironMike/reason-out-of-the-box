# Round 81: ladders, judge-conformant, exploratory lane

## Question

Does the 27B-class base build (`Qwen3.8-27B class local endpoint`, self-hosted, no instruct, no RL,
no reasoning prompt in the dispatch) clear the ladders k-hop reachability family at a
depth beyond its measured trained depth, with one-word answers, at the frozen judge's
minimum exploratory n=40?

## Result

**Checkpoint status: `exploratory_only_model_class`** (the model's training corpus is not
public; the judge records that and does not score a claim - a Qwen-class build is
exploratory by definition, per pins.json).

| Cell | Level | n | ACC |
|------|-------|---|-----|
| calibration L1 | 1 | 40 | 1.00 |
| calibration L2 | 2 | 40 | 1.00 |
| calibration L4 | 4 | 40 | 0.82 |
| calibration L6 | 6 | 40 | 0.28 |
| calibration L8 | 8 | 40 | 0.05 |
| **novel band L6** | 6 | 40 | **0.35** |

d_hat = 4 (the largest level with ACC >= 0.80 for every level <= L on the calibration
pool; L4 = 0.82 holds, L6 = 0.28 breaks the run). The beyond-depth cell (L6, one grid
step past d_hat) reads ACC 0.35 with a Wilson 95% CI computed in score.json.

## Findings

- **Beyond-depth drop**: the build falls from 1.00 (L1-L2) to 0.82 (L4, mastery) to 0.28
  (L6 calibration) and 0.35 (L6 novel band). Competence does not hold one grid step past
  measured trained depth. This is a NEGATIVE-type exploratory signal (a clean negative is
  a valid result per the objective).
- **Delivery-contract finding**: an 8-token answer budget is not deliverable on this
  build. `Qwen3.8-27B class local endpoint` is a thinking-enabled build: its internal reasoning
  trace (in a separate `reasoning` channel, not in the prompt) consumes the token budget,
  so at max_tokens=8 every completion was empty (`finish_reason: length`). At
  max_tokens=256 the one-word answer lands in `content` with `finish_reason: stop` on the
  answered items. The 8-token first pass is retained in `.trash-8tok/` as the failure
  record.
- **Trace-exposure finding (issue #105 class)**: the response carries an internal
  reasoning trace in a separate channel. The prompt is judge-compliant (the frozen
  `build_prompt` carries no "think" instruction; `verify.py` selftest asserts that), but
  the response-side trace must be excluded from scoring - the judge scores `completion`
  only.
- **B3 partner arm**: not_evaluable (no pinned smaller same-family checkpoint for this
  build).
- **Novelty arm**: not_evaluable (no corpus backend for this build; the build's
  training corpus is not public).

## Distance moved

Closes the "no scorable exploratory round exists" distance item: this is the first round
built to the frozen judge's input contract (judge grid levels, judge seed policy, judge
frozen prompt builder) that a `score.py` run can score end-to-end. d_hat for this build
on the ladders family is now measured. The round does not advance the confirmatory
track (owner lane), which remains at 0 measurable beyond-depth cells.

## Reproducibility

- Pinned model: `Qwen3.8-27B class local endpoint` (self-hosted endpoint, exploratory-only class)
- Sampler: temperature 0.0, max_tokens 256 (see delivery-contract finding), one dispatch
  at a time
- Seeds: calibration seed base 20260101, novel-band seed base 20261121 (run-date fresh
  seed, never shipped); item i at level L uses `seed_base + 2_000_000*L + i` (judge
  contract)
- Serving build: recorded at scoring time
- `score.json` is the frozen scorer's checkpoint report, scored against the draft rule
  (PR #197 not yet merged/frozen); the labels are provisional until the owner merges the
  frozen instrument
