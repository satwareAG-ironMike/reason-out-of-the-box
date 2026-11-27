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
- Instrument: `chance_floor_r87.py`, stdlib only, `--selftest` 19 checks / 9 negative
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

### F1 The landed pilot archive is a censored-delivery record, not a scored answer set

All 12 records in `runs/p8-pilot-2026-11-24-olmo32b-pythia28b/raw.jsonl` carry
`finish_reason: "length"` (censored at 128 or 300 tokens) and `item_level: 3` - the pilot
is a level-3-only archive, not the levels 1-4 grid the M2 row describes. In every record
the stored `content` is a 300-character window of the item's own text - it holds the grid
and the option list - so the completion is a restatement of the question cut off by the
cap. 4 of 12 carry an in-range parsed option index; the single `correct: true` record is
a truncated echo whose last numeric token happened to equal the gold index. 6 have
`parsed_answer: null`; 2 have `parsed_answer: 47` on an 8-option item (valid indices are
0-7). The OLMo half of the pilot is superseded by the tracked `olmo-rerun.jsonl` sidecar
(6 records: 3 `stop`, 3 `length`, all parsed, 1 `correct: true`) per `report.md` and the
CHANGELOG, and this round reads the rerun as the OLMo record.
`rule.json` `trained_depth.no_delivery_case`: "A censored arm is a delivery failure,
never a competence floor." The original pilot archive is a delivery failure at 12/12.

### F2 The harness has no delivery state: nothing parsed is unscored, an out-of-range index is scored wrong

`harness/harness_run.py::parse_answer` returns the last all-digit whitespace token of the
completion, and `harness_run.py:103` sets `correct = (parsed == answer_index)` when
something parsed and `correct = None` when nothing did. There is no delivery state: an
out-of-range index (47 on an 8-option item) is recorded as a wrong answer rather than as
`non_answer`. The frozen judge has the states (`DELIVERY_STATES`; `extract_answer` accepts
only an A-H letter or an exact option tuple) and the harness does not use them. The
exit-gate sentence "all deliveries parsed" is contradicted by the M2 d\* grid's own
records: the #234 sidecar grid raw (12 dispatches, `dstar3-grid-raw.jsonl`, shipped as a
tracked artifact by PR #238) is 12/12 delivered and parsed but carries 3 option indices
outside 0-7 (9, 9, 8 - one each at levels 2, 3, 4); the tracked pilot archive separately
carries 2 indices of 47 among its 12 records.

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
0.7923], lower bound below the chance floor. The delivered d\* grid meets `rule.json`
`trained_depth`'s `no_mastery_case`: no level reaches mastery 0.80, so its d_hat is 0, not
1 - and the reading is at n = 3 per level, where the frozen rule defines the calibration
arm at n = 40, so it is a small-n reading, not a calibration-pool measurement. For the
censored pilot archive the rule computes neither: `no_delivery_case` makes that arm
`not_evaluable`, never 0.

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
probe). `measure.json`: pre-dispatch census median **2.91 completion tokens/s** (the median of
the two census rates 1.22 and 4.6; the record originally carried 4.6, the upper element of the
two - the median fix is disclosed below), below the registered 5.0 tok/s reduced-plan floor, so
G8 selected `plan: none` and no prompt was spent (3 of the 40-call cap used, 32 dispatches
owed). These two files are the surviving failure record, per the `research/AGENTS.md` rule that
an arm that could not run keeps its record.

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

