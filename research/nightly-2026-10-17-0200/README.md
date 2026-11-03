# Nightly round 7 (2026-10-17 02:00, pool slot 3/6): ladder depth vs prompt load

Question: can the ladder family separate derivation depth from prompt load, and is the
issue #67 leak gate calibrated against anything? Serves issue #71 acceptance criteria 1,
2, and 4.

Label: **Executed** (deterministic corpus analysis). No model arm ran this round, so
nothing here is Reproduced or Validated. Tracker record: issue #65, round 7 summary plus a
correction comment.

## Method

`ladder_depth_load.py` reads the shipped ladder items directly and imports nothing from
`generators/`, so it is an independent verifier of the corpus rather than a re-run of the
generator. For every item it builds the fact graph, runs BFS from the query subject to the
query object over the query relation, and classifies the item as shortcut (path shorter
than the declared depth), exact, longer, or unreachable. It also measures the reachable
closure size and facts per item, and re-draws the query pair at random from each item's own
entity set (3 draws, fixed seed) to build a level-matched permutation null for the shortcut
statistic. Corpus: `items/ladders/` levels 1, 2, 4, 6, 8, 300 items each, sha256-pinned in
`depth_load_report.json`.

## Results

| level | items | yes / no | exact depth | shortcut | longer | unreachable | closure | facts mean (min-max) |
|---|---|---|---|---|---|---|---|---|
| 1 | 300 | 148 / 152 | 148 | 0 | 0 | 152 | 2 | 2.50 (2-3) |
| 2 | 300 | 140 / 160 | 140 | 0 | 0 | 160 | 3 | 6.08 (4-8) |
| 4 | 300 | 148 / 152 | 148 | 0 | 0 | 152 | 5 | 15.43 (8-24) |
| 6 | 300 | 166 / 134 | 166 | 0 | 0 | 134 | 7 | 30.32 (12-48) |
| 8 | 300 | 157 / 143 | 157 | 0 | 0 | 143 | 9 | 46.48 (16-80) |

Permutation null (shortcut rate): 0.0% at k=1, 9.3% at k=2, 12.3% at k=4, 9.8% at k=6,
10.6% at k=8.

## Findings

1. No derivation shortcut anywhere in the repaired corpus: 0 of 1,500 items admit a path
   shorter than the declared depth, and no `yes` item requires more than the declared
   depth. Every `no` item is unreachable, so a negative requires exhausting the reachable
   closure rather than bounding a search.
2. The reachable closure from the query subject is exactly `k+1` at every level: the chain
   does not branch, so traversal demand equals declared depth.
3. Depth and load are algebraically coupled and the coupling is quadratic. Facts per item
   equal `C * k` with `C` drawn uniformly from `[2, k+2]`, so mean load is `k^2/2 + 2k` and
   the within-level span is `2k` to `k(k+2)`. At level 8 the same nominal depth spans a 5x
   load range. Any accuracy-vs-level curve is therefore confounded, including the round-6
   result at k=16 (32 to 288 facts). Reading `d*` off the level axis is not licensed; a
   `(k, C)` factorial is required.
4. The leak statistic has discriminating power but the fixed 0.55 threshold in issue #67
   criterion 2 is not calibrated to it: the level-matched null sits at 9-12% for `k >= 2`,
   so a 0.55 gate is roughly 5x above the band and would not flag a genuine 10% leak.
   Threshold against the null plus a margin instead.
5. Schema honesty: the first draft of this round's script assumed a name-the-terminal-entity
   task. The shipped task is a yes/no entailment judgement over a rule plus a fact graph. The
   draft was discarded rather than shipped. A gate that does not read the item schema cannot
   gate that corpus.

## Limits

One corpus, one seed family, no model measurements, no repeated seeds, 3 null draws per
item, single relation type. The BFS results are exact for the corpus as written and say
nothing about model behaviour.

## Endpoint note

The assigned local endpoint served one probe completion in 328.6 s wall time while reporting
733 ms of engine generation for 33 tokens. Roughly 327 s per request is spent outside the
engine, so a 40-prompt arm cannot complete inside a round window. The endpoint is not
identified here beyond that: no host, address, or model-file path belongs in this repository
(public-only rule).

## Reproduce

```
python3 research/nightly-2026-10-17-0200/ladder_depth_load.py --selftest
python3 research/nightly-2026-10-17-0200/ladder_depth_load.py --report \
  --out research/nightly-2026-10-17-0200/depth_load_report.json
```

37/37 selftest controls pass. Stdlib only, deterministic.
