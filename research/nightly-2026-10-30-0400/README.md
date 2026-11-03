# Round 37 (2026-10-30 04:00): same-class retest on the 27B NVFP4/vLLM class - the (16, 96)
turnover, the delivery pattern and the per-prompt cost law do not repeat across one re-run,
while the answers and the non-enumerating style do

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is
the reproducible record: script, gate, prompts, raw responses, scores.

## Question

Round 31 re-ran the digest-pinned (k, E) ladder grid on a 27B-class local endpoint under
NVFP4 (4-bit floating-point) quantization, vLLM serving, multi-token-prediction speculative
decoding, and reported: the (16, 96) turnover cell of round 24, 35/35 cross-class answer
agreement, and an inverted enumeration cost law (per-fact slope -6.01 against round 24's
+7.885; per-hop slope -27.13 against +29.36; distractor-mention ratio 0.000 in every cell
against 0.892), concluding that the cost structure is a property of the class. Round 33 then
measured the run-to-run repeatability of exactly these quantities on the flash-next class
(the other class): the verdict surface, the 35 delivered answers, the delivery/silent
pattern, the cost law to within 2.6 percent and the enumeration style all repeated, and 32
of 36 completions were token-for-token identical. The NVFP4 class itself has only ever had
ONE run, so its conclusions are still unbounded by run noise.

> On the endpoint class that produced round 31's results, does a second run of the
> byte-identical digest-pinned prompt set at temperature 0 reproduce the verdict surface,
> the delivered answers, the delivery pattern, and the inverted cost law and the
> non-enumeration style - or is the single-run conclusion of round 31 inside the run noise
> of this class?

Chosen because it is the cheapest experiment that can invalidate (or, if it passed,
harden) round 31's class-level conclusion on this class, and because it directly serves
the per-class self-agreement control of issue #100, the readout contract of #94 and the
depth-ceiling placement of #71.

## Instrument

`sameclass_frontier_retest_probe.py` (stdlib only, `--selftest` with 992 checks including
digest-true positive controls, planted negative controls and the archive-side estimator
audit, house style) is round 33's `retest_repeatability_probe.py` (branch
`research/nightly-2026-10-28-0400`, PR #101) with the reference retargeted from the
round-24 archive to the round-31 archive of this class and the prediction layer replaced
with R1 to R8 below; nothing else touched, so a difference against round 31 can only come
from the endpoint and the run, never from the instrument.

The grid is exactly round 24's (seed base 20261024, same name pools, seed formula and
selection order), so all 36 prompt digests and all 6 candidate-pool blobs must equal the
round-24 gate; `--probe` and `--gate` refuse otherwise. This round's gate: `b90335f1`
(schema `round37-gate-v1`), `anchor_ok` true, all cells pass, `--selftest` green. Round
31's per-prompt archive and round 24's per-prompt archive are both carried as constants in
the script (neither ancestor branch is on `main` at authoring time), so the post-merge
tree verifies every comparison without the ancestors. Per-prompt joins are on the prompt
digest.

## Declared predictions (fixed in `gate.json` before any prompt was spent)

- **R1 verdict surface**: the six cell statuses (round-8 trichotomy) repeat round 31's
  surface cell for cell (five maintained, D2 (16, 96) inconclusive through one 2048-token
  truncation).
- **R2 delivered answer**: agreement 1.00 over at least 30 comparable prompts (both runs
  delivered a content answer).
- **R3 delivery pattern**: the delivered/silent pattern is identical at 36 of 36 prompts,
  and the set of content-silent digests equals round 31's.
- **R4 cost law**: the per-fact slope at k = 8 comes back inside 0.5x to 2.0x of round
  31's published -6.01 (band [-12.02, -3.005]) and the per-hop slope at E = 96 inside
  0.5x to 2.0x of the published -27.13 (band [-54.26, -13.565]), scored on round 31's
  published estimator basis (cell means over uncensored cells; a truncated cell's censored
  mean is the all-cell variant reported next to it, issue #100 reporting rule).
- **R5 enumeration style**: the grid-mean distractor-mention ratio stays at 0.10 or below
  (round 31: 0.000 in every cell, the non-enumerating signature).
- **R6 length**: per-prompt completion length correlates with round 31's (Spearman rho
  >= 0.80) and the grid mean stays inside [0.70, 1.40] of round 31's grid mean.
- **R7 structural pin**: all 36 prompt digests and all 6 pool blobs equal round 24's gate.
- **R8 context, not a prediction**: the same per-prompt join against the round-24 archive
  on the other class, plus an independent recomputation of both rounds' published cost
  slopes from their archived per-prompt lengths.

## Results

Transport clean: endpoint healthy at session start (health 3.2 s at the 256-token budget),
37 of the 40-call cap (1 health + 36 grid prompts), `max_tokens` 2048, `temperature` 0.0,
75.5 tok/s measured single stream, concurrency 2, dispatch wall 160.4 s, zero retries,
zero transport errors, zero abandoned cells, 21,530 completion tokens.

1. **R1 fails: the verdict surface moved.** Five of six cells repeat round 31's surface;
   D2 (16, 96) is now `maintained` (6/6 delivered and correct), not `inconclusive`. The
   (16, 96) turnover, the load-bearing observation of the whole frontier line, did not
   repeat on this class.
