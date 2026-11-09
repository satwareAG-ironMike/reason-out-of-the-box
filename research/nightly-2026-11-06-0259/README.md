# Round 50 (2026-11-06 02:59): depth at matched input load - 23/23 delivered answers correct, every accuracy loss a non-delivery, and the trace-verdict recovery rule fails its own calibration

Nightly round 50, pool slot 2/6, a flash-next-class local endpoint (the same class this
agent session ran on). Tracker issue #65, round summary comment posted 2026-11-06.
Serves #71 (load decoupling for the depth ceiling), #94 (trace-verdict provenance), #126
(the cap-bound premise), #100 (self-agreement), #105 (exposure census).
Evidence label: **Executed** (exploratory, n = 4 per cell, one endpoint, one firing).

## Question

When ladder accuracy fails at high hop depth, did the traversal fail or did the delivery
fail? Round 6 (`research/nightly-2026-10-16-0400/`) established that the verdict token sits
at the end of an O(k) reasoning trace (`completion_tokens = -36 + 80k`), so a fixed output
cap can cut the answer off without touching the reasoning, and recorded that placing `d*`
"needs a budget-controlled or answer-token-first protocol, not a raw truncation count".
Round 49 removed the cap pressure entirely (issue #126: 0/11 truncations at 2048 on the
current builds). Two separations had never been made on one firing:

1. **Depth from input load.** The shipped generator draws the chain count uniformly from
   `[2, k+2]`, so `facts = chains * k`: depth always drags prompt size with it. This probe
   selects items inside a fixed fact-count band, so the prompt size is held constant while
   the queried path grows 4x.
2. **Computation from surfacing.** Each record carries the answer-field verdict and a
   trace-recovered verdict. The recovery rule is calibrated on the same firing against the
   items that did deliver (row N3); if the calibration fails, every trace-derived row is
   refused rather than reported.

An answer-first instruction cannot perform separation 2 on this deployment shape: the
reasoning channel precedes the answer field, so an instruction cannot move the verdict ahead
of the tokens that consume the budget. The decoupling is therefore done by measurement.

## Instrument

`depth_load_probe.py`, stdlib only, `--selftest` green with 157 checks before any prompt:
independent BFS solver plus the issue #67 component-isomorphism guard on every item; the
shipped series re-derives byte-identically to `items/ladders/l8.jsonl`; scorer arithmetic
(perfect 1.0, flipped 0.0, a constant rule exactly at the balanced 0.5 baseline); trace-rule
controls (last-occurrence must read the conclusion, not an intermediate yes/no; the
first-occurrence control must behave differently; empty and non-verdict traces return None);
planted-slip controls (a trace ending on the wrong verdict is scored as a capability failure;
the gate must assign *different* tiers to a planted capability-bound firing and a planted
surfacing-bound firing; a zero-trace deployment must refuse the trace rows; an anchor that
cannot do the shallow item must break the tier); a sanitizer control on RFC 5737
documentation addresses only; and a planted `DUP-`-label control for the duplicate join
(row N2, see "Instrument defect" below).

Cells (all items from `generators/ladders.py`, shipped seed policy, `seed_base` 20261005;
per-item seed `seed_base + 2_000_000 * level + i`):

