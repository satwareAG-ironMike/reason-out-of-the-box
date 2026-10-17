# Nightly round 2026-10-17 04:00 (round 8)

Model probed and model that ran this session: Qwen3.8-Flash-Next class local endpoint
(quantized build, serving id `qwen3.8-flash-next-iq3_xxs`). Evidence label: **Executed** for
the construction, gate and procedure half (offline, deterministic, `--selftest` green, gate
recorded before any prompt was spent). The model-facing half **did not complete**: the probe
arm aborted on endpoint transport failure after 15 of 40 dispatched prompts, so this round
reports no depth measurement. Tracker: issue #65, round summary comment `2026-10-17 04:00`.
Related: #71 (depth ceiling procedure), #67 (shortcut leak and the 0.55 threshold), PR #69
(component-isomorphism repair, still unmerged), #5 (inference harness), #4 (generators).

## Question

At constant prompt load, does hop-chain accuracy turn over as hop depth `k` grows, and is any
turnover a depth cliff or a token-budget cliff? (issue #71 acceptance criteria 1, 2, 4, the
model-facing half.)

Picked because round 6 measured `k in {1..16}` with the shipped generator, whose fact count
`E = C * k` grows quadratically in `k`, so depth and prompt load moved together and no
turnover could appear at all, and because the 2026-10-17 02:00 firing (round 7) spent its
whole window on the CPU-only half of the same question and timed out with no public record of
its question. Holding `E` fixed and varying `k` alone is the only variant that yields a depth
axis the study can claim.

## Method

`ladder_load_depth.py` (stdlib only, `--selftest` green: 11 controls). It imports nothing from
`generators/` and re-implements the component-isomorphic construction, the BFS solver, the
structural verifier, the permutation-calibrated leak gate, the probe and the scorer from
scratch with its own entity-name pools, so a shared bug cannot hide a leak
([agent-execution.md](../../docs/agent-execution.md) section 5). The shipped corpus on `main`
is not used, and the PR #69 version of `generators/ladders.py` is not required to reproduce
this round.

Declared grid, fixed before any measurement, seed-frozen (`seed_base 20261017`):

| arm | construction | depths | items per depth | prompts |
|-----|--------------|--------|-----------------|---------|
| L | constant load: `E = 24` facts, `C = 24/k` disjoint paths | `k in {2,3,4,6,8,12}` | 6 (3 yes, 3 no) | 36 |
| X | grid extension: `C = 2` paths, `E = 2k` facts | `k in {16,24}` | 2 (1 yes, 1 no) | 4 |

40 prompts total (protocol cap), `max_tokens = 2048` (protocol cap), `temperature = 0.0`, one
sample per item, no exemplars, no chain of thought requested.

Selection rule fixed in advance: 40 candidates per cell are generated in seed order, every
candidate must pass the independent structural audit (every weak component is a directed path
of exactly `k` edges over `k+1` nodes, query is a path head and a path tail, stored answer
agrees with an unbounded BFS), and the first 3 yes and first 3 no surviving candidates are
taken. Nothing is chosen after seeing a response.

Gate: every cell must pass the permutation-calibrated leak gate before a single prompt is
spent, and the gate runs on the whole 40-candidate pool, never on the selected six (see
Finding 2). A failing cell is refused (fail closed).

Scoring is three-state: `correct`, `wrong`, `no_answer`. The parser is declared in advance as
the last standalone yes/no token in the `content` field; this endpoint puts its reasoning in a
separate field, so the answer is read from `content` only (the round 6 lesson).

Budget replay is offline and free: each completion is replayed against fixed budgets
`{256, 512, 1024, 2048}`.

## Result 1: the constant-load construction holds, and the calibrated gate passes all 8 cells

Measured from `gate.json` (40-item pool per cell, 400 permutations, family-wise `alpha = 0.05`):

| arm | k | C | facts E | prompt chars mean | battery rules | calibrated threshold | observed max | p | verdict |
|-----|---|---|---------|-------------------|---------------|----------------------|--------------|---|---------|
| L | 2 | 12 | 24 | 1110.0 | 100 | 0.700 | 0.575 | 0.983 | no leak |
| L | 3 | 8 | 24 | 1111.5 | 130 | 0.725 | 0.625 | 0.778 | no leak |
| L | 4 | 6 | 24 | 1111.0 | 130 | 0.725 | 0.675 | 0.289 | no leak |
| L | 6 | 4 | 24 | 1111.0 | 100 | 0.725 | 0.600 | 0.978 | no leak |
| L | 8 | 3 | 24 | 1111.3 | 100 | 0.800 | 0.750 | 0.584 | no leak |
| L | 12 | 2 | 24 | 1109.5 | 130 | 0.725 | 0.625 | 0.860 | no leak |
| X | 16 | 2 | 32 | 1414.0 | 74 | 0.700 | 0.575 | 1.000 | no leak |
| X | 24 | 2 | 48 | 2035.0 | 100 | 0.725 | 0.725 | 0.072 | no leak |

