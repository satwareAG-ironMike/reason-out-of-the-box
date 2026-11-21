# Explore ledger (issue #195)

One row per round. A round is merged only when the CI is green and a `[pr-reviewer]` verdict at
head exists on the PR that carries it. The "distance" column names the unresolved part of the
decision rule the round moved, and the distance it closed or confirmed open.

| Round | Date | Claim | n | Effect | Novelty clean rate | Baseline gap | Verdict | Distance moved |
|-------|------|-------|---|--------|--------------------|--------------|---------|----------------|
| r78-cross-ask | 2026-11-21 | Cross-ask family: does the arm-notes block tune the terminal answer to the interior step (H1_answer_stability)? The #166 `tail_copy_downgrade` trigger is registered at `n_X >= 2 AND every delivered arm-X record emitted the draft's last vocabulary name`. | 29 records | `selection_beyond_tail` (arm X delivered the draft tail 0 of 3) | exploratory only (no corpus arm configured) | exploratory only | `OPEN, exploratory` | P1 prompt-token parity held on C64; confirms the trigger alignment; does not move the beyond-depth gap |
| r79-cross-ask | 2026-11-21 | Cross-ask family: #139/#94/#145 trigger fixes on the cross-ask family. | 28 records | `selection_beyond_tail` (arm X delivered the draft tail 0 of 3); `over_end` control shipped `not_delivered` under its own 512-token budget; censored arm cells read `censored_at_cap` and are excluded from the contrast denominator | exploratory only (no corpus arm configured) | exploratory only | `OPEN, exploratory` | Registers the cross-ask arm; does not move the beyond-depth gap |
| r80-ladders-fresh-seed | 2026-11-21 | Ladders k-hop reachability at a fresh seed (20261121, never shipped), one non-reasoning one-word prompt per level. | 8 probes | L4 and L12 judged, both correct (2 of 2). L8 and up: censored at the 512-token cap; the model traces instead of emitting the one-word answer - a registered delivery-contract finding, not a competence verdict | exploratory only | exploratory only | `OPEN, exploratory; delivery contract violated at depth 8+ on this build` | Adds a second family (ladders) to the pool; no beyond-depth cell produced (confirmatory track blocked, issue #196) |

Both rounds are exploratory (Qwen-class endpoint, `exploratory_only_model_class`). They do not
produce a confirmatory cell and do not advance the confirmatory track, which is blocked at 0
cells by issue #196.
