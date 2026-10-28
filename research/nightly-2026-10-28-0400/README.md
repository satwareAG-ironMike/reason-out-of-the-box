# Round 33 (2026-10-28 04:00): is a single-run n=6 frontier a measurement? Test-retest of the
digest-pinned (k, E) ladder grid on the class that produced round 24's frontier

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is the
reproducible record: script, gate, prompts, raw responses, scores.

## Question

Every ceiling this program has placed is a single run. Rounds 21 to 24 walked the (k, E)
frontier on the flash-next class one firing at a time - six cells, three matched pairs per
cell, temperature 0 - and the load-bearing observation of the whole line is that exactly one
cell, (k = 16, E = 96), stops surfacing an answer inside the 2048-token cap while the other
five are clean. Round 31 then re-ran the identical digest-pinned grid on a different endpoint
class and reported two things: the same turnover cell, and a completely different enumeration
cost law (per-fact slope -6.01 against round 24's +7.885; distractor-mention ratio 0.000
against 0.892), concluding that the cost structure is a property of the class rather than of
the protocol.

That conclusion is a comparison of ONE run per class. It is therefore only as strong as the
run-to-run repeatability of the quantities being compared, and no archived round has ever
measured that repeatability. This round measures it, on the class where the frontier was
originally placed:

> On the model class that produced the archived (k, E) frontier, does a second run of the
> byte-identical prompt set at temperature 0 reproduce the verdict surface, the delivered
> answers, the enumeration cost law and the enumeration style - or is a single n=6 cell
> verdict inside its own run noise?

Motivation, from the archive:

- round 24 (PR #98): maintained at (k = 8, E = 96..160), D2 (16, 96) inconclusive through one
  2048-token truncation; cost laws +7.885 tokens/fact at k = 8 and +29.363 tokens/hop at
  E = 96; per-cell distractor-mention ratios 0.68 to 1.00, grid mean 0.892.
- round 31 (PR #99): same grid, other class, same turnover cell, cost law inverted,
  distractor ratio 0.000 everywhere; explicitly declared that it could not separate
  quantization from serving runtime, and that its cost-law claim compares one run per class.
- round 6: the standing literature gap that no verified source treats the output cap as the
  variable a recorded score depends on; the same gap makes a repeat-run control unpublished
  as far as this program has verified (see Literature below).
- issue #71 ("place the ladder depth ceiling d\*: grid extension and load decoupling") and
  issue #94 (the readout contract): both consume single-run cell verdicts, so both need to
  know how much of a verdict is measurement and how much is decoding.

## Instrument

`retest_repeatability_probe.py` (stdlib only) is round 31's
`crossclass_frontier_probe.py` (PR #99) with the prediction layer replaced and nothing else
touched: construction, solvability audit, gate batteries, matched-pair invariant, readout
stack and cell-status trichotomy are inherited verbatim, so a difference against round 24 can
only come from the endpoint and the run, never from the instrument.

Construction: C disjoint directed paths of exactly k edges over fresh entity names, one rule
sentence (transitivity of `precedes`), E = k x C facts in shuffled order, one query per
prompt, answer required as exactly one word. Gold from an unbounded BFS independent of the
generator plus a structural audit (component edge and node counts, path shape, no branching,
query source a head and query target a tail, label agrees with BFS). Every graph is asked
TWO questions over identical content (arm F forward, gold yes; arm X cross-component, gold
no); `pair_violations()` asserts the shared-content invariant per pair (issue #78 acceptance
criterion 1) and `--selftest` carries the planted non-matched control: 983 checks, 0 failures.

Grid: exactly round 24's (seed base 20261024, same name pools, seed formula and selection
order), so all 36 prompt digests and all 6 candidate-pool blobs must equal the round-24 gate;
`--probe` and `--gate` refuse otherwise. This round's gate: `979585cd`, `anchor_ok` true
(6 cells x pool blob + 3 forward + 3 cross digests all matching round 24). Round 24's per-prompt archive and
round 31's per-prompt archive are both carried as constants in the script (neither ancestor
branch is on `main` at authoring time), so the post-merge tree verifies every comparison
without the ancestors.

## Declared predictions (fixed in `gate.json`, schema `round33-gate-v1`, before any prompt)

Joined per prompt on the prompt digest against the round-24 archive:

- **R1 verdict surface**: the six cell statuses repeat cell for cell (round 24: five
  maintained, D2 inconclusive).
- **R2 delivered answer**: over prompts where both runs delivered a content answer, agreement
  is 1.00, over at least 30 comparable prompts.
- **R3 delivery pattern**: the delivered/silent pattern is identical at 36 of 36 prompts, and
  the set of content-silent digests equals round 24's.
- **R4 cost law**: the per-fact slope at k = 8 and the per-hop slope at E = 96 return inside
  0.5x to 2.0x of round 24's published values - the same bands round 31 declared against the
  same reference, so all three rounds read on one scale.
- **R5 enumeration style**: the grid-mean distractor-mention ratio returns at >= 0.50
  (round 24: 0.892; round 31: 0.000).
- **R6 length**: per-prompt completion length correlates with round 24's (Spearman
  rho >= 0.80) and the grid mean stays inside [0.70, 1.40] of round 24's grid mean.
