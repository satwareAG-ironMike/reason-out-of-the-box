# Round 72 (2026-11-17 04:01): does the interior ask break the tail-copy confound - the cross-ask and budget-matched filler arms on the M4 items

Nightly round 72, pool slot 6/6, a 27B-class local endpoint whose serving build is
identified here by the pinned model digest `26df9af5972ff312`. Tracker issue #65, round
summary comment posted 2026-11-17. Serves #71 (where the ladder ceiling sits), #94 (no
verdict from a trace), #105 (the trace-exposure census), #100 (identical-prompt
self-agreement), #145 (the delivery census), #139 (the NONE controls), #73 and #141
(sequential dispatch on a shared host), #126 (the output-budget reading), #129 (the panel
past the old generator ceiling) and #152 (the owed cross-ask arm and its budget-matched
control). Evidence label: **Executed** (exploratory, one endpoint, one build, one firing,
one sample per cell).

The round-71 firing (2026-11-17 02:00, slot 4/6) died at start (exit 1, a registry drift
on the rotated slot) and left no record; this digest last fired in a scheduled round
whose record never reached the repository (issue #150 class, a local-only record of the
round-58 firing), so as far as the public record goes this is the first firing on it: no
archived number on this build is quoted anywhere below.

## Question

Round 70 (`research/nightly-2026-11-16-0412/`, PR #151) restored each censored deep
cell's own draft into the assistant turn and recovered the correct terminal in 5 of 6
against 0 of 6 without the draft. Its registered control X2 fired on every recovery: the
draft always stops at the asked step, so "copy the draft's last name" and "report the node
at the asked step" are the same operation, and the verdict shipped downgraded to
`readout_gated_downgraded_to_tail_copy`. Issue #152 registered the arm that breaks the
confound: restore the draft produced for the terminal and ask for an INTERIOR step, so
the correct answer sits inside the restored text and a copy rule must fail. Item 2 of the
same issue registered the budget-matched control: the same notes-block budget in filler
instead of the draft, to separate "more context, less work" from "this context". This
round runs both, on the three M4 items whose turn-1 prompts are byte-identical to the
round-63, round-69 and round-70 dispatches.

## Instrument

[cross_ask_r72.py](cross_ask_r72.py), stdlib only. `--selftest` runs 119 checks before any
prompt: solver agreement with the path walk at `j = 0, 1, mid, level` and `None` one step
past the tail on all three items; every item is a load-floor (two chains,
`facts = 2 * level`) component-isomorphic item and a doctored and an out-degree-two item
are refused; the interior ask is asserted strictly inside the walk and the interior gold
asserted distinct from the tail and the start, so the tail-copy detector is not vacuous;
the filler token is asserted outside every item vocabulary; the archived k = 48 anchor
regenerates with seed 116261051 and its archived yes/no prompt digest
`068bc6a1fb0620fb`; three turn-1 prompt digests equal the round-63/69/70 pins and the
round-70 dispatch (row M4), so the claim "same items, same prompts, different serving
build" is machine-checked here; arm construction (the three arms differ only in the notes
block; the filler matches the draft's whitespace-token budget; the cue is shared and
preserves `NONE`); the planted tail-copy outcome (a copy of the draft's last name is a
wrong answer on the right path on the interior ask); the decision rule exercised on
planted outcomes, including the planted all-tail-copy and filler-only outcomes; scoring
controls; the trace merge rule of issue #105; and sanitizer controls on assembled
fixtures so this file carries no instance of what it redacts.

### The manipulation