| Cell | k | Fact band | Chains selected | n | Role |
|------|---|-----------|-----------------|---|------|
| A08 | 8 | none | 2, 5, 2, 6 | 4 | round 6's selection rule verbatim: the archived anchor items (seeds 36261005, 36261006, 36261013, 36261017) |
| M08 | 8 | 64-72 | 8, 8, 9, 9 | 4 | matched-load depth ladder, shallow end |
| M16 | 16 | 64-72 | 4 | 4 | matched-load depth ladder |
| M24 | 24 | 64-72 | 3 | 4 | matched-load depth ladder |
| M32 | 32 | 64-72 | 2 | 4 | matched-load depth ladder, 4x the archived grid |
| H16 | 16 | 180-200 | 12 | 4 | 3x input load at shallow depth |
| H32 | 32 | 180-200 | 6 | 4 | 3x input load at depth |
| DUP | 16/24/32 | as M | as M | 3 | re-dispatches of the smallest-seed gold-yes matched item per level (#100) |

Selection rule, fixed before any call and never seeing a model output: scan the level's
series in generation order and take the first two items with answer `yes` and the first two
with answer `no` inside the cell's band. The class balance is exactly 2/2 per cell, so every
constant baseline sits at 0.50 by construction. The matched band forces the distractor chain
count down as depth goes up (8 chains at k = 8, 2 chains at k = 32), which is the
conservative direction: any turnover at high depth happens while search breadth shrinks.

Prompt template byte-identical to round 6's (rule sentence, shuffled atomic facts, one
yes/no question, "Answer with exactly one word: yes or no."). Dispatch: 31 calls plus 1
census health call = 32 of the protocol's 40-call cap, `max_tokens` 2048, `temperature` 0.0,
`WORKERS` 3 (the slot reported physical execution width 1), one retry budget per record,
none used. Endpoint base URL, model id and bearer token come from `NIGHTLY_BASE_URL`,
`NIGHTLY_MODEL_ID`, `NIGHTLY_API_KEY` and are never written: artifacts carry a one-way
digest of the serving id only, and every prompt, response and trace string passes through the
sanitizer before it reaches a file.

Archived reference pinned fail-closed before any prompt: `research/nightly-2026-10-16-0400/raw.jsonl`,
blob `21987bdfb456c8a44449221defc006623870efb574cd7fe31919a073616e544e`, with its four k = 8
anchor seeds, answers and completion-token counts re-derived from the file (`certify_reference`
refuses to dispatch if the blob, the seed set or the anchor readout moved).

## Gate

`gate.json`, schema `round50-gate-v1`, canonical blob
`a805acd978d3f14350246cff86f988fdc93978709b28957613ff8b82e3e470c4`, frozen before dispatch and
pinned in the instrument as `ROUND50_GATE_BLOB_SHA256` (the run recomputes it and refuses to
dispatch if it moved). Rows and bands come from archived records only: round 6 supplies the
anchor items, the anchor readout (4/4, mean 387 tokens) and the 80-tokens-per-hop length law;
issue #126 supplies the current-build output state.

| Row | Registered statement | Value | Result |
|-----|----------------------|-------|--------|
| D1 | the four archived round-6 items stay at or above 3/4 delivered accuracy | 1.00 (4/4) | pass |
| D2 | matched-load M08 plus M16 stay at or above 7/8 | 1.00 (8/8) | pass |
| D3 | tripling input load at k = 16 keeps accuracy at or above 3/4 | 1.00 (4/4) | pass |
| D4 | at matched load, k = 32 stays at or above 3/4 (no ceiling inside 4x the grid) | 0.75 (3/4) | pass, at threshold |
| D5 | matched minus high accuracy at k = 32 is at or above 0 (load does not help) | +0.50 | pass |
| D6 | matched-load accuracy at or above 10/16, above the 0.50 constant baseline | 0.875 (14/16) | pass |
| N1 | census: reasoning-supplying field open on the health call and on 90 percent or more of records | `reasoning_content`, 28/28 | pass |
| N2 | at least 2 of 3 duplicate pairs byte-identical | 3/3 byte, 3/3 tokens, 3/3 answer | pass |
| N3 | the trace-recovery rule agrees with the delivered answer on 75 percent or more of delivered records | 0.5652 (13/23) | **fail** |
| T1 | decisive row: among undelivered records with trace text, the trace verdict equals gold in 2/3 or more (surfacing) else capability | 1.00 (5/5) but inadmissible | **refused** |
| R1 | readout: matched-load turnover, M08 minus M32 at or above 0.25 | +0.25, turnover flagged | readout |
| R2 | readout: OLS slope of estimated verdict position against depth inside round 6's band [55, 110] | 20.92 | outside band |

Tier rule as frozen: N1 closed gives `answer_level_only`; D1 below 0.75 gives
`anchor_broken`; T1 capability-bound plus a registered turnover gives `capability_bound_depth`;
T1 surfacing-bound gives `surfacing_bound`; no undelivered record and D4 holding gives
`no_ceiling_measured`; otherwise `ambiguous`.

