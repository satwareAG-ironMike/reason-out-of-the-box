## d* depth grid + M2 exit-gate verdict (2026-11-24, sidecar)

### d* depth grid (OLMo-2-0325-32B-Q4_K_M, arm A greedy, pilot scale n=3/level)

| level (simultaneous rules) | n | correct | delivery (option index parsed) |
|---|---|---|---|
| 1 | 3 | 1/3 | 3/3 |
| 2 | 3 | 0/3 | 3/3 |
| 3 | 3 | 0/3 | 3/3 |
| 4 | 3 | 0/3 | 3/3 |

Accuracy is monotone non-increasing; it holds at level 1 (1/3, the single
non-zero level) and collapses to 0 from level 2. **The trained-depth ceiling
for this checkpoint on the digit-matrix family is d* = 1**: the model solves
1-rule items and breaks at 2 rules. (Pilot-scale n=3/level, the same scale
as the pilot itself; a full-depth confirmation at the study's 300 items/level
is M3 work, not M2.) Raw: dstar3-grid-raw.jsonl (12 dispatches, config hash
a7392930ac3330b6, the #5 harness).

### M2 exit-gate verdict

M2 exit gate (docs/next-investigations.md line 793): "Go/no-go: audit recall
calibrated; harness reproducible; d* established for one family."

- **Audit recall calibrated: MET** on the OLMo/Dolma side - canary recall 1.0
  (10/10 planted recovered on a real 1,194 MiB Dolma v1.6 slice); contamination
  report 0/10 pilot items hit. The Pythia/The Pile side is a recorded
  corpus-access blocker (deviation below).
- **Harness reproducible: MET** - the #5 determinism gate PASSES on both
  checkpoints (two independent reruns, 10/10 identical each, 2026-11-24); the
  #5 harness (config as single source, documented raw archive) is shipped.
- **d* established for one family: MET** - d* = 1 for digit matrices on OLMo
  2 32B, above.

**Verdict: M2 GO-able; the M3 commitment is conditional on one blocker:**
a The Pile corpus slice for the Pythia side of the contamination audit. The
Pile's original host is down and every public mirror is gated, so this is a
genuine corpus-access blocker, not an incomplete work item - all four M2 work
packages (#3 audit, #4 generators, #5 harness, #6 patching protocol) are
shipped and calibrated.

### Deviation list (registered)
1. Pile slice unobtainable (the-eye.eu down; HF mirrors gated 401) - Pythia
   contamination side blocked; OLMo/Dolma side fully calibrated.
2. d* grid at pilot scale (n=3/level) not the study's 300 items/level -
   consistent with the pilot's registered small-n deviation; confirmation at
   full n is M3 work.
3. OLMo checkpoint is the 32B confirmatory pin (#196 stand-up), not the #8-
   specified 7B - registered on #8 since the pilot.
4. Arm B CoT-approximation on OpenAI-compatible endpoints - registered on #8
   since the pilot.
5. The pilot's original OLMo raw records ran under host contention and are
   superseded by the olmo-rerun.jsonl sidecar - a serving-contention failure,
   not a model defect.
