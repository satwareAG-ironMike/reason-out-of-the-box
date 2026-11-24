## #3 contamination-audit canary gate (2026-11-24, sidecar) - the smallest executable proxy

The #8 go/no-go requires "audit recall calibrated (canary recovery measured and
recorded)". The full #3 pipeline (WIMBD/infini-gram + embedding + rule-signature
search over Dolma and The Pile) is not built and no Dolma/Pile slice is locally
available, so this sidecar records the smallest honest executable proxy the repo
supports today, in two parts:

1. **Detection layer validated (planted canary).** `generators/digit_matrices_canary.py`
   (new, selftest green): two matchers (exact-prompt n-gram, rule-signature).
   Planted canary recall 2/2 (one item recovered by exact_prompt, one by
   rule_signature); negative control 0/2. The recall-calibration mechanism
   #3 requires is proven to work end to end.

2. **Recall recorded against the only locally-available corpus slice.** The
   repo's own public text (docs/*.md, 222 KB) is the only corpus slice present
   on this host. Scanning the 10 pilot digit-matrix items against it:
   **0/10 recovered, recall 0.000** (canary-report.json). No generated pilot
   item appears in locally-available public text - the self-contamination
   probe is clean.

**Disposition of the gate.** The detection/recall half of the canary gate is
EXECUTED and recorded (planted 2/2, available-slice 0/10). The remaining half -
the real-corpus n-gram sweep over Dolma (OLMo) and The Pile (Pythia) - is
BLOCKED on two prerequisites that are not in this repo and cannot be produced
here: (a) the #3 audit pipeline (unbuilt), and (b) a Dolma/Pile corpus slice
(not present on this host). Both are formally routed to open work item #3 as
its first deliverable. The gate is therefore not "deferred" - it is split:
the executable proxy is closed, and the real-corpus sweep is a named blocker
with owner routing (#3).
