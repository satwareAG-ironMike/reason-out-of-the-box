# Activation-patching protocol (issue #6, study-design Condition 3)

Nanda-style progress measures on OLMo 2 7B / 13B (the study-design's two
patching-eligible checkpoints). This is the only Condition 3 test that directly
answers "algorithm vs retrieval": a shared circuit reused across rule types
(H1) vs rule-specific memorized pathways (H0-a).

## What it measures

The causal signature of *iteration* (Red-team item 3 mitigation): a component
whose activation count or pattern **scales with depth d**, not mere overlap of
ablation effects. We do not accept "ablating circuit C hurts rule X" as
evidence; we accept "ablating component C reduces accuracy on rule X by an
amount that grows with the number of composed rules d".

## Protocol (deterministic, pre-registerable)

1. **Task family.** Digit matrices (family 1, the pilot family). Levels d = 1..4
   (the depth knob = number of simultaneous component rules). One family is
   enough to test cross-rule transfer, because the rule types (constant,
   progression, distribution_of_3, xor, or, and) are the ablation axes.

2. **Locate candidate circuits.** For each rule type R and each depth level d,
   run the model on N items and record the per-layer activation statistics
   (mean |activation| and activation frequency above a fixed quantile) over the
   feed-forward neuron activations during the answer-generating span. A
   component is a *candidate* for rule R at depth d if its activation
   frequency is in the top decile on R-items at level d.

3. **Ablate.** For each candidate (layer L, neuron N), set the activation to
   zero (or to its mean over a null set) during a fresh forward pass on a held-
   out item set, at every level d' in 1..4 and every rule R'. Measure the
   accuracy drop.

4. **The depth-scaling signature (the H1/H0 discriminator).** For a candidate
   on (rule R, layer L, neuron N), plot accuracy drop vs d'. 
   - **H1 (shared algorithmic circuit):** the drop is large and *scales with d'*
     for the rule the candidate was selected on, and a *portion* transfers to
     other rules (the shared component is reused across rule types).
   - **H0-a (memorized pathway):** the drop is large only on the selection rule
     and does not scale with d' (memorization is rule-specific and depth-flat),
     or transfers to *no* other rule.

5. **Control (the negative control, required).** Ablate the *same* number of
   randomly-chosen components matched for activation magnitude (not top-decile)
   and confirm the depth-scaling signature is absent: random ablation drops are
   flat in d' and rule-uniform. Without this, a depth-scaling drop on the
   real candidate could be a size effect, not a circuit effect.

## Checkpoints and compute

- OLMo 2 7B (`allenai/OLMo-2-1124-7B`) and 13B (`-1124-13B`) base, the
  study-design's two patching-eligible checkpoints (32B is excluded - the
  design patches 7B/13B only).
- N = 300 items per (rule, level) for activation statistics (the study's 300
  items/level budget), held-out N = 100 for the ablation readout.
- Component scan: all FFN layers, all neurons - the candidate pool is bounded
  by the top-decile frequency filter, so the ablation set is small even though
  the scan is full.
- One 8x80GB node is sufficient (bf16 7B = 14 GB, 13B = 26 GB).

## Output contract (public-only)

Per (checkpoint, rule, candidate): the activation-frequency rank, the accuracy
drop curve over d' (1..4) for the selection rule and every other rule, the
random-control curve, and a `depth_scaling_slope` (fit over d') with a
significance note. The decision (H1 vs H0-a) is made by the pre-registered
decision table (issue #14), not here - this protocol produces the measurement,
the verdict is downstream.

## Status

Protocol only - not yet executed. Execution is an M2 work package gated on the
harness (#5) and the calibrated audit (#3); the 7B/13B checkpoints must be
served for the activation scan. No compute has been spent.