`d* established MET` is not what the frozen instrument computes from this evidence, and the
two landed archives must be read separately. On the **pilot archive** (`raw.jsonl`: 12/12
censored, 6 unparsed, 2 out-of-range 47s) the frozen `trained_depth.no_delivery_case` gives
`not_evaluable`, never 0 - "a censored arm is a delivery failure, never a competence floor."
On the **M2 d\* grid** (`dstar3-grid-raw.jsonl`, now tracked via PR #238: 12/12 delivered,
1/3 at level 1 and 0/3 at levels 2-4, 3 out-of-range 9s/8) the frozen `no_mastery_case` gives
d_hat = 0 at n = 3 per level, where the rule defines the calibration arm at n = 40. Either
way M2 carries a second blocker next to the corpus blocker - the depth measurement has to be
re-run at the study's calibration n. The re-run is specified: the frozen
`matrix_missing_cell_v1` template, `extract_answer` with `DELIVERY_STATES`, a `max_tokens`
above the echo length, calibration n = 40 per level, and the dispatched set's constant-answer
floor reported as a baseline row.

## Instrument and record corrections (2026-11-26, the #236 review, forward-only)

The first #236 review (NOT MERGED, 8 blocking items) directed these corrections on the open
PR; per `research/AGENTS.md` the instrument changes are disclosed here:

1. Detector fix: `score_record` returns the extracted value as a scalar, so the shipped
   option-index detector never fired; the dispatch now records the frozen `extract_answer`
   option_index, G4 counts through `out_of_range_indexes`, and negative control 9 plants an
   out-of-range judged index and asserts it reaches the G4 count (`--selftest` 19 checks /
   9 negative controls).
2. Median fix: an even-count census median took the upper element; `measure.json`'s
   `median_tok_per_s` is corrected 4.6 -> 2.91 (the census call rates themselves are
   byte-unchanged), G8's `plan: none` selection unchanged.
3. Frozen re-use: the local Wilson re-implementation and the hardcoded mastery 0.80 walk are
   gone; `cmd_score` calls `evaluation/frozen/score.py` `wilson` and `trained_depth` and reads
   the mastery threshold from `RULE["trained_depth"]`, so a rule amendment can no longer leave
   this instrument on a stale threshold.
4. Dead code removed: `solve_all_but_one`, the `if False` branch and the unread
   `mean_matching_options` key, four duplicate IPv4 sanitizer patterns, `binom_tail_ge` with
   its self-anchor, and a no-op self-assignment.
5. Gate re-emitted for change 4: the only content diff is the dropped unregistered
   `solve_all_but_one` keys; registered rows G1-G8, `signal_rule` and every offline-baseline
   value are byte-identical to the original freeze. No registered row or tier moved; no raw
   record changed (no dispatch ran).
6. Record fixes: the F1 headline (4 of 12 in-range parses, level-3-only, the superseding
   `olmo-rerun.jsonl`), the F2 delivery-state wording (`harness_run.py:103`: unparsed ->
   `correct = None`, out-of-range -> `False`), the conflated archive counts (pilot archive
   2 of 12; M2 d\* grid 3 of 12, attributed), and the frozen-rule attribution (censored arm
   `not_evaluable` per `no_delivery_case`; the delivered grid meets `no_mastery_case`).

## Limits

- No dispatched cell this firing: F1-F5 are record and arithmetic findings over archives the
  repository already holds, and F5 is a generator-side measurement, not a model measurement.
- The constant-answer floor is chosen after seeing the keys, so it is an upper bound on the
  content-free rate, not a test; the registered G2 rule compares the model against it and
  against 1/8, and both must clear.
- The sidecar grid archive the round read on disk (12 records, levels 1-4) was not in the
  repository when this PR opened (`git diff 8cdc0e9^ 8cdc0e9 --stat` is empty: the verdict and
  its grid existed only as commit text). It ships as a tracked artifact in the M2 exit-gate
  sidecar PR #238 (`dstar3-grid-raw.jsonl` plus the dated verdict record); until that PR
  merges, its numbers are citable only from PR #238. Its parse class matches F2.
- `scripts/check_serving_ids.py` exits 0 with "serving-id check passed" when invoked with an
  unrecognized flag (it falls through to the tracked-file scan): a mistyped invocation reads
  as a pass. Recorded on issue #206.
