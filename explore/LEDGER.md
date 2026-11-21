# Explore ledger (issue #195)

One row per round. A round is merged only when the CI is green and a `[pr-reviewer]` verdict at
head exists on the PR that carries it. The "distance" column names the unresolved part of the
decision rule the round moved, and the distance it closed or confirmed open.

| Round | Date | Claim | n | Effect | Novelty clean rate | Baseline gap | Verdict | Distance moved |
|-------|------|-------|---|--------|--------------------|--------------|---------|----------------|
| r78-cross-ask | 2026-11-21 | Cross-ask family: does the arm-notes block tune the terminal answer to the interior step (H1_answer_stability)? The #166 `tail_copy_downgrade` trigger is registered at `n_X >= 2 AND every delivered arm-X record emitted the draft's last vocabulary name`. | pending run | pending run | pending run | pending run | OPEN, exploratory | Confirms the trigger alignment; does not move the beyond-depth gap |
| r79-cross-ask | 2026-11-21 | Cross-ask family: #139/#94/#145 trigger fixes on the cross-ask family (cross-ask arm registered before any readout-access claim). | pending run | pending run | pending run | pending run | OPEN, exploratory | Registers the cross-ask arm; does not move the beyond-depth gap |

Both rounds are exploratory (Qwen-class endpoint, `exploratory_only_model_class`). They do not
produce a confirmatory cell and do not advance the confirmatory track, which is blocked at 0
cells by issue #196.
