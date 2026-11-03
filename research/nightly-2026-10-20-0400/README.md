# Nightly round 14 (2026-10-20 04:00): does the traversal verdict hold on a 27B-class local endpoint?

State: **Executed**. The round-11 standard of an independent read-only verifier pass
(analysis-level reproduction) is deferred this round and disclosed under Answer and
Disclosure; the script selftest is green and the gate and summary are byte-regenerable,
but no fresh-clone re-derivation was run.

## Question

Round 11 established, on a matched-pair traversal grid at k = 12, 16, 24 (36 cells,
nine matched items times four arms), that a flash-class local endpoint follows directed
traversal, not undirected connectivity (36/36 cells matched the traversal oracle, the
connectivity oracle fails exactly the nine R1 cells, and the direction family shows 0
discordant McNemar pairs). Rounds 9, 10 and 11 all ran on flash-class endpoints; the
corpus had not yet been run at 27B-class scale.

This round is the scale replication that serves #71 (the depth ceiling d\* is a
property of the (family, endpoint) pair, so its placement needs at least one
measurement per family class): the exact same 36-cell corpus as round 11, with
byte-identical prompts (the gate asserts prompt_sha256 identity against the committed
round-11 raw archive), run on a 27B-class local endpoint. Rounds 12 and 13 crashed
early and shipped no artifacts; this round is the live continuation of the pool
rotation.

## Method

`cross_scale_probe.py` is stdlib-only. It imports the canonical generator
(`generators/ladders.py`, hash pinned in `gate.json`) to build the 900-item pool
(300 per level at k = 12, 16, 24, `seed_base 20261019`, file order) and independently
re-derives every gold label by own BFS. The matched-pair construction, the invariant
checks and the 15-rule direction-blind battery are the round-11 construction, and the
gate pins the three generated-blob hashes to the round-11 gate pins (byte-identical
regeneration). The committed round-11 raw archive
(`round11_reference_raw.jsonl`, sha256 `f5a77a46...`) is the cross-class reference:
the gate asserts all 36 `prompt_sha256` values are identical, so the comparison is
cell-paired, not just same-construction.

Outcome classification, refined versus round 11 per issue #73: `answered`,
`truncated_no_answer`, `no_answer_stop`, `empty_completion`, `transport_<class>`,
`abandoned_budget`. Correctness is scored only on `answered` outcomes. An empty
completion is a transport failure, not a model outcome; a cell killed by the level
budget is written with `abandoned_budget` and never scored (a killed arm is not a
result). The probed endpoint is a thinking model: the visible answer rides on
`content` after the reasoning tokens, so the parser checks `content` first and falls
back to the reasoning field only when `content` carries no yes/no.

### Gate (written before any prompt was spent)

Gate hash `c1c747214417cde57c3555a602de4c0786cb8c6b7f9c3ac3539281b277b3eced`, schema
`round14-gate-v1`. `--selftest`: 66 checks, 0 failures.

| Corpus | items | connectivity != reachability | best blind rule accuracy | discriminating |
|---|---|---|---|---|
| generated pool (k = 12, 16, 24) | 900 | 0 | 1.0000 | no |
| matched corpus (9 x 4) | 36 cells | 9 of 36 | 0.7500 | yes |

The pool reproduces the round-11 leak story at the new levels: five blind rules
(`same_component`, `undirected_connectivity_only`, `target_is_fact_target`,
`endpoint_out_degree_zero`, `chain_len_matches_level`) hit 1.0000 on the generated
pool, so only the matched-pair construction separates the strategies. On the matched
corpus no blind rule fires under the two-sided Bonferroni criterion (bar 3.333e-03;
`same_component` two-sided p = 3.906e-03, accuracy 0.7500, so it fails both
criteria).

## Probe

36 prompts, temperature 0, `max_tokens 2048`, health check 3.125 s (23 completion
tokens, answer-parseable). Transport policy as declared in the gate: the first two
grid cells dispatched sequentially (walls 12.894 s and 18.166 s) set the per-item
estimate to 36.3 s (depth factor applied), and the concurrency is the largest of
{4, 2, 1} with estimate times 34 cells divided by the concurrency times 1.25 under
the 2700 s phase-2 budget: 4. Per-item deadline 900 s, per-level budget 1500 s, one
retry per arm under a global cap of 40 attempts including the health check.

**Total endpoint calls including health: 37 (no retries fired). 36/36 answered,
0 transport failures, 0 completions truncated at 2048, every arm 9/9, every answer
parsed from `content` (36/36), 0 from the reasoning fallback.** Wall 373.1 s. All 36
raw records carry `started_at` and `finished_at` in UTC (window 02:32:05 to 02:38:18,
373 s; attempt `wall_s` sums to 1163.4 s at concurrency 4).

| Strategy | cells matching | items matching all 4 arms |
|---|---|---|
| **Directed traversal** | **36 / 36** | **9 / 9** |
| Undirected connectivity | 27 / 36 | 0 / 9 |
| Constant yes / constant no | 18 / 36 | 0 / 9 |

Exact McNemar: 0 discordant pairs in the direction family (F1, R1) and 0 in the
component family (F2, X), p = 1.0 in both. The connectivity oracle fails exactly on
the nine R1 cells; if the endpoint answered from connectivity, all nine reverse
queries would have been "yes".

| Level | cells | correct | mean completion tokens | mean wall s |
|---|---|---|---|---|
| k = 12 | 12 | 12 | 326.8 | 35.5 |
| k = 16 | 12 | 12 | 396.1 | 30.9 |
| k = 24 | 12 | 12 | 498.5 | 30.5 |