Five turn-1 cells: three terminal name cells (`A48_j48`, `B50_j50`, `C64_j64`, the M4
pins), one past-the-tail control (`C64_over`, j = 72, gold `NONE`), and the shallow
`j = 8` anchor for liveness. Each of the first four cells is replayed as a two-turn
conversation with three arms that differ only in the notes block of the assistant turn;
all three ask the same interior step 40 under the same neutral cue ("which single entity
name is at step 40, or NONE"):

- **arm X**: the turn-1 answer field plus the turn-1 non-report channel under a fixed
  notes label (the draft);
- **arm F**: the turn-1 answer field plus a filler block of the same whitespace-token
  budget as the draft under the same label (890, 941 and 767 filler tokens on the three
  items, field `filler_tokens`);
- **arm B**: the turn-1 answer field only.

Step 40 is interior on all three items (paths of 48, 50 and 64 edges) and is the issue
#152 pre-registered ask on the level-64 item. All caps 2,048, so a censoring is never my
artifact. Selection is frozen with the items: the round-51 seed base
(`SEED_BASE = 20261005`), the load-floor rule (`facts = 2 * level`), the first load-floor
item of each level. Dispatch is sequential, one cell at a time (issue #73), and a
turn-1 channel is held in memory only long enough to build its three arms: no trace text
is written to disk anywhere in this directory.

### What the scorer may read

The verdict is the visible answer field against the generator's own solver, never the
trace (issue #94). The draft is a treatment and a count census (`trace_chars`,
`gold_in_trace`, `interior_gold_in_trace`, `draft_vocab_tail`), and it licenses no
verdict. The registered rows are keys of the frozen gate [gate.json](gate.json)
(`round72-gate-v1`): `V0` to `V3` (preconditions), `R2_cross_ask` (primary),
`X2_tail_shortcut` (the registered downgrade), `F1_filler_budget`, `H1_answer_stability`,
`C1_name_pressure`, `S1_delivery_census`, `W2_wall_law_counts` and `M4_matched_pair`.
Every row is a key of the frozen artifact, closing issue #152 item 4.

## Result

19 prompts of the protocol's 40: 2 pre-gate (the exposure census at cap 256, one
full-cap calibration) plus 17 dispatched (5 turn-1 cells and 12 arms). Dispatch wall
290.1 s, 0 transport errors, 0 retries, per-record rate 46.461 to 131.215 tokens per
second.

Gate rows as frozen: `V0_trace_exposure` passes, the deployment hands back `reasoning`
(247 characters on the census call, 17 of 17 dispatched records carry a channel), so
arm X is constructible. `V1_solver_certified` passes in `--selftest`. `V3_anchor`
passes: `A48_j8` delivers the correct terminal at 266 tokens. `V2_control_liveness`
**fails**: 0 of 1 past-the-tail controls declares `NONE` at turn 1, it runs to the cap
(see Finding 4). `R2_cross_ask` is evaluable (scope 3 against the frozen minimum of 2)
and ships as `cross_ask_gated`. `H1_answer_stability` returns empty.

| Cell | j asked | gold | turn-1 delivery | turn-1 tokens | arm X | arm X tokens | arm F | arm F tokens | arm B | arm B tokens |
|------|---------|------|-----------------|---------------|-------|--------------|-------|--------------|-------|--------------|
| `A48_j48` | 48 | spog | censored at cap | 2,048 | **correct at step 40** | 1,426 | refused | 986 | refused | 1,960 |
| `B50_j50` | 50 | prish | censored at cap | 2,048 | **correct at step 40** | 287 | refused | 764 | refused | 796 |
| `C64_j64` | 64 | brelt | censored at cap | 2,048 | censored at cap | 2,048 | refused | 892 | refused | 1,858 |
| `C64_over` | 72 | NONE | censored at cap | 2,048 | censored at cap | 2,048 | declared NONE | 2,032 | declared NONE | 784 |
| `A48_j8` | 8 | trackst | **correct** | 266 | (anchor, no arms) | | | | | |

Whole-panel delivery census (issue #145): 6 `censored_at_cap`, 6
`declared_none_on_name_gold`, 3 `delivered_correct`, 2 `declared_none`. The interior
gold sits in the turn-1 trace in 3 of 3 terminal cells (the evaluable scope). Wall
laws: `L3_cap_bound` fits 7 records; `L1_self_stop_band` and `L2_reserve_492` fit
none.

## Finding 1 (primary, R2): the interior ask recovers the name the filler and the removal arms cannot, 2 of 3 against 0 of 3 and 0 of 3

All three terminal cells are lost cells (`n_lost = 3`) and all three drafts contain the
interior gold, so the paired set is complete: arm X recovers the step-40 name in 2 of 3
(`A48_j48_X` at 1,426 tokens, `B50_j50_X` at 287; the exception is `C64_j64_X`,
censored again at 2,048), arm F in 0 of 3, arm B in 0 of 3, the six arm-F and arm-B
records all refusals where a name was asked. 2 of 2 discordant X-vs-F pairs are
X-only (exact two-sided binomial on 2-0 is 0.5, reported as arithmetic, not as
significance, at n = 2). The registered verdict ships as `cross_ask_gated`: against a
matched budget, the draft's content recovers what filler and removal do not.

## Finding 2 (X2): both recoveries are selection beyond the draft's tail

In 2 of 2 delivered arm-X records the emitted name is NOT the last vocabulary name of
the restored draft (`answer_is_draft_tail` false, false): the model reports an interior
position of the restored text, not its tail. A copy rule is a wrong answer on the
interior ask, and the registered X2 downgrade does not fire. The tail-copy confound
round 70 could not break is broken by the ask itself, and the budget-matched filler
arm (Finding 1) shows the recovery is not an artifact of context length: 890, 941 and
767 neutral tokens bought no name in 0 of 3.

## Finding 3 (the wall on this build, W2 and M4): cap-bound, a third firing on that side of the split

`L3_cap_bound` fits 7 of 17 records (the four turn-1 cells, `C64_j64_X`,
`C64_over_X`, and `C64_over_F` at a reserve of 16); neither the round-59/69 band of
1,556 to 1,558 at finish `stop` nor the round-53 reserve of exactly 492 fits anything.
The M4 comparison is the sharp part: `A48_j48`, `B50_j50` and `C64_j64` are
byte-identical prompts (digests `baabc346`, `c15a68eb`, `c1ef6c20`) that the round-69
build stopped at 1,556 to 1,558 while emitting `spog`, `NONE` and `cruuk`, that the
round-70 build ran to the cap emitting nothing, and that run to the cap on this build
emitting nothing again. The wall's mode is build-tied, as round 69 asserted and round
70 re-asserted; this is the third public firing on the cap-bound side of that split,
and every "class" statement across rounds remains a build statement under the digest
convention.

## Finding 4 (controls, V2 and C1): the NONE side re-presents on a fourth digest, and no arm manufactures a name

The past-the-tail control runs to the cap at turn 1 instead of refusing, 0 of 1
declared `NONE`, so the control gate is not met: issue #139 re-presents on a fourth
digest, and on this build its direction is truncation. In its favour, arm F declared
`NONE` at 2,032 (itself cap-bound at a reserve of 16) and arm B at 784 while arm X
censored before writing an answer, and in the three arm dispatches on the control and
the six arm-F and arm-B refusals on the name cells there is **not one false name**:
the cue did not buy names with question pressure even with the draft in context, and
the six refusals are not confabulation. Self-agreement
(issue #100): the anchor prompt was dispatched twice, in the pre-gate calibration and
as the `A48_j8` cell, and both times cost exactly 266 tokens and delivered the same
correct terminal.

## Instrument notes

- **The X2 detector is pinned to the treatment.** `answer_is_draft_tail` compares the
  emitted name to the last vocabulary name of the restored draft (field
  `draft_vocab_tail`, computed at arm construction from the in-memory draft), whereas
  round 70 computed the same predicate from the arm response's own channel. On the
  interior ask the two quantities coincide only when the model echoes the draft's tail
  into its own channel; the treatment-side form is the one the gate text describes, and
  `--selftest` asserts that a planted tail copy is a wrong answer on the right path.
- The trace of a turn-1 record is held in memory only long enough to build its three
  arms; no trace text is archived, and `raw.jsonl` carries trace counts, the draft's
  last vocabulary name and the filler budget only.
- The instrument is frozen with the gate at blob `2b3139d7`; no scoring, selection,
  gate or dispatch code was edited after the panel ran, and `--rescore` reproduces
  [summary.json](summary.json) from the frozen [gate.json](gate.json) and the unchanged
  [raw.jsonl](raw.jsonl).

## Theory rows, as carried in the gate

- `T1_verbal_report_bibliographic`, Ericsson & Simon 1980, "Verbal reports as data.",
  Psychological Review 87(3):215-251, DOI 10.1037/0033-295X.87.3.215. Used only as the
  bibliographic anchor for the frame that a report is a retrieval from a prior store
  rather than a special introspective faculty. Verification: Crossref work record
  fetched this session 2026-11-17, record level only; the thesis wording was not read
  this session and is carried as owed.
- `T2_reports_as_causal_theory`, Nisbett & Wilson 1977, "Telling more than we can
  know: verbal reports on mental processes.", Psychological Review 84(3):231-259,
  DOI 10.1037/0033-295X.84.3.231. A fluent report can be produced by implicit causal
  theory instead of by access to the process, which is the reason arm X's recovery is
  not by itself access. Verification: Crossref work record fetched this session
  2026-11-17, record level.
- `T3_accessibility`, Block 2007, "Consciousness, accessibility, and the mesh between
  psychology and neuroscience.", Behavioral and Brain Sciences 30:481-499,
  DOI 10.1017/S0140525X07002786. Row R2 operationalizes availability-for-report
  against report; the article takes accessibility as its object. Verification: Crossref
  work record fetched this session 2026-11-17, record level; no argument content is
  claimed from this row.
- `T4_verbalizable_workspace`, arXiv:2607.15495v1, 2026-07-16, Gurnee, Sofroniew,
  Pearce and 13 more, unrefereed preprint: "Verbalizable Representations Form a Global
  Workspace in Language Models". The abstract describes representations the model is
  poised to verbalize, whose contents can be reported and are "used to carry the
  intermediate steps of silent reasoning" (quote, 9 words). Verification: arXiv export
  API fetched this session 2026-11-17, abstract level. The closest published neighbour
  to the present design, and its interrupt-probe is also cashed out counterfactually.
- `T5_introspection_gap`, arXiv:2601.01828v1, 2026-01-05, Lindsey, unrefereed
  preprint: "Emergent Introspective Awareness in Large Language Models". Injecting
  known concepts into activations and reading the self-report is the nearest published
  analogue of a restore manipulation scored against a known ground truth; the abstract
  reports the capacity is "highly unreliable and context-dependent" (quote, 5 words).
  Verification: arXiv export API fetched this session 2026-11-17, abstract level.
- `T6_trace_answer_dissociation`, arXiv:2605.29087v1, 2026-05-27, unrefereed
  preprint: "The Chain Holds, the Answer Folds: Trace-Answer Dissociation in Reasoning
  Models Under Adversarial Pressure". The abstract reports the chain staying correct
  while the emitted answer flips and that a naive trace-anchored defense backfired.
  Verification: arXiv export API fetched this session 2026-11-17, abstract level. That
  last clause is the registered prior against arm X: restoring the channel was not
  assumed to help, and the filler arm shows it was not the context alone.

Peer-review status: T1, T2 and T3 are journal records at record level (a Crossref type
field is not a peer-review flag); T4, T5 and T6 are unrefereed preprints with no venue
field in their arXiv records. None of the six licenses a measurement; T4 to T6 license
the interpretation of one.

## Limits

- One endpoint, one build, one firing, `temperature` 0.0, one sample per cell. The only
  repetition is structural: the three arms of the same turn-1 record are matched, which
  is a paired design, not a replicate.
- n is single digits. R2 is decided on the count of X-vs-F discordant pairs and reported
  with an exact two-sided binomial over those pairs; at n = 2 the arithmetic cannot
  reach any conventional threshold, and the round says so rather than rounding.
- The interior ask breaks the tail-copy confound but not the retrieval-versus-
  recomputation split. Arm F shows the recovery tracks the draft's content, not its
  budget; whether that content acts as a readout from the record's own store or as a
  precomputed walk the model then shortcuts around the report step is not separated
  here. The round-70 owed arm C (a same-length draft from a different item, frozen
  before dispatch) remains the discriminator between those two accounts, and the claim
  this round licenses is "the draft's content enables the interior report", not
  "the channel is available for report in the introspective sense".
- The filler parity is declared in whitespace tokens, not in the endpoint's
  tokenization: no model tokenizer is available to a stdlib instrument, and the
  registered approximation is stated in the gate (`F1_filler_budget`).
- The trace columns are counts over the record's own reasoning channel (issue #105
  census: this deployment exposes `reasoning`, not `reasoning_content`; a claim
  against a zero-trace deployment would be an answer-level claim only). No verdict in
  this round is taken from a trace and no trace text is archived.
- `H1_answer_stability` came back empty (`n_held = 0`): no terminal cell was correct at
  turn 1, so this firing has no arm-damages-a-right-answer side, and issue #152 item 3
  (a firing on a build that answers at turn 1) stays owed; this build is the
  cap-bound one of the two archived build modes.
- The serving identity of the endpoint is recorded only as a 16-hex digest. The
  instrument reads the endpoint, the model identifier and the key from the environment
  the runner exports and never writes them; the sanitizer redacts host, IP, path and
  serving-id classes from anything the model answers, and that behavior is tested in
  `--selftest`.

## Reproduce

```
cd research/nightly-2026-11-17-0401
python3 cross_ask_r72.py --selftest    # 119 checks, green before any prompt
python3 cross_ask_r72.py --measure      # exposure census at 256 + one full-cap calibration
python3 cross_ask_r72.py --freeze       # writes gate.json and prints its blob
python3 cross_ask_r72.py --run          # refuses to dispatch an unfrozen or drifted gate
python3 cross_ask_r72.py --rescore     # rebuilds summary.json from the frozen gate
```

The endpoint, model identifier and key come from the runner's exported environment.
Artifacts: [gate.json](gate.json), [measure.json](measure.json),
[raw.jsonl](raw.jsonl), [raw_meta.json](raw_meta.json), [summary.json](summary.json),
this README.