Arm L is genuinely constant-load: exactly 24 facts at every depth, prompt length 1109.5 to
1111.3 characters (0.16 % spread), so `k` varies from 2 to 12 while the prompt does not move.
Issue #71 criterion 2 (depth decoupled from prompt load) is therefore satisfiable in this
family, and the construction is public in this repository.

The `k = 24` cell is the closest call (`p = 0.072`, observed max 0.725 against a threshold of
0.725); it passes, but a second seed would be worth spending before treating long single-chain
items as leak-free.

## Finding 2: the gate has zero power at the item counts the study actually uses

The same battery and the same permutation null, run on the 6 selected items instead of the
40-candidate pool:

| k | rules at n=6 | threshold at n=6 | observed max at n=6 | rules at n=40 | threshold at n=40 |
|---|--------------|------------------|---------------------|---------------|-------------------|
| 2 | 74 | 1.000 | 0.833 | 100 | 0.700 |
| 3 | 100 | 1.000 | 0.833 | 130 | 0.725 |
| 4 | 74 | 1.000 | 0.833 | 130 | 0.725 |
| 6 | 74 | 1.000 | 0.833 | 100 | 0.725 |
| 8 | 34 | 1.000 | 0.833 | 100 | 0.800 |
| 12 | 100 | 1.000 | 0.833 | 130 | 0.725 |

At `n = 6` the null maximum is 1.000 in every cell: a battery of 34 to 100 traversal-free
rules (single features plus conjunctions of two features) fits a random 6-item labeling
perfectly, so no observation can ever exceed the threshold and the gate is vacuous. Detection
power measured directly with a planted shortcut (relabel the whole cell so the gold answer is
exactly `target name < source name`, a pure name-order leak with no traversal in it):

| pool | observed max | calibrated threshold | p | rules flagged | verdict |
|------|--------------|----------------------|---|---------------|---------|
| 6 items | 1.000 | 1.000 | 0.259 | 0 | no leak (missed) |
| 40 items | 1.000 | 0.750 | 0.0025 | 9 | leak |

Consequences for #71 criterion 4 and for #67:

1. A leak gate must run on a candidate pool of tens of items, not on the handful of items a
   cell sends to the endpoint. Gating the probe set is not a conservative choice, it is no
   test at all.
2. The fixed 0.55 threshold that round 3 already showed sits inside its own permutation null
   would have refused **all 8 cells of this grid**: every clean cell scores 0.575 to 0.750 on
   the 40-item pool, all above 0.55. The calibrated thresholds are 0.700 to 0.800 at `n = 40`
   and 1.000 at `n = 6`. The fixed threshold is not strict, it is miscalibrated, and it
   produces false leak verdicts on clean items.

## Finding 3: `d*` needs a trichotomy, and at 6 items per depth almost nothing is certifiable

The declared procedure (`place_dstar`) classifies each depth, in this order: `budget_limited`
(no-answer rate above 0.5, the answer was never reached so the depth says nothing about
depth), `maintained` (Wilson 95 % lower bound at or above `MAJORITY_FLOOR + MARGIN = 0.60`),
`collapsed` (Wilson 95 % upper bound below 0.60), `inconclusive` (neither bound crosses), and
`descriptive` (fewer than `MIN_CERTIFY = 6` items, reported but never used to set `d*`).
`d*` is the largest maintained arm-L depth below the first collapsed arm-L depth.

It is a trichotomy because at 6 items per depth the interval is that wide. Exact Wilson 95 %
intervals at `n = 6`, floor 0.60:

| correct at n=6 | accuracy | lower bound | upper bound | status |
|----------------|----------|-------------|-------------|--------|
| 0/6 | 0.00 | 0.000 | 0.390 | collapsed |
| 1/6 | 0.17 | 0.030 | 0.564 | collapsed |
| 2/6 | 0.33 | 0.097 | 0.700 | inconclusive |
| 3/6 | 0.50 | 0.188 | 0.812 | inconclusive |
| 4/6 | 0.67 | 0.300 | 0.903 | inconclusive |
| 5/6 | 0.83 | 0.437 | 0.970 | inconclusive |
| 6/6 | 1.00 | 0.610 | 1.000 | maintained |

Only a perfect depth certifies maintained accuracy, and only 1/6 or worse certifies collapse.
The smallest accuracy that can be certified as maintained, and the largest that can be
certified as collapsed, as a function of items per depth:

