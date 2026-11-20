# Round 70 (2026-11-16 04:12): a name the record contains and the answer field omits - the paired restore/remove probe, and what a recovered name does and does not prove

Nightly round 70, pool slot 2/6, a flash-next-class local endpoint whose serving build is
identified here by the pinned model digest `4075b5949b2b0487`. Tracker issue #65, round summary
comment posted 2026-11-16. Serves #71 (where the ladder ceiling sits), #94 (no verdict from a
trace), #105 (the trace-exposure census), #100 (identical-prompt self-agreement), #145 (the
delivery census), #139 (the NONE controls), #73 and #141 (sequential dispatch on a shared host),
#126 (the output-budget reading), #129 (the panel past the old generator ceiling) and #137 (the
row-label guard). Evidence label: **Executed** (exploratory, one endpoint, one build, one firing,
one sample per cell).

This digest last fired in a scheduled round whose record never reached the repository (issue #150
lists rounds 56 to 58 in that class), so as far as the public record goes this is the first firing
on it: no archived number on this build is quoted anywhere below.

## Question

Round 69 (`research/nightly-2026-11-16-0219/`, committed on its round branch, no PR opened because
the firing timed out under issue #150) found that on deep rungs of the name-walk ladder the
record's non-report channel names every node of the asked path, the asked terminal included
(`gold_in_trace` true in 4 of 4 endpoint cells), while the answer field carries a wrong name, a
refusal, or a token that is not an entity of its own item. Its own reading: the walk is not where
the loss happens, the loss is between a name the record already contains and the one word the
answer field carries.

That is a measurement of a gap, not an account of it. Two accounts fit it and this record has never
separated them:

1. the name is **not available**, and its appearance in the non-report channel is a coincidence of
   format (the channel is just text the walk produced in a form nothing reads out of);
2. the name **is available for report** and the report step is where the system fails.

Availability for report and report are different properties, and no round here has manipulated one
while scoring the other. This round does exactly that.

## Instrument

[readout_recovery_r70.py](readout_recovery_r70.py), stdlib only. `--selftest` runs 92 checks before
any prompt: solver agreement with the path walk at `j = 0, 1, mid, level` and `None` one step past
the tail on all three items; every item is a load-floor (two chains, `facts = 2 * level`)
component-isomorphic item and a doctored 94-fact item and an out-degree-two item are refused; the
archived k = 48 anchor regenerates with seed 116261051 and its archived yes/no prompt digest
`068bc6a1fb0620fb`; three turn-1 prompt digests equal the round-63 pins and the round-69 dispatch
(row M4), so the claim "same items, same prompts, different serving build" is machine-checked here;
scoring controls (the last name wins, `NONE` parses, an empty field is not a delivery, a non-entity
is a delivery without an item name, all six delivery states are reachable); the three wall laws
including the planted negative where a band token count at finish `length` must not count as the
self-stop law; arm construction (the two arms differ in exactly one message, arm B carries no trace
text, the cue is identical and preserves the `NONE` option); the decision rule exercised on planted
outcomes, including the planted all-tail-copy firing that must downgrade the primary reading; the
trace merge rule of issue #105; and sanitizer controls on assembled fixtures so this file carries
no instance of what it redacts.

### The manipulation

Nine turn-1 cells: six deep name cells (j = 40 and the terminal at 48, 42 and 50, 56 and 64 on
three load-floor items at level 48, 50 and 64), two past-the-tail controls (j = 56 on the level-48
item, j = 72 on the level-64 item, so the links run out and the gold is `NONE`), and the shallow
`j = 8` anchor for liveness. Every non-anchor cell is then replayed as a two-turn conversation
whose second user turn is the same neutral cue: "starting at X and following the direct links for
exactly j steps, which single entity name is at step j? Answer with exactly one entity name, or the
single word NONE if the links run out before j steps." The assistant turn differs in one bit:

- **arm A**: the turn-1 answer field plus the turn-1 non-report channel, under a fixed label;
- **arm B**: the turn-1 answer field only.

Both arms request cap 2,048, so a censoring is never my artifact. Selection is frozen with the
items: the same seed base as rounds 51 to 69 (`SEED_BASE = 20261005`), the load-floor rule
(`facts = 2 * level`), the first load-floor item of each level. Dispatch is sequential, one cell at
a time (issue #73), and a turn-1 channel is held in memory only long enough to build its two arms:
no trace text is written to disk anywhere in this directory.

### What the scorer may read

The verdict is the visible answer field against the generator's own solver, never the trace
(issue #94). Round 50 refused a surfacing row because its trace-derived scorer calibrated at 0.5652
against delivered answers; that failure was in the **scorer**, and this instrument keeps the line:
the trace is a treatment (arm A) and a count census (`trace_chars`, `gold_in_trace`, the notes'
last vocabulary name), and it licenses no verdict. The registered rows are in
[gate.json](gate.json).

## Result

27 prompts of the protocol's 40: 2 pre-gate (the exposure census at cap 256, one full-cap
calibration) plus 25 dispatched (9 turn-1 cells and 16 arms). Dispatch wall 416.2 s, 0 transport
errors, 0 retries, per-record rate 27.208 to 91.159 tokens per second.

Gate rows as frozen: `V0_trace_exposure` passes, the deployment hands back `reasoning_content` (205
characters on the census call, and 25 of 25 dispatched records carry a channel), so arm A is
constructible. `V1_solver_certified` passes in `--selftest`. `V3_anchor` passes: `A48_j8` delivers
the correct terminal at 1,096 tokens. `V2_control_liveness` **fails**: 0 of 2 past-the-tail controls
declare `NONE` at turn 1, both run to the cap (see Finding 5). `R1_readout_recovery` is evaluable
(6 lost cells against the frozen minimum of 3) and ships downgraded. `H1_answer_stability` returns
empty. Flags: `control_gate_failed`, `x2_downgrade_fires`, `no_false_names`.

| Cell | j asked | gold | turn-1 delivery | turn-1 tokens | arm A | arm A tokens | arm B | arm B tokens |
|------|---------|------|-----------------|---------------|-------|--------------|-------|--------------|
| `A48_over` | 56 | NONE | censored at cap | 2,048 | declared NONE | 1,637 | censored at cap | 2,048 |
| `C64_over` | 72 | NONE | censored at cap | 2,048 | censored at cap | 2,048 | declared NONE | 916 |
| `A48_j48` | 48 | spog | censored at cap | 2,048 | **correct** | 1,144 | refused | 915 |
| `B50_j50` | 50 | prish | censored at cap | 2,048 | **correct** | 1,888 | refused | 867 |
| `C64_j64` | 64 | brelt | censored at cap | 2,048 | censored at cap | 2,048 | refused | 933 |
| `A48_j40` | 40 | knudnd | censored at cap | 2,048 | **correct** | 634 | refused | 1,471 |
| `B50_j42` | 42 | quudk | censored at cap | 2,048 | **correct** | 689 | refused | 908 |
| `C64_j56` | 56 | frum | censored at cap | 2,048 | **correct** | 903 | refused | 1,050 |
| `A48_j8` | 8 | trackst | **correct** | 1,096 | (anchor, no arms) | | | |

Whole-panel delivery census (issue #145): 11 `censored_at_cap`, 6 `delivered_correct`, 6
`declared_none_on_name_gold`, 2 `declared_none`. Gold-in-own-trace census over the 19 records with a
name gold: true 15, false 4. Wall laws: `L3_cap_bound` fits 11 records, `L1_self_stop_band` and
`L2_reserve_492` fit none.

## Finding 1: on this build every deep cell delivers nothing

All six deep turn-1 cells end `finish_reason = length` at exactly 2,048 tokens with reserve 0 and
the answer field never written, and `gold_in_trace` is true in all six. The issue #145 census gives
`n_eligible = 0` for the deep panel: nothing was put on the wire, so any registered count over these
cells would take the name `inconclusive_budget` and a competence verdict from them would be a
verdict about the output budget (which is issue #126's reading, and this firing does not contradict
it). This is round 69's readout gap in its extreme form: there, three of four endpoint cells
answered and one refused; here none answers at all.

## Finding 2: the wall on this build is cap-bound and neither archived self-stop law fits it

11 of 25 records sit at 2,048 with reserve 0. The round-59 and round-69 band of 1,556 to 1,558
tokens at finish `stop` fits nothing here, and so does the round-53 reserve of exactly 492. The M4
comparison is the sharp part: `A48_j48`, `B50_j50` and `C64_j64` are byte-identical prompts (digests
`baabc346`, `c15a68eb`, `c1ef6c20`, asserted in `--selftest` against the round-63 pins) that the
round-69 build stopped at 1,557, 1,556 and 1,558 while emitting `spog`, `NONE` and `cruuk`, and that
run to the cap on this build emitting nothing. The wall's *mode* is build-tied, which is what round
69 asserted from the other direction, and this build exhibits the cap-bound mode round 63 recorded
on the other side of that identity split.

## Finding 3 (primary, R1): restoring the record's own draft converts a censoring into a correct name, 5 of 6 against 0 of 6

All six deep cells are lost cells, so the paired set is complete and no cell is dropped from the
comparison. Arm A recovers the correct terminal in 5 of 6 (the exception is `C64_j64_A`, censored
again at 2,048); arm B in 0 of 6. All six arm-B records are refusals where a name was asked, at 867
to 1,471 tokens. Every one of the 5 discordant pairs is A-only; the exact two-sided binomial on 5-0
is 0.0625, reported as arithmetic, not as significance, at this n.

`H1_answer_stability` came back with `n_held = 0`: no deep cell was correct at turn 1, so this
firing has no arm-damages-a-right-answer side to report, and the stability question stays owed to a
firing on a build that answers at turn 1.

## Finding 4 (the registered downgrade, X2): every recovery is a copy of the draft's last name

In 5 of 5 arm-A recoveries the emitted name is the last generator-vocabulary name in the restored
notes, so the pre-registered downgrade fires and the R1 verdict ships as
`readout_gated_downgraded_to_tail_copy`. The reason is structural, not incidental: the draft stops
at the asked step, so on every item in this panel "copy the last name" and "report the node at step
j" are the same operation, including the three mid-path asks. A design that restores a draft ending
where the question points cannot distinguish readout from copying, and no access claim survives
that. What does survive, and is new for this record, is narrower: the information needed for the
answer is present in the model's own output text in a form the model will emit *as its answer* when
that text is in the report context, and it is not emitted when that text is absent.

## Finding 5 (controls, V2 and C1): the NONE controls fail again, and no arm manufactures a name

Both past-the-tail controls run to the cap at turn 1 instead of refusing, 0 of 2 declared `NONE`, so
`turn1_declared_none = 0` and the control gate is not met: issue #139 re-presents on a third digest,
and on this build its direction is truncation rather than spurious refusal. Against that, in all
four control arms and all six arm-B refusals there is **not one false name**: nothing in this firing
names an entity where the links ran out, so the cue did not purchase names with question pressure,
and arm B's refusals are not confabulation. On the arms the controls split 1 of 2 correct refusals
each way (`A48_over_A` and `C64_over_B` refuse, their partners censor), so with 2 controls the arm
comparison on the NONE side is noise and is reported as such.

Self-agreement (issue #100): the anchor prompt was dispatched twice, once as the pre-gate calibration
and once as the `A48_j8` cell, and both dispatches cost exactly 1,096 tokens and delivered the same
correct terminal. Per-record rates vary 27.208 to 91.159 tokens per second across the firing, so the
per-cell rate belongs to the cell (issue #73) and none of the deep conclusions rests on a rate.

## Instrument notes

- **Row ids and the #137 guard.** `R1` and `C1` are gate rows in [gate.json](gate.json)
  (`decision_R1`, `controls_C1`). `V0`, `V1`, `V2`, `V3`, `X2`, `H1`, `S1`, `W2` and `M4` are named
  in the instrument docstring, which was written and self-tested before the freeze, but they are not
  separate keys in the frozen gate, and this round did **not** implement the round-69 style
  `--check-readme` label guard. Every number above is nevertheless computed by
  `--rescore` from the frozen gate and the unchanged `raw.jsonl`. Stated here rather than papered
  over, because issue #137 is exactly this defect class.
- **The arms inherit an empty answer field.** Every deep turn-1 cell was censored, so arm B's
  assistant turn is an empty prior answer, not "the answer field with content". That is the honest
  reading of the frozen definition, and it means arm B here is "ask again with nothing kept", while
  arm A is "ask again with the draft kept".
- The trace of a turn-1 record is held in memory only long enough to build its two arms; no trace
  text is written anywhere in this directory, and `raw.jsonl` carries trace *counts* and the notes'
  last vocabulary name only.
- **Post-dispatch edit, declared here in full** (the round-69 precedent): after the panel ran, the
  sanitizer's test fixtures were re-assembled twice, once to move them onto RFC 5737 documentation
  addresses with a port outside the `:808x` class and once to shorten the planted quantization tag,
  so that the instrument file itself carries no instance of the classes the issue #85 guard and the
  round protocol's pre-push grep look for. No scoring, selection, gate or dispatch code changed
  after the panel ran, and `--rescore` reproduces [summary.json](summary.json) from the frozen
  [gate.json](gate.json) and the unchanged [raw.jsonl](raw.jsonl).

## Theory rows, as carried in the gate

- `T1_verbal_report_bibliographic`, Ericsson & Simon 1980, "Verbal reports as data.",
  Psychological Review 87(3):215-251, DOI 10.1037/0033-295X.87.3.215. Used only as the
  bibliographic anchor for the frame that a report is a retrieval from a prior store rather than a
  special introspective faculty. Verification: Crossref work record fetched 2026-11-16, record
  level only (title, authors, venue, year, DOI). The thesis wording was **not** read this session
  and is carried as owed; nothing below attributes a quotation to this article.
- `T2_reports_as_causal_theory`, Nisbett & Wilson 1977, "Telling more than we can know: verbal
  reports on mental processes.", Psychological Review 84(3):231-259,
  DOI 10.1037/0033-295X.84.3.231. A fluent report can be produced by implicit causal theory instead
  of by access to the process, which is the reason arm A's recovery is not by itself access.
  Verification: Crossref work record fetched 2026-11-16, record level. Corrected during this
  round: the working draft of the gate had this as a 1977 Journal of Experimental Social Psychology
  article titled "Telling more than we can do", and a fabricated-looking Elsevier DOI; the
  literature arm caught it against the registry before the freeze.
- `T3_accessibility`, Block 2007, "Consciousness, accessibility, and the mesh between psychology
  and neuroscience.", Behavioral and Brain Sciences 30:481-499, DOI 10.1017/S0140525X07002786.
  Row R1 operationalizes availability-for-report against report; the article takes accessibility as
  its object. Verification: Crossref work record fetched 2026-11-16, record level; no argument
  content is claimed from this row. Caveat on record: citation databases circulate a second DOI
  suffix for this article and the alternative was not cross-checked this session.
- `T4_verbalizable_workspace`, arXiv:2607.15495v1, 2026-07-16, Gurnee, Sofroniew, Pearce and
  13 more, unrefereed preprint: "Verbalizable Representations Form a Global Workspace in Language
  Models". The abstract describes representations the model is poised to verbalize, whose contents
  can be reported and are "used to carry the intermediate steps of silent reasoning" (quote, 9
  words), and a training method that changes only what a model would say if interrupted and asked
  to reflect. Verification: arXiv export API fetched 2026-11-16, abstract level. This is the
  closest published neighbour to the present design, and its interrupt-probe is also cashed out
  counterfactually.
- `T5_introspection_gap`, arXiv:2601.01828v1, 2026-01-05, Lindsey, unrefereed preprint: "Emergent
  Introspective Awareness in Large Language Models". Injecting known concepts into activations and
  reading the self-report is the nearest published analogue of a restore manipulation scored against
  a known ground truth; the abstract reports the capacity is "highly unreliable and
  context-dependent" (quote, 5 words). Verification: arXiv export API fetched 2026-11-16, abstract
  level. The base-model against post-trained asymmetry is **not** in the abstract and is not
  claimed here.
- `T6_trace_answer_dissociation`, arXiv:2605.29087v1, 2026-05-27, unrefereed preprint: "The Chain
  Holds, the Answer Folds: Trace-Answer Dissociation in Reasoning Models Under Adversarial
  Pressure". The abstract reports the chain staying correct while the emitted answer flips, a
  latent-correct rate near 50 percent at the behavioral flip in think mode against 11 to 15 percent
  without a thinking channel, and that a naive trace-anchored defense backfired. Verification:
  arXiv export API fetched 2026-11-16, abstract level. That last clause is the registered prior
  against arm A: restoring the channel is not assumed to help.

Peer-review status: T1, T2 and T3 are journal records at record level (a Crossref type field is not
a peer-review flag); T4, T5 and T6 are unrefereed preprints with no venue field in their arXiv
records. None of the six licenses a measurement; T4 to T6 license the interpretation of one.

## Limits

- One endpoint, one build, one firing, `temperature` 0.0, one sample per cell. The only repetition
  is structural: the two arms of the same turn-1 record are matched, which is a paired design, not
  a replicate.
- n is single digits. R1 is decided on the count of discordant pairs and reported with an exact
  two-sided binomial over those pairs; at this n the arithmetic cannot reach any conventional
  threshold, and the round says so rather than rounding.
- Arm A is not an introspection test. Restoring a model's own draft converts the remaining work
  from a recomputation into a lookup over text already in the context, and both accounts predict a
  recovery. What arm A separates is only whether the information is reportable from that store; the
  discrimination between retrieval and privileged access needs the owed arm C (a same-length,
  same-token-count draft from a different item, frozen before dispatch), which would show whether
  any restoration helps or only this one.
- Prompt budget is not matched between arms: arm A carries the draft, so it sees strictly more
  context. Arm B is the "answer again from scratch" condition, and a turn-1 censor leaves arm B with
  an empty prior turn, which is a degenerate but honest reading of "the answer field only". A
  budget-matched arm (equal total tokens, filler instead of the draft) is owed.
- The trace columns are counts over the record's own reasoning channel (issue #105 census). No
  verdict in this round is taken from a trace and no trace text is archived.
- The serving identity of the endpoint is recorded only as a 16-hex digest. The instrument reads the
  endpoint, the model identifier and the key from the environment the runner exports and never
  writes them; the sanitizer redacts host, IP, path and serving-id classes from anything the model
  answers, and that behavior is tested in `--selftest`.

## Reproduce

```
cd research/nightly-2026-11-16-0412
python3 readout_recovery_r70.py --selftest    # 92 checks, green before any prompt
python3 readout_recovery_r70.py --measure     # exposure census at 256 + one full-cap calibration
python3 readout_recovery_r70.py --freeze      # writes gate.json and prints its blob
python3 readout_recovery_r70.py --run         # refuses to dispatch an unfrozen or drifted gate
python3 readout_recovery_r70.py --rescore     # rebuilds summary.json from the frozen gate
```

The endpoint, model identifier and key come from the runner's exported environment. Artifacts:
[gate.json](gate.json), [measure.json](measure.json), [raw.jsonl](raw.jsonl),
[raw_meta.json](raw_meta.json), [summary.json](summary.json), this README.