Per arm: F1 9/9 (mean 309.9 tokens), R1 9/9 (493.8), F2 9/9 (320.9), X 9/9 (503.9).
Reverse cost: R1 is +59.3 % mean tokens over F1; the cross arm X is +57.0 % over F2
(both n = 9 per arm, descriptive only). Latency is flat in depth (per-level means
35.5 to 30.5 s); completion size grows with depth (326.8 to 396.1 to 498.5 tokens,
i.e. +17.3 per hop from 12 to 16 and +12.8 per hop from 16 to 24), maxing at 853
tokens, far under the 2048 budget, so no answer was lost to truncation at any tested
depth on this endpoint.

### Cross-class comparison against the round-11 reference

Cell-paired on the 36 identical prompts (flash-class local endpoint, round 11):
**36/36 cells agree, 0 disagreements** (per level 12/12 at each of k = 12, 16, 24).
The endpoint answered every cell with the same word the flash-class endpoint did.
Per-level mean completion-token ratio (this round over round 11): 0.9832 (k = 12),
0.9952 (k = 16), 0.7942 (k = 24); per-level mean wall-s ratio: 1.1875 (k = 12),
0.9228 (k = 16), 0.9586 (k = 24). One style difference: the flash-class endpoint
recited every interior chain node in all 36 completions, while this endpoint does so
in 18 of 36 (per arm: F1 0/27, R1 8/27, F2 5/27, X 5/27) and still matches the
traversal oracle on every cell. The answer-level signature is class-invariant on this
corpus; the visible trace is not. The completion is reasoning-heavy (mean 1078
reasoning characters, max 2360, content mean 2.5 characters): the answer is the last
few characters of the completion.

## Answer

The traversal verdict holds on a 27B-class local endpoint. On the byte-identical
36-cell corpus, every cell follows the directed-traversal oracle, the
connectivity shortcut fails exactly the nine R1 cells, and the exact McNemar
discordant counts are zero in both families. The verdict is cell-identical to the
flash-class round-11 run on the same prompts (36/36 cell agreement), so on this
corpus the traversal signature is not a property of the flash class: two self-hosted
endpoint classes (flash-class and 27B-class) produce the identical 36-cell answer
pattern. For #71: this is the first non-flash measurement of the corpus; there is
still no turnover to place d\* against at any class (no depth at which the verdict
flips), and the truncation cliff round 9 localized does not bind at 2048 (max 853
tokens). What changed with class is completion style, not answers: reasoning traces
are longer and less exhaustive (18/36 full interior recitations vs 36/36), with a
lower k = 24 token count (498.5 vs 627.7) but comparable latency.

## Disclosure

- No independent verification pass this round (deferred to the runner time budget):
  the round is **Executed** only. The script selftest is green (66 checks), the gate
  hash is stable across regeneration, and `summary.json` is byte-regenerable with
  `--analyze`; `raw.jsonl` is the endpoint output. The round-11 standard (fresh
  non-mutating clone, own BFS re-derivation) is not met here.
- One endpoint, one run; the endpoint's training data is undisclosed. Not H1
  evidence and not Condition-2 study data. The 373.1 s run wall and the 3.125 s
  health-check latency are runner-side observations; the raw-record UTC timestamp
  window (02:32:05 to 02:38:18, 373 s) corroborates the wall, and attempt `wall_s`
  sums to 1163.4 s at concurrency 4.
- Items are generated, not shipped: `items/ladders/` has no level > 8. Reproduction
  of the pool is a command, not a committed file: `generators/ladders.py`'s
  `generate_items(level, 300, 20261019)` for level in 12, 16, 24; the byte hashes of
  the three generated blobs are pinned in `gate.json` (`item_source.blob_sha256`)
  and equal the round-11 gate pins.
- The orchestration session and the probed endpoint are the same 27B-class local
  endpoint this round; verifier independence is therefore not carried by model
  diversity, and no verifier pass was run at all (see above).
- n = 9 per arm means each arm-level 9/9 has Wilson 95 % lower bound 0.701: the grid
  describes and replicates a strategy, it cannot certify a ceiling. The gate
  certifies only that the matched corpus is discriminating under the declared
  battery.
- The cross-class comparison compares answers, not completion text: the recitation
  difference (18/36 vs 36/36) is a style difference, not a disagreement. Per-level
  token and wall ratios are descriptive per-level mean ratios (n = 12 per level), not
  paired inferences.
- The probed endpoint is a thinking model: the parser reads the answer from
  `content` with a reasoning-field fallback, and `max_tokens 2048` must cover
  reasoning plus answer. A tighter budget risks truncating the answer after the
  reasoning tokens (issue #73); 2048 never bound here (max 853 completion tokens).

## Files

- `cross_scale_probe.py`: probe script (`--selftest`, `--gate`, `--probe`, `--analyze`)
- `gate.json`: gate record, hash `c1c747...` bound into every `raw.jsonl` record
- `round11_reference_raw.jsonl`: round-11 raw archive (36 records, sha256
  `f5a77a46...`), committed as the cross-class reference
- `raw.jsonl`: 36 raw records, per-attempt `started_at`/`finished_at` UTC, sanitized text
- `transport.json`: transport-policy outcome (phase-1 measurement, concurrency choice,
  wall time, endpoint call count)
- `summary.json`: analysis over `raw.jsonl` including the cross-class comparison against
  the round-11 reference, regenerable with `--analyze`
