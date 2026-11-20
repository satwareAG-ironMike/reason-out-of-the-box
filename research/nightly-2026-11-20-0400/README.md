# Round 77 (2026-11-20 04:00): does the own-content readout survive when the arms are token-matched - the registered P1 debt, a tokenization-aware filler/donor budget on the 27B build

Nightly round 77, pool slot 6/6, a 27B-class local endpoint whose serving build is
identified here by the pinned model digest `26df9af5972ff312`. That id string fired
publicly in round 54 (PR #133), round 63 (PR #143), round 72 (PR #153) and round 75
(open PR #155), all unmerged; this is its fifth public firing, and no archived number on
this build is quoted below except the registered M4 prompt-identity and wall-shape
comparisons. Tracker issue #65. Serves the P1 debt registered by round 75 and owed in
issue #152 (the token-matched filler), plus #152, #71, #94, #105, #100, #145, #139,
#126 and #73. Evidence label: **Executed** (exploratory, one endpoint, one build, one
firing, one sample per cell).

## Question

Round 75 shipped the primary verdict `own_content_selects` (arm X 3 of 3 against arm C
0 of 3 and arm F 0 of 3) with the context-length claim downgraded to
`context_length_unmatched`: the notes arms were matched on whitespace tokens, not on the
endpoint's tokenization, so arm X added a constant 2,057 measured prompt tokens over arm
B while arm F added only 776 to 950 and the P1 band of 400 failed on every armed cell.
The round-75 "Next" item and issue #152 register the debt: **match the arms on measured
`prompt_tokens` with a tokenization-aware filler/donor budget**. This round re-runs the
same four-arm panel with that fix, on the three M4 items whose turn-1 prompts are
byte-identical to the round-63/69/70/72/73/75 dispatches:

- **arm X**: the turn-1 answer field plus the item's own turn-1 non-report channel under
  the notes label (the own draft);
- **arm C**: the turn-1 answer field plus a draft of a DIFFERENT item, **used whole and
  uncut** under the same label (a donor chosen for prompt-token parity by taking the
  donor's cap-censored draft whole, instead of the round-75 whitespace-token cut; donor
  map frozen in the gate: A48 takes B50's draft, B50 takes C64's, C64 takes A48's, the
  control takes A48's);
- **arm F**: the turn-1 answer field plus a **tokenization-aware filler**: the block
  starts at the draft's whitespace-token budget and is tuned by at most two registered
  probes at cap 1 that read the endpoint's own measured `prompt_tokens`, to sit within
  the P1 band of arm X's measured `prompt_tokens`;
- **arm B**: the turn-1 answer field only.

Per-cell dispatch order X, C, B, then the F probes and the F scoring dispatch, so the
tuner sees arm X's and arm B's measured `prompt_tokens` before it places the filler.
Row P1 keeps the round-75 band (400 tokens of spread across the measured
`prompt_tokens` of X, C and F, all above arm B's) and ships the context-length claim
only while it holds; violation ships it downgraded, which is the registered fallback.

## Instrument

[cross_ask_tk_r77.py](cross_ask_tk_r77.py), stdlib only. `--selftest` runs 151 checks
before any prompt: solver agreement with the path walk at `j = 0, 1, mid, level` and
`None` one step past the tail on all three items; every item is a load-floor (two
chains, `facts = 2 * level`) component-isomorphic item and a doctored and an
out-degree-two item are refused; the interior ask is asserted strictly inside the walk
and the interior gold asserted distinct from the tail and the start; the filler token
asserted outside every item vocabulary; the archived k = 48 anchor regenerates with
seed 116261051 and its archived yes/no prompt digest `068bc6a1fb0620fb`; three turn-1
prompt digests equal the round-63/69/70/72/73/75 pins and the dispatch (row M4), so
"same items, same prompts, different firing" is machine-checked; the per-donor-pair
gold-leak precondition is asserted (the asked interior gold is absent from the donor
item's vocabulary - the item vocabularies are not pairwise disjoint, so the narrower
per-pair property is the asserted one); the F tuner is exercised on planted outcomes
(in-band keep, the rescale step, the non-positive-increment fallback, the
missing-measurement keep, the rescale floor); the probe records are exercised to stay
out of every scored row and census; and sanitizer controls on assembled fixtures so
this file carries no instance of what it redacts.

Gate `round77-gate-v1` frozen before dispatch, blob
`c42a9f657da9bf524b58b0fdcd62db080a45ccb22f74e13c0ddba4cdca5d67de`, and
`raw_meta.json` records the same blob as dispatched against; no re-freeze this round.

The per-cell F tuning landed as registered: probe 1 at the whitespace budget (951,
943, 946 and 842 words) read 1,954 to 2,252 measured prompt tokens against arm X's
3,050 to 3,354, out of band, so the registered rescale ran (one probe 2 per cell, 8
probes total) and the tuned filler of 2,035 to 2,038 words landed within 10 to 13
measured prompt tokens of arm X on all four armed cells.

## Result

31 prompts of the protocol's 40: 2 pre-gate (the exposure census at cap 256, one
full-cap calibration) plus 29 dispatched (5 turn-1 cells, 16 arm scoring dispatches,
8 F probes at cap 1). Dispatch wall 343.1 s, 0 transport errors, 0 retries.

Gate rows as frozen: `V0_trace_exposure` passes, the deployment hands back `reasoning`
(239 characters on the census call, 29 of 29 dispatched records carry a channel), so
arms X and C are constructible. `V1_solver_certified` passes in `--selftest` (including
the per-donor-pair gold-leak assertion). `V3_anchor` passes: `A48_j8` delivers the
correct terminal at 1,113 tokens. `V2_control_liveness` **fails**: 0 of 1 past-the-tail
controls declares `NONE` at turn 1, it censors at the cap (see Finding 5).
`C2_foreign_draft` is evaluable (scope 3 against the frozen minimum of 2) and ships as
`own_content_selects`, now under a token-matched context (Finding 2).
`P1_prompt_tokens_parity` **holds on all four armed cells** (Finding 1), which
licenses the context-length claim that round 75 had to ship downgraded.

| Cell | j asked | gold | turn-1 delivery | turn-1 tokens | arm X | arm X tokens | arm C | arm C tokens | arm F | arm F tokens | arm B | arm B tokens |
|------|---------|------|-----------------|---------------|-------|--------------|-------|--------------|-------|--------------|-------|--------------|
| `A48_j48` | 48 | spog | censored at cap | 2,048 | **correct at step 40** | 269 | **correct at step 40** | 1,622 | censored at cap | 2,048 | **correct at step 40** | 1,898 |
| `B50_j50` | 50 | prish | censored at cap | 2,048 | **correct at step 40** | 333 | censored at cap | 2,048 | censored at cap | 2,048 | **correct at step 40** | 1,966 |
| `C64_j64` | 64 | brelt | censored at cap | 2,048 | **correct at step 40** | 782 | censored at cap | 2,048 | censored at cap | 2,048 | censored at cap | 2,048 |
| `C64_over` | 72 | NONE | censored at cap | 2,048 | **NONE declared** | 1,571 | censored at cap | 2,048 | censored at cap | 2,048 | censored at cap | 2,048 |
| `A48_j8` | 8 | trackst | **correct** | 1,113 | (anchor, no arms) | | | | | | | |

Whole-panel delivery census over the 21 scored records (issue #145): 13
`censored_at_cap`, 7 `delivered_correct`, 1 `declared_none`. The interior gold sits in
the turn-1 trace in 3 of 3 terminal cells (the evaluable scope). Wall laws:
`L3_cap_bound` fits 13 of 21 scored records; `L1_self_stop_band` and `L2_reserve_492`
fit none.

## Finding 1 (P1, the registered debt): the token-matched arms hold the band on all four cells, so the context-length claim ships

The P1 band (spread of at most 400 measured prompt tokens across X, C and F, all above
arm B's) now **holds on 4 of 4 armed cells**: the notes-arm spreads are 11 (A48), 10
(B50), 10 (C64) and 13 (the control) tokens, against 1,168, 1,107, 1,281 and 1,202 in
the round-75 whitespace-matched firing. The arithmetic is coherent: every own draft is
cap-censored at exactly 2,048 completion tokens, so arm X adds a constant 2,056 to 2,057
measured prompt tokens over arm B; the whole donor draft (arm C) adds 2,056 to 2,057;
and the tuned filler (arm F, 2,035 to 2,038 words) adds 2,044 to 2,047. Whitespace
parity did not imply model-token parity (the round-75 failure mode); measured parity
is what the tuner registers and achieves. "The recovery is not an artifact of context
length" therefore ships this round without the `context_length_unmatched` downgrade.

## Finding 2 (primary, C2): own_content_selects survives the matched context, 3 of 3 against 1 of 3, but the margin thins

All three terminal cells are lost cells (each censored at the cap at turn 1, the
answer field never written) and all three drafts contain the interior gold, so the
paired set is complete: arm X recovers the step-40 name in 3 of 3 (`A48_j48_X` at 269
tokens, `B50_j50_X` at 333, `C64_j64_X` at 782 - all stopping well short of the cap),
arm C in 1 of 3 (`A48_j48_C` at 1,622; censored on `B50_j50` and `C64_j64`), arm F in
0 of 3. The two X-vs-C discordant pairs are both X-only (exact two-sided binomial on
2-0 is 0.5, arithmetic, not significance, at n = 2). The registered verdict ships as
`own_content_selects` (n_X = 3, n_C = 1, n_X - n_C = 2 meets the frozen threshold of
two or more): under a token-matched context, the item's own draft still outperforms the
foreign draft by two recoveries.

The margin is thinner than round 75's 3-0: the foreign whole-draft arm buys 1 of 3
against 0 of 3 under the whitespace match, and the removal arm buys 2 of 3 (`A48_j48_B`
at 1,898, `B50_j50_B` at 1,966) against 1 of 3. The within-cell matched pairs are the
sharp part: on `A48_j48` and `B50_j50`, arm X and arm C share their measured context to
within one prompt token (3,050 to 3,051 and 3,077 to 3,076), yet X delivers at 269 and
333 tokens where C censors or delivers near the cap. The own draft is a fast route to
the interior name (269 to 782 tokens); the foreign draft and the removal arm are the
slow, near-cap route (1,622 to 1,966) or no route at all (censoring, 5 of 8 slow-route
records).

## Finding 3 (C, the gold-leak precondition does its work): the one foreign recovery is a recomputation, not a readout of the donor's content

The `A48_j48_C` recovery of `knudnd` cannot be a copy of the restored donor block: the
donor is B50, the gold-leak precondition asserts `knudnd` is absent from B50's item
vocabulary (the selftest check), and the delivered foreign block's census field
`foreign_block_contains_gold` is `false`. The foreign-draft arm's context therefore
never carries the answer, and its one correct answer is a fresh traversal of the fact
block that the FULL turn-1 prompt user turn keeps in every arm - the same route arm B
uses. What survives the matched context is a content-specificity claim about routes,
not a scaffold claim: the own prior output is the fast route; any name scaffold is
either the same slow recompute (arm C) or nothing (arm F at matched length, arm B on
the two cells it does not reach). The scaffold hypothesis ("any name scaffold puts it
in a lookup posture") stays unsupported: the matched-length filler, the arm-F route,
bought 0 of 3.

## Finding 4 (R2, the token-matched filler): 3 of 3 against 0 of 3, now without the context confound

The carried row `R2_cross_ask` ships `cross_ask_gated` on this firing: arm X 3 of 3
against arm F 0 of 3 (exact two-sided binomial on 3-0 is 0.25, arithmetic, not
significance, at n = 3) - and arm F this round is the tokenized filler, so the
round-75 owed "context-matched filler bought nothing" claim is licensed: a block of
2,035 to 2,038 filler words, matched to the draft's measured prompt-token length within
10 to 13 tokens, recovered no interior name on any of the three cells. All three arm-F
records censored at the cap.

## Finding 5 (controls, V2 and C1): the NONE side re-presents a sixth time, truncating, and no arm manufactures a name

The past-the-tail control censors at the cap at turn 1 instead of refusing, 0 of 1
declared `NONE`, so the control gate is not met: issue #139 re-presents (sixth public
firing on record, fifth distinct serving id string), and on this build its direction is
truncation. In its favour, the control's arm X **declared `NONE` at 1,571 tokens** -
the control's arm side declares the correct refusal on this firing where round 75's
censored on all four arms. And across all sixteen arm dispatches there is **not one
false name** (0 of 4 on the control's arms, 0 of 12 on the name-cell arm dispatches):
the cue did not
buy names with question pressure even with the own or a whole foreign draft in context.
Self-agreement (issue #100): the anchor prompt was dispatched twice, in the pre-gate
calibration and as the `A48_j8` cell, and both times delivered the same correct
terminal (`trackst`) at 1,113 tokens: the answer and the cost are byte-stable on this
firing, unlike round 75's 250/1,176 split.

## Finding 6 (the wall, W2 and M4): cap-bound, a fifth public firing on that side

`L3_cap_bound` fits 13 of 21 scored records (the four turn-1 cells and nine arm
censorings, all at a reserve of 0); neither the round-59/69 band of 1,556 to 1,558 nor
the round-53 reserve of exactly 492 fits anything. The three M4 prompts (digests
`baabc346`, `c15a68eb`, `c1ef6c20`) run to 2,048 emitting nothing again, a fifth public
firing on the cap-bound side of the round-59/69 split, and every "class" statement
across rounds remains a build statement under the digest convention.

## Reading

The round-75 debt is paid: with the arms matched on the endpoint's measured
`prompt_tokens`, the context-length claim is licensed, and under that licensed reading
the primary verdict survives - the item's own draft still recovers the interior name
two or more times better than a foreign draft of the same measured length. But the
matched context also thins the margin (3-1 instead of 3-0) and exposes the second route:
the removal arm and the foreign arm share the slow, near-cap recomputation route, while
the own draft is the fast route. What remains a readout claim about the record's own
prior output store is now a route claim: the own prior output is available for report
fast, and nothing else in context is. The competing caution from T6 (arXiv:2605.29087,
the trace-anchored defense backfired there) is not excluded by this firing. Trace
exposure on this build is `reasoning` (issue #105), so this is a trace-exposed-deployment
claim and does not transfer to a zero-trace deployment.

## Next

(1) The flash build's token-matched arm C plus tuned filler completes the
{terminal, interior} x {flash, 27B} x {own, foreign} square with a licensed
context-length claim (round 73 ran the whitespace-matched interior ask there).
(2) `H1` needs a firing on a band build where several deep cells answer at turn 1
(`n_held = 0` on this fifth cap-bound firing; issue #152 item 3 stays owed).
(3) The slow-route finding (arm B 2 of 3, arm C 1 of 3, both near-cap recomputations)
is owed a follow-up: is the recompute route a stable second channel on this build, and
does it survive a turn-1 delivery build? (4) Flowing to #152 (the P1 debt is paid;
items 1 and 4 stay done, item 3 owed), #139 (sixth re-presentation, truncating) and
#145 (fourth censored-panel instance). Round directory
`research/nightly-2026-11-20-0400` on branch `research/nightly-2026-11-20-0400`; a PR
follows.
