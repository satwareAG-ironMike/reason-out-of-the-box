# Round 53 (2026-11-07 04:00): the 1556 stop does not move with the cap, and it is not the cap

Firing: 2026-11-07 04:00 (issue #65 timer). Class: a flash-next-class local endpoint (serving id
disclosed only in the commit `Model:` trailer; artifact digest `c62b81e96826354e`). No metered or
hosted provider was used; no search API was used. Status label: **Executed** (see Limits).

## Question

Registered before dispatch (schema `round53-gate-v1`, frozen in `gate.json`, pinned in the
instrument), blob:

`1f78366a0d610f12e03b3f46c4ab8e6ee21c9301d5a51e452758dd3998b9ae8c`

> Does the 1,556-token stop that two firings on this deployment produced at the 2048 cap come from
> the traversal or from a budget in the serving stack? Hold the prompt bytes fixed, move the
> requested cap to 512, 1024 and 1536, and ask whether the stop length and the self-termination
> marker move with the cap.

Three hypotheses were registered. `H1_proportional_budget`: the stop lands at `1556*cap//2048`
(band 8 tokens) with `finish_reason` `stop` and the marker sentence present at every cap.
`H2_absolute_budget`: at every cap below the pin the output reaches the cap itself with
`finish_reason` `length`, no marker and no answer. `H3_no_serving_budget`: lengths track the task,
the marker appears wherever the model writes it, and the pin is a property of the family on the
class. Tier rule as registered, in order: `serving_budget_hook` if C1 >= 5 of 6 and C2 <= 1 of 6
and C5 == 2 of 2; `absolute_pin` if C2 >= 5 of 6; `no_serving_budget` if C1 <= 2 of 6 and C5 == 0
of 2; `unresolved` otherwise.

## Why this is the decisive test

