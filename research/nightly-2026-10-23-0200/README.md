# Round 19 (2026-10-23 02:00): the budget elasticity of answer surfacing at fixed depth

Branch `research/nightly-2026-10-23-0200` (stacked on round 18 so the round-15/16/17 archives
are in-tree as the pairing anchor). Endpoint: a flash-next-class local endpoint (the class
rounds 15 and 17 measured). Evidence label: **Executed** - no independent verifier pass this
round. Serves issue #71 (its option 3, the budget-controlled arm), #78 (instrument validity),
#73 (transport), #65 (tracker).

## Question

Rounds 15 and 17 recorded 36 of 36 correct on this endpoint class at `max_tokens = 2048`,
but the archived `answer_source` fields show that every level-24 R1 and X answer came from the
declared parser's reasoning fallback (round 15 and round 17: R1 3 of 3 and X 3 of 3 from
`reasoning`, F1 and F2 from `content`). Round 17 next-step 1 names the instrument gap: make
answerability observable without the rescue convention. Round 6 measured a budget ladder on the
single-query family (26 of 40 lost at 256 tokens, 12 at 512, 4 at 1024) but arm-blind and before
the issue #69 repair.

This round inverts the treatment used in rounds 17 and 18: **depth is fixed at k = 24 and the
output budget is varied**. The nine level-24 cells (arms F1 forward, R1 reverse, X
cross-component; 3 items each) are dispatched at `max_tokens` in {256, 640, 1280, 2048} at
temperature 0. Question: **how does answer surfacing depend on the output-token budget, and how
much budget does surfacing need beyond the budget the reasoning itself needs?**

Declared in the gate before any prompt was spent:

| # | Prediction |
|---|------------|
| P1 | within an arm, the count of cells with a parseable yes/no in the answer field is non-decreasing across 256, 640, 1280, 2048 |
| P2 | at 2048, F1 surfaces 3 of 3 and X surfaces 0 of 3 (the round-17 signature), and F1 surfaces at least as often as X at every budget |
| P3 | every answer-field answer is correct at every budget: the budget moves surfacing, not correctness |
| P4 | for every cell, the smallest budget carrying a reasoning-field answer is no larger than the smallest budget carrying an answer-field answer |
| P5 | the 2048 rung reproduces round 17's declared answer on all nine cell-paired cells |

## Gate (before any prompt was spent)

`gate.json`, gate hash `407339131d62`, schema `round19-gate-v1`. `--selftest`: 98 checks,
0 failures.

- Corpus identity: generator sha256 `b0d77efd...` (the issue #69 repair on `main`), 300 pool
  items at level 24 from seed_base 20261019, blob pin `cab16fae...` byte-identical to the
  round-15/16/17/18 pins, double-generation determinism verified, gold labels recomputed on the
  whole pool (0 mismatches).
- Matchedness: prompt length, endpoint name multiset, endpoint degree profile and undirected
  distance matched inside the direction family; connectivity differs inside the component
  family. Connectivity and reachability disagree in exactly the three R1 cells.
- Leak battery on the nine dispatched cells (blind lexical rules, two-sided exact tests,
  Bonferroni alpha 0.0071): no rule fires (best 0.778, `src_mentioned_after_dst`); the
  reachability oracle scores 9 of 9 and the connectivity oracle 6 of 9, failing exactly the R1
  cells; a planted-leak control confirms the battery fires when a shortcut exists.
- Pairing, fail-closed: **9 of 9 prompt sha256 equal round 15's archived cells and 9 of 9 equal
  round 17's**; `--probe` refuses to spend a prompt when pairing is unverified.
- Caps: 36 prompts + 1 health check = 37 of the 40-call round cap; `max_tokens <= 2048`.

## Probe

`surfacing_budget_curve.py`, stdlib only. 36 prompts (9 cells x 4 budgets), temperature 0,
two-phase transport per issue #73: two cells sequentially to measure throughput (walls 7.452 and
7.296 s, about 35 tokens/s), then the rest at concurrency 4. Per-item deadline 900 s. Retry
policy inherited from round 17: truncation and model stops are measured outcomes and are never
retried; only transport failures and empty completions are.

**Endpoint calls: 37 (36 cells + health). Zero retries, zero transport failures, zero abandoned
cells. Wall 504.1 s.** Seven cells of the 256-token rung were written by a first dispatch that
was interrupted by the runner; the round was completed with `--probe --resume`, which requires
gate-hash equality, so all 36 records sit under one gate.

## Answer

**Surfacing is monotone in budget, and at k = 24 the two negative arms never fill the answer
field at any budget up to 2048.**