**Tier: `ambiguous`.** The discriminator fired itself out of the running: N3 failed, so T1 was
refused exactly as registered. What survives is the answer-level ledger and the mechanism
finding below.

## Result

Answer-level ledger over the 28 experimental records: **23 delivered, 23 correct, 0 delivered
wrong, 5 non-delivered** (every one `finish_reason = length` at exactly 2048 tokens).

| Cell | k | Facts | Chains | n | Delivered | Truncated | Correct | Accuracy | Mean completion tokens | Trace chars on truncations |
|------|---|-------|--------|---|-----------|-----------|---------|----------|------------------------|----------------------------|
| A08 | 8 | 16-48 | 2-6 | 4 | 4 | 0 | 4 | 1.00 | 349.8 | - |
| M08 | 8 | 64-72 | 8-9 | 4 | 4 | 0 | 4 | 1.00 | 753.5 | - |
| M16 | 16 | 64 | 4 | 4 | 4 | 0 | 4 | 1.00 | 929.2 | - |
| M24 | 24 | 72 | 3 | 4 | 3 | 1 | 3 | 0.75 | 1433.5 | 5631 |
| M32 | 32 | 64 | 2 | 4 | 3 | 1 | 3 | 0.75 | 1420.8 | 5334 |
| H16 | 16 | 192 | 12 | 4 | 4 | 0 | 4 | 1.00 | 1263.5 | - |
| H32 | 32 | 192 | 6 | 4 | 1 | 3 | 1 | 0.25 | 1719.8 | 5069-6796 |

Transport: 27,980 prompt and 34,011 completion tokens, 1,641.8 s wall across 3 streams, zero
retries, zero transport errors. Census: `reasoning_content` on 31/31 records (the same
exposure state as round 49 on this class; the health call returned 213 trace characters).

## Finding 1: no wrong answers anywhere, so this firing's accuracy loss is entirely a delivery loss

23 of 23 delivered answers were correct, at every depth from k = 8 to k = 32 and at every
input load from 16 to 192 facts. The only failures are five records that never surfaced an
answer field, all cut at the 2048-token cap. Within this firing there is no capability
failure to attribute anything to: `d*` is still not placed, because the accuracy curve has
not turned over at all, only the delivery curve.

## Finding 2: at constant input load depth is nearly free, and the depth-times-load cell is where the door closes

Delivered accuracy is 4/4 at k = 8 and k = 16 with the prompt pinned at 64-72 facts, 3/4 at
k = 24 and 3/4 at k = 32 (both misses truncations). Tripling the prompt at k = 16 costs
nothing (H16 4/4, 192 facts, mean 1,263.5 tokens). Tripling it at k = 32 costs three of four
verdicts (H32 1/4 delivered, mean 1,719.8 tokens, accuracy 0.25). Input load and depth
interact, and they interact on the axis of whether a verdict arrives before the cap, not on
the axis of whether the answer is right. Note the conservative asymmetry: at fixed load the
distractor chain count shrinks with depth (8 chains at k = 8 versus 2 at k = 32), so the deep
items had *less* search breadth to reject, not more.

## Finding 3: round 6's 80-tokens-per-hop law was a depth-plus-load law

Over the matched-load cells the estimated verdict surface position grows at **20.9 tokens per
hop** (row R2, outside the registered [55, 110] band) and raw completion length at **31.3
tokens per hop**, against round 6's fitted 80 per hop. Round 6's fit was taken on a series
where the fact count grew with k, so it measured depth and load together. Consequence for
issue #71 and the study design: any depth curve that does not hold the fact count fixed
cannot be quoted as a depth law, and any budget derived from the 80-per-hop number
over-provisions the deep items at constant load by roughly 2.5x.

## Finding 4: the trace-verdict recovery rule is captured by the model's own instruction echo, so the surfacing question could not be scored

