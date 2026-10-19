# Nightly round 11 (2026-10-19 02:00): does the traversal strategy survive at depth 12, 16, 24?

State: **Executed** (probe completed, 36/36 arms answered, gate verified before any prompt
was spent). Reproduction status is recorded in Errata/Verification below as the verifier
pass completes. Not Validated: one endpoint, one run, no second endpoint.

## Question

Round 10 showed, on a matched-pair probe built from shipped ladder items at k = 4, 6, 8,
that the probed endpoint follows directed traversal, not undirected connectivity (36/36
cells matched the traversal oracle; 0 of 9 items were consistent with connectivity). Round
9 placed the constant-load depth ceiling of the same family at d\* >= 12 on a different
pool slot. Both runs are single-execution facts on different quantizations of one model
family.

This round asks one question: **does the traversal verdict replicate at depths k = 12, 16,
24**, i.e. at and above the certified constant-load region, on seed-generated items of the
canonical generator beyond the shipped grid, on this round's endpoint? This serves #71
(depth ceiling placement: a traversal failure at these depths would sit inside the band the
study design wants to probe at d\*+1..d\*+4) and gives round 10's Executed-only finding an
independent re-run at a different quantization slot of the pool.

## Method

`deep_depth_probe.py` is stdlib-only. It imports the canonical generator
(`generators/ladders.py`, hash pinned in `gate.json`) to build a 900-item pool (300 per
level at k = 12, 16, 24, `seed_base 20261019`, file order), and independently re-derives
every gold label by own BFS. The matched-pair construction, the invariant checks and the
15-rule direction-blind battery follow round 10's corrected script
(`research/nightly-2026-10-18-0400/matched_pair_probe.py`). Three round-10 verification
findings are fixed here rather than copied:

1. pool-corpus null bounds use the true support `[|a+y-n|, n-|a-y|]` (round-10 verification
   section 6);
2. both permutation nulls report one-sided and two-sided exact p values and gate firing
   uses the two-sided value against the Bonferroni bar (round-10 verification section 5);
3. a global attempt budget caps endpoint calls at 40 including the health check and all
   retries (round-10 disclosure: 37 dispatched but up to 73 possible attempts).

Nine matched items: first three usable items per level, generated file order (usable =
gold-yes query witnessed by a simple in-degree <= 1, out-degree <= 1 chain of length >= 4,
plus a second component holding a terminal node whose name length equals the chain
terminal). Four arms per item as in round 10: F1 `(p_1, p_k)` gold yes, R1 `(p_k, p_1)`
gold no, F2 `(p_2, p_{k+1})` gold yes, X `(p_2, m)` gold no. F1/R1 span undirected
distances 11, 15, 23 hops; the queried forward pairs have exactly one directed path of
that length, so a "yes" cannot come from any shorter route.

### Gate (written before any prompt was spent)

Gate hash `4e3d799b0266e93f8b7068357fba5cff3f994158534175a02209647f1936854c`, schema
`round11-gate-v3`. `--selftest`: 48 checks, 0 failures.

| Corpus | items | connectivity != reachability | best blind rule accuracy | discriminating |
|---|---|---|---|---|
| generated pool (k = 12, 16, 24) | 900 | 0 | 1.0000 | no |
| matched corpus (9 x 4) | 36 cells | 9 of 36 | 0.7500 | yes |

The pool reproduces the shipped-corpus leak story at the new levels: five blind rules
(`same_component`, `undirected_connectivity_only`, `target_is_fact_target`,
`endpoint_out_degree_zero`, `chain_len_matches_level`) hit 1.0000 on the generated pool,
so only the matched-pair construction can separate the strategies. On the matched corpus
no blind rule fires under the two-sided Bonferroni criterion (bar 3.333e-03;
`same_component` two-sided p = 3.906e-03, accuracy 0.7500, so it fails both criteria).

## Probe