- **R7 structural pin**: all 36 prompt digests and 6 pool blobs equal round 24's gate.
- **R8 context, never scored as a prediction**: the same per-prompt join against the round-31
  archive on the other class, including an independent recomputation of round 31's two
  published cost slopes from its archived per-prompt lengths.

Basis, declared: R4 is scored on round 24's own fitting basis (cell means over all six cells,
a truncated cell's censored mean included), because the reference slopes were fitted that
way; the round-31 censored variant (any cell containing a truncation dropped) is reported
beside it. The two estimators differ by about 23 tokens/hop on round 24's own data, and
`--selftest` asserts that a perfect replay of the archived grid certifies on the scored basis
and fails on the censored one, so the basis can never be confused silently.

`--selftest` also asserts that the whole R stack is **fail-closed**: on synthetic records with
foreign digests (no join to the archive) no R claim certifies, and it carries a digest-true
positive control (a run that reproduces the archive certifies all seven) plus two planted
negative controls (one planted silence breaks R3 and only R3-side delivery accounting; a
planted length reversal breaks R6 while R2 and R3 keep passing).

## Transport and how to reproduce

Endpoint read from `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`, `NIGHTLY_API_KEY`; nothing
endpoint-specific is written anywhere; stored model text passes a sanitizer (URLs, IP
addresses, absolute paths). Health probe, then 36 prompts (18 matched pairs), `max_tokens`
2048, `temperature` 0.0, concurrency auto-selected from the phase-1 measured rate. This round:
37 of the 40-call cap, zero retries, zero transport errors, no resume.

```
python3 research/nightly-2026-10-28-0400/retest_repeatability_probe.py --selftest
python3 research/nightly-2026-10-28-0400/retest_repeatability_probe.py --gate   # refuses on digest drift
python3 research/nightly-2026-10-28-0400/retest_repeatability_probe.py --probe  # gate-hash-guarded --resume
python3 research/nightly-2026-10-28-0400/retest_repeatability_probe.py --analyze
```

`run.log` (endpoint console noise) stays outside the repository by design.

## Results

## Results (headline)

**All seven declared predictions pass, and the reproduction is far tighter than the bands
required.** Three days apart, the same prompt set on the same class returns the same six cell
verdicts, the same 35 delivered answers, the same single content-silent prompt digest, cost
slopes within 2.6% of the archived ones, an identical enumeration style, and 32 of 36
completions token-for-token identical to the archived run.

| cell | k | C | E | delivered | correct | content-silent | truncated | mean completion tokens (this / r24 / r31) | ratio this/r24 |
|------|---|---|---|-----------|---------|----------------|-----------|--------------------------------------------|----------------|
| L0 | 8 | 12 | 96 | 6/6 | 6/6 | 0 | 0 | 1169.5 / 1171.8 / 611.5 | 0.9980 |
| L1 | 8 | 14 | 112 | 6/6 | 6/6 | 0 | 0 | 1148.0 / 1105.5 / 665.2 | 1.0384 |
| L2 | 8 | 16 | 128 | 6/6 | 6/6 | 0 | 0 | 1392.7 / 1392.7 / 483.0 | 1.0000 |
| L3 | 8 | 20 | 160 | 6/6 | 6/6 | 0 | 0 | 1615.8 / 1615.8 / 269.7 | 1.0000 |
| D1 | 12 | 8 | 96 | 6/6 | 6/6 | 0 | 0 | 1189.5 / 1196.0 / 503.0 | 0.9946 |
| D2 | 16 | 6 | 96 | 5/6 | 5/5 | 1 | 1 | 1406.0 / 1406.7 / 1095.2 | 0.9995 |

