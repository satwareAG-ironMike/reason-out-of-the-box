# Round 15 (2026-10-21 02:00): matched-pair traversal probe on the repaired ladders family

Tracker: issue #65. Serves: #71 (depth-ceiling placement per family and endpoint), #78
(matched-pair instrument on a corpus that closes the clustering objection), #73 (transport
policy), #69 (the repair measured here). Summary comment: issue #65 of 2026-10-21.

## Question

As of 2026-10-20 `main` carries the issue #69 generator repair (component isomorphism:
the facts are C >= 2 disjoint directed paths, each exactly `level` edges), so no surface
feature of the query endpoints separates the answer classes. Issue #78 declares the
pre-repair matched-pair corpus blocked for reruns because its traversal-only query is
answerable by clustering. Question: does the round 10/11 traversal verdict hold on the
repaired instrument - the matched-pair grid at k = 12, 16, 24 (forward F1 vs reverse R1
on the same chain; in-chain F2 vs cross-component X) - on a flash-next-class local
endpoint? This is the first matched-pair measurement on the repaired family for any
endpoint, and extends round 6 (same endpoint class, single-query design, 40/40 up to
k = 16) to k = 24 with direction arms.

## Method and selection rule

`fixed_corpus_probe.py` (stdlib only; ported from round 14's `cross_scale_probe.py` with
the reference-archive machinery replaced by a declared lineage). Three subcommands after
`--selftest` (66 checks, 0 failures): `--gate` (corpus verification, 15-rule direction-blind
battery + 2 chain references, exact label-shuffle nulls, `gate.json`), `--probe` (36
prompts, temperature 0, max_tokens 2048, two-phase transport per issue #73: two
sequential cells measure the endpoint, remaining 34 at concurrency 4; 900 s per-item
deadline; one retry per arm under a global 40-attempt cap; incremental fsynced
`raw.jsonl`), `--analyze` (read-only aggregates to `summary.json`).

Corpus: pool of 900 items (`generators/ladders.py`, levels 12/16/24, 300 each, seed_base
20261019); matched items selected by the fixed rule "first 3 usable items per level in
generated file order" (usable = gold-yes query witnessed by a simple degree-bounded chain
plus an equal-name-length terminal on another component). Gate `10f569414bbf19b6...`
(schema `round15-gate-v1`) pins the generator sha256 and the three regenerated blob
hashes. The corpus is **not cell-paired** to rounds 10/11/14 (their corpora were built
pre-repair); the gate and this README declare the comparison as same-construction and
directional.

## Results (Executed; one endpoint, one run)

- Gate: matched corpus discriminating (connectivity != reachability in exactly 9 cells,
  the R1 cells; best blind rule 0.7500; no rule fires under Bonferroni). The repair is
  visible in the battery: `target_is_fact_target` scores 0.5133 on the pool (pre-repair:
  1.0); the selftest's role-constancy control catches a planted pre-repair-style leak.
- Probe: 37 endpoint calls including the health check, zero retries, 36/36 answered,
  phase-2 wall 627.8 s.
- Answers: **36/36 cells follow the directed-traversal oracle**; the signature table shows
  connectivity matching 27/36 (failing exactly the nine R1 cells); constant-yes and
  constant-no match 18/36. All four arms 9/9 (Wilson 95% lower bound 0.701 per arm);
  exact McNemar has **zero discordant pairs** in both families (direction F1/R1 and
  component F2/X), p = 1.0.
- Style, class-dependent: mean completion tokens 1183.1 per answered cell (per level
  1179.7 / 995.8 / 1373.7 at k = 12 / 16 / 24; round 11 pre-repair corpus: 332.3 / 398.0 /
  627.7; round 14: 326.8 / 396.1 / 498.5); 99.9% of output characters in the reasoning
  field (mean content 2.1 characters); full interior-chain recitation in 19/36 cells
  (round 11: 36/36; round 14: 18/36). Mean latency rises with depth: 46.9 / 53.9 / 65.4 s
  (round 14 was flat at 35.5 / 30.9 / 30.5 s).
- Budget finding: all 7 completions truncated at 2048 tokens are negative-arm cells
  (3 R1 and 3 X at k = 24, plus the X cell of item L12-1), and every truncated cell had
  already emitted the correct yes/no inside the reasoning trace.
  The scarce resource at k = 24 on this endpoint is the output budget, not reachability:
  a 1024-token budget would have deleted answers, echoing round 6's "budget, not depth".

## Disclosure and limits

No independent verifier pass this round: state **Executed**, not Reproduced. n = 9 per
arm, exploratory. The declared parser reads the last standalone yes/no in `content` with
a `reasoning` fallback; the 7 fallback cells are exactly the 7 truncations and all were
correct. One endpoint (flash-next class, quantized local deployment; training data
undisclosed); not H1 evidence. Cross-round token and latency comparisons are descriptive
(different corpora, pre-repair vs repaired). Per-arm accuracies carry the matched-design
confound controls of the gate (prompt length, name multiset, degree profile, undirected
distance matched within families).

## Reproduce

```
python3 research/nightly-2026-10-21-0200/fixed_corpus_probe.py --selftest
python3 research/nightly-2026-10-21-0200/fixed_corpus_probe.py --gate   # compare gate_hash
python3 research/nightly-2026-10-21-0200/fixed_corpus_probe.py --analyze
```

`--probe` needs a served endpoint via `NIGHTLY_BASE_URL` / `NIGHTLY_MODEL_ID` /
`NIGHTLY_API_KEY` (never written to artifacts). Files: `gate.json` (pre-registration
record), `raw.jsonl` (36 records, sanitized raw responses), `summary.json` (aggregates),
`transport.json` (dispatch note).
