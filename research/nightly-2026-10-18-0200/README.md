# Nightly round 2026-10-18 02:00 (round 9)

Model probed: a local 27B-class NVFP4-quantized endpoint with an MTP draft layer and a
separated-reasoning response shape (`reasoning_content` separate from `content`), public
label `Qwen3.8-27B-NVFP4-MTP-HIGH`. The orchestration session ran on a different local
model (Unsloth UD Q4_K_XL 27B build). Evidence label: **Executed** for the construction,
gate, probe, and procedure halves; no independent rerun was done, so nothing is labelled
Reproduced or Validated. Tracker: issue #65, round summary comment `2026-10-18 02:00`.
Related: #71 (depth ceiling procedure), #73 (probe transport hardening, acceptance met),
#74 (comparative-TI archive round, literature verification posted), PR #69
(component-isomorphism repair, still unmerged), #4 (generators).

## Question

At constant prompt load, does hop-chain accuracy turn over as hop depth `k` grows, and is
any turnover a depth cliff or a token-budget cliff? (issue #71 acceptance criteria 1, 2,
4, the model-facing half.) Secondary: does the #73-hardened probe dispatch complete a full
40-item grid on a healthy fast endpoint, with transport failures classified as such and
never as `no_answer`?

Picked because round 8 ran this exact grid on a slow endpoint and the probe arm failed on
transport (12 of 15 surviving completions empty, wall-clock exhausted, no `raw.jsonl`).
The same item stream is re-run here on the faster assigned endpoint with the #73
hardening applied, so round 8's apparatus is now measured under conditions where the arm
can actually finish.

## Method

`const_load_depth.py` (stdlib only, `--selftest` green: 15 controls including the #73
empty-completion and deadline negative controls, a planted-leak control, a planted
negative, seed determinism, and a stream-identity control against round 8's published
per-cell gate record). It imports nothing from `generators/` and re-implements the
component-isomorphic construction, the BFS solver, the structural verifier, the
permutation-calibrated leak gate, the probe and the scorer from scratch with its own
entity-name pools, so a shared bug cannot hide a leak
([agent-execution.md](../../docs/agent-execution.md) section 5). The item stream is
byte-identical to round 8's: same entity pools, same RNG call sequence, same selection
rule, same `seed_base 20261017`, so round 9 cross-checks round 8's published gate record
cell by cell (selftest control 4) and its three surviving completions (Finding 3).

Declared grid, fixed before any measurement, seed-frozen (`seed_base 20261017`):

| arm | construction | depths | items per depth | prompts |
|-----|--------------|--------|-----------------|---------|
| L | constant load: `E = 24` facts, `C = 24/k` disjoint paths | `k in {2,3,4,6,8,12}` | 6 (3 yes, 3 no) | 36 |
| X | grid extension: `C = 2` paths, `E = 2k` facts | `k in {16,24}` | 2 (1 yes, 1 no) | 4 |

40 prompts total (protocol cap), `max_tokens = 2048` (protocol cap), `temperature = 0.0`,
one sample per item, no exemplars, no chain of thought requested.

Selection rule fixed in advance: 40 candidates per cell are generated in seed order, every
candidate must pass the independent structural audit (every weak component is a directed
path of exactly `k` edges over `k+1` nodes, query is a path head and a path tail, stored
answer agrees with an unbounded BFS), and the first 3 yes and first 3 no surviving
candidates are taken. Nothing is chosen after seeing a response.

#73 hardening, all declared before the grid: pre-grid health check (must complete before
any grid prompt), sequential dispatch (no worker pool), per-item deadline 600 s with one
retry, incremental fsynced raw archive after every item, empty completions and deadline
timeouts classified `transport_failure` with a recorded `error_class` and never
`no_answer`, and a per-arm wall-clock budget of 3600 s so an arm that cannot run is
abandoned early and reported as such.

Gate: every cell must pass the permutation-calibrated leak gate before a single prompt is
spent, on the whole 40-candidate pool (round 8 Finding 2), fail closed. Recorded to
`gate.json` before dispatch. All 8 cells verdict `no leak at family-wise alpha`; the
cell-level values (battery rules, calibrated threshold, observed max, p, gold-yes count,
prompt-character mean) are byte-identical to round 8's published `gate.json`, so the two
rounds measure the same stream.