36 prompts, temperature 0, `max_tokens 2048`, concurrency 4, 900 s per-item deadline, one
retry per arm under a global cap of 40 attempts. Health check 2.237 s. **Total endpoint
calls including health: 37 (no retries fired). 36/36 answered, 0 transport failures, 0
completions truncated at 2048, every arm 9/9.** Wall 295.6 s. All 36 raw records carry
`started_at` and `finished_at` in UTC (closes the named `finished_at` open item of #73).

| Strategy | cells matching | items matching all 4 arms |
|---|---|---|
| **Directed traversal** | **36 / 36** | **9 / 9** |
| Undirected connectivity | 27 / 36 | 0 / 9 |
| Constant yes / constant no | 18 / 36 | 0 / 9 |

Exact McNemar: 0 discordant pairs in the direction family (F1, R1) and 0 in the component
family (F2, X), p = 1.0 in both. The connectivity oracle fails exactly on the nine R1
cells; if the endpoint answered from connectivity, all nine reverse queries would have
been "yes". 36 of 36 completions name every interior node of their chain.

| Level | cells | correct | mean completion tokens | mean wall s |
|---|---|---|---|---|
| k = 12 | 12 | 12 | 332.3 | 29.9 |
| k = 16 | 12 | 12 | 398.0 | 33.5 |
| k = 24 | 12 | 12 | 627.7 | 31.9 |

Per arm: F1 9/9 (mean 402.4 tokens), R1 9/9 (452.0), F2 9/9 (481.3), X 9/9 (474.9).
Direction-family reverse cost: R1 is +12.3 % mean tokens over F1 (round 10 measured +35 %
on the reverse arm at k <= 8; both are n = 9 per arm, descriptive only). Latency is flat
in depth (per-level means 29.9 to 33.5 s); completion size grows with depth (+29 tokens
per hop across levels) but maxes at 878 tokens, far under the 2048 budget, so no answer
was lost to truncation at any tested depth on this endpoint.

## Answer

The traversal verdict replicates. At k = 12, 16 and 24, on nine seed-generated matched
items, the endpoint answered every arm in the pattern only directed traversal predicts,
and no item was consistent with the connectivity shortcut. Combined with round 10, the
same matched-pair signature holds from k = 4 to k = 24 across two quantization slots of
the same model family (round 10: IQ3_XXS; this round: the pool's `qwen38-flash-next`
slot, an IQ4_XS-class quantization per its runtime). For #71: there is still no turnover
to place d\* against, now up to 24 hops on a non-constant-load construction with full
chain recitation; the truncation cliff round 9 localized (answers lost under small
budgets) did not bind at 2048.

## Disclosure

- One endpoint family, one run per depth band; the endpoint's training data is
  undisclosed. Not H1 evidence and not Condition-2 study data.
- Items are generated, not shipped: `items/ladders/` has no level > 8. Reproduction of the
  pool is a command, not a committed file: `python3 -c` with `generators/ladders.py`'s
  `generate_items(level, 300, 20261019)` for level in 12, 16, 24; the byte hashes of the
  three generated blobs are pinned in `gate.json` (`item_source.blob_sha256`).
- The orchestration session and the probed endpoint are the same public model family this
  round (`qwen38-flash-next`), unlike round 10; verifier independence is therefore carried
  by the verifier pass, not by model diversity.
- n = 9 per level means each arm-level 9/9 has Wilson 95 % lower bound 0.701: this grid
  describes and replicates a strategy, it cannot certify a ceiling. The gate certifies
  only that the matched corpus is discriminating under the declared battery.
- The pool-corpus null on 900 items reports the fixed support bounds; the matched-corpus
  nulls report both tails; `gate.json` says so in `null_model.tail_note`.

## Errata and verification

To be completed by the independent verifier pass (read-only, per the round-10 process
fix): regenerate `--selftest`, `--gate` and `--analyze` from the pushed commit and
confront each published number against `raw.jsonl`. If the verifier regenerates the
artifacts byte-identically, this round's state upgrades to **Reproduced at the analysis
level** (round-10 convention) and this section records the record's location.

## Files

- `deep_depth_probe.py`: probe script (`--selftest`, `--gate`, `--probe`, `--analyze`)
- `gate.json`: gate record, hash `4e3d799b...` bound into every `raw.jsonl` record
- `raw.jsonl`: 36 raw records, per-attempt `started_at`/`finished_at` UTC, sanitized text
- `summary.json`: analysis over `raw.jsonl`, regenerable with `--analyze`
