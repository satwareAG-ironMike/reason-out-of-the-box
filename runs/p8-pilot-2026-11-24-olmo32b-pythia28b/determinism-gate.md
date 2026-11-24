## #5 determinism gate (2026-11-24, sidecar)

Two independent reruns of a fixed 10-item digit-matrix level-3 set (seed base
20261124, items in det10-items.jsonl), arm A greedy (temp 0, max_tokens 128),
on both live endpoints:

| endpoint | run1 == run2 |
|---|---|
| pythia-2.8b-deduped (:8081) | PASS (10/10 identical) |
| OLMo-2-0325-32B-Q4_K_M (:8083) | PASS (10/10 identical) |

Raw outputs: det10-outputs.json (all 40 records: 10 items x 2 runs x 2 endpoints).
The #5 acceptance criterion "two independent reruns of a fixed 10-item set
produce identical outputs" is met on both checkpoints. Greedy decoding is
deterministic on both serving builds, as the harness contract requires.
