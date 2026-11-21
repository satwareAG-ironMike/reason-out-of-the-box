# Round 73 (2026-11-18 04:23): the interior ask breaks the tail-copy confound on the flash build that produced it - 3 of 3 recoveries are selection beyond the draft's tail, the fourth cell of the {terminal,interior} x {flash,27B} square

Nightly round 73, pool slot 2/6, a flash-next-class local endpoint whose serving build is
identified here only by the pinned model digest `4075b5949b2b0487`. Tracker issue #65, round
summary comment posted 2026-11-18. Serves #152 (the owed cross-ask arm, which this round runs on
a second build), #71 (where the ladder ceiling sits), #94 (no verdict from a trace), #105 (the
trace-exposure census), #100 (identical-prompt self-agreement), #126 (the 2048 wall as a firing
property), #145 (the delivery census), #139 (the NONE controls), #137 (the row-and-blob guard),
and #73 and #141 (sequential dispatch on a shared host). Evidence label: **Executed**
(exploratory, one endpoint, one build, one firing, one sample per cell).

This round is a build transfer of round 72's confound-breaking arm, not a new design. The
digest `4075b5949b2b0487` is the build that round 70 (open PR #151, unmerged here) ran when it
found the confound, so this is the arm run on the very build whose result motivated it.

## Erratum (2026-11-20, forward-only, issue #120; refs #151, #178, #169)

Two statements in the `## Question` section and the first row of the 2x2 table below describe
round 70 as a firing whose registered control `X2` fired on every recovery and whose verdict
shipped downgraded to `readout_gated_downgraded_to_tail_copy`. They were accurate as shipped on
2026-11-18: the round-70 instrument of that date did compare each arm-A answer against the last
vocabulary name of that arm's own fresh channel, and on that predicate the downgrade fired.

Both are superseded. Issue #151 showed the predicate read the wrong text, and PR #178 restored
the round-70 record on `main`: with the tail taken over the draft the arms receive, `X2` reads
`selection_beyond_tail` with 0 of 5 recoveries equal to the draft's last name and the round-70
verdict is `readout_gated`, undowngraded (`summary.json` sha256 `362e1ca5`, reproducible by
`--rescore` from the byte-unchanged `gate.json` and `raw.jsonl`; the proof is posted on #178,
2026-11-20).

What that changes here and what it does not:

- The square's flash/terminal row now reads: arm X 5 of 6, beyond the tail in 5 of 5 delivered
  recoveries, source round 70 as restored by #178. No cell of the square is tail-anchored.
- On the terminal-ask side the confound this round was built to break was partly an artifact of
  the round-70 instrument defect rather than a property of the flash build. The interior arm is
  still owed on its own grounds: only an interior gold makes a tail copy a detectable wrong
  answer, so the interior ask is the only design of the four that can test the copy rule.
- Nothing in this round's own measurement moves. This round's `X2` predicate is taken over the
  draft the arms receive, its `X2_tail_shortcut.verdict` is `selection_beyond_tail` on 3 of 3,
  and its registered verdict is `cross_ask_gated` with `arm_X_correct` 3 of 3 against arm F 0 of
  3 and arm B 0 of 3. `gate.json`, `raw.jsonl` and `summary.json` of this round are untouched by
  this erratum (issue #120).

## Question

Round 70 (open PR #151, `research/nightly-2026-11-16-0412/`) restored each censored deep cell's
own draft into the assistant turn on this build and recovered the correct terminal in 5 of 6
against 0 of 6 without it, but its registered control `X2` fired on every recovery: the draft
always stops at the asked step, so "copy the draft's last name" and "report the node at the asked
step" were the same operation, and the verdict shipped downgraded to
`readout_gated_downgraded_to_tail_copy` (as shipped then; superseded by #178, see the Erratum
above). Issue #152 registered the arm that breaks that confound:
restore the draft produced for the terminal and ask for an INTERIOR step, so the correct answer
sits inside the restored text and a copy rule must fail, plus a budget-matched filler control.
Round 72 (open PR #153, unmerged here) ran both on a different, 27B-class build (digest
`26df9af5972ff312`) and got 2 of 3 cross-ask recoveries, both selection beyond the draft's tail.

That leaves the 2x2 of {terminal ask, interior ask} x {this flash build, the 27B build} missing
its fourth cell: the interior ask on the flash build where the confound lives. The square so far:

| build (digest) | ask | arm X recovers | beyond the tail | source |
|----------------|-----|----------------|-----------------|--------|
| flash `4075b5949b2b0487` | terminal | 5 of 6 | no, `X2` fired on all | round 70, open PR #151 (row superseded 2026-11-20, see Erratum) |
| flash `4075b5949b2b0487` | interior | 3 of 3 | yes, 3 of 3 | this round |
| 27B `26df9af5972ff312` | interior | 2 of 3 | yes, 2 of 2 delivered | round 72, open PR #153 |

The within-firing question this round answers: does the interior ask also break the confound on
the flash build, or is that build's readout tail-anchored so that round 72's beyond-tail result is
build-specific? Under the digest convention every "class" statement here is a build statement.

## Instrument

[cross_ask_r73.py](cross_ask_r73.py) is a byte-identical port of round 72's
`cross_ask_r72.py` (PR #153) except for the gate schema, the gate question, the round identity,
and the theory-row verification strings. The selection rule, the arm construction, the scoring and
the whole `--selftest` are unchanged, so the same items and prompts are dispatched on a different
serving build. `--selftest` runs 119 checks green before any prompt, and three of them pin the
turn-1 prompt digests to the round-63, round-69 and round-70 values (row `M4`), so "same items,
same prompts, different build" is machine-checked on the post-merge tree.

### The manipulation

Five turn-1 cells: three terminal name cells (`A48_j48`, `B50_j50`, `C64_j64`, the round-63/69/70
byte-identical `M4` pins), one past-the-tail control (`C64_over`, j = 72, gold `NONE`), and the
shallow `A48_j8` anchor for liveness. The first four are each replayed as a two-turn conversation
with three arms that differ only in the notes block of the assistant turn; the three name cells ask
the same interior step 40 under one neutral cue ("which single entity name is at step 40, or NONE"):

- **arm X**: the turn-1 answer field plus the turn-1 non-report channel under a fixed notes label
  (the draft);
- **arm F**: the turn-1 answer field plus a filler block of the same whitespace-token budget as the
  draft (940, 900 and 850 filler tokens on the three items, field `filler_tokens`);
- **arm B**: the turn-1 answer field only.

Step 40 is interior on all three items (paths of 48, 50 and 64 edges) and is the issue #152
pre-registered ask on the level-64 item. All caps 2,048, so a censoring is never my artifact.
Dispatch is sequential, one cell at a time (issue #73); a turn-1 channel is held in memory only
long enough to build its three arms, and no trace text is written to disk in this directory.

### What the scorer may read

The verdict is the visible answer field against the generator's own solver, never the trace
(issue #94). The draft is a treatment and a count census, and licenses no verdict. The registered
rows sit in the frozen gate [gate.json](gate.json) (`round73-gate-v1`): `V0` to `V3`
(as `V0_precondition` to `V3_anchor`), `R2_cross_ask` (primary, as `decision_R2`),
`X2_tail_shortcut` (the registered downgrade), `F1_filler_budget`, `H1_answer_stability`,
`C1_name_pressure` (as `controls_C1`), and the definitions of `S1_delivery_census`,
`W2_wall_law_counts` and `M4_matched_pair` as the data keys `delivery_states`, `wall_laws` and
`matched_pair`. `--selftest` asserts all eleven keys.

## Result

19 prompts of the protocol's 40: 2 pre-gate (the exposure census at cap 256, one full-cap
calibration) plus 17 dispatched (5 turn-1 cells and 12 arms). Dispatch wall 696.5 s, 0 transport
errors, 0 retries, 0 dropped cells, per-record 14.4 to 54.0 completion tokens per second
(~29 tokens per second aggregate over the 20,360 completion tokens the run archived).

Gate rows as frozen: `V0_trace_exposure` passes, the deployment hands back `reasoning_content`
(217 characters on the census call, 17 of 17 dispatched records carry a channel), so arm X is
constructible. `V1_solver_certified` passes in `--selftest`. `V3_anchor` passes: `A48_j8` delivers
the correct terminal at 381 tokens. `V2_control_liveness` **fails**: 0 of 1 past-the-tail controls
declares `NONE` at turn 1, it runs to the cap (Finding 4). `R2_cross_ask` is evaluable (scope 3
against the frozen minimum of 2) and ships as `cross_ask_gated`.

| Cell | j asked | terminal gold | turn-1 delivery | turn-1 tokens | step-40 gold | arm X | arm X tokens | arm X vs draft tail | arm F | arm B |
|------|---------|---------------|-----------------|---------------|--------------|-------|--------------|---------------------|-------|-------|
| `A48_j48` | 48 | spog | **delivered correct** | 2,006 | knudnd | **correct** | 955 | not the tail | refused | refused |
| `B50_j50` | 50 | prish | censored at cap | 2,048 | clog | **correct** | 604 | not the tail | refused | refused |
| `C64_j64` | 64 | brelt | censored at cap | 2,048 | frixm | **correct** | 1,028 | not the tail | refused | refused |
| `C64_over` | 72 | NONE | censored at cap | 2,048 | (none) | censored at cap | 2,048 | no delivery | declared NONE | declared NONE |
| `A48_j8` | 8 | trackst | **delivered correct** | 381 | (anchor, no arms) | | | | | |

Whole-panel delivery census (issue #145): 5 `delivered_correct`, 6
`declared_none_on_name_gold`, 4 `censored_at_cap`, 2 `declared_none`. The step-40 gold sits in the
turn-1 trace in 3 of 3 terminal cells (the evaluable scope). Wall laws: `L3_cap_bound` fits 4
records (the level-50 and level-64 turn-1 cells and the two control arms that ran to the cap);
`L1_self_stop_band` and `L2_reserve_492` fit none.

## Finding 1 (primary, R2): the interior ask recovers the name the filler and removal arms cannot, 3 of 3 against 0 of 3 and 0 of 3

All three terminal cells have the step-40 interior gold in their turn-1 draft, so the paired set is
complete: arm X recovers the step-40 name in **3 of 3** (`A48_j48_X` at 955 tokens, `B50_j50_X` at
604, `C64_j64_X` at 1,028), arm F in **0 of 3**, arm B in **0 of 3**, the six arm-F and arm-B
records all refusals where a name was asked. All three X-vs-F pairs are discordant and all three
are X-only (exact two-sided binomial on 3-0 is 0.25, reported as arithmetic, not as significance, at
n = 3). The registered verdict ships as `cross_ask_gated`: against a matched budget, the draft's
content recovers what filler and removal do not, on this build exactly as round 72 found on the
27B build.

## Finding 2 (X2, the point of the round): all three recoveries are selection beyond the draft's tail, so the flash-build confound is broken

In **3 of 3** delivered arm-X records the emitted name is NOT the last vocabulary name of the
restored draft (`answer_is_draft_tail` false, false, false), so `X2_tail_shortcut` returns
`selection_beyond_tail` and the round-70 downgrade does not fire. The model reports an interior
position of its own restored text, not its tail: it answers "knudnd" for step 40 on the level-48
item whose draft tail and terminal is "spog", "clog" on the level-50 item whose terminal is "prish",
"frixm" on the level-64 item whose terminal is "brelt". A copy rule is a wrong answer on the
interior ask and was not used.

This is the fourth cell of the square, and it confirms the transfer rather than localising it: the
tail-copy behaviour round 70 could not escape on this build was an artifact of the terminal
coinciding with the draft's tail; once the ask is moved to an interior position, this build selects
by position within its own draft (3 of 3), and it does so on the same side of the distinction as the
27B build (2 of 2 delivered, round 72). The budget-matched filler arm (Finding 1) shows the recovery
is not a context-length artifact: 940, 900 and 850 neutral tokens bought no name in 0 of 3, matching
round 72's filler 0 of 3 on that build. Under the digest convention the beyond-tail selection is a
readout property observed on two builds across two classes, not a single-machine result.

## Finding 3 (H1, the answer-stability side #152 item 3 owed): a held answer is not damaged by restoring the draft, 1 of 1 against 0 of 1 and 0 of 1

`A48_j48` answered its own terminal ("spog") at turn 1 at 2,006 tokens, so this firing has one held
cell (`n_held = 1`, the first in this family: rounds 70 and 72 both came back `n_held = 0`). Asked
for the interior step 40 of that same item, arm X still reports it correctly 1 of 1, while arm F and
arm B each lose it 0 of 1 (both refuse). So on the one cell where the turn-1 report was already
right, restoring the draft does not damage the interior report; removing it or replacing it with
filler does. This is the arm-damages-a-right-answer contrast issue #152 item 3 asked for, at n = 1.

## Finding 4 (controls, V2 and C1): the NONE side re-presents, and no arm manufactures a name

The past-the-tail control `C64_over` runs to the cap at turn 1 instead of refusing, 0 of 1 declared
`NONE`, so the control gate is not met: issue #139 re-presents, and on this build its direction is
truncation. In its favour, under all three arms the control produces no false name (arm X censored,
arm F declared `NONE` at 1,207, arm B declared `NONE` at 1,470), and across the six arm-F and arm-B
refusals on the name cells there is **not one manufactured name** (`C1_name_pressure` false names
0, 0, 0): the cue did not buy names with question pressure even with the draft in context.
Self-agreement (issue #100): the anchor prompt was dispatched twice, in the pre-gate calibration and
as the `A48_j8` cell, and both times cost exactly 381 tokens and delivered the same correct terminal
(byte-identical and token-identical on this firing).

## Finding 5 (the wall on this build, W2 and M4): the cap-bound side is firing-variable, not a fixed build law

`L3_cap_bound` fits 4 of 17 records, all at finish `length`: the level-50 and level-64 turn-1 cells
and the two control arms at the cap. But `A48_j48`, the same `M4` pin (prompt digest `baabc346`),
that round 70 ran to the cap emitting nothing on THIS digest, delivered its terminal at 2,006 tokens
this firing. Neither the round-59/69 self-stop band (1,556 to 1,558 at `stop`) nor the round-53
reserve of exactly 492 fits anything. So on one digest, across two firings, the deep-cell answer
surface moved (round 70 censored all six deep cells; round 73 answered the level-48 cell just under
the cap and censored level-50 and level-64): the wall is a (build, firing) property, which is the
#126 reading, and every "class" statement across rounds stays a build statement under the digest
convention. The beyond-tail result (Findings 1 and 2) does not depend on that surface: it holds on
both censored and non-censored turn-1 drafts.

## Instrument notes

- **The gate was re-frozen once, and only on an unscored prose line.** The gate was frozen before
  any prompt as blob `91ba85358651e5154400cf1569293604a72dcaa19f3bb2c3fd6134fe38072a1d` (recorded in
  [raw_meta.json](raw_meta.json) and dispatched against). After the dispatch, the literature
  subagent reported that the Crossref DOI for Block 2007 (theory row `T3`) returned 429 and the
  record was confirmed via OpenAlex, so that one verification-channel string was corrected in the
  source and the gate re-frozen as blob `9437206403fb372ed4a2410c046f0bd6df1d14d12ce041f4930413d1363178fc`.
  A programmatic diff of the two gates shows the ONLY difference is the `theory_rows` key; the cells,
  `model_digest`, `decision_R2`, `matched_pair`, `caps`, `delivery_states` and `wall_laws` are
  byte-identical, and no scored row, decision rule, prompt pin or model digest moved. The scored
  result is therefore the same against either blob. This note is the record of that re-freeze.
- The `X2` detector is pinned to the treatment: `answer_is_draft_tail` compares the emitted name to
  the last vocabulary name of the restored draft (`draft_vocab_tail`, computed at arm construction
  from the in-memory draft), the quantity the gate text describes, and `--selftest` asserts a planted
  tail copy is a wrong answer on the right path.
- The trace of a turn-1 record is held in memory only long enough to build its three arms; no trace
  text is archived, and `raw.jsonl` carries trace counts and the draft's last vocabulary name only.
- The instrument is frozen with the gate; no scoring, selection, gate or dispatch code was edited
  after the panel ran, and `--rescore` reproduces [summary.json](summary.json) from the frozen
  [gate.json](gate.json) and the unchanged [raw.jsonl](raw.jsonl).

## Theory rows, as carried in the gate

The six rows are carried from round 72's gate (open PR #153, unmerged here) and were re-confirmed
this round against bibliographic records via Crossref (T1, T2; T3 via OpenAlex after a Crossref 429)
and the arXiv export API (T4, T5, T6). None licenses a measurement; T4 to T6 license the reading of
one.

- `T1_verbal_report_bibliographic`, Ericsson & Simon 1980, Psychological Review 87(3):215-251,
  DOI 10.1037/0033-295X.87.3.215. The bibliographic anchor for the frame that a report is a
  retrieval from a prior store. Crossref work record re-fetched 2026-11-18, record level; the thesis
  wording was not read this round and is carried as owed.
- `T2_reports_as_causal_theory`, Nisbett & Wilson 1977, Psychological Review 84(3):231-259,
  DOI 10.1037/0033-295X.84.3.231. A fluent report can be produced by implicit causal theory instead
  of by access to the process, which is why arm X's recovery is not by itself access. Crossref work
  record re-fetched 2026-11-18, record level.
- `T3_accessibility`, Block 2007, Behavioral and Brain Sciences 30:481-499,
  DOI 10.1017/S0140525X07002786. Row R2 operationalizes availability-for-report against report.
  Re-confirmed 2026-11-18 via OpenAlex (OpenAlex id W2047192086; Crossref returned 429 through the
  retry budget), record level; the circulating alternative DOI suffix was not cross-checked.
- `T4_verbalizable_workspace`, arXiv:2607.15495v1, 2026-07-16, unrefereed preprint: "Verbalizable
  Representations Form a Global Workspace in Language Models." The abstract describes reportable
  representations "used to carry the intermediate steps of silent reasoning" (quote, 9 words,
  re-confirmed verbatim against the arXiv abstract 2026-11-18). The closest published neighbour to
  this design.
- `T5_introspection_gap`, arXiv:2601.01828v1, 2026-01-05, Lindsey, unrefereed preprint: "Emergent
  Introspective Awareness in Large Language Models." A restore manipulation scored against a known
  ground truth is its analogue; the abstract reports the capacity is "highly unreliable and
  context-dependent" (quote, 5 words, re-confirmed verbatim 2026-11-18).
- `T6_trace_answer_dissociation`, arXiv:2605.29087v1, 2026-05-27, unrefereed preprint: "The Chain
  Holds, the Answer Folds." The abstract reports the chain staying correct while the emitted answer
  flips and that a naive trace-anchored defense backfired (re-confirmed 2026-11-18). That clause is
  the registered prior against arm X: restoring the channel was not assumed to help.

Peer-review status: T1, T2 and T3 are journal records at record level (a Crossref type field is not
a peer-review flag); T4, T5 and T6 are unrefereed preprints with no venue field in their arXiv
records. A 2025-2026 scan (OpenAlex relevance search and an arXiv metadata search, indicative not
exhaustive) did not surface a restore-then-probe-intermediate design; the nearest published neighbour
found removes reasoning steps rather than restoring the model's own trace.

## Limits

- One endpoint, one build, one firing, `temperature` 0.0, one sample per cell. The only repetition
  is structural: the three arms of the same turn-1 record are matched, a paired design, not a
  replicate.
- n is single digits. R2 is decided on the count of X-vs-F discordant pairs and reported with an
  exact two-sided binomial over them; at n = 3 the arithmetic cannot reach any conventional
  threshold, and the round says so rather than rounding.
- The interior ask breaks the tail-copy confound but not the retrieval-versus-recomputation split.
  Arm F keeps the full original fact block in the user turn and still refuses 0 of 3, so the
  recovery is not a fresh traversal of the facts in the second pass; it needs the draft's content,
  not its budget. Whether that content acts as a readout from the model's own store or as a generic
  name-scaffold that puts the model in a lookup posture is not separated here. The round-70 owed arm
  C (a same-length draft from a DIFFERENT item, frozen before dispatch) is the discriminator between
  those two accounts and is still owed; the claim this round licenses is "the draft's content enables
  an interior report, on two builds," not "the channel is available for report in the introspective
  sense."
- `H1_answer_stability` rests on a single held cell (`n_held = 1`). `A48_j48` answered at turn 1 this
  firing and censored in round 70 on the same digest (Finding 5), so the answer-at-turn-1 side is
  firing-dependent; #152 item 3 needs a firing where several deep cells answer at turn 1.
- The filler parity is declared in whitespace tokens, not in the endpoint's tokenization; the
  registered approximation is stated in the gate (`F1_filler_budget`).
- The trace columns are counts over the record's own `reasoning_content` channel (issue #105 census:
  this deployment exposes `reasoning_content`; a claim against a zero-trace deployment would be an
  answer-level claim only). No verdict is taken from a trace and no trace text is archived.
- The serving identity of the endpoint is recorded only as a 16-hex digest. The instrument reads the
  endpoint, model identifier and key from the runner's exported environment and never writes them;
  the sanitizer redacts host, IP, path and serving-id classes from anything the model answers, and
  that behavior is tested in `--selftest`.

## Reproduce

```
cd research/nightly-2026-11-18-0423
python3 cross_ask_r73.py --selftest    # 119 checks, green before any prompt
python3 cross_ask_r73.py --measure     # exposure census at 256 + one full-cap calibration
python3 cross_ask_r73.py --freeze      # writes gate.json and prints its blob
python3 cross_ask_r73.py --run         # refuses to dispatch an unfrozen or drifted gate
python3 cross_ask_r73.py --rescore     # rebuilds summary.json from the frozen gate
```

The endpoint, model identifier and key come from the runner's exported environment. Artifacts:
[gate.json](gate.json), [measure.json](measure.json), [raw.jsonl](raw.jsonl),
[raw_meta.json](raw_meta.json), [summary.json](summary.json), this README.
