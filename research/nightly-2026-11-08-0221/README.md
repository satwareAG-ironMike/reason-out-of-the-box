# Round 54 (2026-11-08 02:21): the 27B-class cap ladder is cap-bound at every rung below the pin, the flash class's 492-reserve region does not travel to the class, and the 27B-class answer state reproduces round 52 on all three items

Firing: 2026-11-08 02:21 (issue #65 timer). Class: a 27B-class local model (serving id disclosed
only in the commit `Model:` trailer; artifact digest `26df9af5972ff312`). No metered or hosted
provider was used; no search API was used. Status label: **Executed** (see Limits).

## Question

Registered before dispatch (schema `round54-gate-v1`, frozen in `gate.json`, pinned in the
instrument), blob:

`435e193993b2f7ffe871c6839bb6e84fec0546d6e2995b99cda1c00f99de71a3`

> On the 27B class, does the cap-ladder design (prompt bytes fixed, requested cap moved to 512,
> 1024 and 1536) show a serving-stack budget, a constant reserve region below the requested cap
> (the shape round 53 measured on the flash class), or neither; and does the byte-identical
> self-agreement control (issue #100) hold on this deployment; and does this firing give the 27B
> class a second same-class pair with the reasoning channel open on both sides (issue #105)?

Four hypotheses were registered. `H1_proportional_budget`: the stop lands at `1556*cap//2048`
(band 8 tokens) with `finish_reason` `stop` and the marker sentence present at every cap.
`H2_absolute_budget`: at every cap below the pin the output reaches the cap itself with
`finish_reason` `length`, no marker and no answer. `H3_no_serving_budget`: lengths track the task,
the marker appears wherever the model writes it, and the pin is a property of the family on this
class as well. `H4_reserve_region` (cross-class contrast, post-hoc readout only): the pinned
ladder records stop at a constant nonzero reserve below the requested cap, the shape round 53
measured on the flash class; decided after the dispatch from the stop-offset column, never by the
tier rule. Tier rule as registered, in order: `serving_budget_hook` if C1 >= 5 of 6 and C2 <= 1
of 6 and C5 == 2 of 2; `absolute_pin` if C2 >= 5 of 6; `no_serving_budget` if C1 <= 2 of 6 and
C5 == 0 of 2; `unresolved` otherwise.

## Why this firing discharges two debts

Round 53 (flash class, #131) re-fired the 1,556-token pin as a cap ladder and found none of its
three registered shapes: the stops moved with neither the cap (1,044 at cap 1,536 where the
proportional prediction was 1,167) nor a fixed fraction, and every one of its seven pinned ladder
records stopped with 492 tokens of reserve below its requested cap. Round 52 (27B class, #132),
the last 27B-class firing, showed the opposite shape on the same item family at the load floor:
every censored record ran to the full 2,048 cap (reserve 0) with `finish_reason` `length`, and the
1,556 pin never appeared. The two debts this firing discharges are: **(B)** the cap-ladder design,
and with it the 492-reserve shape, had so far been measured on one class only, so this
byte-identical re-dispatch of round 53's prompts on a 27B-class deployment asks whether the
reserve region travels with the class or is a property of the flash-class deployment; and **(A)**
a second 27B-class firing of the certified k = 48 item set, which gives the 27B class its second
same-class pair with the reasoning channel open on both sides (issue #105), read against round
52's archived k = 48 records (gate row X1, answer-level only: round 52's archive stores the
reasoning text but no marker count, so its cross-firing cannot be a marker claim).

## Items, arms and dispatch plan

`k = 48` load-floor ladders (`facts = 2k = 96`, 98 entities, two disjoint 48-edge paths,
`n_chains = 2`), seed base 20261005. Three seeds certified against the archived digests before
any dispatch: the two gold-no items round 51 delivered wrong (116261051, 116261076), and the
gold-yes item 116261338 whose archived natural stop 1310 sits below the pin. Prompt digests
matched rounds 51 and 53 byte for byte before dispatch: `068bc6a1fb0620fb`,
`ffc75c928f37f0d9`, `87e36020f5c31c93`.

| arm | what it is | caps |
|---|---|---|
| `as_is` | the round 51 prompt unchanged | 2048 (both gold-no, plus a duplicate re-dispatch of 116261051, plus the gold-yes control), 1536, 1024, 512 (both gold-no) |
| `enumerate` | same facts and query, the reachable set asked for first (a task variant: it cannot show the as-is task is solvable) | 2048, both gold-no items |
| `listing` | non-ladder control: count 1 to `N` in order, one number per line, stop with DONE | 2048 (`N = 4000`), 1024 (`N = 4000`) |

15 planned calls of the 40-call cap (14 experiment records plus one 256-token census health
call, issue #73), `temperature 0.0`, `max_tokens` at most 2048, dispatch budget 3,000 s (the 27B
class is the slower of the two classes measured so far). The decisive same-prompt anchors, the
duplicate control and the enumerate arm were dispatched first so a wall-clock cutoff would cost
the low-cap rungs and not the replication. Dispatch took 237.36 s wall, 11,283 prompt tokens and
20,044 completion tokens. No call was dropped, no arm timed out.

## What fired

`completion_tokens`, `finish_reason`, marker count and the answer-channel readout (issue #94),
from `raw.jsonl`:

| label | cap | tokens | finish | markers | gold | declared | reserve (cap - tokens) |
|---|---|---|---|---|---|---|---|
| `as_is_116261051_c2048` | 2048 | 2048 | length | 0 | no | (no answer) | 0 |
| `as_is_116261076_c2048` | 2048 | 2048 | length | 0 | no | (no answer) | 0 |
| `dup_116261051_c2048` | 2048 | 1798 | stop | 0 | no | no | 250 |
| `as_is_116261338_c2048` (gold-yes control) | 2048 | 838 | stop | 0 | yes | yes | 1210 |
| `enum_116261051_c2048` | 2048 | 2048 | length | 0 | no | (no answer) | 0 |
| `enum_116261076_c2048` | 2048 | 2048 | length | 0 | no | (no answer) | 0 |
| `listing_4000_c2048` | 2048 | 2048 | length | 0 | (no answer field) | - | 0 |
| `as_is_116261051_c1536` | 1536 | 1536 | length | 0 | no | (no answer) | 0 |
| `as_is_116261076_c1536` | 1536 | 1536 | length | 0 | no | (no answer) | 0 |
| `listing_4000_c1024` | 1024 | 1024 | length | 0 | (no answer field) | - | 0 |
| `as_is_116261051_c1024` | 1024 | 1024 | length | 0 | no | (no answer) | 0 |
| `as_is_116261076_c1024` | 1024 | 1024 | length | 0 | no | (no answer) | 0 |
| `as_is_116261051_c512` | 512 | 512 | length | 0 | no | (no answer) | 0 |
| `as_is_116261076_c512` | 512 | 512 | length | 0 | no | (no answer) | 0 |

Answers: 2 of the 14 records delivered a verdict through the answer channel, both of them
correct (the duplicate's `no` on gold-no 116261051, and the gold-yes item's `yes`), and none
delivered a verdict that contradicts the solver's gold label. The self-termination marker
sentence `I have thought about this long enough; time to give my answer.` is absent from all 14
records (the flash class wrote it in 11 of 14 in round 53). The census (issue #105): 14 of 14
records censused, reasoning channel `reasoning` on all of them (this deployment supplies the
reasoning text through the `reasoning` field, not `reasoning_content`; the health probe's field
list is `audio`, `content`, `function_call`, `reasoning`, `refusal`).

## Gate rows

| row | registered band | measured | status |
|---|---|---|---|
| C1 hook at the cap ladder | 6 of 6 | 0 of 6 | fail |
| C2 absolute cap signature | 5 of 6 or more refuses C1 and the H1 reading | 6 of 6 | pass |
| C3 marker locked to the hook | 0 disagreements | 0 | pass |
| C4 gold-yes control below the pin | 1 of 1 | 1 of 1 | pass |
| C5 listing control cut by the same hook | 2 of 2 | 0 of 2 | fail |
| C6 enumerate arm recovers the gold label | 2 of 2 | 0 of 2 | fail |
| C7 duplicate re-dispatch byte-identical (issue #100) | 1 of 1 | 0 of 1 | fail |
| C8 same-prompt cross-firing vs round 51 | 2 of 2 | 0 of 2 | fail |
| X1 27B-class cross-firing vs round 52 (answer-level) | 3 of 3 | 3 of 3 | pass |
| C9 off-hook marker anomalies | reported | 0 | reported |
| N1 census | every record censused | 14 of 14 | pass |
| R1 coverage, H0 health | reported | reported | reported |

Tier: **`absolute_pin`** (the registered rule fired on its second branch: C2 6 of 6 >= 5 of 6).
Flag: `same_class_pair_exposed` (N1 complete with a non-empty reasoning source on every record,
and round 52's archived source non-empty on all of its records: the 27B class now has a
same-class pair with the channel open on both sides).

## Reading

1. **H2 is what the registered rule picked, and it picked it fully.** All six ladder records
   below the pin reached their requested cap with `finish_reason` `length`, no marker and no
   answer line (1,536, 1,024 and 512 on both gold-no items, C2 6 of 6). On this 27B-class build
   the output consumes the whole requested budget at every rung; the cap is the binding
   constraint, not a hook.
2. **The reserve region does not travel to the class (H4, negative).** The post-hoc stop-offset
   column's shape flag is `no_reserve_cap_bound`: every pinned-pair record stopped at its cap
   with reserve 0 (round 52's 27B-class shape), not at one shared positive reserve (round 53's
   flash-class shape, 492 at every rung). Same items, same prompt bytes, two classes, two
   shapes: the 492-reserve region is not a class invariant and did not transfer from the flash
   class to this 27B-class deployment.
3. **The natural stop is class-tied, too.** The gold-yes control stopped at 838 (round 52's
   27B-class archived stop was 840; round 51's flash-class stop was 1,310): this build tracks
   the 27B-class position, not the flash-class one.
4. **The marker is not a cross-class invariant.** The flash class wrote the self-termination
   marker in 11 of 14 records; this build wrote it in none of 14. The marker claim of rounds
   49/51/53 stays scoped to the flash class.
5. **The traversal finished before the cut.** R1: all four cap-2048 as-is records mention all 98
   entities of their items (coverage 1.0, query target mentioned in every record) before the
   stop, so the censored cuts are a budget artifact, not a traversal failure.

## The reserve column is post-hoc, and labelled as such

`summary.json.stop_offsets` is not part of the registered gate blob: it reads only the frozen
`raw.jsonl`, and `gate.json` and the gate blob are untouched by it (`gate.json`
`8a9859758e1b6e530b434678fa975023d2e808c955817b470ed6a84d9d455aa4`; `raw.jsonl`
`041c8d6b18280abaa963141e18192583e7b85002e87f38ea132d49a214fb4689`). Its reserve histogram,
emitted by the instrument: reserve 0 carries 12 rows (every censored record across all three
arms), 250 the duplicate's 1,798 stop and 1,210 the gold-yes control. **No verdict of this round
rests on that column**; the tier came from the registered rows alone. It is reported because it
is the readout the H4 cross-class contrast was registered against, and it names the shape
(`no_reserve_cap_bound`) the flash-class shape (`constant_reserve_below_cap`) failed to
produce.

## Two side findings that did not need the ladder

**Identical prompt bytes, different stop, different verdict (C7, 0 of 1).** The duplicate
re-dispatch of 116261051 at cap 2048 had the same prompt SHA-256
(`068bc6a1fb0620fb`), but where its twin was censored at 2,048 with no answer, it stopped
naturally at 1,798 and declared `no` (the correct gold label), traces 5,616 vs 5,130 characters.
At `temperature 0.0` this deployment is not answer-deterministic for this item either: the flash
class diverged no-then-yes in round 53, this class diverges censored-then-correct.

**The verdict is not read from the traversal (C6, 0 of 2).** Both enumerate records were censored
at 2,048 before they had listed the reachable set or answered, so the recovery flag is
unreachable and the ceiling stays exactly as registered. The listing controls are cap-bound as
well: the model did not write 4,000 integers. At cap 2,048 it enumerated 1 to 100, then planned
chunking (`101-200`, `201-300`, ...; 337 numbers in the trace, 253 distinct) and was cut; at cap
1,024 it enumerated 1 to 100 and was cut after 143 numbers (42 distinct, including the model's
own character-count estimates). The `DONE` the measure reports in both traces is the
instruction's own word, quoted at the top of the trace, not a terminator line the model wrote.

## Cross-firing against round 52 (X1, 3 of 3) and round 51 (C8, 0 of 2)

X1 matches round 52's archived k = 48 answer state on all three items: the two censored gold-no
records stayed censored (no declared answer, as archived), and the gold-yes item delivered and
was correct (`yes`, as archived). The pair is answer-level only by the exposure rule: round 52's
archive stores the reasoning text but no marker count. The two sides of the 27B-class pair
differ in build (round 52's deployment versus this one) and in trace-field name
(`reasoning_content` versus `reasoning`), which is exactly what the exposure statement of the
pair must carry.

C8 is 0 of 2 against round 51's archived rows (both items: `stop`, 1,556, marker 1, answer
`yes`): the serving-id digests differ (`26df9af5972ff312` here, `c62b81e96826354e` in round 51),
the class differs, and the finish states do not reproduce (censored here). The cross-class
non-reproduction is the expected reading, not a defect: it is the control row against which the
in-class reproduction of X1 is contrasted.

## Archive provenance (disclosed, no verdict depends on it)

The pin and the cross-firing rows are quoted from three round directories that are open PRs, not
on `main` yet: round 51 (`research/nightly-2026-11-06-0433`, #130), round 52
(`research/nightly-2026-11-07-0319`, #132) and round 53
(`origin/research/nightly-2026-11-07-0400`, #131). Those rows are vendored into the instrument
with the SHA-256 of each archived `raw.jsonl` beside them (round 51
`fbfa4fde59f43ea3f484b4205b5beff11d2add27e6c3f60e210ca092e3452f7a`, round 52
`6c1ca286bffd4421ea4aef0bb71aac50648f6591b2c950b1185ba4d989544a1b`, round 53
`d75ced46f51ece2ddf7413bf4331fe8618568d4e300965471486700657efc246`) and re-certified before
any dispatch. Round 52's archive stores the reasoning text but no marker count, so its
cross-firing (row X1) is an answer-level claim only; the certifier refuses a planted exposure
slip in either direction.

## Firing integrity

All 15 planned calls ran inside the 3,000 s dispatch guard (dispatch wall 237.36 s): 14
experiment records plus the health probe, `not_dispatched` empty, no arm timed out, and no
runner abnormality followed. No arm is reported as a result other than what `raw.jsonl`
carries. The local `run.log` stays out of the round directory by the round contract.

## Limits

Executed only: one firing, one 27B-class build (a third 27B-class firing, a different build
from round 52's), 14 experiment records, n = 2 items per cap band and n = 2 per arm, which is
exploratory. The three archive quotes come from branches that are still unmerged, and this
firing is itself in an open PR, so its own numbers are not yet main-carried evidence. The
reserve observation is post-hoc and single-firing: it is one stop-offset column of one dispatch
on one deployment, consistent with round 52's censored-at-cap shape but not a serving-stack
measurement, and no stack-level mechanism was probed here. The registered tier names what the
firing rules out (a cap-proportional budget and the flash-class reserve shape for the ladder
family on this class), not what it confirms: an absolute budget is the reading of this
firing's stops, and whether it is a property of this build, this class or this stack
configuration is a question the next firing is owed.

## Reproduction

```
python3 class_reserve_probe.py --selftest    # 152 checks, prints the gate blob
python3 class_reserve_probe.py --archive      # the three archive quotes, recomputed
python3 class_reserve_probe.py --dry-run      # the 15 planned calls with prompt digests
python3 class_reserve_probe.py --rescore      # rebuilds summary.json and gate.json from raw.jsonl
```

`--selftest`, `--archive` and `--rescore` need no endpoint. `--run` reads `NIGHTLY_BASE_URL`,
`NIGHTLY_MODEL_ID` and `NIGHTLY_API_KEY` from the environment and writes none of them; this
firing ran without an `NIGHTLY_API_KEY` value because the endpoint serves without a credential.
The duplicate-divergence numbers above come from `raw.jsonl` with:

```
python3 - <<'PY'
import json
recs = [json.loads(l) for l in open("raw.jsonl") if l.strip()]
by = {r["label"]: r for r in recs}
a, b = by["as_is_116261051_c2048"], by["dup_116261051_c2048"]
i = 0
while i < min(len(a["trace"]), len(b["trace"])) and a["trace"][i] == b["trace"][i]:
    i += 1
print(i, len(a["trace"]), len(b["trace"]), a["content"], b["content"])
PY
```