Two earlier firings on this same class produced 1,556 completion tokens at the 2048 cap with the
marker sentence in the trace: 33 records of round 49 and 8 of round 51, both at utilisation 0.7598
(`1556/2048`, recomputed by the instrument's archive certifier). A single firing cannot tell those
two readings apart, because at one cap a proportional budget and an absolute budget are the same
number. Moving the cap while holding the prompt bytes fixed separates them: H1 predicts 389, 778
and 1167 at caps 512, 1024 and 1536; H2 predicts 512, 1024 and 1536 themselves.

## Items, arms and dispatch plan

`k = 48` load-floor ladders (`facts = 2k = 96`, 98 entities, two disjoint 48-edge paths,
`n_chains = 2`), seed base 20261005. Three seeds certified against the archived digests before any
dispatch: the two gold-no items round 51 delivered wrong (116261051, 116261076), and the gold-yes
item 116261338 whose archived natural stop 1310 sits below the pin. Prompt digests matched round 51
byte for byte before dispatch: `068bc6a1fb0620fb`, `ffc75c928f37f0d9`, `87e36020f5c31c93`.

| arm | what it is | caps |
|---|---|---|
| `as_is` | the round 51 prompt unchanged | 2048 (both gold-no, plus a duplicate re-dispatch of 116261051, plus the gold-yes control), 1536, 1024, 512 (both gold-no) |
| `enumerate` | same prompt, plus "list every entity you can reach from the query entity before you answer" | 2048, both gold-no items |
| `listing` | non-ladder control: count 1 to `N` in order, one number per line, stop with DONE | 2048 (`N = 4000`), 1024 (`N = 4000`) |

15 planned calls of the 40-call cap (14 experiment records plus one 256-token census health call,
issue #73), `temperature 0.0`, `max_tokens` at most 2048, dispatch budget 900 s. Anchors, the
duplicate control and the enumerate arm were dispatched first so a timeout would leave the
cap-ladder comparison intact. Dispatch took 305.729 s wall, 11,283 prompt tokens and 16,549
completion tokens. No call was dropped, no arm timed out.

## What fired

`completion_tokens`, `finish_reason`, marker count and the answer-channel readout (issue #94), from
`raw.jsonl`:

| label | cap | tokens | finish | markers | gold | declared | reserve (cap - tokens) |
|---|---|---|---|---|---|---|---|
| `as_is_116261051_c2048` | 2048 | 1556 | stop | 1 | no | no | 492 |
| `as_is_116261076_c2048` | 2048 | 1556 | stop | 1 | no | yes | 492 |
| `dup_116261051_c2048` | 2048 | 1556 | stop | 1 | no | yes | 492 |
| `as_is_116261338_c2048` (gold-yes control) | 2048 | 1205 | stop | 0 | yes | yes | 843 |
| `enum_116261051_c2048` | 2048 | 1715 | stop | 1 | no | yes | 333 |
| `enum_116261076_c2048` | 2048 | 1713 | stop | 1 | no | yes | 335 |
| `listing_4000_c2048` | 2048 | 2048 | length | 1 | (no answer field) | - | 0 |
| `as_is_116261051_c1536` | 1536 | 1044 | stop | 1 | no | yes | 492 |
| `as_is_116261076_c1536` | 1536 | 1044 | stop | 1 | no | yes | 492 |
| `listing_4000_c1024` | 1024 | 1024 | length | 1 | (no answer field) | - | 0 |
| `as_is_116261051_c1024` | 1024 | 532 | stop | 1 | no | yes | 492 |
| `as_is_116261076_c1024` | 1024 | 532 | stop | 1 | no | yes | 492 |
| `as_is_116261051_c512` | 512 | 512 | length | 0 | no | (no answer) | 0 |
| `as_is_116261076_c512` | 512 | 512 | length | 0 | no | (no answer) | 0 |

Every pinned ladder record carries the same sentence in its trace: `I have thought about this long
enough; time to give my answer.` Answers: 10 of 14 records delivered a verdict through the answer
channel, 2 were correct, 8 delivered a verdict that contradicts the solver's gold label. The
census (issue #105): 14 of 14 records censused, reasoning channel `reasoning_content` on all of
them; the health probe reports the same two fields.

## Gate rows

| row | registered band | measured | status |
|---|---|---|---|
| C1 hook at the cap ladder | 6 of 6 | 0 of 6 | fail |
| C2 absolute cap signature | 5 of 6 or more refuses C1 | 2 of 6 | fail |
| C3 marker locked to the hook | 0 disagreements | 4 disagreements | fail |
| C4 gold-yes control below the pin | 1 of 1 | 1 of 1 | pass |
| C5 listing control cut by the same hook | 2 of 2 | 0 of 2 | fail |
| C6 enumerate arm recovers the gold label | 2 of 2 | 0 of 2 | fail |
| C7 duplicate re-dispatch byte-identical (issue #100) | 1 of 1 | 0 of 1 | fail |
| C8 same-prompt cross-firing vs round 51 | 2 of 2 | 1 of 2 | fail |
| C9 off-hook marker anomalies | reported | 8 records | reported |
| R1 coverage, R2 seed pairing, N1 census, H0 health | reported | reported | reported |

Tier: **`no_serving_budget`** (the registered rule fired on its third branch: C1 0 of 6 <= 2 of 6
and C5 0 of 2). Flag: `marker_not_locked_to_predicted_hook`.

## Reading

1. **The 1,556 figure is not a proportional budget.** At cap 1536 the ladder stopped at 1044, not
   the predicted 1167; at cap 1024 it stopped at 532, not 778. The measured offsets from the
   predicted hook are -123 and -246, growing with the distance from the pin. C1 is 0 of 6.
2. **The ladder is not pinned at the requested cap either.** Only the two cap-512 records reached
   their cap (`finish_reason` `length`, no marker, no answer line), and C2 is 2 of 6, two short of
   the band that would have refused H1.
3. **What recurs is a constant gap below the requested cap.** Every one of the seven pinned ladder
   records stopped with 492 tokens of reserve below its cap: 1556/2048, 1044/1536, 532/1024. The
   two enumerate records hold 333 and 335, and the listing controls hold 0. The reserve is not a
   constant fraction either: 0.2402 at 2048, 0.3203 at 1536, 0.4805 at 1024.
4. **The marker is not a hook signal.** It appears in 11 of the 14 records, including both listing
   controls (which have no traversal at all) and both enumerate records (159 and 157 tokens *above*
   the predicted hook). It is absent exactly where the output is hard-truncated (the two cap-512
   records) and in the gold-yes control that stopped naturally at 1205. C9 reports 8 anomalies, 4 of
   them ladder records landing below their own predicted hook and 4 above it.
   This firing therefore cannot use the marker as evidence of a budget at all, and the registered
   flag says so.
5. **H3 is what survives, partly.** Lengths move with the arm (ladder, enumerate, listing, and the
   natural 1205 of the gold-yes item), the marker appears wherever the model writes it, and the
   listing control shows a different shape entirely: truncated at its cap with DONE already present
   and only 180/160 distinct numbers of 4000 (3,821 and 3,840 missing), i.e. the counter skipped
   rather than enumerated. So the serving stack did bound the listing arm, and did not bound the
   ladder arm at the requested cap.

## The reserve column is post-hoc, and labelled as such

`summary.json.stop_offsets` is not part of the registered gate blob: it was added after the tier
rule had been frozen because the fired pattern matched none of the three registered shapes. It
reads only the frozen `raw.jsonl`, and `gate.json` and the gate blob are untouched by it
(`gate.json` is byte-identical before and after the rebuild: `2fee1dc16de56597e2ccfda657127acb7468dc7e7e6b2435e0be2fd2e5fb1c85`;
`raw.jsonl` `d75ced46f51ece2ddf7413bf4331fe8618568d4e300965471486700657efc246`). Its reserve
histogram, emitted by the instrument: reserve 492 carries 7 rows (all `as_is`, all marker-bearing),
reserve 0 carries 4 rows (2 `as_is` at cap 512 plus both `listing`), 333 and 335 one `enumerate`
row each, 843 the gold-yes control. **No verdict of this round rests on that column**; the tier
came from the registered rows alone. It is reported because the next round has to test the reserve,
not the pin.

## Two side findings that did not need the ladder

**Identical prompt bytes, different reasoning, different verdict (C7, 0 of 1).** The duplicate
re-dispatch of 116261051 at cap 2048 had the same prompt SHA-256 (`068bc6a1fb0620fb`), the same
1,556 completion tokens, the same `stop` and the same marker count, but the two traces share only a
108-character common prefix (4,372 vs 4,668 characters) and the answers differ: `no` then `yes`. At
`temperature 0.0` the deployment is not answer-deterministic for this item, which is also why the
archived verdict of round 51 (`yes`) reproduces on one twin and not the other.

**The verdict is not read from the traversal (C6, 0 of 2).** Both enumerate records listed exactly
the 49 entities the independent BFS reaches from the query entity (extra 0, missing 0,
`list_equals_bfs_reachable_set` true), the query target is not among them, and the gold label is
`no`; both records still answered `yes`. Listing the reachable set did not recover the label, it
contradicted its own list.

## Cross-firing against round 51 (C8, 1 of 2)

Same serving-id digest as round 51 (`c62b81e96826354e`), so the prompt digests are directly
comparable. For both certified items the finish state reproduces (`stop`, 1556 tokens). The answer
channel reproduces for 116261076 (`yes` in round 51, `yes` here) and does not for 116261051 (round
51 `yes`; this firing `no` on the first dispatch and `yes` on the duplicate). Census on both sides
is `reasoning_content`. The gold-yes control moved from 1310 (archived) to 1205 (here).

## Archive provenance (disclosed, no verdict depends on it)

The pin and the cross-firing rows are quoted from four round directories that are open PRs, not on
`main` yet: round 48 (`research/nightly-2026-11-05-0229`, #125), round 49
(`origin/research/nightly-2026-11-05-0400`, #127), round 50 (`research/nightly-2026-11-06-0259`,
#128), round 51 (`research/nightly-2026-11-06-0433`, #130). Those rows are vendored into the
instrument with the SHA-256 of each archived `raw.jsonl` beside them and re-certified before any
dispatch. Round 48's archive stores no reasoning text (its census lists a `reasoning` field that
its records do not store), so its marker column is recorded as **not evaluable** and no marker
count is quoted for it; the certifier refuses a planted exposure flip in either direction.

## Reproduction

```
python3 budget_hook_probe.py --selftest    # 156 checks, prints the gate blob
python3 budget_hook_probe.py --archive     # the four archive quotes, recomputed
python3 budget_hook_probe.py --dry-run     # the 15 planned calls with prompt digests
python3 budget_hook_probe.py --rescore     # rebuilds summary.json and gate.json from raw.jsonl
```

`--selftest` and `--rescore` need no endpoint. `--run` reads `NIGHTLY_BASE_URL`,
`NIGHTLY_MODEL_ID` and `NIGHTLY_API_KEY` from the environment and writes none of them; this firing
ran without an `NIGHTLY_API_KEY` value because the endpoint serves without a credential. The
duplicate-divergence numbers above come from `raw.jsonl` with:

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

## Firing integrity

The runner posted an abnormal-end record for this firing on issue #65 (exit 124 at the 90-minute
window). That record post-dates a completed dispatch: all 15 planned calls ran, `dispatch_wall_s`
305.729, `not_dispatched` empty, and the tier was resolved from the frozen `raw.jsonl` afterwards.
No arm timed out, so no arm is reported as a result other than what `raw.jsonl` carries. The round's
own surviving failure record is the runner line on #65 plus the local `run.log`; `run.log` stays
local by the round contract.

## Limits

Executed only: one firing, one class, 14 experiment records, n = 2 items per cap band and n = 2 per
arm, which is exploratory. The four archive quotes come from branches that are still unmerged, and
this firing is itself in an open PR, so its own numbers are not yet main-carried evidence. The
reserve observation is post-hoc and single-firing: it is consistent across the seven pinned records
of one dispatch on one deployment, which is not the same as a serving-stack measurement, and no
stack-level mechanism was probed here. The registered tier names what the firing rules out (a
cap-proportional budget and a cap-absolute budget for the ladder family), not what it confirms.
