# Nightly round 87 (2026-11-25 02:27, nightly lane, issue #65): the chance floor under the M2 depth ceiling

Evidence label: `Executed`, exploratory. **No dispatch arm ran**: the frozen pre-dispatch
rate gate (row G8) refused the panel. Model class: a locally served flash-class reasoning
endpoint, `exploratory_only_model_class` per `evaluation/frozen/pins.json`; build pin
`model_digest` `c62b81e96826354e`. No confirmatory cell: that track stays blocked at issue #196.

Gate: `gate.json`, blob `c70231ac4cd8ffba`, frozen before any prompt was spent;
re-emitted 2026-11-26 after the verdict-directed instrument cleanup (disclosed
below): the unregistered `solve_all_but_one` diagnostic was dropped from the
gate body - registered rows G1-G8, `signal_rule` and every offline-baseline
value are byte-identical to the original freeze (blob `e28654b3085a8628`).

## Question

The 2026-11-24 M2 exit gate (landing commit `8cdc0e9`) reports a d\* depth grid -
"levels 1-4 x 3 items ... 1/3 at level 1, 0/3 at levels 2-4, all deliveries parsed" - and
marks "d\* established MET", which is what makes M2 GO-able. Can a 3-items-per-level,
8-option digit-matrix grid separate competence from guessing at all, and what does the
shipped instrument actually record?

Why this question: it is the freshest load-bearing gate claim on `main`, every part of it is
checkable against archives the repository already carries, and the M3 commitment is now
conditional on it. `docs/agent-execution.md` requires an independent confrontation pass on a
gate claim before milestone spend.

## Method

- **Lens 1, record audit (no prompts).** The landed pilot archive
  `runs/p8-pilot-2026-11-24-olmo32b-pythia28b/raw.jsonl` (12 records, on `main`) against the
  shipped harness `harness/harness_run.py` + `harness/config.json` and the frozen judge
  `evaluation/frozen/verify.py` + `rule.json`.
- **Lens 2, floor arithmetic (no prompts).** Exact content-free floor of an 8-option grid at
  pilot n; exact two-sided binomial and Wilson 95% interval; and the family's structural
  floors on a fresh 30-item set (digit matrices levels 1-2, n = 15 per level, seed base
  20261125, the fresh-seed date policy): best constant-answer floor, one-component
  partial-solver floor under a fixed random tie-break and under lowest-index tie-break, and
  the mean number of options carrying the gold digit at a single component. All of it is
  frozen in `gate.json` (`offline_baselines`) before dispatch.
