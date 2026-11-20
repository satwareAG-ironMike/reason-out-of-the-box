# Round 75 (2026-11-19 04:01): does the interior-ask recovery need the item's own draft - the round-70 owed arm C (foreign same-length scaffold) on the 27B build

Nightly round 75, pool slot 6/6, a 27B-class local endpoint whose serving build is
identified here by the pinned model digest `26df9af5972ff312`. That id string fired
publicly in round 54 (PR #133), round 63 (PR #143) and round 72 (PR #153), all unmerged;
this is the fourth public firing on it, and no archived number on this build is quoted
below except the registered M4 prompt-identity and wall-shape comparisons. Tracker issue
#65. Serves #152 (the owed arm C, the sharpest discriminator), #71, #94, #105, #100,
#145, #139, #73, #141, #126 and #137. Evidence label: **Executed** (exploratory, one
endpoint, one build, one firing, one sample per cell).

The round-74 firing (2026-11-19 02:00, slot 4/6, a flash-class local endpoint) died at
start on a registry drift between the rotated slot's pool entry and the agent's model
registry (exit 1, no artifacts); its runner fallback line on #65 is its only record.

## Question

Rounds 72 (27B build, PR #153) and 73 (flash build, PR #154) ran the issue #152
cross-ask: restore the turn-1 draft and ask an interior step. On both builds the recovery
was selection beyond the draft's tail, against a budget-matched filler arm (F) that bought
nothing. Both rounds registered the same next discriminator, owed since round 70 and
commented on issue #152 as "the sharpest discriminator, not in the item list": **arm C, a
same-length draft from a DIFFERENT item, frozen before dispatch.** Arm F already rules out
context budget and a fresh traversal of the facts, so the recovery needs the draft's
content; but that does not separate "the model reads its own store for this item" from
"any name-scaffold puts it in a lookup posture". This round runs arm C on the 27B build;
the flash build's arm C remains owed.

## Instrument

[cross_ask_c_r75.py](cross_ask_c_r75.py), stdlib only. `--selftest` runs 140 checks before
any prompt: solver agreement with the path walk at `j = 0, 1, mid, level` and `None` one
step past the tail on all three items; every item is a load-floor (two chains,
`facts = 2 * level`) component-isomorphic item and a doctored and an out-degree-two item
are refused; the interior ask is asserted strictly inside the walk and the interior gold
asserted distinct from the tail and the start; the filler token asserted outside every
item vocabulary; the archived k = 48 anchor regenerates with seed 116261051 and its
archived yes/no prompt digest `068bc6a1fb0620fb`; three turn-1 prompt digests equal the
round-63/69/70/72/73 pins and the dispatch (row M4), so "same items, same prompts,
different serving build and firing" is machine-checked; **the gold-leak precondition: for
each interior cell the asked interior gold is asserted absent from the donor item's
vocabulary** (the item vocabularies are not pairwise disjoint - 7 names are shared between
the two level-48/50 items - so the asserted property is the narrower gold-leak one,
recorded per donor pair); arm construction (the four arms differ only in the notes block;
the user turn of every arm is the FULL turn-1 prompt; the foreign block is cut
word-safely to the item's own draft whitespace-token budget and a short donor is used
whole; the decision rules C2, R2, X2 and P1 are exercised on planted outcomes); scoring
controls; the trace merge rule of issue #105; and sanitizer controls on assembled
fixtures so this file carries no instance of what it redacts.

### The manipulation

Five turn-1 cells: three terminal name cells (`A48_j48`, `B50_j50`, `C64_j64`, the M4
pins), one past-the-tail control (`C64_over`, j = 72, gold `NONE`), and the shallow
`j = 8` anchor for liveness. Each of the first four cells is replayed as a two-turn
conversation with four arms that differ only in the notes block of the assistant turn;
all ask the same interior step 40 under the same neutral cue ("which single entity name is
at step 40, or NONE"), cap 2,048 on every arm so a censoring is never this instrument's
artifact:

- **arm X**: the turn-1 answer field plus the item's own turn-1 non-report channel under
  a fixed notes label (the own draft);
- **arm C**: the turn-1 answer field plus a draft of a DIFFERENT item, cut to the item's
  own draft whitespace-token budget under the same label (the foreign scaffold). The
  donor map is frozen in the gate: round robin, A48 takes B50's draft, B50 takes C64's,
  C64 takes A48's, and the control (item C64) takes A48's draft. A donor draft shorter
  than the budget is used whole; the realized count is the field `foreign_tokens`;
- **arm F**: the turn-1 answer field plus a filler block of the same whitespace-token
  budget under the same label (880, 941, 767 and 846 filler tokens on the four armed
  cells, field `filler_tokens`);
- **arm B**: the turn-1 answer field only.

**Design fix carried in from the 2026-11-18 pr-review record on this instrument
family:** the round-72/73 arms were built from the archived 900-character copy of the
turn-1 prompt, so an arm "that also loses half the context is not a one-bit
manipulation". This instrument dispatches every arm from the reconstructed full turn-1
prompt (asserted in `--selftest`), so the four arms differ only in the notes block, and
row P1 matches the arms on the endpoint's measured `prompt_tokens` rather than on word or
whitespace counts: the context-length claim in this README ships only while P1 holds.

All caps 2,048. Selection is frozen with the items: the round-51 seed base
(`SEED_BASE = 20261005`), the load-floor rule, the first load-floor item of each level.
Dispatch is sequential, one cell at a time (issue #73): the three terminal turn-1 cells
first (arm C needs another item's draft), then the control and the anchor, then the
sixteen arms. A turn-1 channel is held in memory only long enough to build its arms: no
trace text is written to disk anywhere in this directory.

### What the scorer may read

The verdict is the visible answer field against the generator's own solver, never the
trace (issue #94). The draft is a treatment and a count census (`trace_chars`,
`gold_in_trace`, `interior_gold_in_trace`, `draft_vocab_tail`, `foreign_vocab_tail`,
`foreign_block_contains_gold`), and it licenses no verdict. The registered rows sit in
the frozen gate [gate.json](gate.json) (`round75-gate-v1`): `V0` to `V3`
(preconditions), `C2_foreign_draft` (primary, as the decision table `decision_C2`),
`R2_cross_ask` (carried from round 72, as `decision_R2`), `X2_tail_shortcut`,
`F1_filler_budget`, `P1_prompt_tokens_parity`, `H1_answer_stability`,
`C1_name_pressure` (as `controls_C1`), and the definitions of `S1_delivery_census`,
`W2_wall_law_counts` and `M4_matched_pair` registered as data keys: the census states as
`delivery_states`, the wall-law tests L1 to L3 as `wall_laws`, the byte-identical prompt
pins as `matched_pair`, the donor map as `foreign_map`. `--selftest` asserts all of
these keys, so every row definition lives in the frozen artifact (issue #137 shape).

## Result

23 prompts of the protocol's 40: 2 pre-gate (the exposure census at cap 256, one
full-cap calibration) plus 21 dispatched (5 turn-1 cells and 16 arms). Dispatch wall
470.2 s, 0 transport errors, 0 retries, per-record rate 23.535 to 131.4 tokens per
second.

Gate rows as frozen: `V0_trace_exposure` passes, the deployment hands back `reasoning`
(311 characters on the census call, 21 of 21 dispatched records carry a channel), so
arms X and C are constructible. `V1_solver_certified` passes in `--selftest` (including
the per-donor-pair gold-leak assertion). `V3_anchor` passes: `A48_j8` delivers the
correct terminal at 1,176 tokens. `V2_control_liveness` **fails**: 0 of 1 past-the-tail
controls declares `NONE` at turn 1, it runs to the cap (see Finding 5).
`C2_foreign_draft` is evaluable (scope 3 against the frozen minimum of 2) and ships as
`own_content_selects`. `H1_answer_stability` returns empty. `P1_prompt_tokens_parity`
fails on all four armed cells (see Finding 6).

| Cell | j asked | gold | turn-1 delivery | turn-1 tokens | arm X | arm X tokens | arm C | arm C tokens | arm F | arm F tokens | arm B | arm B tokens |
|------|---------|------|-----------------|---------------|-------|--------------|-------|--------------|-------|--------------|-------|--------------|
| `A48_j48` | 48 | spog | censored at cap | 2,048 | **correct at step 40** | 267 | censored at cap | 2,048 | censored at cap | 2,048 | censored at cap | 2,048 |
| `B50_j50` | 50 | prish | censored at cap | 2,048 | **correct at step 40** | 271 | censored at cap | 2,048 | censored at cap | 2,048 | censored at cap | 2,048 |
| `C64_j64` | 64 | brelt | censored at cap | 2,048 | **correct at step 40** | 692 | censored at cap | 2,048 | censored at cap | 2,048 | **correct at step 40** | 1,965 |
| `C64_over` | 72 | NONE | censored at cap | 2,048 | censored at cap | 2,048 | censored at cap | 2,048 | censored at cap | 2,048 | censored at cap | 2,048 |
| `A48_j8` | 8 | trackst | **correct** | 1,176 | (anchor, no arms) | | | | | | | |

Whole-panel delivery census (issue #145): 16 `censored_at_cap`, 5 `delivered_correct`.
The interior gold sits in the turn-1 trace in 3 of 3 terminal cells (the evaluable
scope). Wall laws: `L3_cap_bound` fits 16 of 21 records; `L1_self_stop_band` and
`L2_reserve_492` fit none.

## Finding 1 (primary, C2): the foreign same-length scaffold buys nothing - the recovery is specific to the item's own draft, 3 of 3 against 0 of 3

All three terminal cells are lost cells (`n_lost_turn1 = 3`, each censored at the cap
with the answer field never written) and all three drafts contain the interior gold, so
the paired set is complete: arm X recovers the step-40 name in 3 of 3 (`A48_j48_X` at
267 tokens, `B50_j50_X` at 271, `C64_j64_X` at 692 - all stopping well short of the
cap), arm C in 0 of 3, arm F in 0 of 3. The three X-vs-C discordant pairs are all
X-only (exact two-sided binomial on 3-0 is 0.25, reported as arithmetic, not as
significance, at n = 3). The registered verdict ships as `own_content_selects`
(n_X = 3, n_C = 0, n_X - n_C = 3 >= 2): a draft of a different item, cut to the same
whitespace-token budget, does not recover the interior name. The recovery is specific to
the model's own prior output for that item; the scaffold hypothesis (any name block puts
it in a lookup posture) is not supported on this build.

## Finding 2 (X2): all three recoveries are selection beyond the draft's tail

In 3 of 3 delivered arm-X records the emitted name is NOT the last vocabulary name of
the restored draft (`answer_is_draft_tail` false, false, false): the model reports the
interior position (`knudnd` for the item whose terminal is `spog`, `clog` where the
terminal is `prish`, `frixm` where the terminal is `brelt`), and a copy rule is a wrong
answer on the interior ask, so the registered X2 downgrade does not fire. This repeats
round 72's result on the same id string: the interior ask breaks the tail-copy confound
on the 27B build, on a second firing.

## Finding 3 (R2, carried): the filler arm still buys nothing, 3 of 3 against 0 of 3

The carried round-72 row `R2_cross_ask` ships `cross_ask_gated` on this firing: arm X
3 of 3 against arm F 0 of 3. Note the delivery nuance: on this cap-bound build the arm-F
failure is a censoring (1,883 to 2,073 prompt tokens, running to the 2,048 cap), not a
refusal - the registered downgrade for that distinction is row P1, which fails here
(Finding 6), so "the filler bought nothing" is owed as a context-matched claim, not
licensed.

## Finding 4 (the removal arm recomputes once): `C64_j64_B` delivers the interior name without any notes

Arm B (the turn-1 answer field only, which is empty on this censored panel) recovered
the step-40 name on `C64_j64` at 1,965 tokens - the model recomputed the interior step
from the fact block alone, on one of three items. Arm B censored on the other two. So
the record now has two routes to the interior name on this build: the item's own draft
(X, 3 of 3, fast, 267 to 692 tokens) and a fresh traversal of the facts (B, 1 of 3,
1,965 tokens). The discriminator result of Finding 1 is unchanged: a foreign item's
scaffold is neither route. This is the first public firing of the readout family in
which the removal arm is not a null arm, and it lands on the build whose wall is
cap-bound, so the one recomputation is a delivery just under the cap, not a stable
property.

## Finding 5 (controls, V2 and C1): the NONE side re-presents on this id string, and no arm manufactures a name

The past-the-tail control runs to the cap at turn 1 instead of refusing, 0 of 1 declared
`NONE`, so the control gate is not met: issue #139 re-presents (fifth public firing on
record, fourth distinct serving id string), and on this build its direction is
truncation, this time under all four arms as well (0 of 4 arms declared `NONE`). In its
favour, and this matters for Findings 1 and 4: **not one false name in any arm** (0 of 4
on the control, 0 of 3 on each name cell's arms), so the cue did not buy names with
question pressure even with the own or a foreign draft in context. Self-agreement
(issue #100): the anchor prompt was dispatched twice, in the pre-gate calibration and as
the `A48_j8` cell, and both times delivered the same correct terminal (`trackst`), at
250 and 1,176 tokens respectively: the answer is stable on this build, the cost is not
byte-stable, unlike round 72's exactly-266-token twin.

## Finding 6 (P1, the registered downgrade): the arms are not matched on endpoint prompt_tokens, so the context-length claim ships downgraded

The row P1 band (measured spread of at most 400 tokens across the prompt_tokens of X, C
and F, all above arm B's) is violated on all four armed cells: the notes-arm spread is
1,168 (A48), 1,107 (B50), 1,281 (C64) and 1,202 (the control) tokens. The arithmetic is
coherent and build-tied: every own draft is cap-censored at exactly 2,048 completion
tokens, so arm X adds a constant 2,057 measured prompt tokens over arm B on all three
name cells (2,048 draft + the 9-token notes label); the foreign blocks (donor drafts
truncated to 767 to 880 whitespace tokens) add 1,646 to 1,859; the filler blocks add
776 to 950 (a filler token is roughly one model token). Whitespace-token parity
(F1: 880, 941, 767) therefore does NOT imply model-token parity, exactly the
mismatch the 2026-11-18 pr-review record predicted for this instrument family. The
context-length claim in this README (Finding 3) ships downgraded to
`context_length_unmatched` per the gate: the "recovery is not an artifact of context
length" reading is owed until the arms are matched on measured prompt tokens (a
tokenization-aware filler budget is the natural next instrument).

## Finding 7 (the wall on this build, W2 and M4): cap-bound, a fourth public firing on that side of the split

`L3_cap_bound` fits 16 of 21 records (every censored record, reserve at or below 19);
neither the round-59/69 band of 1,556 to 1,558 at finish `stop` nor the round-53 reserve
of exactly 492 fits anything. The M4 comparison is the sharp part: `A48_j48`,
`B50_j50` and `C64_j64` are byte-identical prompts (digests `baabc346`, `c15a68eb`,
`c1ef6c20`) that the round-69 build stopped at 1,556 to 1,558 while emitting `spog`,
`NONE` and `cruuk`, that the round-70 build ran to the cap emitting nothing, that round
72 ran to the cap emitting nothing again on this id string, and that run to the cap
emitting nothing on this fourth firing. The wall's mode is build-tied, and on this id
string it is cap-bound on both of its public firings so far; every "class" statement
across rounds remains a build statement under the digest convention (issue #126).

## Reading

The registered discriminator answers its question on the 27B build: the interior-ask
recovery of round 72 is specific to the item's own draft. A different item's draft, cut
to the same whitespace-token budget, recovers the interior name in 0 of 3 against 3 of 3
for the own draft; a neutral filler of the same budget also recovers in 0 of 3; and the
removal arm recovers in 1 of 3 by recomputing from the facts. What survives is a
readout claim about the record's own prior output store for that item, not a
scaffold claim about name blocks in general, and not yet an introspective-access claim:
the T6 prior (arXiv:2605.29087, the trace-anchored defense backfired) is not excluded,
the P1 context-length downgrade is owed (Finding 6), and H1 (the arm-damages-a-right-
answer side) returned empty on this build (n_held = 0). Trace exposure on this build is
`reasoning` (issue #105), so this is a trace-exposed-deployment claim and does not
transfer to a zero-trace deployment. Small n per level is exploratory and is stated as
such.

## Next steps

1. The flash build's arm C completes the square: the 2x2x2 of {terminal ask, interior
   ask} x {flash build, 27B build} x {own draft, foreign draft} is now missing exactly
   one cell, the interior ask on the foreign draft on the flash build (round 73 ran the
   own-draft interior ask there).
2. The P1 debt: match the arms on measured endpoint prompt_tokens (a tokenization-aware
   filler budget, or a donor draft selected for prompt-token parity) so Finding 3's
   context-length claim can be licensed instead of downgraded.
3. Issue #152 item 3 stays owed: this build is the cap-bound side of the split, so no
   cell answered at turn 1, `H1_answer_stability` returned empty (n_held = 0), and the
   record still has no "does the arm damage a right answer" side; a firing on a band
   build that answers is what item 3 requires.
4. Finding 4's recomputation (1 of 3 on arm B) is worth a follow-up on a build that
   answers at turn 1: does removing the draft damage a right answer, and is the B-arm
   recovery item-specific?

## Instrument notes

- The gold-leak precondition is the narrow one: the three item vocabularies are NOT
  pairwise disjoint (7 names shared between the two level-48/50 items, 3 between 48 and
  64, 1 between 50 and 64), but the asked interior gold is asserted absent from each
  donor item's vocabulary per donor pair, and the field
  `foreign_block_contains_gold` is a belt-and-suspenders census on every delivered
  foreign block (false on all 4 this round).
- The donor drafts are the donor items' own cap-censored traces: 880 of 880 budget for
  A48 (B50's draft truncated exactly at budget), 767 of 941 for B50 (the C64 draft used
  whole, it is shorter than the budget), 767 of 767 for C64 (A48's draft truncated at
  budget) and 846 of 846 for the control.
- The trace of a turn-1 record is held in memory only long enough to build its four
  arms; no trace text is archived, and `raw.jsonl` carries trace counts, the draft's
  last vocabulary name, the foreign block's last vocabulary name and the realized
  budgets only.
- The instrument is frozen with the gate at blob `94b56078aea92c82`; no scoring,
  selection, gate or dispatch code was edited after the panel ran, and `--rescore`
  reproduces [summary.json](summary.json) from the frozen [gate.json](gate.json) and
  the unchanged [raw.jsonl](raw.jsonl). `raw_meta.json` records the gate blob the
  dispatch was run against (the same blob; no re-freeze this round).

## Theory rows, as carried in the gate

- `T1_verbal_report_bibliographic`, Ericsson & Simon 1980, "Verbal reports as data.",
  Psychological Review 87(3), DOI 10.1037/0033-295X.87.3.215. Used only as the
  bibliographic anchor for the frame that a report is a retrieval from a prior store
  rather than a special introspective faculty. Verification: Crossref work record
  refetched this session 2026-11-19, record level (title match); the thesis wording
  was not read this session and is carried as owed.
- `T2_reports_as_causal_theory`, Nisbett & Wilson 1977, Psychological Review
  84(3):231-259, DOI 10.1037/0033-295X.84.3.231. A fluent report can be produced by
  implicit causal theory instead of by access to the process, which is the reason arm X's
  recovery is not by itself access. Verification: Crossref work record fetched 2026-11-17
  in the round-72 gate (PR #153), record level only, with the round-72 title/venue
  correction on record; not refetched this session.
- `T3_accessibility`, Block 2007, Behavioral and Brain Sciences 30:481-499,
  DOI 10.1017/S0140525X07002786. The row operationalizes availability-for-report
  versus report. Verification: Crossref work record fetched 2026-11-17 in the round-72
  gate (PR #153), record level only; the circulated second-DOI-suffix caveat stands.
- `T4_verbalizable_workspace`, arXiv:2607.15495 v1 (Gurnee, Sofroniew, Pearce and
  co-authors; Lindsey corresponding group), unrefereed preprint: a set of
  representations the model is poised to verbalize whose contents can be reported and
  carry the intermediate steps of silent reasoning. Verification: arXiv export API,
  abstract level, refetched this session 2026-11-19, quoted phrase present.
- `T5_introspection_gap`, arXiv:2601.01828 v1 (Lindsey), unrefereed preprint:
  injecting known concepts into activations and reading the self-report separates
  grounded report from confabulation; the abstract reports the capacity is highly
  unreliable and context-dependent. Verification: record level via the archived [FT]
  entry `archive/round8-do-llms-think/2601.01828-lindsey-introspective-awareness.md`;
  the base-model versus post-trained asymmetry is not in the abstract and is not
  claimed.
- `T6_trace_answer_dissociation`, arXiv:2605.29087 v1, unrefereed preprint (paper
  title "The Chain Holds, the Answer Folds"): the chain stays correct while the emitted
  answer flips, a latent-correct rate near 50 percent at the behavioral flip in think
  mode against 11 to 15 percent without a thinking channel, and a naive trace-anchored
  defense backfires. That last clause is the registered prior against arms X and C:
  restoring the channel is not assumed to help. Verification: arXiv export API,
  abstract level, refetched this session 2026-11-19, quoted phrase present.

## How to reproduce

`python3 cross_ask_c_r75.py --selftest` (140 checks, no prompts), then with
`NIGHTLY_BASE_URL` / `NIGHTLY_MODEL_ID` (and `NIGHTLY_API_KEY` when the endpoint needs
one) exported: `--fetch-theory` (three free scholarly API calls: two arXiv abstracts,
one Crossref record), `--measure` (2 prompts against the 40 cap), `--freeze` (writes
[gate.json](gate.json), prints the blob), `--run` (21 dispatches, sequential),
`--rescore` (reproduces [summary.json](summary.json) from the frozen gate and
[raw.jsonl](raw.jsonl)). The gate blob of the frozen dispatch is in
[raw_meta.json](raw_meta.json).
