# Hypothesis: the flash-class pool slots have a measured trained depth on `ladders`, or they cannot carry one

Nightly firing 2026-11-21 04:40 (issue #65, slot 2/6). Nightly round 79 in the runner's count;
see the README for why this firing does not reuse the `r79` lane label.

## Question

What is `d_hat` - the frozen judge's measured trained depth - for this self-hosted flash-class
endpoint on the `ladders` family, computed under the frozen calibration definition
(`evaluation/frozen/rule.json` `trained_depth`: `calibration_n` 40, `calibration_seed_base`
20260101, `d_hat` = the greatest level L such that ACC(level) >= 0.80 for every level <= L)?

## Why this round, in one paragraph

The loop's two previous rounds (the cross-ask pair in `explore/`, issue #195) both came back
`selection_beyond_tail` and both recorded "does not move the beyond-depth gap". Every
beyond-depth sentence those rounds wrote is unanchored on this build: the frozen rule defines
"beyond depth" only relative to a measured `d_hat` for the model being probed, and the `N1`
negative branch is measurable only when "the calibration arm measured ACC(d_hat) > 0". No
calibration record exists for any build the nightly pool actually serves - the calibration
records the project has are for the pinned OLMo 2 and Pythia checkpoints, and issue #196 says
the pool serves none of them. So the loop has been describing a depth axis it has never
measured on the hardware it owns. This round measures it on one family at the frozen `n`, and
either gives the next round an anchor (it can then pick `level = d_hat + offset` per the frozen
`depth_offset_rule`) or establishes the blocker in measured terms: this class of endpoint
cannot produce a calibration record, so no depth-anchored arm can ever be built on a nightly
slot and the depth question has to move to owner-provisioned pins.

## What would make this round worthless

- Level accuracy driven by censoring (`finish_reason: length` at a too-small budget) or by an
  answer-extraction failure rather than by depth. Guard: the frozen delivery census is reported
  per level, `censored_at_cap` is counted separately, and the pre-gates assert the extraction
  and censoring semantics on planted records.
- A surface leak in the pool: then a high accuracy at high k is a shortcut, not depth. Guard:
  the #67 permutation-calibrated leak gate runs on exactly this pool before dispatch
  (`leak_gate.json`).
- The serving build moving mid-run: then the 40 records are not one model's calibration. Guard:
  the digest is pinned in `gate.json` and re-checked after dispatch.
- Reading 8 items per level as skill: `n` = 8 per level is far below the frozen
  `min_n_exploratory` of 40 per cell, so every level accuracy is reported with its Wilson 95%
  interval and its majority-class baseline, and the verdict this round can carry is
  exploratory only.