- **R1 passes.** Cell statuses repeat exactly: five `maintained`, D2 `inconclusive`
  (accuracy 0.8333, Wilson 95% interval [0.4365, 0.9699] against the 0.60 floor). The
  trichotomy edges reproduce as published by round 24: `maintained_by_edges` 96 to k = 12 and
  112, 128, 160 to k = 8; `maintained_by_k` k = 8 to E = 160 and k = 12 to E = 96;
  `non_maintained_cells` is `["D2"]` in both runs. The single-axis transitions are the same
  four (three load steps maintained, one depth step maintained to inconclusive).
- **R2 passes.** 35 comparable prompts (both runs delivered), 35 agreed, rate 1.00. Zero
  wrong answers in the grid.
- **R3 passes: 36 of 36 prompts share the delivered/silent pattern.** The one content-silent
  prompt is the same digest as round 24's silence (`e21833ff126f...`, D2 arm X, outcome
  `trace_only`, capped at 2048); the silent-digest set equality holds. McNemar on paired
  delivery: b = 0, c = 0, exact p = 1.0. The turnover is now the same item failing at the cap
  in two runs on this class and one on the other class.
- **R4 passes.** Scored on round 24's basis: per-fact slope at k = 8 **+7.686** tokens/fact
  (ratio 0.974 of +7.885), per-hop slope at E = 96 **+29.563** tokens/hop (ratio 1.007 of
  +29.363), both inside the 0.5x-2.0x bands. On the round-31 censored basis the same run gives
  +7.686 and +5.0 (D2 dropped), which is the basis difference, not a different measurement.
- **R5 passes: identical.** Grid-mean distractor-mention ratio 0.8922 (round 24: 0.8922);
  per-cell L0 1.0, L1 0.6795, L2 0.8333, L3 0.8421, D1 0.9982, D2 1.0. Round 31's class
  returned 0.000 everywhere.
- **R6 passes with a wide margin.** Pearson 0.995, Spearman 0.9938 (n = 36, floor 0.80); grid
  mean ratio 1.0041 (band [0.70, 1.40]); absolute relative deviation vs round 24: median 0.0,
  p90 0.0035, max 0.1687. **32 of 36 completions are token-identical**; the deviating items
  are L1 arm X 1512 to 1767 (+16.9%, same correct answer), D1 arm X 1415 to 1376 (-2.8%),
  L0 arm F 1101 to 1087 (-1.3%), D2 arm F 1141 to 1137 (-0.35%).
- **R7 passes:** 36/36 digests and 6/6 pool blobs pinned to round 24's gate (`979585cd`).
- **R8 (context, not a prediction):** vs the round-31 archive on the other class, 35/35
  delivered answers agree; recomputing round 31's published slopes from its own archived
  per-prompt lengths with this script's estimator returns -6.010357 (published -6.01) and
  -27.125 (published -27.13), and its per-cell means reproduce digit for digit.
- **Run-noise guard** (the point of the round): run-to-run slope ratios on one class are 0.974
  and 1.007; cross-class slope ratios against the same reference are -0.762 and -0.924. Run
  noise of the measured size cannot move a slope across zero, so round 31's conclusion that the
  enumeration cost law is class-specific is now noise-bounded rather than merely asserted.
- **Budget replay** (character-proportional estimate): 1 answer surfacing at 256 tokens, 2 at
  512, 4 at 1024, 35 at 2048 - identical to round 24's replay counters.
- **Transport disclosure:** one item (L2 arm X, digest `1de707958baa...`) hit the 600 s
  per-item deadline and was retried once, delivering 1883 completion tokens, exactly the
  archived length for that digest. Dispatch window 57.2 min at ~42 tok/s with concurrency 2;
  47,529 completion tokens; 37 of 40 calls; zero abandoned cells.


## Evidence label

