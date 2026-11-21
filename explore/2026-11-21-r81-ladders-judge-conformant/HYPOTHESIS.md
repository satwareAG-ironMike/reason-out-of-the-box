# Round 81: ladders, judge-conformant, exploratory lane

Tests: does the 27B-class base build (qwen3.8-27b-nvfp4-mtp, self-hosted, no instruct, no RL,
no reasoning prompt) clear the ladders k-hop reachability family at a depth beyond its
measured trained depth, with one-word answers, at the frozen judge's minimum exploratory
n=40?

Expected information gain: this is the first round built to the frozen judge's input
contract (judge grid levels 1-8, judge seed policy, judge frozen prompt builder). It moves
two distance items at once: (1) it measures d_hat for this build on the ladders family
(calibration arm, 5 x 40 items, seed base 20260101, mastery 0.80), which positions the
beyond-depth band for the family; (2) it produces the first scorable exploratory cell
(40 items at the grid level past d_hat, fresh seed base 20261121). Rounds r78/r79
(cross-ask) are not in the frozen FAMILIES and r80's items are off the judge's seed grid,
so this round is the first that a `score.py` run can score end-to-end once PR #197
merges. The round is worth running because it de-risks the whole scoring pipeline on real
data; it is worthless only if every one of the 240 dispatches fails to deliver.

The round is exploratory only: the model class is exploratory-only per pins.json
(exploratory class), B3 partner arm is not_evaluable (no pinned smaller same-family
checkpoint for this build), and no claim verdict is held. A NEGATIVE on the beyond-depth
cell is a valid result and is logged as such.