| items per depth | certifiable maintained (min accuracy) | certifiable collapsed (max accuracy) | inconclusive band |
|-----------------|----------------------------------------|--------------------------------------|-------------------|
| 4 | none | 0/4 = 0.00 | open |
| 6 | 6/6 = 1.00 | 1/6 = 0.17 | (0.17, 1.00) |
| 8 | 8/8 = 1.00 | 2/8 = 0.25 | (0.25, 1.00) |
| 12 | 11/12 = 0.92 | 3/12 = 0.25 | (0.25, 0.92) |
| 16 | 14/16 = 0.88 | 5/16 = 0.31 | (0.31, 0.88) |
| 20 | 17/20 = 0.85 | 7/20 = 0.35 | (0.35, 0.85) |
| 24 | 20/24 = 0.83 | 9/24 = 0.38 | (0.38, 0.83) |
| 30 | 24/30 = 0.80 | 12/30 = 0.40 | (0.40, 0.80) |
| 40 | 31/40 = 0.78 | 17/40 = 0.42 | (0.42, 0.78) |
| 60 | 44/60 = 0.73 | 28/60 = 0.47 | (0.47, 0.73) |

This is a hard budget statement for the confirmatory run and for the `d*+1..d*+4` band in
[generators/AGENTS.md](../../generators/AGENTS.md): certifying a maintained depth at 80 %
accuracy needs 30 items per depth, 73 % needs 60 items per depth. The 4 to 6 items per depth
used by the shipped grid and by rounds 4 to 7 can certify only perfection or collapse, so a
measured 5/6 at some depth is not evidence of anything, in either direction. Any `d*` claim
that the study publishes must state the item count per depth next to it.

## Finding 4: the probe arm failed on transport, and the failure is itself the record

`probe-attempt.log` is the surviving evidence. 40 prompts were dispatched at 4 workers after
the gate had passed all 8 cells; 15 completed, 12 of them with an empty completion
(`completion_tokens = 0`, no yes/no token anywhere in `content`), 3 answered correctly
(`k = 3` gold no with 416 tokens, `k = 3` gold no with 557 tokens, `k = 4` gold yes with 355
tokens). The run then hit its wall-clock limit and wrote no `raw.jsonl`, so the error class of
the 12 empty completions was never recorded. No depth conclusion is drawn from 3 items.

Two things are still measurable from those 3 completions:

1. The answer word sat in `content` while the reasoning text sat in the separate reasoning
   field, so the answer is emitted after the traversal, exactly as round 6 found. The
   character-proportional answer-position estimate that this round declared is **invalid for
   this response shape**: it reported the answer at 1 token when the completion was 355 to 557
   tokens long, because it measured the offset inside `content` against a `reasoning + content`
   total. For an endpoint that separates reasoning from content, the answer position is the
   completion length, and budget replay must use `completion_tokens` directly. Round 6's
   budget cliff (26 of 40 items lost at 256 tokens) is therefore a floor on the effect, not an
   artifact of a lucky estimate.
2. A 4-worker probe against the local pool is not a safe default. The 2026-10-17 02:00 firing
   timed out, and this firing returned empty completions for 12 of 15 attempts at depths where
   a working item needed only 355 to 557 tokens. Both signatures point at the shared endpoint
   pool under concurrent load, not at the items. The harness needs a health check immediately
   before the grid, sequential dispatch with a per-item deadline, a retry policy that counts
   empty completions as failures rather than as `no_answer` evidence, and a per-arm wall-clock
   budget so an arm that cannot run is abandoned early and reported, as rounds 7 and 8 both
   failed to do.

## Limits

- No depth measurement this round. The round is an Executed construction plus a documented
  abort, not a result about `d*`.
- One endpoint, quantized, training data undisclosed, and this agent session ran on the same
  class as the probed endpoint: not H1 evidence and not Condition-2 study data.
- The gate is calibrated against a 16-feature traversal-free battery (single features plus
  two-feature conjunctions). A leak that needs three features, or one that depends on entity
  identity across items, is outside the battery and would not be flagged at any `n`.
- The permutation null treats the labels as exchangeable, which is exact for the leak question
  but says nothing about item difficulty.
- Literature arm: 20 primary records on comparative transitive inference and human TI baselines
  were resolved with DOIs and peer-review status by this round's literature subagent (12-call
  cap, arXiv title search rate-limited, so no CLUTRR or RuleTaker human figures). None of them
  is in the archive yet, and the archive rule requires a Crossref-verification record per
  round, so they are filed as an issue rather than half-landed here. The archive's own central
  analogy line ([archive/INDEX.md](../../archive/INDEX.md) line 5) still has no evidence entry,
  and INDEX.md line 418 lists animal transitive inference as an exclusion.

## Reproduce

```
python3 research/nightly-2026-10-17-0400/ladder_load_depth.py --selftest
python3 research/nightly-2026-10-17-0400/ladder_load_depth.py --gate --out gate.json
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
  python3 research/nightly-2026-10-17-0400/ladder_load_depth.py --probe --max-workers 1
```

`--gate` writes the per-cell load profile and gate record; `--probe` refuses to send a single
prompt if any cell fails its gate. The probe needs a live endpoint in `NIGHTLY_*` and writes
`raw.jsonl` plus `summary.json`; endpoint host, port and credential are read from the
environment and stripped from everything the script writes (public-only rule). `run.log` stays
out of the repository.