Scoring is three-state plus a transport class: `correct`, `wrong`, `no_answer`,
`transport_failure`. This endpoint separates reasoning from the answer, so the parser
reads the last standalone yes/no token from `content` only, and the answer position for
budget replay is `completion_tokens` directly (round 8's invalid
`est_answer_tokens = 1` estimate does not apply to this response shape).

Budget replay is offline and free: each completion is replayed against fixed budgets
`{256, 512, 1024, 2048}` on that position.

`d*` placement is the named trichotomy from round 8: `budget_limited`, `maintained`
(Wilson 95 % lower bound at or above 0.60, at least 6 items), `collapsed` (Wilson 95 %
upper bound below 0.60, at least 6 items), `inconclusive`, and `descriptive` (fewer than
6 items, reported but never used to set `d*`).

## Result 1: the probe completed, and the #73 hardening held

40 of 40 dispatched, 40 of 40 answered, 40 of 40 correct, 0 wrong, 0 no-answer,
0 transport failures, 40 of 40 on the first attempt, all `finish_reason = stop`.
Latency 7.4 s to 118.7 s per item (mean 33.2 s, median 22.0 s); the pre-grid health
check took 2.2 s. The empty-completion and deadline paths that failed round 8 did not
fire; they remain covered by selftest controls 10 and 11. The raw archive was written
incrementally, so even a mid-arm abort would leave a per-item record with its error
class, which round 8 lacked.

## Result 2: no turnover to `k = 12` at constant load; `d* >= 12`

| arm | k | n | correct | wrong | no-answer | transport failures | mean completion tokens | mean latency s | status |
|-----|---|---|---------|-------|-----------|--------------------|------------------------|----------------|--------|
| L | 2 | 6 | 6 | 0 | 0 | 0 | 379.5 | 30.5 | maintained |
| L | 3 | 6 | 6 | 0 | 0 | 0 | 314.2 | 30.4 | maintained |
| L | 4 | 6 | 6 | 0 | 0 | 0 | 410.7 | 34.9 | maintained |
| L | 6 | 6 | 6 | 0 | 0 | 0 | 444.3 | 26.5 | maintained |
| L | 8 | 6 | 6 | 0 | 0 | 0 | 388.2 | 32.5 | maintained |
| L | 12 | 6 | 6 | 0 | 0 | 0 | 552.5 | 51.6 | maintained |
| X | 16 | 2 | 2 | 0 | 0 | 0 | 1055.0 | 31.9 | descriptive |
| X | 24 | 2 | 2 | 0 | 0 | 0 | 922.5 | 12.3 | descriptive |

Every arm-L depth certifies `maintained` (Wilson 95 % lower bound 0.6097 at `n = 6`,
above the 0.60 floor), none certifies `collapsed`, and there is no `budget_limited` or
`inconclusive` depth, so `d*` is placed at the top of the declared arm-L grid:
`d* = 12`, i.e. `d* >= 12` within the grid, with no turnover observed. Arm X is
descriptive only at `n = 2` (2/2 at both `k = 16` and `k = 24`, the `k = 16` item
completing at 1741 tokens).

The completion-size fit on arm L is `311.1 + 17.8 * k` tokens (Pearson r = 0.22 over the
36 arm-L completions): at constant load, depth is nearly free in output tokens, unlike
round 6's shipped-generator run where completion size tracked load (`-36 + 80k`, r = 0.75).
The scarce resource on this endpoint is budget, not depth, up to `k = 12`.

Budget replay at the answer position:

| budget | answerable | correct | unanswerable | accuracy over all | accuracy over answerable |
|--------|-----------|---------|--------------|-------------------|--------------------------|
| 256 | 15 | 15 | 25 | 0.375 | 1.000 |
| 512 | 22 | 22 | 18 | 0.550 | 1.000 |
| 1024 | 38 | 38 | 2 | 0.950 | 1.000 |
| 2048 | 40 | 40 | 0 | 1.000 | 1.000 |

