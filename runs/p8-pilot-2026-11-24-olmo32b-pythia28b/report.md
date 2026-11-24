# #8 pilot arm, first confirmatory-track dispatch (2026-11-24)

## Result

| checkpoint | arm A | arm B |
|---|---|---|
| pythia-2.8b-deduped | 1/3 | 0/3 (both B answers out of the 0..7 option range - parse of a free-form integer, deviation recorded) |
| OLMo-2-0325-32B-Q4_K_M | 0/3 unparseable | 0/3 unparseable |

## The OLMo serving finding (blocks the confirmatory track)

The OLMo-2-0325-32B-Q4_K_M slot (issue #196 pin, omar-2 iGPU) is UP - liveness,
exact-id gate and generation all pass - but the generated text is degenerate on
trivial probes ("The capital of France is" -> incoherent token soup, both arms of
this pilot: zero option-index tokens in 128/300 tokens, finish_reason=length with
repetition loops like "overhead overhead overhead ..."). The 8-token probe on
2026-11-24 was already degenerate. The GGUF is byte-exact (verified against the
registry content-length), so the defect is in the serving, not the download.
The confirmatory pin is therefore "serving up but not usable": #196's liveness
criteria pass, its usability criterion does not.

## Consequence

- The #8 pilot's confirmatory-track half (OLMo checkpoint) cannot produce
  decision-grade data on this deployment; the go/no-go on the OLMo arm is
  BLOCKED on the serving fix.
- The pythia-2.8b-deduped half executed cleanly: 3/3 items delivered a parsed
  answer on arm A (1/3 correct at level 3 - consistent with a small scale-control
  checkpoint at depth 3), arm B's CoT approximation delivered 3/3 parseable but
  0/3 in-range (the free-integer parse is a harness-side deviation, registered).
- Next step (tracked): diagnose the OLMo iGPU serving (weight offload split,
  Vulkan driver state, or context/KV setup), fix, re-probe, then re-run this arm.

Evidence labels: Executed (n=12 dispatches, 2 checkpoints, 2 arms). Not
Validated (the OLMo half is a serving failure record, not a score).

## Sidecar 2026-11-24 15:2x: OLMo re-run supersedes the OLMo half (serving contention, not a model defect)

The "up but not usable" verdict above was WRONG in its root cause. After a clean
restart of the OLMo llama-server (the first instance had been contending with the
co-resident pythia server and a 15:07 oom-kill on the host), the same checkpoint
answers the trivial probe correctly and the re-run of the 6 OLMo dispatches parses
clean option indices (no token soup):

| checkpoint | arm | result |
|---|---|---|
| OLMo-2-0325-32B-Q4_K_M | A | 1/3 |
| OLMo-2-0325-32B-Q4_K_M | B | 0/3 |

The original OLMo raw records stand as-is (immutable); they are a serving-contention
failure record, and `olmo-rerun.jsonl` (sidecar) supersedes their scores. Pilot
state: pythia-2.8b-deduped A 1/3, B 0/3 in-range; OLMo-2-0325-32B A 1/3, B 0/3.
Both checkpoints at level 3: 1/3 arm A. The OLMo half of the go/no-go is no longer
blocked on serving; it is now a measured (negative-leaning, small-n) data point.
