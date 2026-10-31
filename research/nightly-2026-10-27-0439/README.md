# Round 31 (2026-10-27 04:39): cross-class replication of the round-24 (k, E) bisection grid on a 27B-class NVFP4/vLLM endpoint

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is the
reproducible record: script, gate, prompts, raw responses, scores.

## Question

Round 24 (branch `research/nightly-2026-10-25-0405`, PR #98) measured the declared six-cell
(k, E) grid on the flash-next class: the k = 8 load frontier is maintained to E = 160 (the
bracket then tightens to (160, 192), one step beyond the cell), and at the safe load E = 96
the depth arm turns over at k = 16 (one arm-X truncation at exactly 2048 tokens, 5/6 delivered
and correct), with zero wrong answers grid-wide. Every archived frontier point so far sits on
one class, so it is untested whether that frontier is a property of the model weights or of the
deployment (quantization format, serving runtime, output cap). This round re-runs the
IDENTICAL prompt set (byte-identical, pinned by digest to the round-24 archive) on a NEW
endpoint class: a 27B-class local model under NVFP4 (4-bit floating point) quantization,
served by vLLM with multi-token-prediction speculative decoding. The readout is per cell and
per prompt against the flash-next archive: same prompt, same graph, two deployments. A
difference is a class signal, not a measurement artifact.

Motivation, from the archive:

- round 24 (PR #98): the k = 8 load frontier maintained through E = 96, 112, 128, 160; the
  depth arm at E = 96 maintained at k = 12, non-maintained at k = 16 (turnover cell D2).
- round 23 (PR #97): (8, 192) non-maintained on the flash-next class, 4/6 delivered.
- round 22 (PR #96): load at k = 4 free to E = 240 on a 27B-class deployment (GGUF), with
  an enumeration switch above ~100 facts that the flash-next class does not make: the
  cross-class cost structure was already suspect.
- round 6: no verified evidence that quantization or inference precision degrades multi-hop
  depth reasoning specifically; this round is its first cross-class data point on the 4-bit
  floating point axis.

Issue #71 names the instrument family ("place the ladder depth ceiling d*: grid extension and
load decoupling"); this round is the load-decoupling test across classes, and issue #94's
probe-readout gap (the agreement fields) is what P5 targets.

## Instrument

`crossclass_frontier_probe.py` (stdlib only). Construction: C disjoint directed paths of
exactly k edges over fresh entity names, one rule sentence (transitivity of `precedes`),
E = k x C facts in shuffled order, one query per prompt, answer required as exactly one word.
Gold from an unbounded BFS independent of the generator, plus a structural audit (component
edge and node counts, path shape, no branching, query source a head and query target a tail,
label agrees with BFS).

Matched pair (issue #78 acceptance criterion 1, shipped round 22): every dispatched graph is
asked TWO questions over the identical fact list, identical entity names, identical fact
count and the identical queried source; only the queried target varies. Arm F: forward query,
gold yes, k hops. Arm X: cross-component query, gold no. `pair_violations()` asserts the
shared-content invariant on every dispatched pair; `--selftest` carries the planted
non-matched control (946 checks, 0 failures).

Grid: exactly round 24's grid, seed base 20261024, same name pools, seed formula and
selection order, so ALL 36 prompt digests and ALL 6 candidate-pool blobs must equal the
values archived in `research/nightly-2026-10-25-0405/` (PR #98); `--probe` and `--gate`
refuse otherwise. The digests and the round-24 per-prompt results are carried as constants in
the script, transcribed from that round's gate.json and raw archive, so the post-merge tree
verifies the pin without the unmerged ancestor; the digest anchor is fail-closed across ALL
six cells (gate `8d9c445f`, `all_cells_pass` true).

| cell | k | C (paths) | E (facts) | role on the flash-next class (round 24) |
|------|---|-----------|-----------|------|
| L0 | 8 | 12 | 96 | anchor; maintained 6/6 |
| L1 | 8 | 14 | 112 | load bisection 1; maintained 6/6 |
| L2 | 8 | 16 | 128 | load bisection 2; maintained 6/6 |
| L3 | 8 | 20 | 160 | load bisection 3; maintained 6/6, frontier bracket (160, 192) |
| D1 | 12 | 8 | 96 | depth at safe load 1; maintained 6/6 |
| D2 | 16 | 6 | 96 | depth at safe load 2; turnover cell (5/6, one truncation) |

Readout stack, declared in round 24 (issue #94): `content_only` (primary),
`delivered_or_strict` (content, else the round-19 strict trace-commitment rule),
`loose_fallback` (the archived convention of rounds 10 to 22; reported, and never the scoring
basis for a maintained claim). Cell status per the round-8 trichotomy (Wilson 95%, floor
0.60): maintained / inconclusive / budget_limited / collapsed.

Declared predictions, fixed in `gate.json` before any prompt was spent (schema
`round31-gate-v1`):

- P1 the frontier is class-specific: all six cells maintained under `content_only`.
- P2 the delivered answer is never wrong: every content answer in the grid is correct.
- P3 no truncation: all 36 prompts deliver the answer in the answer field under the 2048 cap.
- P4 the enumeration cost law is class-invariant: the per-hop slope at E = 96 (k = 8, 12, 16
  over uncensored cell means) in [0.5x, 2.0x] of round 24's +29.36 tokens/hop, and the
  per-fact slope at k = 8 (E = 96, 112, 128, 160) in [0.5x, 2.0x] of round 24's +7.89
  tokens/fact. Out of band: the quantization or runtime axis changes enumeration length,
  not only surfacing.
- P5 the surfacing is mostly class-invariant: at least half of the prompts where BOTH
  classes delivered a content answer carry the same answer (agreement over the comparable
  subset; reported as vacuous when no prompt is comparable).
- P6 the anchor reproduces cross-class: all three L0 arm-F prompts deliver "yes", as round 24
  recorded on the flash-next class at (k = 8, E = 96).
- P7 prompt-digest identity: all 36 prompt digests and 6 pool blobs equal round 24's gate
  (structural; true by construction, asserted by `--gate`).

Class caveat, declared: the NVFP4/vLLM deployment differs from the flash-next class on two
axes at once (quantization format and serving runtime; the flash-next class ran on a GGUF
deployment). This is a class replication, not a controlled quantization experiment; the
cross-class delta spans model class + quantization + runtime and is recorded as such. At
temperature 0 the multi-token-prediction draft acceptance is deterministic, so the
completions are the underlying model's greedy outputs; that is an assumption about the
serving runtime, noted and not verified from outside.

## Transport and how to reproduce

Endpoint read from `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`, `NIGHTLY_API_KEY`; nothing
endpoint-specific is written anywhere; stored model text passes a sanitizer (URLs, IP
addresses, absolute paths). Health probe at a 256-token budget, then 36 prompts (18 matched
pairs), `max_tokens` 2048, `temperature` 0.0, concurrency auto-selected from the phase-1
measured rate. This round: 37 of the 40-call cap, zero retries, zero transport errors, zero
abandoned cells, no resume; health answered in 2.6 s, phase-1 measured ~68.4 tok/s,
concurrency 2, dispatch wall 204.0 s.

```
python3 research/nightly-2026-10-27-0439/crossclass_frontier_probe.py --selftest
python3 research/nightly-2026-10-27-0439/crossclass_frontier_probe.py --gate   # refuses on digest drift
python3 research/nightly-2026-10-27-0439/crossclass_frontier_probe.py --probe  # gate-hash-guarded --resume
python3 research/nightly-2026-10-27-0439/crossclass_frontier_probe.py --analyze
```

`run.log` (endpoint console noise) stays outside the repository by design.

## Results (headline)

Cross-class replication: the round-24 frontier structure transfers verbatim to this class.
The identical 36-prompt grid comes back maintained through (k = 8, E = 160) and non-maintained
at exactly the same turnover cell (k = 16, E = 96): one arm-X truncation at 2048 tokens with
the answer field silent, 5/6 delivered and correct - the flash-next D2 event reproduced on a
different quantization, serving runtime and model class. All 35 delivered answers are correct
(zero wrong answers); over the 35 prompts where both classes delivered a content answer,
35/35 carry the same answer (P5 agreement 1.0, no prompt is comparable in the other
direction).

| cell | k | C | E | delivered | correct | content-silent | truncated | mean completion tokens | mean prompt tokens |
|------|---|---|---|-----------|---------|----------------|-----------|------------------------|--------------------|
| L0 | 8 | 12 | 96 | 6/6 | 6/6 | 0 | 0 | 611.5 | 1446.8 |
| L1 | 8 | 14 | 112 | 6/6 | 6/6 | 0 | 0 | 665.2 | 1699.7 |
| L2 | 8 | 16 | 128 | 6/6 | 6/6 | 0 | 0 | 483.0 | 1939.3 |
| L3 | 8 | 20 | 160 | 6/6 | 6/6 | 0 | 0 | 269.7 | 2423.0 |
| D1 | 12 | 8 | 96 | 6/6 | 6/6 | 0 | 0 | 503.0 | 1462.2 |
| D2 | 16 | 6 | 96 | 5/6 | 5/5 | 1 | 1 | 1095.2 | 1447.2 |

Prompt-token means are digit-identical to round 24's (1446.8 / 1699.7 / 1939.3 / 2423.0 /
1462.2 / 1447.2), independently corroborating the digest pin. Readout stack: all three arms
(`content_only`, `delivered_or_strict`, `loose_fallback`) agree on the cell verdicts; the
depth transition D1 to D2 is maintained to inconclusive (Wilson lower bound 0.437 against
the 0.60 floor), single-axis load transitions all maintained to maintained.

- P1 fails as declared: D2 is non-maintained on this class, so the k = 16 turnover at
  E = 96 is not a flash-next-class artifact; the two classes carry the same verdict surface
  at the cells probed (P5 35/35). The failure is the round's first result, not a gate event.
- P2 passes: 35/35 content answers correct, zero wrong answers grid-wide, the same
  surfacing-not-correctness pattern as rounds 23 and 24.
- P3 fails as declared: one truncation, D2 arm X at exactly 2048 tokens, answer field
  silent; unlike round 24's silent cell, this one carries no loose-fallback trace token
  (fallback provenance `no_trace_token`, strict rule finds no commitment), so the accidental
  fallback-correct event of round 24 does not recur.
- P4 fails on both axes: the enumeration cost law is NOT class-invariant. Per-fact slope at
  k = 8 over uncensored cell means: -6.01 tokens/fact (r = -0.934, 4 points) against the
  declared band [3.945, 15.78] (round 24: +7.89); per-hop slope at E = 96 over uncensored
  cell means: -27.13 tokens/hop (2 points, L0 and D1) against the band [14.68, 58.72]
  (round 24: +29.36). Descriptive fits: load law n = 4 r = -0.934; depth law including the
  censored D2 mean n = 3, +60.46 tokens/hop (r = 0.767); two-factor over the six cell means
  r2 = 0.695 (descriptive only). The class-specific signature is the distractor-mention
  ratio: 0.0 in every cell here versus 0.68 to 1.00 on the flash-next class - this class
  does not enumerate the irrelevant components, so completion length is set by the forward
  chain traversal plus a wide per-prompt tail, and does not ramp with irrelevant load.
  Round 22's 27B-class load-free-to-240 behavior is thus a 27B-class property, not a
  quantization artifact.
- P6 passes: all three L0 arm-F prompts deliver "yes" as round 24 recorded, at 196 / 1024 /
  191 completion tokens versus the flash-next 1101 / 1098 / 1050: the anchor reproduces the
  answer at a 4-5x cheaper enumeration.
- P7 passes: all 36 prompt digests and all 6 pool blobs equal round 24's gate (structural,
  verified by `--gate`; gate `8d9c445f`).
- Budget replay (character-proportional estimate): 17/36 answers would surface at 256
  tokens, 25/36 at 512, 34/36 at 1024, 35/36 at 2048 - the surfacing curve is far steeper
  than round 24's (1/36 at 256, 35/36 at 2048) because the non-enumerating style keeps the
  verdict inside small budgets.
- Polarity direction (McNemar over the 18 matched pairs): b = 1 (the D2 pair: forward
  delivered, its cross partner silent), c = 0, p = 1.0, under-powered as expected.

## Evidence label

`Executed` per `docs/agent-execution.md`: one endpoint, one run, no independent second
implementation, not covered by the pre-registered decision table. n = 6 per cell:
exploratory. The deployment is a quantized 27B-class endpoint under NVFP4 with vLLM
serving; nothing here is H1 evidence. Every ceiling above is conditional on the 2048-token
output cap; a non-maintained cell is a statement about surfacing under this protocol, not
about competence.
