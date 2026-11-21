# Round 80: ladders k-hop reachability, fresh seed (exploratory)

## Hypothesis paragraph (the selection rule, one paragraph)

The ledger's two rounds both measured the cross-ask family. The decision rule's
beyond-depth gate (a cell whose level sits 1-4 steps past the model's own calibration
depth `d_hat`) has no ladders data at all: the confirmatory floor needs 2 beyond-depth
cells across 2 families, and the families are ladders, digit-matrices, and trap. A
fresh-seed ladders depth scan is the cheapest way to add a second family to the
pool and to test whether the 27B-class build answers k-hop reachability correctly at
depths it has never seen before. The round would be worthless if it produced no
delivered one-word answer at any level; the kill condition is 0 of 8 probes delivered.

## Instrument

- Task family: ladders k-hop reachability, `generators/ladders.py`, one item per level.
- Levels: 4, 8, 12, 16, 20, 32, 48, 64.
- Seed: 20261121 (a seed the generator has never shipped; `FRESH_SEED`).
- Prompt: the fact list, the query, and "Answer exactly one word: yes or no." No
  chain-of-thought scaffold, no few-shot reasoner trace, no "think step by step".
- Sampler: `temperature 0.0`, `max_tokens 8`.
- Budget: 8 prompts, one dispatch at a time (issue #73, #141).

## Gate (frozen before dispatch, issue #137 shape)

```
V0_solver_certified   the generator's independent solver certifies the gold at every level
P0_non_reasoning_prompt the prompt is non-reasoning and names the answer format
P1_fresh_seed         the seed is 20261121, never shipped; the item manifest sha256 is recorded
P2_delivery           every probe either delivered a one-word answer or shipped not_delivered
```

## Run

- Endpoint: `qwen38-flash-next` (public name only, self-hosted, no metered key).
- `--selftest`: 6 of 6 checks green.
- 8 records dispatched sequentially.
- `--rescore`: exits 0, `summary.json` sha256 `f689dfb92089`.
- L4 and L12: judged, both correct (2 of 2).
- L8, L16, L20, L32, L48, L64: censored at the 512-token cap; the model traces
  instead of emitting the one-word answer. 0 of 6 delivered a one-word answer
  inside the cap.

## Finding (registered, not a failure of the round)

The one-word non-reasoning answer contract (P0) is violated at depth 8 and up on
this build: the model spends the full cap on a trace and never emits a terminal
yes/no. This is the same class of finding as the round-75 `context_length_unmatched`
downgrade: the delivery contract and the model's actual decoding behavior do not
match. The round ships the censored result, not a competence verdict. No beyond-depth
cell is produced; the confirmatory track remains blocked by issue #196.

## Scoring

Exploratory only. The frozen judge (`evaluation/frozen/`, issue #194) scores these
raw records at the first PR merge; no confirmatory cell is produced (issue #196).
