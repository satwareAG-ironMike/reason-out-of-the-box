# Round 22 (2026-10-24 04:05): the load arm at constant depth, on a true matched pair - free all the way to 240 facts on the 27B class

Nightly firing 2026-10-24 04:05 (tracker [#65](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65),
round 22; slot 2 of the local pool was assigned and was generation-hung, the round ran on the pool's
next generation-healthy slot, a 27B-class local endpoint, sanitized description with no endpoint value
in any artifact). Serves issue [#71](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/71)
(the load axis its option 2 leaves open: round 21 placed the ceiling there), issue
[#78](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/78) (acceptance criterion 1:
a true matched pair inside one item), issue [#94](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/94)
(content-only arm beside the fallback arms, declared before dispatch) and issue
[#73](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/73) (transport). State:
**Executed** (no independent second implementation reproduced this round; disclosed per
`docs/agent-execution.md`).

## Question

At a **fixed hop depth** (k = 4), does the delivered answer turn over as the fact count E grows
through {24, 48, 96, 144, 192, 240} - and if it turns over, is that a surfacing (budget) collapse or
a correctness collapse?

Picked because it is the mirror of the last measurement and the only unmeasured axis. Round 21
(`research/nightly-2026-10-24-0205/`, PR #95) measured depth at constant load E = 24 on the
flash-next class: 36 of 36 cells answered in the answer field, 36 of 36 correct to k = 12, depth
costing ~29 completion tokens per hop. Its stated consequence was that the level-24 negative-arm
failure of round 19 (0 of 6 negative cells delivered any answer at budgets up to 2048) is a joint
prompt-load x budget effect, i.e. **the ceiling lives on the load axis** - and the load axis has
never been measured with the hop count pinned. Round 21 also named the mirror arm on the 27B-class
slot as the follow-up, because rescue properties do not transfer across classes (rounds 16 and 18).
This round is that arm, on that class, by circumstance as much as by design: the assigned slot hung
(see Transport), and the healthy slot was the 27B-class one.

The instrument question is separate and older: every prior grid compares *different* items, so any
arm difference is confounded with construction, entity set and fact count (issue #78 called this
"there is no matched pair"). Here each graph is asked two questions over the identical fact list, so
the polarity contrast is unconfounded at every load level.

## Method

`constant_depth_load_arm.py` (stdlib only). Construction: the component-isomorphic hop chain of
issue #67 (PR #69) as re-implemented for round 21, same seed base (`20261024`), same name pools, same
seed formula, same candidate order. Arm M: k = 4 fixed; E in {24, 48, 96, 144, 192, 240} with
C = E/4 disjoint directed paths (6, 12, 24, 36, 48, 60); 3 graphs per level; each graph queried
twice:

| Arm | Query | Gold |
|-----|-------|------|
| F | (head of path p, tail of the same path p) | yes, distance exactly k |
| X | (head of path p, tail of a *different* path, chosen deterministically from the item digest) | no, unreachable |

That is the matched pair of issue #78 acceptance criterion 1 adapted to the **polarity** contrast:
`pair_violations()` asserts on every dispatched pair that the two items share the identical fact
list (canonical equality), the identical entity-name set, the identical fact count and the identical
queried source, that only the queried target differs, and that an unbounded BFS certifies both labels
(reachable at distance k for F, unreachable for X). `--selftest` carries the planted control #78 asks
for: a variant built from a different item's facts, and a pair with an identical queried target, are
both caught. What this pair does *not* vary is shortcut-versus-traversal depth (a single-fact-answerable
query); that arm of #78 stays open, as does its criterion 2 (pairing by item identity inside the
shipped generator) and its criterion-4 blocker on #77.

Selection rule, fixed in advance: candidate order by seed, the first 3 **gold-yes** candidates at each
level become the arm-F members, each paired with its deterministic arm-X variant. Every candidate and
every variant passes the independent structural audit (each weak component a directed path of exactly
k edges, query head-to-tail, stored answer equal to an unbounded BFS).

36 prompts (18 matched pairs) + 1 health probe = 37 of the 40-call cap; `max_tokens = 2048`,
`temperature = 0.0`, one sample per item, no exemplars, no chain of thought requested. Two-phase
transport per #73 (two sequential cells, then concurrency chosen from the measured rate), incremental
fsync'd `raw.jsonl`, `--resume` refusing unless every stored record carries the current gate hash.

Readout stack (issue #94, declared before dispatch, vendored verbatim from round 19 through round 21):
`content_only` (last standalone yes/no in the answer field), `loose_fallback` (the archived convention:
content, else the last yes/no in the reasoning field), `delivered_or_strict` (content, else the strict
trace commitment). The strict rule and the echo-phrase test are asserted by `--selftest`, so they
cannot drift silently from the rounds this grid must stay comparable to.

### Anchor to round 21 (fail-closed)

Because this arm re-uses round 21's seed base, pools, seed formula and candidate order, its E = 24
level *is* round 21's k = 4 level. Two pins are hardcoded in the script and checked before any prompt
is spent (provenance: `research/nightly-2026-10-24-0205/gate.json` and `raw.jsonl`, PR #95):

- the 40-candidate pool blob at E = 24 equals round 21's k = 4 pool blob (`11ab33ac...`);
- the three arm-F prompt digests at E = 24 equal three archived round-21 prompt digests
  (`0541a776...`, `7aaa76e6...`, `8e09374c...`).

Both matched, and `--probe` refuses on any mismatch. They also make those three cells a cross-round
re-run check at temperature 0 (round 19 next step 4): on *different* deployments, so the claim is
answer-transfer across classes, not same-endpoint determinism.

## Gate (before any prompt was spent)

Gate `7afc9cc5` (schema `round22-gate-v1`), selftest 355 checks 0 failures, corpus blob `4ae304490c03`.
The permutation-calibrated leak battery (traversal-free blind lexical rules, exact label-shuffle nulls,
400 permutations, family-wise alpha 0.05) runs on **two** pools per level, never on the selected six:
the 40-candidate pool, and a **paired pool** that adds each yes candidate's matched X variant, i.e. the
exact construction that is dispatched. No cell is flagged on either pool. Recorded edge: two pools reach
an observed maximum of 0.725 exactly *at* the calibrated threshold 0.725 (E = 96 pool, rule
`conj:~tgt_first_mention_before_src&~tgt_last_third`, p = 0.11; E = 240 pool, rule
`conj:~tgt_first_mention_before_src&~tgt_is_target_of_last_fact`, p = 0.08); the flag rule is strictly
greater, so they are not flagged. Prompt length ramps as designed: mean 946.8 characters at E = 24 to
8007.3 at E = 240.

Predictions declared in the gate: P1 prompt tokens at E = 240 >= 5x the mean at E = 24 and non-decreasing;
P2a levels 24/48/96 all `maintained` under `content_only` (round-8 trichotomy, Wilson 95% floor 0.60);
P2b level 240 **not** maintained; P3 mean completion tokens at E = 240 >= 3x the mean at E = 24
(the enumeration hypothesis); P4 at least one matched pair where F delivered correctly and its own X
partner did not, and no pair in the opposite direction; P5 every delivered (answer-field) answer correct;
P6 where the answer field is silent, the loose fallback token is "no" in at least 2/3 of cells; P7 the
three anchored prompts reproduce round 21's delivered answers.

## Transport

See `transport.json`. Three disclosures, none of which touches a measurement:

1. **The assigned slot was generation-hung and the round rotated.** The assigned slot served
   `GET /models` in 0.03 s while chat completions timed out at 180 s and 90 s; a 256-token probe
   returned in 115 s (~0.3 tok/s). Zero grid prompts were spent there. Per the pool's documented
   rotation to the first generation-healthy slot, the round ran on the 27B-class slot (the class of
   rounds 16 and 18), which is also the mirror arm round 21 asked for.
2. **The health probe's output budget was lowered to 256 tokens before the first prompt.** On this
   deployment a 2048-token health call was killed by an upstream gateway at ~66 s with http_502 while a
   256-token call returned in ~1 s. `MAX_TOKENS`, the grid, the corpus and therefore the gate hash are
   untouched by this transport-only change.
3. **`aggregate()` was patched after all 36 cells were archived.** The P2a/P2b lines read `status` from
   the per-level token rows instead of the trichotomy classification rows and KeyErrored during
   aggregation. The measurement path was untouched; the fix was gate-hash-guarded `--resume` plus one
   further health call at zero prompt cost (#73's resume contract), `--selftest` was re-run green and
   `gate.json`/`summary.json` regenerated at the committed HEAD under gate `7afc9cc5`.

Endpoint calls: 36 grid prompts, 4 health calls on the serving slot (one refused http_502 before the
budget patch, one ok, one on the resume) plus two short capacity diagnostics, and four diagnostics on
the assigned slot. Zero cell retries, zero transport failures on the serving slot, zero abandoned cells.
Phase-1 walls 24.7 s and 22.4 s, concurrency 1 chosen.

## Answer

**The load axis is free at constant depth, and the delivered answer carries that.** All 36 cells
answered in the answer field and all 36 correct at every level to E = 240; every level `maintained`
(Wilson 95% lower bound 0.6097 for 6/6), none `budget_limited`, none `collapsed`:
**E\* >= 240 on (constant-depth k = 4, matched-pair construction, 27B class, budget 2048)**. Max
completion 1958 tokens of the 2048 budget, and **no cell was truncated**: all 36 attempts ended with
`finish_reason` `stop`, none at `length`.

| E | C | n | correct | status | mean completion tok | mean prompt tok | distractor mention ratio |
|---|---|---|---------|--------|---------------------|-----------------|--------------------------|
| 24 | 6 | 6 | 6 | maintained | 344.0 | 438.0 | 1.00 |
| 48 | 12 | 6 | 6 | maintained | 564.3 | 768.2 | 1.00 |
| 96 | 24 | 6 | 6 | maintained | 1081.2 | 1448.5 | 1.00 |
| 144 | 36 | 6 | 6 | maintained | 669.5 | 2175.0 | 0.34 |
| 192 | 48 | 6 | 6 | maintained | 544.2 | 2897.3 | 0.18 |
| 240 | 60 | 6 | 6 | maintained | 332.8 | 3645.8 | 0.016 |

1. **Matched-pair sensitivity: zero discordance.** 18 of 18 pairs have both members correct (F yes, its
   own X partner no, over the same facts); exact McNemar b = c = 0, p = 1.0. Per arm over the whole ramp
   (n = 18 each): F 18/18 correct, Wilson lb 0.8241; X 18/18 correct, Wilson lb 0.8241. No false-yes on
   the cross-component query anywhere in the ramp.
2. **P3 fails honestly and that is the positive result: the output does not grow with the irrelevant
   facts.** Mean completion at E = 240 is **0.97x** the mean at E = 24 against a declared floor of 3.0x;
   the least-squares slope is **-0.53 tokens per added fact** (r = -0.16), while prompt tokens rise
   +14.86 per fact (r = 0.9998), so the ramp is fully visible to the tokenizer. The mechanism is a
   strategy switch, measured as the share of non-queried components whose entity names appear in the
   completion: 1.00, 1.00, 1.00 at E = 24/48/96 (full recitation of every component, up to 1958 tokens)
   then 0.34, 0.18, 0.016 at E = 144/192/240. Above ~100 facts this class stops enumerating: an E = 240
   arm-F trace cites the four relevant facts and answers in 125 tokens. Compare round 19 on flash-next at
   k = 24, where the traces were still listing facts at the 2048 cutoff and never delivered.
3. **Predictions:** P1 pass (prompt-token ratio 8.32). P2a pass. **P2b fail** (E = 240 is maintained:
   load alone at k = 4 does not reach the ceiling inside this grid). **P3 fail** (0.97x). **P4 fail as
   declared** (it required at least one discordant pair and there is none). P5 pass (36/36 delivered
   answers correct; no answer in the grid is wrong). P6 **vacuous** (zero content-silent cells; reported
   as vacuous, not retrofitted to a pass). P7 pass (3/3 anchored prompts reproduce round 21's answers,
   at 293/340/304 completion tokens against round 21's 351/360/385, about 15% cheaper).
4. **Fallback provenance** (declared, unused for scoring since content never went silent): the last
   reasoning-field yes/no is terminal in 32 of 36 records (median commit fraction 0.9966), mid-trace in 4,
   zero instruction echoes; terminal tokens agree with gold in 24 of 32. Because this grid is label-balanced
   (18 gold-no of 36), the loose fallback would score 24/36 = 0.667 against a constant-"no" baseline of
   0.50: the same skew direction as round 19, a materially smaller magnitude.
5. **Budget replay** (character-proportional estimate recomputed from archived attempt fields, never a
   measured token count): an estimated 7/36 answers would surface at a 256-token cut, 20/36 at 512,
   30/36 at 1024, 36/36 at 2048.

## Consequences

- **#71**: the load axis is measured at constant depth and is free inside the declared ramp. With
  round 21 (depth free at constant load) this makes the ceiling **two-dimensional**: neither axis alone
  bites in the grids tried, while their conjunction at k = 24 with ~240-288 facts is what round 19 could
  not surface. The d\* statement should become a frontier in (k, E) rather than a curve in one variable;
  the cheap next instrument is the interior of that frontier on this class, content-only readout.
- **#78**: a working, asserted, shared-content matched pair ships here (18 pairs, per-pair fact-list and
  entity-set identity, planted cross-item negative control). It is a polarity pair, not the
  shortcut-versus-traversal pair #78's criterion 1 describes; the generator-side port and the #77 blocker
  remain open.
- **#94**: second round with both arms live before dispatch; at constant depth the arms cannot diverge,
  and the fallback would have been right by accident at 0.667 against a 0.50 baseline.
- Cross-class: on this same 27B class, rounds 16 and 18 saw the X arm truncate 7 of 9 cells at k = 24.
  Here the X arm delivers 18 of 18 at 240 facts. The difference is hop depth, not fact count.

## Disclosure and limits

- Small n: 3 graphs (6 prompts) per level, one endpoint, one class; exploratory, labeled per
  `docs/agent-execution.md`. State **Executed**, not Reproduced or Validated.
- One quantized local deployment, undisclosed training data; not H1 evidence.
- The endpoint is not the one the runner assigned, so the round is a 27B-class measurement; the
  comparison to round 21 is by prompt digest across deployments. No cross-round endpoint identity
  fingerprint exists in the archive (public-only rule), so "the same deployment as rounds 16 and 18" is
  a slot inference, not a verified fact.
- P4 and P6 are declared fails/vacuous on a grid where the phenomenon cannot appear; they are reported as
  such, not restated post-hoc. P2b is a genuine failed prediction of a ceiling that did not appear.
- The distractor-mention ratio is a text-presence measure over entity names, not a reading of the trace:
  it counts how much of the irrelevant material is written out, and nothing more.
- Two literature candidates could not be confirmed and are cited nowhere. All cited arXiv IDs were
  fetched this round from free scholarly APIs at abstract level by the scan lens; no full text was read.

## Reproduce

```
python3 research/nightly-2026-10-24-0405/constant_depth_load_arm.py --selftest
python3 research/nightly-2026-10-24-0405/constant_depth_load_arm.py --gate
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
  python3 research/nightly-2026-10-24-0405/constant_depth_load_arm.py --probe
python3 research/nightly-2026-10-24-0405/constant_depth_load_arm.py --analyze
```

The script reads the endpoint from the environment and writes no endpoint value anywhere; stored model
text passes a sanitizer for URLs, IP addresses and absolute paths.
