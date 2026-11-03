# Round 24 (2026-10-25 04:05): bisecting the (k, E) frontier at fixed depth and the depth arm at safe load

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is the
reproducible record: script, gate, prompts, raw responses, scores.

## Question

Where does the load boundary E\* sit at fixed hop depth k = 8 on a flash-next-class local endpoint
between the archived maintained point (E = 96) and the archived non-maintained point (E = 192),
and at fixed safe load E = 96, does the delivered answer survive depth to k = 12 and k = 16?
If the whole bisection is maintained, the frontier narrows toward 192; if the depth arm turns
over at E = 96, E\* shrinks as k grows and the frontier is a joint (k, E, budget) surface, not a
load-only curve.

Motivation, from the archive:

- round 23 (PR #97): the frontier walk on this class - maintained at (k = 8, E = 96), first
  non-maintained at (8, 192) (4/6 delivered), a surfacing collapse (25/25 delivered answers
  correct, all 11 failures truncations at 2048).
- round 21 (PR #95): depth at E = 24 maintained to k = 12 on this class (~29 completion tokens
  per added hop).
- round 22 (PR #96): load at k = 4 free to E = 240 on the 27B class, with an enumeration switch
  above ~100 facts that this class does not make.

Issue #71 names this exact instrument ("bisect the load axis at fixed depth (k = 8, E in {112,
128, 160}) and add the two missing depth points at the safe load (k = 12 and k = 16 at E = 96),
to test whether E\* shrinks as k grows or the boundary is load-only").

## Instrument

`frontier_bisect_probe.py` (stdlib only). Construction: C disjoint directed paths of exactly k
edges over fresh entity names, one rule sentence (transitivity of `precedes`), E = k x C facts in
shuffled order, one query per prompt, answer required as exactly one word. Gold from an unbounded
BFS independent of the generator, plus a structural audit (component edge and node counts, path
shape, no branching, query source a head and query target a tail, label agrees with BFS).

Matched pair (issue #78 acceptance criterion 1): every dispatched graph is asked TWO questions
over the identical fact list, identical entity names, identical fact count and the identical
queried source; only the queried target varies. Arm F: forward query, gold yes, k hops. Arm X:
cross-component query, gold no. `pair_violations()` asserts this on every dispatched pair, and
`--selftest` carries the planted non-matched control.

Declared grid (seed base 20261024), two arms, each single-axis within itself:

| cell | k | C (paths) | E (facts) | role |
|------|---|-----------|-----------|------|
| L0 | 8 | 12 | 96 | anchor; IS round 23's S3 level (blob + prompt-digest pins) |
| L1 | 8 | 14 | 112 | load bisection 1 |
| L2 | 8 | 16 | 128 | load bisection 2 |
| L3 | 8 | 20 | 160 | load bisection 3 |
| D1 | 12 | 8 | 96 | depth at safe load 1 |
| D2 | 16 | 6 | 96 | depth at safe load 2 |

Readout stack, declared before dispatch (issue #94): `content_only` (primary),
`delivered_or_strict` (content, else the round-19 strict trace-commitment rule), `loose_fallback`
(the archived convention of rounds 10 to 22; reported, and here never the scoring basis for a
maintained claim). Cell status per the round-8 trichotomy (Wilson 95%, floor 0.60): maintained /
inconclusive / budget_limited / collapsed.

Predictions were fixed in `gate.json` before any prompt was spent (schema `round24-gate-v1`, gate
`85e70f3f`, selftest 938 checks 0 failures); they are evaluated in `summary.json` and reported in
the tracker comment, including the three that failed as declared (P1 by 0.4 tokens, P2b, P2c).

## Transport and how to reproduce

Endpoint read from `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`, `NIGHTLY_API_KEY`; nothing endpoint-
specific is written anywhere; stored model text passes a sanitizer (URLs, IP addresses, absolute
paths). Health probe at a 256-token budget, then 36 prompts (18 matched pairs), `max_tokens` 2048,
`temperature` 0.0, concurrency 2 from the phase-1 measured rate. This round: 37 of the 40-call
cap, zero retries, zero transport errors, zero abandoned cells, dispatch wall 938.1 s.

```
python3 research/nightly-2026-10-25-0405/frontier_bisect_probe.py --selftest
python3 research/nightly-2026-10-25-0405/frontier_bisect_probe.py --gate   # refuses on anchor drift
python3 research/nightly-2026-10-25-0405/frontier_bisect_probe.py --probe  # gate-hash-guarded --resume
python3 research/nightly-2026-10-25-0405/frontier_bisect_probe.py --analyze
```

`run.log` (endpoint console noise) stays outside the repository by design.

## Results (headline)

- Load arm k = 8: maintained at E = 96, 112, 128 and 160 (24/24 delivered in the answer field,
  24/24 correct). P2b fails as declared; the frontier at k = 8 narrows to (160, 192).
- Depth arm E = 96: D1 (k = 12) maintained 6/6; **D2 (k = 16) non-maintained**: 5/6 delivered and
  correct, one arm-X cell truncated at exactly 2048 tokens with the answer field silent. P2c
  fails as declared: **E\* shrinks as k grows; the frontier is a joint (k, E, budget) surface.**
- Zero wrong answers anywhere (P5: 35/35 delivered correct). The silent cell's loose fallback
  token was correct by accident with no strict commitment (issue #94, provenance `mid_trace`).
- No enumeration switch: distractor-mention ratio 0.68 to 1.00 in every cell (P3 pass).
- Cost laws (uncensored means): +7.89 tokens/fact at k = 8 (r = 0.931), +29.36 tokens/hop at
  E = 96 (r = 0.909, reproducing round 21's ~29 tok/hop at 12x lower load); two-factor over cell
  means gives a positive hop x fact interaction (+0.394, r2 0.87, one cell censored; descriptive).
  The silence onset at (16, 96) sits well below the mean-cost extrapolation of the cap: the
  frontier is where the upper tail of enumeration length crosses 2048, not where the mean does.
- Near-miss: one L3 arm-X cell (seed 28461024) committed its verdict at 2043 of 2048 tokens with
  `finish_reason = stop` (five tokens of margin).
- Anchor: L0 arm-F prompts reproduce round 23's S3 answers at 1101/1098/1050 tokens vs archived
  1134/1098/1050 (P7 pass); the construction pins matched at gate time.

## Evidence label

`Executed` per `docs/agent-execution.md`: one endpoint, one run, no independent second
implementation, not covered by the pre-registered decision table. n = 6 per cell: exploratory.
The deployment is quantized with undisclosed training data; nothing here is H1 evidence. Every
ceiling above is conditional on the 2048-token output cap; a non-maintained cell is a statement
about surfacing under this protocol, not about competence.
