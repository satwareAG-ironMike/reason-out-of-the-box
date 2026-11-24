# Nightly round 85 (2026-11-24 04:01, nightly lane, issue #65): the instruction arms at the wall

Evidence label: `Executed`, exploratory. n = 5 items per arm at depth k = 64 (plus a
3-row wall census), one build of a flash-class local reasoning endpoint (build pin
`model_digest` `c62b81e96826354e`). No confirmatory cell: that track stays blocked at
issue #196.

## Question

Round 84 found that an instruction that forbids reasoning throttles the emitted trace
but never switches it off, and its verdicts never moved - but every item it used was
one this build solves, so the verdict invariance was unfalsifiable there. The
discriminating test: at or past this build's measured depth wall, where verdicts do
move, does the instruction arm change the verdict, or only the delivery surface?

Two readings, opposite predictions. If the trace is the computation (C4 false for
this build at depth), a ban that shortens the trace loses accuracy at the wall while
a permission that lengthens it gains some. If the trace is epiphenomenal narration
(C4), the verdict moves with the wall, not the instruction: all four arms land at
the same accuracy and only the delivery surface (length, censoring, trace) differs
between arms.

## Method

- Family: ladders k-hop reachability, beyond the frozen grid (the generator module is
  called directly, the sanctioned nightly-lane wall pattern of the archived load-floor
  rounds). The frozen judge still builds the prompt and judges the gold.
- Wall census: baseline arm, one load-capped item per census level, k = 32 / 48 / 64.
  The wall is the smallest census level that is not fully delivered_correct; if every
  census level is fully correct, the panel sits at the top of the available depth and
  the round states a top-of-depth invariance reading instead of a wall claim.
- Panel: 5 load-capped items at k = 64 under the four instruction arms (the item text
  is byte-identical across arms): baseline (the frozen judge template verbatim),
  suppression (an imperative: produce no reasoning at all), ironic (the same ban in
  negated form, the white-bear / ironic-process framing), posthoc (an explicit
  permission to reason after the one-word answer).
- Load-capped selection (registered in the gate): the generator draws
  `n_chains = randint(2, level + 2)`, so a level-64 item can carry up to 4,224 facts
  and turn the depth question into a load question. Qualifying means at most 4 chains
  (at most 4 x level facts); items are taken in ascending scan order, and the scanned
  and skipped seeds are recorded in the gate.
- 22 planned prompts: 3 census rows + 19 panel rows (the census k = 64 row doubles as
  the panel's baseline item 0). max_tokens 2048, temperature 0.0, one dispatch at a
  time. Under the 40-prompt round cap.
- Seed base 20261124 (the judge's run-date policy). Fresh items; no prompt on this
  build has fired publicly at these depths before this round.
- Gate frozen before dispatch, blob `d7d0ce0c31d36546afd102054372d8ac71d46ccd12958b541ec5a4a0af89cf52`;
  the pre-dispatch measurement's worst-case estimate decides the dispatch (the
  round-61 kill rule, pre-registered in the gate).
- Build pin: the sha256 digest of the serving id, first 16 hex (the house convention).
  A digest match across rounds is a serving-identity match, not a proof of identical
  binaries.

## Pre-dispatch measurement (measure.json)

Census: k = 32 delivered_correct in 914 tokens; k = 48 delivered_wrong, stopping at
1,556 tokens (the build's self-stop band); k = 64 mixed. Mean rate 38.4 tok/s;
worst-case wall 19.6 minutes at the 2048 cap, under the 45-minute kill bound, so the
panel dispatched.

Deviation from the round-61 shape: the measure step's census filter picks the plan's
own baseline rows at the census levels, so it bills 7 of the 22 planned rows (not
3); the dispatch step bills the remaining 15. Total is 22 either way; no off-plan
calls this round.

## Results (summary.json)

G0 wall identified: pass, reading `wall_at_48` (k = 32 correct, k = 48 wrong,
k = 64 mixed). G1 trace channel exposed: pass, `reasoning_content` on 22/22 records
(served surface: `/chat/completions`). G2 ban reduces trace: fail (the ban does not
reduce trace presence: 5/5 traced under the ban vs 7/7 baseline, both fractions 1.0;
medians pinned at 1,556 tokens in both arms). G3 negated ban backfires: fail
(5 traced under ironic vs 7 baseline, margin -2 against the +2 threshold). G4 verdict
invariant to the ban: fail (5 comparable items, 4 invariant, but the rule's
gold-agreement clause fails on item L64_i196, wrong in both arms). G5 ban rescues at
the wall: inconclusive_budget (1 eligible item, below the pre-registered minimum of 3,
issue #145; the one eligible item, L64_i196, was not rescued). G6 permission
lengthens: pass (posthoc median 2,024 completion tokens vs 1,556 baseline, ratio
1.301, with the round's only censoring: one posthoc record at the 2,048 cap).

The load-capped panel at k = 64 under baseline: 4 of 5 delivered_correct. The build
fails L64_i196 in every arm (declared "yes", gold "no") and flips L64_i322: declared
"no" (correct) under baseline, "yes" (wrong) under both ban arms, censored under the
permission arm.

Self-stop census (the build's 1,556-1,558 completion-token band, an uncapped
readout; the text marker is observable only inside the recorded 1,600-char trace
window and was not observed in any record): baseline 4/7 in band, suppression 4/5,
ironic 4/5, posthoc 0/5. The band is instruction-invariant under the ban arms and
gone under the permission arm.

## Reading

- The verdict moves with the wall, not the instruction. The two items this depth
  defeats (L64_i196 outright, L64_i322 under every non-baseline arm) move between
  arms only in the direction of worse delivery, and the ban rescues nothing: G5 is
  inconclusive_budget, not a competence claim.
- The ban is not a length lever at the wall. Round 84's throttle finding held inside
  the wall (median 336.5 ban vs 439.0 baseline tokens); at the wall the build
  self-stops in the 1,556 band regardless of instruction (median completion tokens
  1,556 in baseline and suppression alike), so the instruction rides the build's own
  stop signature instead of moving it.
- The permission arm is the only arm that leaves the band (0/5 in band, median
  2,024), lengthening at the cost of one censored record.
- C4 reading at this build's wall: the verdict is decided by the computation at
  depth; the trace and the instruction are epiphenomena on top of it, and the
  instruction's noise here degrades delivery (the L64_i322 flip) rather than
  improving it. Exploratory, one build; the confirmatory track stays blocked at
  #196.

## Cap ledger (issue #195)

Round cap: 22 of 40 prompts. Weekly: this round's 22 sit in 2026-W48 alongside round
84's open PR #219 (34 prompts: 32 scored + 2 out-of-plan diagnostics recorded in its
README), so the true W48 nightly-lane ledger is 56 of 80 - cap not spent. The cap
audit instrument's static open-PR registry (research/nightly-2026-11-22-0409/
cap_audit.py) predates PR #219 and does not carry a record for it, so its recorded
W48 total is 22 of 80; the registry gap is noted here and is owed to the next
maintenance round (or to the merge of #219).

## Next steps

- A panel at k = 48 (the identified wall level) with more eligible items would make
  G5's rescue question decidable; 5 items per arm and 3 census rows would fit the
  remaining weekly budget.
- The registry update owed above (cap audit open-PR records).
- The L64_i322 instruction flip is owed to #126 (cap-wall / instruction dependence
  tracking); it is recorded here, not cross-posted this round.

## Row-and-blob guard (issue #137)

Rows G0 G1 G2 G3 G4 G5 G6 and H1. gate blob `d7d0ce0c31d36546afd102054372d8ac71d46ccd12958b541ec5a4a0af89cf52`