Answer-field counts (cells with a parseable yes/no in the answer field) across the ladder:

| Arm | 256 | 640 | 1280 | 2048 | Correct among surfaced |
|-----|-----|-----|------|------|------------------------|
| F1 forward | 0 of 3 | 0 of 3 | 3 of 3 | 3 of 3 | 6 of 6 |
| R1 reverse | 0 of 3 | 0 of 3 | 0 of 3 | 0 of 3 | 0 |
| X cross-component | 0 of 3 | 0 of 3 | 0 of 3 | 0 of 3 | 0 |

The declared parser reports 9 of 9 answered at every rung (9 rescued from the trace at 256 and
640, 6 at 1280 and 2048) and 5, 7, 9, 9 correct across the rungs. Answer-field-only accuracy
over the 36 cell-budget pairs is 6 of 36 = 0.167. So the declared parser reports complete
answerability at 256 tokens, where no answer had surfaced at all.

Where the budget goes: F1 stops early once it has the chain (648 to 720 completion tokens at the
1280 and 2048 rungs, mean 684.7; the 640 rung truncates it at traversal coverage 0.96), while R1
and X consume the entire budget at every rung (mean completion equals the budget exactly) and are
still enumerating fact lists at the cutoff. 24 of 36 cell-budget pairs carry a correct yes/no in
the trace and none in the answer field. With four rungs spaced by doubling, the extra budget
surfacing needs is bracketed, not measured: for F1 it lies between 640 and 1280 tokens.

Predictions: **P1 holds** (0, 0, 3, 3 / 0, 0, 0, 0 / 0, 0, 0, 0); **P2 holds** (F1 3 of 3 and
X 0 of 3 at 2048, F1 >= X at every rung); **P3 holds** (no answer-field answer was wrong at any
budget); **P4 holds but is weak** - only 1 of 9 cells has both thresholds, so the
trace-before-surface ordering is barely tested; **P5 holds on declared answers** - at the 2048
rung all 9 cell-paired declared answers reproduce round 17, no discordant pair in either
direction, exact McNemar p = 1.0. Length reproduction is **not testable** against that archive:
it stores no per-cell completion counts (the gate field `round17_completion_tokens` is null for
all nine cells), so P5 is a claim about answers, not about token counts. Within this round the
2048 rung does reproduce the 1280 rung cell for cell: F1 stops at 720, 686 and 648 completion
tokens at both rungs, R1 and X sit at the ceiling at both.

## The readout control (post-hoc, declared as post-hoc)

The first dispatch cells showed that a 256-token trace already classifies as answered-in-trace,
so the analysis adds two controls for what a trace yes/no is worth. Both are post-hoc: the five
gate predictions above are unchanged by them.

1. **Provenance of the last trace yes/no** (`trace_token_provenance_post_hoc`): 7 of 36 records
   are literal instruction echoes inside a "yes/no" or "yes or no" phrase (median position 0.024
   of the trace), 18 are mid-trace mentions (median 0.717), 11 are terminal (median 0.995).
2. **A strict commitment rule** (`strict_commitment_post_hoc`): a trace token counts only when it
   sits outside an echo phrase and either closes the trace or is cued by an answer word within 30
   characters and closed by punctuation. "No other incoming." fails, "Thus yes." passes.

The loose readout carries no information on this grid: **34 of 36 records yield "no", and its
accuracy is 24 of 36 = 0.667, identical to the constant-"no" baseline (gold is "no" in 24 of 36
pairs, 0.667)**. The strict rule keeps 13 of 36 records and **all 13 agree with the gold label**:
F1 7, R1 6, **X 0 at every budget**. On this class at k = 24, R1 commits to the correct "no"
inside the trace (6 of 12 pairs) but never emits it; X never commits anywhere in the trace, so its
recorded correctness in earlier rounds is the constant-"no" coincidence, not a computation.

Consequence for the archive, stated precisely: at k = 24 on this endpoint class the
traversal-versus-connectivity discrimination was carried by fallback tokens (rounds 15 and 17 both
score R1 3 of 3 and X 3 of 3 from `reasoning`), and a constant-"no" predictor reproduces those six
cells. The identical k = 24 grid on the 27B-class endpoint (rounds 16 and 18) answers R1 from
`content` 3 of 3, so at that level the direction-family claim is currently supported by surfaced
answers only on the 27B class. Positive arms are unaffected: F1 and F2 surface in `content` on
both classes.

## Adjacent literature (free scholarly APIs, abstract-level, 2026-10-23)

14 free-API calls in total: 12 by the literature scan (sequential, single-phrase, arXiv export
HTTPS, Crossref, OpenAlex filters) plus 2 spot-verification calls by the round agent - two over
the round's 12-call cap, disclosed. No hosted search or completion provider.

