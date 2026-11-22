# Instrument

## Task family and pool

- Family `ladders` (`generators/ladders.py`, task type `hop_chain`): the item states a
  transitivity rule and a set of atomic `A precedes B` facts over fresh synthetic entity
  strings, and asks one yes/no question. Depth level `k` is the shortest directed path length
  between the queried pair; the grid is `1, 2, 4, 6, 8`, and `k = 1` is a lookup control and
  never depth evidence (`generators/AGENTS.md`).
- Pool: 8 items per level, 5 levels, 40 items. Seed policy: `seed_base` 20260101, the frozen
  `trained_depth.calibration_seed_base` - deliberately not the date-derived novel-item seed,
  because this pool is a calibration pool, not a novel band.
- Pre-gate `V3`: the #67 permutation-calibrated leak gate (`generators/audit_ladder_leaks.py
  --generated --count 8 --seed-base 20260101`) runs on exactly this pool. Recorded in
  `leak_gate.json`. The gate's own report at this `n` matters as much as its verdict - see the
  README.

## Prompt builder

The frozen judge builds every prompt (`evaluation/frozen/verify.py::build_prompt`, template
`hop_chain_yes_no_v1`): the rule sentence, the facts, one question, and "Answer with exactly
one word, yes or no." No chain-of-thought scaffold, no hint tokens, zero-shot, the same
template for all 40 items (study-design Condition 2). The built text and its sha256 are in
`prompts/calibration.jsonl`; the builder asserts no gold token survives in any built prompt
(pre-gate `V4`).

## Sampler, frozen before dispatch (`sampler.json`)

| Setting | Value |
|---------|-------|
| temperature | 0.0 |
| max_tokens | 512 |
| request seed | 20261121 |
| dispatch order | round-robin over levels, so endpoint contention cannot be read as depth (issue #141) |
| transport | sequential, one request in flight (issues #73, #141), 2 retries on transport error only |
| request timeout | 150 s, dispatch budget 1500 s |
| build pin | `model_digest` = sha256(model id)[:16], pinned in `gate.json` and re-checked after dispatch |

No pre-dispatch rate measurement was taken, so the standing round-61 rule (keep a
`measure.json` when the dispatch plan was selected by a frozen rate measurement) does not bind
this round: the prompt count is fixed by the frozen `calibration_n` of 40, not chosen from a
rate. The cost of that is honest and visible - the wall-clock budget is an estimate taken from
the lane's published throughput, so a starved host shows up as `stopped_early` in
`raw_meta.json` rather than being planned around.

## Scoring

- Judge: `evaluation/frozen/verify.py` at commit `634d7fa`, pinned by bytes
  (`sha256 40b6a6eb...`); the runner refuses any other bytes. That path is not on `main` yet
  (issue #194, PR #197 is owner-merge only), so the round supplies `FROZEN_JUDGE_DIR` pointing
  at a checkout of that commit and nothing in this directory copies the judge into the repo.
- Correctness is the visible answer field against the judge's own independent BFS solver, never
  the trace (issue #94). The judge re-derives every gold; it does not trust the generator's
  `answer` field.
- Delivery census: the frozen `DELIVERY_STATES`. A completion exhausted at the cap with nothing
  judgeable is `not_delivered`, not a wrong answer (issue #145); `censored_at_cap` is also
  counted per level from `finish_reason`. Every record carries the message-field census
  (`message_fields`, `trace_field`, `trace_chars`, issue #105).
- Intent to treat: every dispatched item stays in `n`. Accuracy per level is reported with the
  Wilson 95% score interval and the pool's majority-class accuracy for that level.
- `d_hat` is computed by the frozen definition in `rule.json`, including the `no_mastery_case`
  (no level at 0.80 means `d_hat = 0` and the accuracy floor is reported).

## Reproduce

```sh
# 1. a checkout of the frozen judge, PR #197's head
FROZEN_JUDGE_DIR=/path/to/checkout/evaluation/frozen
# 2. endpoint from the environment only
export NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=...
python3 calibrate.py --selftest    # 26 checks, no prompt dispatched
python3 calibrate.py --freeze      # tasks, prompts, sampler, gate, leak gate
python3 calibrate.py --run         # 40 dispatches, resume-safe on item_key
python3 calibrate.py --rescore     # raw.jsonl -> summary.json, never re-dispatches
```

`--run` writes `raw.jsonl` incrementally and refuses to dispatch at all when
`NIGHTLY_MODEL_ID` is empty (issue #200: an identity-empty slot is not a build change).