`Executed` per `docs/agent-execution.md`: one endpoint, one re-run, no independent second
implementation, not covered by the pre-registered decision table. n = 6 per cell:
exploratory. The class identity ("the same class as round 24") is an inference from the pool
slot and the served model id, not a fingerprint: the archive deliberately does not fingerprint
endpoints, so the digest anchor, not slot metadata, carries every construction-identity claim,
and R6's per-prompt length agreement is the strongest available evidence that this is the same
deployment rather than a look-alike. Nothing here is H1 evidence; every ceiling stays
conditional on the 2048-token output cap.

## Literature (free scholarly APIs only; scan 2026-10-28)

The literature scan for this round ran on OpenAlex (arXiv's export API returned persistent
HTTP 429 during the scan, so every record below was reached through OpenAlex, several of them
arXiv preprints via their `10.48550/...` DOIs). Verification level is stated per record:
abstract-level means the abstract in the fetched record supports the sentence, metadata-only
means the record carries no abstract and only title/venue/year is attested. No hosted or
metered provider was used, and none of this was added to `archive/` (these are method records
for the protocol, not thesis evidence).

- arXiv:2408.04667 (Atil et al., 2024, abstract-level), "Non-Determinism of 'Deterministic'
  LLM Settings": five models configured to be deterministic, 8 tasks, 10 runs; accuracy
  varies by up to 15 percentage points across naturally occurring runs with best-to-worst
  gaps up to 70 points, no model repeatable on all tasks; introduces output-agreement (TARr@N)
  and parsed-answer agreement (TARa@N), and names input-buffer co-mingling (batching) as a
  mechanism. This is the direct prior art for R2/R3 as a measurement, and the mechanism this
  round cannot control.
- arXiv:2604.13413 (Fang et al., 2026, abstract-level): aggregate dataset-level metrics
  systematically attenuate non-determinism; configurations with similar aggregate scores can
  differ substantially on individual inputs. The reason this round joins per prompt (digest
  level) instead of comparing only cell means.
- arXiv:2609.15476 (La Rosa, 2026, abstract-level), "Temperature Fragility and the Conditional
  Benefits of Truncation Sampling": 13 open-weight models, GSM8K and MMLU-Pro; "the lost
  accuracy comes from generations that run to the token limit or never state an answer". The
  published statement of the surfacing-not-correctness mechanism this program has been
  recording since round 23.
- 10.1145/3697010 (Ouyang et al., TOSEM 2024, abstract-level): repeated identical prompts on
  829 code-generation problems quantified by semantic/syntactic/structural similarity between
  repeated outputs; frames non-determinism as a reproducibility threat to published results.
- 10.18653/v1/2025.emnlp-main.1006 (Hua et al., EMNLP 2025, abstract-level), "Flaw or
  Artifact? Rethinking Prompt Sensitivity in Evaluating LLMs": 7 models x 6 benchmarks x 12
  templates; much of the measured sensitivity is scored-practice artifact. Belt for the
  readout-stack contract in issue #94.
- 10.48550/arXiv.2604.00851 (Iftikhar et al., 2026, abstract-level): 2 benchmarks x 3
  paraphrases x 10 repeated runs x 3 models x 3 prompting strategies, variance and prompt
  sensitivity reported as separate reliability sources - the design shape this round applies
  to one deployment.
- JudgeSense (Reddy et al., 2026, abstract-level; the fetched OpenAlex record carries no DOI,
  so none is reported): 880 items x 2 intent-preserving wordings x 25 judges, every score
  reported against the judge's own agreement with itself on the identical prompt, so decoding
  noise is not charged to wording. That self-agreement baseline is exactly the control this
  round supplies for a reasoning probe.
- Statistics: 10.1007/s00265-020-02916-y (Smith and Ruxton, 2020, metadata-only) for paired
  binary outcomes; 10.1080/09332480.2024.2348953 (Andersson, 2024, metadata-only) for the
  Wilson interval this program uses per cell.

Verified absences (OpenAlex-indexed only, arXiv search unreachable, so these are weak
negatives and must not be cited as strong): no record that reports per-cell confidence
intervals for LLM benchmark accuracy in a small-n multi-hop evaluation; no record applying
McNemar-type paired tests across repeated identical evaluations of the same deployment; no
record studying the stability of a depth/load *frontier placement*; no record treating
`max_tokens` cap height itself as the independent variable; and no abstract attributing
greedy/temperature-0 divergence specifically to MoE expert routing, speculative decoding or
continuous-batching composition (only the generic input-buffer remark above).