- **arXiv:2601.03914** Wong et al., "When Models Decide and When They Bind: A Two-Stage
  Computation for Multiple-Choice Question-Answering" (2026, preprint, comment "Under review";
  API-verified by the round agent). Probing plus causal interventions: the winning content
  position is linearly decodable right after the last option is read, the output symbol is
  represented only near the answer-emission position, and MCQA accuracy conflates reasoning
  errors with symbol-binding failures. The closest mechanistic analogue to computed-but-unsurfaced.
- **arXiv:2607.11089** Ehab et al., "OS-Pruner: Pruning Chains-of-Thought of Reasoning Models via
  Optimal Stopping" (2026, preprint; API-verified) and **arXiv:2506.13752** Li et al., "Steering
  LLM Thinking with Budget Guidance" (2025, preprint): both presuppose a determinable moment where
  the answer is ready before generation ends. Round 17 measured such a moment on this class (median
  commitment at 0.4571 of the reasoning stream, max 0.9996); this round's strict-commitment
  landmarks sit later (median 0.717 mid-trace, 0.995 terminal). Neither thread asks whether the
  answer stopped at is ever emitted, which is what this round measured.
- **DOI 10.18653/v1/2025.emnlp-main.504** Tutek et al., "Measuring Chain of Thought Faithfulness
  by Unlearning Reasoning Steps" (EMNLP 2025, peer-reviewed): the causal template for deciding
  which trace steps the emitted answer actually depends on.
- **DOI 10.18653/v1/2025.findings-naacl.193** Liu et al. (Findings of NAACL 2025,
  peer-reviewed): logical problems with many premises in context; brittleness to disorder and
  irrelevant premises - support for premise count and ordering, not hop depth, driving difficulty.
- **arXiv:2505.05410**, "Reasoning Models Don't Always Say What They Think" (2025, preprint as
  fetched; API-verified by the round agent): the objection this round must carry - traces
  frequently fail to report the process that produced the answer, so a mid-trace yes/no needs an
  independent validity check instead of being read as the model's answer.
- Novelty boundary: the shared-budget crowding-out effect is already published as
  **arXiv:2605.07686** ("the coupling tax", found in round 17). This round claims the localisation
  and readout-validity result, not the budget effect, and the budget-forcing/overthinking area is
  occupied.

## Disclosure and limits

- State **Executed**: no independent verifier pass, and no second implementation.
- n = 3 items per arm, one endpoint class, one run: exploratory, not confirmatory. Not H1
  evidence (undisclosed training data, quantized local deployment).
- The provenance classes and the strict commitment rule are **post-hoc**, added after the first
  cells showed a 256-token trace already yields a yes/no. They are labeled `declared_post_hoc`
  in `summary.json` and do not alter the five gate predictions.
- The gate was written before dispatch and is unmodified afterwards (`load_gate` refuses a gate
  whose recomputed hash differs). The dispatch code was not changed between the interrupted first
  run and the resumed completion; the added functions are analysis-only, and `--selftest` and
  `--analyze` were re-run at the final HEAD, so `summary.json` is the output of the committed
  code over the committed `raw.jsonl`.
- Four budget rungs spaced by doubling bracket the surfacing threshold; they do not measure it.
- Self-audit after posting (2026-10-23): the first version of this record claimed cell-level
  completion-token reproduction against round 17 and attributed round 17's 0.457 commitment median
  to this round. Both are corrected above. No measurement, gate or artifact changed; the #65
  summary comment and the PR body carry the same correction.
- Prompt load and chain depth stay coupled at k = 24 (issue #71 option 2 remains open).
- A reasoning-field yes/no is the last such token in a still-running trace. Treating it as the
  model's answer is a convention; this round measures the cost of that convention instead of
  assuming it away.

## Reproduce

```
python3 research/nightly-2026-10-23-0200/surfacing_budget_curve.py --selftest
python3 research/nightly-2026-10-23-0200/surfacing_budget_curve.py --gate   # writes gate.json
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
  python3 research/nightly-2026-10-23-0200/surfacing_budget_curve.py --probe
python3 research/nightly-2026-10-23-0200/surfacing_budget_curve.py --analyze
```

The script reads the endpoint from the environment and writes no endpoint value anywhere; stored
model text passes a sanitizer for URLs, IP addresses and absolute paths. Pairing against the
round-15 and round-17 archives is verified before any prompt is spent. `raw.jsonl` is 36 records
(one per cell-budget pair), `summary.json` carries the aggregates, `transport.json` the dispatch
mechanics.