Row N3 exists precisely because issue #94 recorded that the trace-fallback token has never
had a provenance test. It failed here at 13/23 = 0.5652 against the delivered answer field,
and the mechanism is legible in the raw archive: **in 10 of the 10 disagreements the captured
token is the `no` inside the model's own instruction-to-self tail**, the sentence
`Need final exactly one word: yes. Ensure no extra.` that closes 16 of the 23 delivered
traces. The last-occurrence rule reads the echo of the task constraint, not a verdict. This
is #94's class of defect reproduced on an independent design with the capture mechanism
identified, and it propagates backwards: trace-derived measures used by rounds 42 to 49 (the
distractor-ratio family) inherit the same doubt until re-scored under a boilerplate-aware rule.

The surfacing hypothesis did not survive contact with the traces either, and that too is
worth recording. Post-hoc and explicitly unscored, a cue-anchored rule (a yes/no inside a
conclusion-cue sentence) agrees with the delivered answer on 20/23 records, but on the five
truncated records it recovers **no verdict at all**: those traces are 5,069 to 6,796
characters of fact enumeration cut off mid-check, with no commitment sentence anywhere in
them. So this firing does not support "the model computed the right answer and never surfaced
it". It shows the model still enumerating when the cap arrived, which is the same story
issue #126 tells about the panel: the cap binds on the traversal, and where it binds the
verdict was never reached.

## Finding 5: instrument defect found and fixed mid-round, disclosed with the raw bytes unchanged

The first aggregation reported N2 with `n_pairs: 0`. The duplicate identity join had keyed on
the cell label, while the dispatcher labels re-dispatches `DUP-M16` and friends, so no pair
ever joined and a real control silently scored zero. Fixed by keying the join on the item
(`seed` plus `prompt_sha256`, which is what dispatch identity means), and the aggregation was
recomputed by `--rescore` from the **identical** raw archive: `raw.jsonl` blob
`e2a9d47ecb69e40e4e908df9adf20362ea6f9ff9e0430516148a5e4c8021041f` before and after, zero new
endpoint calls, `gate.json` untouched. A planted `DUP-`-label control now sits in the selftest
so the join cannot break unseen again. The `ambiguous` tier is unchanged by the fix (it comes
from N3, not N2).

## Limits

- n = 4 per cell is depth resolution, not a confidence interval. The 2/4 cells turn on single
  items.
- One endpoint, one firing, quantized serving build, training data undisclosed: not H1
  evidence and not Condition-2 study data. It is a difficulty and harness measurement.
- The verdict surface position is a character-proportional estimate (characters before the
  verdict over total characters, scaled by billed completion tokens), not a tokenizer
  measurement.
- The trace is a text channel, not evidence of computation (claim ladder C4). No claim in
  this round rests on it: the row that would have is the one N3 refused.
- Chain count and fact count move together within the band (64 facts can be 8 chains at
  k = 8 or 2 chains at k = 32), so "matched load" holds the prompt size, not the number of
  distractor components. The direction of the residual imbalance is stated in Finding 2.
- The literature phase spent 10 of the round's 12 API calls and lost 6 arXiv attempts to
  plain-HTTP 301 redirects with empty bodies; venue and peer-review status were therefore not
  independently confirmed for the 2026 records cited, which are cited as arXiv records at
  abstract level.

## Reproduce

```
python3 generators/ladders.py --selftest
python3 research/nightly-2026-11-06-0259/depth_load_probe.py --selftest
python3 research/nightly-2026-11-06-0259/depth_load_probe.py --dry-run
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
  python3 research/nightly-2026-11-06-0259/depth_load_probe.py --run \
  --raw raw.jsonl --summary summary.json --health health.json
python3 research/nightly-2026-11-06-0259/depth_load_probe.py --rescore \
  --raw raw.jsonl --summary summary.json --health health.json
```

`--run` refuses to dispatch unless the gate blob matches the pin in the instrument and the
round-6 reference archive still hashes to its pinned blob. `--rescore` recomputes the gate and
summary from an existing `raw.jsonl` without any endpoint call. The `run.log` of the dispatch
stays out of the repository (the serving endpoint returns vendor telemetry blobs in `usage`
that this script deliberately does not record).
