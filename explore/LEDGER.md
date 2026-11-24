# Explore ledger (issue #195)

One row per round. A round is merged only when the CI is green and a `[pr-reviewer]` verdict at
head exists on the PR that carries it. The "distance" column names the unresolved part of the
decision rule the round moved, and the distance it closed or confirmed open.

| Round | Date | Claim | n | Effect | Novelty clean rate | Baseline gap | Verdict | Distance moved |
|-------|------|-------|---|--------|--------------------|--------------|---------|----------------|
| r78-cross-ask | 2026-11-21 | Cross-ask family: does the arm-notes block tune the terminal answer to the interior step (H1_answer_stability)? The #166 `tail_copy_downgrade` trigger is registered at `n_X >= 2 AND every delivered arm-X record emitted the draft's last vocabulary name`. | 29 records | `selection_beyond_tail` (arm X delivered the draft tail 0 of 3) | exploratory only (no corpus arm configured) | exploratory only | `OPEN, exploratory` | P1 prompt-token parity held on C64; confirms the trigger alignment; does not move the beyond-depth gap |
| r80-ladders | 2026-11-21 | Ladders k-hop reachability on a fresh seed (20261121), one probe per level 4-64. | 8 probes | L4/L12 correct (2/2); L8+ censored at the 512-token cap (delivery-contract finding at depth 8+, not a competence verdict) | exploratory only | exploratory only | `OPEN, exploratory` | Items are off the frozen judge's seed grid (judge: `seed_base + 2_000_000*L + i`); n=1 per level < exploratory min n=40 - the next ladders round must fire the judge-conformant arm (r81) |
| r81-ladders-judge-conformant | 2026-11-21 | First judge-conformant exploratory round: ladders grid (1,2,4,6,8), judge seed policy, judge frozen prompt builder; calibration arm measures d_hat, novel-band arm fires the first scorable exploratory cell. | 240 prompts (200 calibration + 40 novel band) | pending (scoring) | exploratory only | B3 not_evaluable (no pinned smaller partner for this class) | `pending` | Closes the "no scorable exploratory round exists" distance item; d_hat measured for the build on the ladders family |

Both rounds are exploratory (Qwen-class endpoint, `exploratory_only_model_class`). They do not
produce a confirmatory cell and do not advance the confirmatory track, which is blocked at 0
cells by issue #196. r78/r79 use the cross-ask family, which is not in the frozen judge's
FAMILIES (digit_matrices, ladders, trap): a `score.py` run over them reports "family not in
the frozen grid", so their distance contribution is the registered finding itself, not a
numeric cell.

| refreeze-126 | 2026-11-24 | #126 panel re-freeze (owner go, W48): re-fire the round-49 battery on a live flash-class build to re-verify the "cap-bound premise void" finding and re-derive the cap-bound panel. | 36 dispatches | mode A truncates 8/11 at 2048 (round 49: 0/11) - the wall is a build property and is back on the current build | n/a (panel re-derivation, not a scorable cell) | n/a | `re-derivation executed` | The #126 "premise void" finding is false on the current build; the cap-bound panel is not empty and re-anchors to the 5 dispatches that hit 2048: S4-X(k=8), S5-F/S5-X(k=12), S6-F/S6-X(k=16). Exploratory rounds keep the cap-bound panel; the archived 11-item panel is retired, not amended |