- **Lens 3, replication arm (registered, not run).** 30 items at `max_tokens` 1,024,
  temperature 0.0, the frozen judge's own `build_prompt` / `extract_answer` /
  `score_record` / `solve_digit_matrices`, plus two byte-identical re-dispatch controls
  (issue #100). Selected only if the pre-dispatch rate cleared row G8.
- Instrument: `chance_floor_r87.py`, stdlib only, `--selftest` 18 checks / 8 negative
  controls, `--check-readme` (issue #137). Reproduce: `--selftest`, then `--freeze-gate`,
  `--health`, `--census`, `--dispatch`, `--score`.

## Registered rules (gate.json)

| Row | Rule |
|-----|------|
| G1_chance_floor | content-free floor per level: best constant option index on the dispatched item set, reported next to the nominal 1/8 |
| G2_signal | signal at level L iff correct >= 5/15 AND Wilson 95 lower bound > the G1 floor AND exact two-sided binomial p vs 1/8 < 0.05 (p = 0.031073 at 5/15, 0.107785 at 4/15) |
| G3_d_hat | d_hat per `rule.json` `trained_depth`: mastery 0.80, greatest L with ACC >= 0.80 for every level <= L; `not_evaluable` when a level delivers nothing |
| G4_parse_integrity | count of judged option indices outside 0-7 (must be 0) and count of records whose judged letter also appears earlier in the completion |
| G5_delivery_census | counts per `DELIVERY_STATES` per level; n is the dispatched count |
| G6_determinism | the two byte-identical re-dispatches must reproduce the judged value; divergence flags `dup_pair_diverges` |
| G7_option_histogram | diagnostic only, no tier input: judged option-index histogram against the item key histogram |
| G8_rate_gate | pre-dispatch median completion-token rate selects the plan: >= 20 tok/s full (32 dispatches), >= 5 tok/s reduced (n = 8 per level, 18 dispatches), below that no dispatch |

## Results

### F1 The landed pilot archive contains no answer to score

All 12 records in `runs/p8-pilot-2026-11-24-olmo32b-pythia28b/raw.jsonl` carry
`finish_reason: "length"` (censored at 128 or 300 tokens). In every record the stored
`content` is a 300-character window of the item's own text - it holds the grid and the option
list - so the completion is a restatement of the question cut off by the cap. 6 of 12 have
`parsed_answer: null`; 2 have `parsed_answer: 47` on an 8-option item (valid indices are
0-7); the single `correct: true` record is a truncated echo whose last numeric token happened
to equal the gold index. `rule.json` `trained_depth.no_delivery_case`: "A censored arm is a
delivery failure, never a competence floor." The pilot is a delivery failure at 12/12.

### F2 The harness scores an unparseable answer as a wrong delivery

`harness/harness_run.py::parse_answer` returns the last all-digit whitespace token of the
completion and sets `correct = (parsed == answer_index)`. There is no delivery state, so an
out-of-range index is recorded as a wrong answer rather than as `non_answer`. The frozen
judge has the states (`DELIVERY_STATES`; `extract_answer` accepts only an A-H letter or an
exact option tuple) and the harness does not use them. The exit-gate sentence "all deliveries
parsed" is contradicted by the grid's own records: 3 of 12 carry an option index outside 0-7.

### F3 The landed grid is not reproducible from the shipped instrument

Rebuilding the arm-A and arm-B prompts for the landed items with
`harness/harness_run.py::grid_prompt` and `harness/config.json` gives `prompt_sha256`
`828aa443a8dca4d9` and `e9ee51a49c275299`; the landed records carry `0bee6c2bd77ae5e6`.
The shipped config's arm A is `max_tokens: 256`; the pilot manifest records 128. The harness's
digit-matrix suffix is "Answer with the option index number only." with numeric options, not
the frozen `matrix_missing_cell_v1` template (options A-H, "Answer with exactly one option
letter"). `harness/` is not listed in the root AGENTS.md Child DOX Index.

### F4 At pilot n the grid cannot separate competence from guessing

With 3 items and 8 options, some option index is the gold at least once, so the best
constant-answer strategy scores >= 1/3 by the pigeonhole principle. The grid's only non-zero
cell is exactly 1/3. The grid overall is 1/12 = 0.083, below the nominal 1/8 = 0.125. Exact
two-sided binomial for 1/3 at n = 3 against 1/8: p = 0.3301; Wilson 95% interval [0.0615,
0.7923], lower bound below the chance floor. Under `rule.json` `trained_depth` (mastery 0.80,
calibration n 40) the grid computes d_hat = 0, not 1: no level reaches 0.80 and the
calibration arm is defined at n = 40 per level, not 3.

### F5 The family's depth axis is not clean (frozen, measured pre-dispatch)

| Level | best constant floor | mean options matching one component | one-component floor (random tie-break) | one-component floor (index order) |
|-------|--------------------|------------------------------------|----------------------------------------|-----------------------------------|
| 1 | 0.2000 (index 1) | 1.00 | 1.0000 | 1.0000 |
| 2 | 0.2667 (index 7) | 4.27 (comp 0), 4.73 (comp 1) | 0.2667 / 0.0667 | 0.1333 / 0.0000 |

`generators/digit_matrices.py::_distractors` builds every wrong option by changing exactly one
component, so at level 2 about 4.5 of the 8 options carry the gold digit at any single
component. A solver that infers one component rule and ignores the rest reaches 0.267 at
level 2 with no second-rule competence, against a 0.125 nominal floor and a 0.267
best-constant floor on the same items. Level-1 accuracy above the constant floor is therefore
not yet evidence about simultaneous-rule depth.

### F6 The replication arm did not run (G8)

`health.json`: the issue #211 model-resolution precondition passes (registry present, size 1,
configured column resolves), trace exposed on `reasoning_content` (115 characters on the
probe). `measure.json`: pre-dispatch census median **4.6 completion tokens/s**, below the
registered 5.0 tok/s reduced-plan floor, so G8 selected `plan: none` and no prompt was spent
(3 of the 40-call cap used, 32 dispatches owed). These two files are the surviving failure
record, per the `research/AGENTS.md` rule that an arm that could not run keeps its record.

### F7 Literature (abstract-level; OpenAlex and arXiv export API only)

Option-ID preference is intrinsic and content-independent, traced to token-level probability
mass on option labels (Zheng, Zhou, Meng, Zhou, Huang, ICLR 2024, OpenAlex `W4386555476`);
option-order permutation alone moves MC scores (Pezeshkpour & Hruschka, Findings of NAACL
2024, `W4401043020`); a null-prompt probe measures a model's own lucky rate and equalizes it
(Jeong, Kim & Whangbo, arXiv 2025, OpenAlex `W4414886880`); "a model answering A to most items
scores above chance wherever the key sits at A, and reads as recognition when it is not" is
measured on 11,990 four-option items (Ovcharov, arXiv 2026, arXiv:2608.15428); pilot-scale
hypothesis testing is the standing methods caution (Arain et al., BMC Medical Research
Methodology 2010, DOI 10.1186/1471-2288-10-67). Searched for and not found: a power analysis
for items-per-difficulty-level in an LLM reasoning grid; d-prime or bias-corrected accuracy
applied to an LLM analogical-reasoning benchmark.

## Consequence for the M2 row

`d* established MET` is not what the frozen instrument computes from this evidence. The row
should read: d_hat `not_evaluable` on the pilot grid (12/12 censored, 6 unparsed, 3
out-of-range indices), d_hat = 0 under `rule.json` mastery 0.80, and M2 carries a second
blocker next to the corpus blocker - the depth measurement has to be re-run. The re-run is
specified: the frozen `matrix_missing_cell_v1` template, `extract_answer` with
`DELIVERY_STATES`, a `max_tokens` above the echo length, calibration n = 40 per level, and the
dispatched set's constant-answer floor reported as a baseline row.

## Limits

- No dispatched cell this firing: F1-F5 are record and arithmetic findings over archives the
  repository already holds, and F5 is a generator-side measurement, not a model measurement.
- The constant-answer floor is chosen after seeing the keys, so it is an upper bound on the
  content-free rate, not a test; the registered G2 rule compares the model against it and
  against 1/8, and both must clear.
- The sidecar grid archive the round read on disk (12 records, levels 1-4) is not in the
  repository: `git diff 8cdc0e9^ 8cdc0e9 --stat` is empty, so the verdict and its grid exist
  only as commit text. Its parse class matches F2 and is reported as such, not as a public
  artifact.
- `scripts/check_serving_ids.py` exits 0 with "serving-id check passed" when invoked with an
  unrecognized flag (it falls through to the tracked-file scan): a mistyped invocation reads
  as a pass. Recorded on issue #206.