The cliff is a truncation cliff: 25 of 40 items never reach the answer word at 256
tokens (median completion 404 tokens), and every item that does reach the answer word
answers correctly. Same shape as round 6's cliff (26 of 40 lost at 256), on a
constant-load arm.

## Finding 3: the three items that survived round 8's transport failure answer the same

Round 8's three surviving completions were `k = 3` gold-no twice (416 and 557 tokens)
and `k = 4` gold-yes (355 tokens), all correct, on a stream whose cell-level fingerprint
this round reproduces byte-identically at the published gate record. On this round's
stream, all three corresponding items are answered correctly (the three `k = 3` gold-no
items at 299, 621, 621 tokens and the three `k = 4` gold-yes items at 127, 133, 137
tokens). Different endpoint, same items, same verdict: the round-8 survivors were not
lucky items. (Round 8 archived no raw records, so item identity rests on the seed-frozen
stream plus the cell fingerprint, not on a per-item hash; this round's raw archive
carries `seed_hash` and `prompt_sha256`, so the next round's cross-check can be
per-item.)

## Finding 4: the depth ceiling is still unplaced, and this round sharpens where to look

Nothing collapses to `k = 12` at constant load on a fast endpoint, so the ceiling, if it
exists in this family, sits above 12 hops. The declared grid stops at arm-L `k = 12` and
descriptive arm-X `k = 24`, so the ceiling is not measured, only bounded. The two next
moves from #71's own option list are the natural ones: extend the grid (`k = 32`,
option 1, noting arm-X load still grows with `k`), or run a base-checkpoint arm
(option 4), where a ceiling would speak to the core question. The constant-load
construction makes the extended arm cheap: at `k = 32` the prompt stays at 24 facts
(`C = 3/4` chains is not an integer, so `k = 32` needs the arm-X construction or a
relaxed `E`; see #71 for the parameterization).

## Limits

One endpoint, quantized, training data undisclosed; the orchestration session ran on a
different local model than the probed endpoint. Not H1 evidence and not Condition-2
study data. `n = 6` per depth means only 6/6 certifies maintained and only 1/6 or worse
certifies collapsed (round 8 Finding 2): this grid describes but cannot certify, and
40/40 at one seed on one endpoint is one arm of one seed. The gate battery is
traversal-free and reaches only two-feature conjunctions; a three-feature leak or one
depending on entity identity across items is outside it at any `n`, and at `n = 6` its
power is zero (it runs on the 40-candidate pool, which is what is certified). The
`k = 24` cell remains the closest gate call (`p = 0.072`). Raw records carry latency
but no absolute timestamp, so no wall-clock inter-item reading is made; the `finished_at`
field stays open under #73.

## Reproduce

All artifacts sha256-pinned:

| file | sha256 |
|------|--------|
| `const_load_depth.py` | `724f585f6336f062a3fd28c7a48dec03d92de6cd40dcd6b2af0ba28e09c4089d` |
| `gate.json` | `6cfcb0e16e4b0e235a22476e6981d0a4494b0b89a34ddcfc19117cf520b0e129` |
| `raw.jsonl` | `4cfeb3f1d69636ecf18219f33e5b4dbc46ff56ef752c67aa85078e08d2341e32` |
| `summary.json` | `7c8058ed08a1bce9dc5be17269abec621d12e16165b679244777c3a80dab5f1c` |

- `python3 const_load_depth.py --selftest` (offline, deterministic; numbers are
  reported only if the 15 controls pass).
- `python3 const_load_depth.py --gate --out gate.json` (offline, deterministic; the gate
  is recorded before any prompt is spent).
- `python3 const_load_depth.py --probe --out-dir .` requires the endpoint environment
  (`NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`, optional `NIGHTLY_API_KEY`), which is not
  reproducible from the repository; `raw.jsonl` and `summary.json` are the record, and
  `python3 const_load_depth.py --replay` re-derives the aggregate from `raw.jsonl`
  offline.
- The item stream is pinned by `seed_base 20261017` and the gate fingerprint; the raw
  records carry `seed_hash` and `prompt_sha256` per item.
