# Round 84 (2026-11-24 02:26, nightly lane, issue #65): the process-suppression probe

Evidence label: **Executed** (exploratory: n = 4 items per level per arm, one build, one firing).
Not a confirmatory cell: the confirmatory track is blocked on a pinned checkpoint (issue #196), and
the model class here is exploratory-only. Model is referred to by public class only: a flash-class
local reasoning endpoint.

## Question

When a build emits a reasoning trace under the frozen judge's neutral one-word contract, can an
instruction switch that trace off, and does the verdict move when the trace changes?

Why this question. Rounds 80 and 81 hit the same wall from the other side: the model "traces
instead of emitting the one-word answer", and round 81 had to raise its token budget from 8 to 256
just to get an answer out. The untested assumption underneath that fix is that the trace is not
under instruction control. If an instruction can switch it off, the delivery problem is a prompting
problem and costs nothing; if it cannot, the trace is not an output mode and the only lever is
budget. The same measurement is the cheap behavioural probe of the C4 position in
`docs/counterarguments.md` (an emitted trace is not evidence of the computation), so it earns its
dispatch on both counts.

Nearest prior art and the narrow delta are in [literature-scan.md](literature-scan.md). The ironic
framing is **not** novel: arXiv:2511.12381 ("Don't Think of the White Bear: Ironic Negation in
Transformer Models Under Cognitive Load") already runs negation-instruction rebound in LLMs. What
that scan found unoccupied, and what this round owns, is a negated process-suppression instruction
aimed at the **emitted reasoning trace** rather than at a concept in the answer stream, with a
four-arm imperative / negated / permission contrast on one byte-identical task surface and a
verdict-invariance measure.

## Method

One task surface, one gold, four instruction arms that differ **only** in what they say about
reasoning. The item text is byte-identical across arms; the selftest asserts that the `baseline`
prompt is byte-identical to `evaluation/frozen/verify.py` `build_prompt` output and that it is the
only arm that is.

| Arm | Suffix appended to the frozen template |
|-----|----------------------------------------|
| `baseline` | nothing (judge template verbatim, control) |
| `suppression` | imperative ban: give no reasoning, no explanation and no steps |
| `ironic` | the same ban in negated form: "Do not think about the chain of precedes links step by step." |
| `posthoc` | explicit permission/request to reason after the one-word answer |

- Family: `ladders` (k-hop reachability, `generators/ladders.py`), frozen grid levels 4 and 8,
  4 items per level, 8 items, 4 arms, **32 dispatched prompts**.
- Seed base 20261124: the judge's fresh-seed policy (run date), so no item predates this firing.
- Sampler: `temperature` 0.0, `max_tokens` 1024, sequential dispatch, one at a time.
- Verdict is read from the visible answer field only, never from the trace (issue #94). The last
  standalone yes/no wins, because a traversal that enumerates both answer classes must not be read
  as a verdict from its first mention.
- Delivery census per issue #145: a record whose `finish_reason` is not `stop` is `censored_at_cap`
  and is never scored wrong. Delivery therefore requires termination, not the presence of a token.
- Budget gate: the pre-dispatch rate census (`measure.json`, standing round-61 rule) measured 67.5
  tok/s over 2 calls, worst case 8.1 minutes for the whole plan, so the plan was deliverable and was
  dispatched rather than registered.
- Gate frozen before dispatch. gate blob `80fa3866f4807fc0344b226836337f9c46fc20910d3dc24ab46cf8a2ab3f3d2d`.
- Registered thresholds live in the script constants and are quoted in `gate.json`; the full pass on
  the trace gate is always the stronger tier than the partial pass (a selftest control fails if the
  tiers are ever inverted).

### Registered criteria

| Row | Name | Rule |
|-----|------|------|
| G1 | trace_channel_exposed | at least one dispatched record carries a non-empty trace on a named channel (issue #105) |
| G2 | ban_reduces_trace | partial: `suppression` traces strictly fewer records than baseline AND its trace-present fraction is below baseline's. Full: partial AND the `suppression` trace-present fraction is at or under 0.25 |
| G3 | negated_ban_backfires | `ironic` traces at least baseline + 2 records (the ironic-process prediction) |
| G4 | verdict_invariant_to_the_ban | among items with a stop-terminated verdict in both `baseline` and `suppression`, at least 80% carry the same verdict AND both arms agree with the judge gold on every one |
| H1 | dispatch_integrity | every record has a non-null `finish_reason` and a token count; a transport failure is recorded, not scored |

## Results

All four arms trace-present on every record, so the two trace gates fail and the invariance gate
passes. H1 passes: 32/32 records carry a finish reason and a token count, zero transport errors.

| Arm | trace present | `censored_at_cap` | median completion tokens | median trace chars | delivered correct | delivered wrong |
|-----|---------------|-------------------|------------------------|------------------|-------------------|-----------------|
| `baseline` | 8/8 | 2 | 439.0 | 1308.5 | 6 | 0 |
| `suppression` | 8/8 | **0** | 336.5 | 966.0 | 8 | 0 |
| `ironic` | 8/8 | **0** | 406.0 | 1211.5 | 8 | 0 |
| `posthoc` | 8/8 | 2 | 846.5 | 1600.0 | 6 | 0 |

`trace_chars` is a **sanitized and capped** measure: `sanitize()` truncates the stored trace at 1600
characters, so a median of 1600.0 means "at least the cap", not a length. All length claims in this
round therefore rest on `completion_tokens`, which the endpoint reports uncapped. The stored trace is
kept for inspection, not for measurement.

Paired per item (same item, `suppression` against `baseline`):

| Measure | Value |
|---------|-------|
| items where the ban shortened the generation | 7 of 8 |
| median of per-item suppression/baseline completion ratios | 0.894 |
| arm-median ratio | 0.767 |
| median ironic/baseline ratio | 0.970 |
| median posthoc/baseline ratio | 1.361 |
| comparable items (both arms delivered) | 6 |
| of those, same verdict and both matching the judge gold | 6 of 6 |
| items correct in all four arms at once | 5 of 8 |
| verdicts wrong anywhere in the round | 0 of 28 delivered |

Findings:

1. **The ban does not switch the trace off** (G2 fails both tiers, 32/32 trace-present in all four
   arms). On this build the trace is not an instruction-controlled output mode.
2. **The negated ban does not backfire** (G3 fails). `ironic` traces 8/8 like baseline and its median
   generation is slightly *shorter* (ratio 0.970), not longer. This is the opposite sign to the
   ironic-rebound result for concepts in arXiv:2511.12381, and it is consistent with the
   load-conditionality in the Wang/Hagger/Chatzisarantis 2020 meta-analysis (immediate enhancement
   appears mainly under added cognitive load, which this single-endpoint design does not manipulate).
   It is a null on one build at n = 8, not a refutation of the paradigm.
3. **The instruction is a throttle on trace length, not a switch on trace presence.** Ordering is
   `suppression` < `ironic` < `baseline` < `posthoc`, monotone in how much each arm invites reasoning.
4. **Censoring tracks the instruction-driven length.** 4 truncations total: 2 in `baseline` (both
   level 8), 2 in `posthoc` (one level 8, one **level 4**), 0 in `suppression`, 0 in `ironic`. The
   sharpest single record is `L4_i2_posthoc`, which truncates at the 1024 cap on a level-4 item that
   `baseline` delivered in 150 tokens: what truncated it was the request to explain, not task depth.
5. **The verdict never moves** (G4 passes). An instruction that changes generated length across a
   range of 0.89x to 1.36x at the median of per-item ratios (ban and permission, paired against
   baseline) does not change a single answer.

Against issue #108, so finding 4 is not read as a budget claim: #108 ruled that an output-policy knob
"moves the delivery surface but does not re-claim the budget", against a completion-ratio ceiling of
0.50. The ban arm lands the same way: ratio 0.894 (median of per-item ratios), 0.767 arm-median, well
above that ceiling. **A ban clause removes censoring at this cap on this family while reclaiming well
under half the tokens: a delivery-surface lever, not a budget lever.**

Reading discipline on finding 5. It is a **non-falsification of the epiphenomenal reading, not proof
of it.** Every item here is one this build solves; an instruction cannot move a verdict the model was
going to get anyway. The discriminating test is the same four arms on items at or past this build's
measured wall, where verdicts do flip. That is the next step below, and it is why the round is
labelled exploratory rather than reported as a faithfulness result.

## Trace-exposure census (issue #105)

Field census over all 32 records: `content`, `reasoning_content`, `role`; the trace is supplied by
`reasoning_content` on 32 of 32. `think_open`/`think_close` are 0 on the chat surface and
`think_closed` is `null` for all 32 records, because on this surface the trace is a separate field
rather than an inline block: `think_closed` is a completions-surface measure here and reads `null`,
which is deliberately not the same observation as `false`.

A two-call **out-of-plan diagnostic** (not scored, not in `raw.jsonl`, not a cell) compared the two
API surfaces on the same build:

| Surface on the same build | Reasoning supplied | Answer field |
|---------------------------|--------------------|--------------|
| `/chat/completions` | `reasoning_content`, 178 chars | `content` = the one-word answer, no tags |
| `/completions` | no reasoning field | trace inlined as `text` between think tags |

So the channel is a property of the **surface**, not only of the deployment. The issue #105 merge
rule (`reasoning_content` if non-empty, else `reasoning`, else empty) reads this one build as
trace-exposed via chat and as **zero-trace via completions**, and the `raw.jsonl` census as specified
cannot distinguish that from a genuinely zero-trace deployment. Reported as a proposed one-field
amendment (`served_surface`) in a comment on #105, not as a new issue.

## Reproduce

```
export NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=...   # endpoint config, never stored here
python3 research/nightly-2026-11-24-0226/suppression_trace_probe_r84.py --selftest
python3 research/nightly-2026-11-24-0226/suppression_trace_probe_r84.py --freeze-gate
python3 research/nightly-2026-11-24-0226/suppression_trace_probe_r84.py --measure
python3 research/nightly-2026-11-24-0226/suppression_trace_probe_r84.py --dispatch
python3 research/nightly-2026-11-24-0226/suppression_trace_probe_r84.py --summarize
python3 research/nightly-2026-11-24-0226/suppression_trace_probe_r84.py --check-readme
```

`--dispatch` is resumable: it skips labels already present in `raw.jsonl`, so a partial firing is
completed rather than duplicated. `--selftest` and `--check-readme` touch no endpoint.

The `--selftest` negative controls, each verified to fail when its own mechanism is broken: inline
trace split, the never-closed think block, the no-trace case read as *no trace* rather than empty
trace, last-yes/no-wins extraction, censored-is-not-wrong, the sanitizer on URL / address / home path
/ quantization-tagged label, gate-blob stability and movement under a changed threshold, frozen
baseline-prompt parity, verdict-drift capture on G4, the ban-does-nothing control on G2, the
zero-trace refusal on G1, and the gate-tier ordering control.

## Sanitization

Scripts read `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID` and `NIGHTLY_API_KEY` from the environment and
write none of them anywhere. Every model-facing string (prompt, trace, visible field, transport error
text) passes `sanitize()` before it is written: URLs, IP addresses with optional ports, home and
mount paths, and quantization-tagged serving labels are replaced. The sanitizer patterns are
themselves assembled by concatenation so this source carries no instance of the class it strips, and
the selftest fixtures use RFC 5737 documentation addresses, a `.invalid` domain and a dummy path.
The model is named by public class only.

## Next steps

- The discriminating run: the same four arms at or past this build's measured wall, where verdicts do
  flip, testing whether the ban changes **accuracy** there. Bearing on #71 and #126: a cap-bound
  selection or a `d*` placement that does not record the instruction arm is measuring the instruction
  as well as the depth.
- If a load manipulation is ever added to the arms, the ironic arm becomes interpretable against
  arXiv:2511.12381 directly, since that result is load-dependent and this design has no load
  condition.
- One-field census amendment (`served_surface`) proposed on #105.