2. **R2 passes: 35/35 delivered answers agree** (rate 1.00 over 35 comparable prompts).
   This run delivered all 36: 36/36 correct, zero wrong answers. Surfacing, not
   correctness, again.
3. **R3 fails: the delivery pattern is 35 of 36.** The single discordance is one-way:
   the prompt that was silent in round 31 (D2 arm X, digest `e21833ff126f`, truncated at
   exactly 2048) delivered this time (803 tokens, correct). Discordance b = 1, c = 0,
   exact McNemar p = 1.0.
4. **R4 fails on the depth slope: the cost law moved within the run.** Load slope at
   k = 8: -5.19 (band [-12.02, -3.005], inside). Per-hop slope at E = 96: -9.48 (band
   [-54.26, -13.565], outside; reference -27.13). With no truncation in this run the
   scored uncensored basis and the all-cell variant coincide. The noise-guard verdict
   fires: the cross-class slope gap between round 31 and round 24 (recomputed ratios:
   load -1.31, depth -0.22) is not separable from run-to-run variation on this class
   (this run against round 31: load ratio 0.86, depth ratio 0.35).
5. **R5 passes: the non-enumerating signature is stable.** Grid-mean distractor-mention
   ratio 0.0, all six cells 0.0, exactly round 31's class signature.
6. **R6 fails: the per-prompt length structure did not repeat.** Spearman 0.17 against
   round 31 (floor 0.80; Pearson 0.01). One of 36 prompts is token-identical to round
   31; 27 of 36 moved more than 20 percent; median relative deviation 0.61, p90 3.95,
   max 6.13. The grid mean, however, repeats: 598.1 vs 604.6 (ratio 0.99).
7. **R7 passes:** 36/36 prompt digests and 6/6 pool blobs equal the round-24 gate.
8. **R8 context:** join against the round-24 archive: 35 comparable, all agree (rate
   1.00). Independent recomputation: round 31 load slope -6.0104 (published -6.01),
   depth slope -27.125 (published -27.13); round 24 load slope +7.8854 (published
   +7.885), depth slope +6.05 on the uncensored basis against the published all-cell
   +29.36 (a documented estimator-basis difference, issue #100).

Budget replay (character-proportional estimate): 15/36 answers surface at 256 tokens,
24/36 at 512, 33/36 at 1024, 36/36 at 2048. No content-silent cells in this run, so the
#94 fallback-provenance section is vacuous here: no trace token on any prompt (`no_trace_token`
on all 36 records).

Per-cell mean completion tokens, this run vs round 31 vs round 24: L0 758.8 / 611.5 /
1171.8; L1 336.0 / 665.2 / 1105.5; L2 632.5 / 483.0 / 1392.7; L3 309.0 / 269.7 / 1615.8;
D1 869.0 / 503.0 / 1196.0; D2 683.0 / 1095.2 / 1406.7. Round 31's P6 anchor (the L0 arm-F
prompts delivering "yes" at 196 / 1024 / 191 tokens, a 4-5x cheaper enumeration than
round 24) did not repeat: L0 arm F is 1024 / 272 / 1031 this time.

## What this means for the program

- On this class, the answers and the class-level enumeration style are stable across runs
  (R2 and R5 pass; 36/36 correct in both runs), while the delivery surface at the
  turnover cell and the per-prompt length structure are not (R1, R3 and R6 fail). On the
  flash-next class (round 33) both were stable: the same silent digest in two runs and
  32 of 36 token-identical completions. The stability of the surfacing collapse is
  itself a class-level property.
- Consequence for #100: the per-class self-agreement control now exists for both classes,
  and on this class a single-run n=6 verdict surface is NOT a repeatable measurement: the
  (16, 96) turnover round 31 confirmed here did not hold on re-run, and the class-level
  cost-law claim is not separable from this class's run noise (the guard verdict fired).
  The archived ceiling at (16, 96) now stands on two agreeing runs on the flash-next class
  and two DISAGREEING surfaces on this class.
- Consequence for #94: round 31's no-trace-token provenance class for the silent cell is
  not re-testable in this run (no silent cell); the readout stack reported cleanly on all
  36 prompts.
- Consequence for #71: on this class the frontier has moved past (16, 96): k = 16 at
  E = 96 is now maintained, so d* on this class is not placed at k = 16, E = 96; the
  depth ceiling stays open on this class.
- The public record does not establish whether the round-31 and round-37 firings used the
  same inference host; the same-class claims do not depend on host identity.

State: **Executed** (no independent verifier pass; the selftest certifies the instrument's
controls, the digest-true replay and the archive-side estimator audit).

## Reproducing

Point `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID` and `NIGHTLY_API_KEY` at a 27B-class
NVFP4/vLLM endpoint and run, in order:

    python3 sameclass_frontier_retest_probe.py --selftest
    python3 sameclass_frontier_retest_probe.py --gate --out gate.json
    python3 sameclass_frontier_retest_probe.py --probe --out-dir .
    python3 sameclass_frontier_retest_probe.py --analyze

`--probe` resumes from `raw.jsonl` under a matching gate hash; `--analyze` reproduces
`summary.json` from the archived raw records.
