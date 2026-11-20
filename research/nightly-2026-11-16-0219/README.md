# Round 69 (2026-11-16 02:19): the k > 48 name-walk panel re-fired byte-identically on the self-stopping build - 1 of 4 again, but every failure is a delivered answer, the 1,556 to 1,558 band returns at 5 of 8 cells, and the trace-tail prediction fails on its position measure

Nightly round 69, pool slot 1/6, a flash-next-class local endpoint whose serving build is
identified here by the pinned model digest `c62b81e96826354e` (the same digest as round 59,
`research/nightly-2026-11-11-0318/`, PR #140, unmerged at this firing). Tracker issue #65,
round summary comment posted 2026-11-16.
Serves #129 (the panel past the generator ceiling), #126 (the output-budget reading), #145 (the
delivery census, run for the first time), #100 (identical-prompt self-agreement), #105 (trace
exposure census), #94 (no trace-recovery scoring), #139 (dead-end controls at the deep cap),
#73 and #141 (sequential dispatch so a cell's rate belongs to that cell), #137 (the row-label
guard, extended), #150 (opened by this firing, see "Instrument notes").
Evidence label: **Executed** (exploratory, one endpoint, one build, one firing, 12 prompts, one
sample per cell plus two re-dispatched pairs).

## Question

Row P1 was registered by the round-61 gate (`research/nightly-2026-11-12-0232/gate.json`,
PR #142, unmerged here) on four endpoint cells past the old generator ceiling: `A48_j48`,
`A49_j49`, `B50_j50`, `C64_j64`, name arm, requested cap 2,048. 3 or 4 of them delivering the
correct terminal makes the measured wall an output-budget and output-policy artifact (the issue
#126 reading); 1 or fewer keeps the length-generalization reading (rows T1 to T3) alive; exactly
2 of 4 is inconclusive.

Round 63 dispatched that panel on a 27B-class build whose serving identity is a different digest
(recorded in that round's own gate) and returned 1 of
4 (`research/nightly-2026-11-13-0348/`, PR #143, unmerged here). This firing dispatches the
**identical eight cells on the other side of the identity split**: the build whose digest is
pinned in the gate, the build that returned 2 of 4 on the same four labels at level 48 to 64 in
round 49, and the only build in this record that has produced wrong terminal names (rounds 37,
38, 47, 49, 59). Items, seeds, golds, caps, prompt template and dispatch order are frozen from
the shipped generator, and the eight prompt digests are asserted in `--selftest` against the
round-63 pins, so **the build is the only variable between the two firings**.

Two rows were added on top of the registered one, both frozen before dispatch in
[gate.json](gate.json) (blob
`7d574b8e74e3bc245557d37f8232db92e27380b6a71eeb421888d9a347a61865`):

- `S1_delivery_census` (issue #145): the registered count treats a cell that delivered nothing
  the same as a cell that delivered a wrong name. Every endpoint cell is therefore also
  classified into one of seven delivery states and `n_eligible` (cells that put a readable answer
  on the wire) is reported beside the count. When the 1-or-fewer branch is carried entirely by
  non-deliveries the outcome takes the name `inconclusive_budget` and the reading stays owed.
- `X1_stopping_build_prediction`: round 64 (`research/nightly-2026-11-13-0441/`, PR #144,
  unmerged here) registered a prediction about this build: a wrong position should coincide with
  a self-truncated trace, and the emitted name should be the last position its own trace reached.
  That prediction was owed a firing on its own build. This is that firing.

`W2_wall_signature_census` fits every record against the three archived wall laws: `L1` the 1,556
to 1,558 token band at finish `stop` (round 59, the same digest), `L2` a reserve of exactly 492
tokens (round 53, PR #131, unmerged), `L3` a reserve at or below 19 tokens (round 54, PR #133,
unmerged).

## Instrument

[name_walk_panel_r69.py](name_walk_panel_r69.py), stdlib only. `--selftest` green with 125 checks
before any prompt, including planted negatives: the archived k = 48 anchor regenerates with seed
116261051 and its archived yes/no prompt digest `068bc6a1fb0620fb`; every item is a load-floor
(two chains, `facts = 2 * level`), component-isomorphic item and a doctored 94-fact item and an
out-degree-two item are refused; the independent solver agrees with the path walk at `j = 0, 1, 8,
level` and returns None one step past the tail; all eight prompt digests equal the round-63
matched-pair pins; the seven delivery states, the three wall laws at both boundaries, the four P1
branches, the `inconclusive_budget` naming, the three X1 measures, a controls-invalid panel, an
undispatched panel, a mid-word cap censor, a stopped record that wrote no answer, an answer field
carrying a token that is not one of the item's entities, the trace-merge rule, the sanitizer
(IP, host path, serving-id label classes) and six planted README-guard negatives are each tested.
`init_items()` fails closed before any call if a recomputed prompt drifts from a pin.

Dispatch is one worker at a time in panel order (issue #73, adopted here for the first time) and
each record is written to [raw.jsonl](raw.jsonl) before the next call starts, so a cell's wall
time, token count and rate belong to that cell (issue #141: a co-fired grid starves a shared host
to about one completion token per second). Per-call guard 900 s, at most 4 attempts, backoff
`5 * attempts`, dispatch budget 3,000 s with a 120 s floor to start a cell; `temperature` 0.0,
requested cap 2,048 for every cell.

Pre-gate measurement (the round-61 standing rule, frozen thresholds kept identical to round 63:
full panel at or above 10.0 tok/s, trimmed panel below 5.0, and the trimmed plan is six cells):
two census calls at cap 256 plus one full-cap calibration dispatch on the anchor prompt. Measured
17.744 tok/s, so `--freeze --panel auto` froze the **full eight-cell panel** before any panel cell
was called. Trace exposure (row E2, issue #105): this deployment answers the reasoning query
correctly and supplies the trace in `reasoning_content`, with message fields `content`,
`reasoning_content`, `role`. Round 63's build on the identical prompts supplies the same census
class in a field named `reasoning`, so every cross-build trace statement here names both sides.

## Result

12 prompts of the protocol's 40: 2 census (cap 256) + 1 calibration + 1 trace-exposure call + 8
panel cells. Panel dispatch wall 260.3 s, 0 transport errors, 0 retries, 8 of 8 cells dispatched,
9,362 completion tokens and 8,194 prompt tokens on the panel.

Gate rows: `N3` anchor and matched pair certified pre-dispatch, pass. `E2` census answers "yes"
with a 227-character `reasoning_content` channel, pass. `R1` both dead-end controls declare NONE
at cap 2,048 with finish `stop` (1,059 and 185 tokens, reserves 989 and 1,863), pass, so the
issue #139 inheritance failure does not re-present. `E1` the anchor cell `A48_j8` delivers the
correct terminal `trackst`, pass. `P1` evaluable, certified, controls valid. `S1`, `W2`, `X1`
reported below. Tier: `panel_delivered`. Flags: `endpoint_named_wrong:A49_j49`,
`x1_prediction_refuted`.

| Cell | j asked | gold | answer field | delivery state | tokens | reserve | finish | wall s | tok/s | trace chars | path positions named |
|------|---------|------|--------------|----------------|--------|---------|--------|--------|-------|-------------|----------------------|
| `A49_deadend` | 1 | NONE | NONE | declared_none | 1,059 | 989 | stop | 18.881 | 56.088 | 3,048 | 1 of 1 |
| `C64_deadend` | 1 | NONE | NONE | declared_none | 185 | 1,863 | stop | 26.430 | 7.000 | 693 | 1 of 1 |
| `A48_j48` | 48 | spog | **spog** | delivered_correct | 1,557 | 491 | stop | 31.293 | 49.756 | 4,525 | 49 of 49 |
| `A49_j49` | 49 | studnd | blont (step 47) | delivered_wrong_on_right_path | 1,557 | 491 | stop | 32.348 | 48.133 | 4,247 | 50 of 50 |
| `B50_j50` | 50 | prish | NONE | declared_none_on_name_gold | 1,556 | 492 | stop | 46.118 | 33.740 | 4,389 | 51 of 51 |
| `C64_j64` | 64 | brelt | cruuk (no such entity in this item) | delivered_no_item_name | 1,558 | 490 | stop | 34.301 | 45.421 | 4,039 | 65 of 65 |
| `B50_j50_dup` | 50 | prish | NONE | declared_none_on_name_gold | 1,556 | 492 | stop | 51.822 | 30.026 | 4,344 | 51 of 51 |
| `A48_j8` | 8 | trackst | **trackst** | delivered_correct | 334 | 1,714 | stop | 19.067 | 17.517 | 1,162 | 9 of 9 |

"path positions named" counts the nodes of the asked path whose name appears in that record's
trace channel. It is a census of the trace text, not a second verdict: per issue #94 and the
round-50 calibration failure (0.5652 on the identical items) no verdict in this round is taken
from a trace, and no trace text is archived.

## Finding 1: the registered count is 1 of 4 on both sides of the split, and the matched pair makes the build the only variable

`A48_j48` correct, `A49_j49` a wrong name, `B50_j50` a refusal where a terminal was asked,
`C64_j64` an answer field carrying `cruuk`, a five-letter token that is not one of the 128
entities of its own item. `n = 1` of 4, which lands on the registered 1-or-fewer branch: the
length-generalization reading (T1 to T3) stays alive on this build as it did on the round-63
build. Both sides of the identity split now return 1 of 4 on byte-identical cells, machine-checked
against the round-63 pins in `--selftest` and recorded in `N3` with no digest mismatch. The count
does not move with the build. What moves is everything underneath it, which is what rows S1 and W2
are for.

The correct cell is the shallowest of the four (`j = 48`), and the three failures degrade in asked
step order: `j = 49` emits a name two links short of the terminal, `j = 50` refuses, `j = 64`
emits a token that is not in its own item. Four cells, one sample each: this is an ordering
observation, not a slope.

## Finding 2: the same count has opposite eligibility on the two builds (row S1, issue #145)

Here `n_eligible = 4`: all four endpoint cells put a readable answer on the wire (a correct name,
a wrong name on the asked path, a delivered refusal, a delivered non-entity token), so the
1-or-fewer branch is `delivery_backed` and stays evaluable. `inconclusive_budget` does not apply:
none of the three failures is a non-delivery.

Retro-scanning round 63's eight records against this round's census rule (round 63's gate had no
S1 row, and its records carry `finish_reason = length`, `completion_tokens = 2048` and an empty
answer field for `A48_j48`, `A49_j49`, `C64_j64` and `B50_j50_dup`) classifies those four as
`censored_at_cap` and gives `n_eligible = 1`: its 1 of 4 would carry the name
`inconclusive_budget`, because every non-correct endpoint cell of that branch delivered nothing.
That is the distinction issue #145 asked for, and the matched pair shows why it matters: two
firings with the same registered count, one in which the model answered three questions wrongly
and one in which it was cut off before answering them. The registered P1 evaluation is scored
exactly as the round-61 gate defines it; the eligibility state is reported beside it and does not
replace it.

## Finding 3: on this build the wall is a self-stop in a 3-token window that does not move with depth (row W2)

5 of 8 records sit in the 1,556 to 1,558 band at finish `stop` (`A48_j48` 1,557, `A49_j49` 1,557,
`B50_j50` 1,556, `B50_j50_dup` 1,556, `C64_j64` 1,558) and **no cell is cap-bound**; the three
outside the band are the two NONE controls and the shallow anchor. `L1` re-presents, and the two
1,556 records also fit `L2` (reserve exactly 492). The band spans `j = 48` to `j = 64`, i.e. the
self-stop is depth-independent on this build, and it reproduces the round-59 signature (16 of 26
records in the same band) on the identical digest. `L3` (the cap-bound shape that round 54 measured
on the 27B class) fits nothing here, so the wall mode stays build-tied rather than firing-tied.

The matched pair sharpens that claim: on the same eight prompts, the round-63 build put four
records at exactly 2,048 with reserves 0 (cap-bound, `L3` shape) while this build put five records
inside a 3-token window 490 to 492 tokens below the same requested cap. Trace length behaves the
same way: 4,039 to 4,525 characters here against 5,183 to 5,664 there.

## Finding 4: the prediction about self-truncated traces fails on its position measure (row X1)

One endpoint cell named a terminal the solver did not accept, so the row is evaluable on exactly
one record. `A49_j49` emitted `blont`, which is node 47 of the 49-link path it was asked to walk.
Two of the three measures hold: `blont` is the last generator-vocabulary name in its own trace
(`name_is_trace_tail` true) and the record truncated itself rather than being cut (finish `stop`,
491 tokens of reserve, `self_truncated` true). The third fails: the furthest position along the
asked path that its trace names is 49, two positions past the name it emitted
(`position_agrees` false). So the emitted name was not the furthest place its own reasoning got
to, and the prediction is **refuted** on this build. `n = 1` record.

Two coverage limits on that row, stated before anyone leans on it. Its definition is
vocabulary-bound: `C64_j64` answered with a token that is not an entity of its item, which is not
"a terminal the solver did not accept", so X1 cannot see the single most unusual failure of the
firing while S1 classifies it. And the name-tail measure is not a property of this build's traces:
in `A48_j48`, the cell that answered correctly, the trace's last generator-vocabulary name is
`blixt`, not the terminal `spog` it emitted, so `name_is_trace_tail` holding for `A49_j49` has no
mechanism behind it in this record set.

## Finding 5: in all four endpoint cells the trace names the asked terminal, and only one answer field carries it

Per the census columns above: in `A48_j48`, `A49_j49`, `B50_j50` and `C64_j64` the trace names
every node of the asked path (`path positions named` equals `j + 1` in all four), the node at the
asked step included (`trace_max_step_index` equals `j` in all four, and `gold_in_trace` is true in
all four, as it was in all four on the round-63 build). Only `A48_j48` puts that terminal in the
answer field. `A49_j49` names a node two links short, `B50_j50` declares NONE, `C64_j64` emits a
non-entity token.

On this build, at these depths, the walk is not where the loss happens: the loss is between a name
the record already contains and the one word the answer field carries. That is a different failure
from the one the registered 1-or-fewer branch licenses, and the two statements have to sit next to
each other: `P1` scores 1 of 4 and the registered reading stands, while this firing's own record
shows the depth reached and the readout lost. This firing does not resolve that tension; it
measures it, and it does so without letting the trace score anything (issue #94, and the round-50
rule that a trace-derived verdict is refused rather than trusted).

## Finding 6: instrument notes, one of which is an erratum against my own gate

- **Sequential dispatch attributes rate to the cell** (issue #73 adopted, issue #141 mitigated).
  Per-cell rates run 30.026 to 56.088 tok/s. A 185-token NONE control took 26.430 s and a
  60-token census call took 109.521 s (0.548 tok/s, and its second run 29.875 s, 2.008 tok/s), so
  this host carries a fixed floor of roughly 19 to 30 s per request and the small-request rate is
  not the deep-cell rate. The whole eight-cell panel then ran in 260.3 s against the frozen 3,000
  s budget.
- **The pre-gate rate measured 17.744 tok/s and selected the full panel, and it predicted
  nothing**: it was neither the census rate (0.548, 2.008) nor the deep-cell rate (30.0 to 56.1).
  One calibration dispatch on a shallow prompt is a weak estimator of a panel-scale commitment.
  Round 49 already called the cap-bound selection premise stale; this firing narrows the complaint
  from the threshold to the instrument.
- **Erratum against the frozen gate**: `dispatch.planned_calls = 8` plus `pre_gate_calls = 3`
  accounts for 11 prompts, but `--run` also makes the trace-exposure call, so the firing spent 12.
  No rule, cell, cap or threshold changed and the call cap (40) is nowhere near touched; the gate
  blob is left as frozen rather than re-frozen, because re-freezing after dispatch would replace
  the promise with a description of what happened.
- **Self-agreement is stable on this build** (issue #100). `B50_j50` and `B50_j50_dup` produce
  byte-identical completion counts (1,556 and 1,556) and the same verdict (NONE, NONE); no
  `dup_pair_diverges` flag. The anchor prompt was dispatched twice (pre-gate calibration 359
  tokens, panel `A48_j8` 334 tokens) and delivered the same correct terminal both times. The
  traces are not identical (the two B50 records end their reasoning on different names, `smosh`
  and `schalt`), so the agreement is in the verdict and the token count, not the trace. Round 63's
  identical pair diverged on the other build (1,956 correct against 2,048 censored).
- **The same prompt costs very different amounts on different builds and the anchor token count is
  not a build signature.** On the identical `A48_j8` prompt the panel records are 334 tokens here,
  306 on the round-63 build and 1,123 on the round-61 build, while the round-63 pre-gate
  calibration of the same prompt cost 1,113. Correct (`trackst`) in all five dispatches.
- **This firing also opened #150**: walking the remote's `research/nightly-*` heads against the
  runner's working copy found two complete round records (rounds 56 and 58) plus one
  script-only firing (57) with no branch and no PR, and three firings that created a local head at
  `main` with no commit at all. Six scheduled firings contributed nothing to the public record.

## Theory rows, as carried in the gate

- `T1_tc0_bound`, arXiv:2604.25800 (Barriers to Universal Reasoning With Transformers (And How to
  Overcome Them), Kraus, Sarrof, Yao, Koller, Hahn, arXiv preprint, 2026): learnable
  chain-of-thought length generalizes only within TC0 under standard positional encodings and a
  finite alphabet, and the signpost-token remedy shows the barrier is encoding-specific. Re-read
  at work-record level in this session (OpenAlex record: title, authors, year, venue; no quote
  taken).
- `T2_crasp_characterization`, arXiv:2608.13433 (Algebraic Decomposition Theory for Transformer
  Length Generalization, Yang, Veseli, Barloy, and co-authors including Hahn, arXiv preprint,
  2026): length generalization for regular languages under NoPE holds exactly when the syntactic
  monoid decomposes into loop-balanced integer counters, and a near-binary split with 10x data
  does not rescue the failing class. Re-read at work-record level in this session. Caveat on
  record: the theory is NoPE; these deployments use RoPE.
- `T3_encoding_specific_remedies`, arXiv:2608.31067 with arXiv:2604.25800 (Universal Transformers
  for Circuit Computations: Perfect Length Generalization in Tiny Transformers, Ito, Puri,
  Campbell, Ram, arXiv preprint, 2026): a depth-tracking positional encoding plus halting gives
  exact length generalization on Boolean evaluation, ListOps and modular arithmetic with 280
  parameters, i.e. the wall moves with the encoding. Re-read at work-record level in this session.
- `T4_task_complexity_not_the_wall`, in-repo (rounds 51, 52, 59): the load-floor item at any tested
  depth here is a two-path reachability problem (96 to 128 facts), so the task stays
  computationally trivial while the measured walls sit at a 3-token self-stop window and at asked
  step position. No external source.

Peer-review status: all three external rows are arXiv preprints, none is indexed as
peer-reviewed. None of the three is quoted in this round; the rows license the *interpretation* of
a count, not a measurement.

## Limits

- One endpoint, one build, one firing, `temperature` 0.0, one sample per cell. The only repetition
  is the two re-dispatched pairs (`B50_j50` pair, and the anchor prompt twice).
- `n = 4` endpoint cells. The depth-ordering observation in Finding 1 and the trace-readout
  observation in Finding 5 are each four records wide, and the X1 verdict in Finding 4 rests on a
  single record.
- The comparison set is unmerged. Rounds 52, 53, 54, 55, 59, 60, 61, 63 and 64 are open PRs
  (#131, #132, #133, #136, #140, #138, #142, #143, #144); `main` is at round 50. Every neighbor
  number quoted above is labelled with its PR and its unmerged state.
- Trace text is not archived and never scores a verdict. The trace columns are counts and a
  position census over the record's own reasoning channel (issue #105 census, issue #94 limit).
- The serving identity of the endpoint is recorded only as a 16-hex digest. The instrument reads
  the endpoint, the model identifier and the key from the environment the runner exports and never
  writes them; the sanitizer redacts host, IP, path and serving-id classes from anything the model
  answers, and that behavior is tested in `--selftest`.
- The instrument file was edited after dispatch in one place only: a sanitizer test fixture was
  re-assembled so the file itself carries no serving-id pattern instance (issue #85; the guard
  scans tracked text). No scoring, selection, gate or dispatch code changed after the panel ran;
  `--rescore` reproduces [summary.json](summary.json) byte-identically from the frozen
  [gate.json](gate.json) and the unchanged [raw.jsonl](raw.jsonl).

## Reproduce

```
cd research/nightly-2026-11-16-0219
python3 name_walk_panel_r69.py --selftest          # 125 checks, green before any prompt
python3 name_walk_panel_r69.py --measure           # 2 census calls at 256, 1 calibration at 2048
python3 name_walk_panel_r69.py --freeze --panel auto
python3 name_walk_panel_r69.py --run --panel auto  # refuses to dispatch unfrozen or drifted pins
python3 name_walk_panel_r69.py --check-readme      # row-label and blob guard, issue #137
```

The endpoint, model identifier and key come from the runner's exported environment; the panel and
the frozen thresholds are selected by the measured rate, not by a hand. Artifacts:
[gate.json](gate.json) (blob
`7d574b8e74e3bc245557d37f8232db92e27380b6a71eeb421888d9a347a61865`),
[measure.json](measure.json), [health.json](health.json), [raw.jsonl](raw.jsonl),
[summary.json](summary.json), this README.
