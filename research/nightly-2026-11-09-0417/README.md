# Round 56 (2026-11-09 04:17): the registered name space on the first item past k = 48 - the k = 64 load-floor item [RESULTS PENDING]

Firing: 2026-11-09 04:17 (issue #65 timer, pool slot 4/6). Class: a 27B-class local model
(the serving id is disclosed only in the commit `Model:` trailer; the records carry a one-way
digest). No metered or hosted provider was used. One free scholarly fetch was used to verify the
CLUTRR depth statement below (ar5iv rendering of the arXiv record, no API key). Status label:
**Executed** (see Limits).

## Question

Registered before dispatch (schema `round56-gate-v1`, frozen in `gate.json`, pinned in the
instrument), blob:

`5ee32d3f59c2e3891246720dfe6cf4322f8fe8d5284b48827137c708f4ef87d8`

> On a 27B-class local deployment, with the registered name-or-NONE response format (round 55's
> template re-pinned byte-identically, every cell's prompt digest frozen in this gate before the
> first prompt) and the prompt bytes fixed with only the step count `j` moving, does the one-of-many
> entity-name answer space (a) deliver correct terminals in the mid band `j = 8..32` of the first
> ever dispatched `k = 64` load-floor item (issue #129), (b) hold in the deep band `j = 40..64`
> past the deepest archived level 48, (c) refuse with no false name when the links run out,
> (d) reproduce the archived `k = 48` and `k = 32` anchor cells on this class, (e) hold
> self-agreement on the re-dispatched deep cells, and (f) pass or refuse itself on the matched-name
> trace-provenance row?

## Why this question

Round 55 (`research/nightly-2026-11-09-0301/`, PR open at this firing) introduced the name-answer
arm exploratorily on the flash-next class: 18 of 18 delivered names correct, zero false names, and
censorship at the 2,048 cap exactly where the yes/no arm censored on the same 96 facts. It left two
registered next steps, both taken here: (1) extend `j` past 48, and (2) register the response
format before any confirmatory use.

Issue #129 measured the generator-side blocker: the entity-pool ceiling is a ceiling on *item
size*, not on ladder depth. The whole-series call dies at `k = 49` because one large-`C` item
exhausts the 2,700-name pool, but the load-floor items (`C = 2`, `2*(k+1)` names) keep generating
far past it. This instrument implements issue #129's option (a) locally: a per-item scan of level
64 with skip-on-raise, in the generator's own seed formula (`seed_base + 2_000_000 * level +
index`, seed base 20261005, unchanged). The first load-floor item of the series is pinned at seed
148261120 (raw scan index 115, 128 facts, query `smixg -> brelt`, answer yes) and the scan is
pinned at 235 of 400 generated items, so a generator revision change breaks the selftest before
any prompt is spent. This item is the first item of any level ever dispatched past `k = 48` in
this repository.

The response format is registered in this gate (block `response_format`): the prompt template
(byte-identical to round 55's; the per-cell digests in `gate.json` are the check), the
declared-answer rule (last generator-vocab name in the content field, else the NONE sentinel, else
undetermined; an empty content field is a non-delivery), the two NONE-gold classes, and the
two-part control score that closes round 55 finding 4: a censored control is a non-delivery, not a
miss; the false-name count among delivered controls is the gated quantity, and the control
delivery rate is reported, not gated. The selftest plants a censored control and asserts the tier
does NOT read `controls_invalid` (the round 55 gate would have failed it).

The name space is also the space the closest published multi-hop benchmark uses (Sinha et al.
2019, CLUTRR, EMNLP 2019, arXiv:1908.06177, archived in `archive/INDEX.md` round 20): kinship
relations between characters, so a correct answer is a name and an incorrect one a wrong name, not
a coin flip. In CLUTRR's systematic-generalization experiments the clause length (the number of
reasoning steps in the proof) is tested up to 10, and the entities are drawn from a pool of 300
common English names (verified 2026-11-09 against the ar5iv rendering of the arXiv record). The
`k = 64` item here sits six times beyond that tested depth, over a 2,700-name pool, and the gold
terminal is one name no constant rule and no connectivity shortcut can produce (the out-degree-zero
tail shortcut is worth about 1/2 only at `j = k` and about nothing at intermediate `j`).

## Items, arms and dispatch plan

Load-floor items (exactly two disjoint `k`-edge paths, `facts = 2k`), selected by the
deterministic rule in the instrument, never by run-time choice:

| item | level | seed | facts | lineage |
|---|---|---|---|---|
| L64 | 64 | 148261120 | 128 | NEW: first load-floor item of the level-64 series (issue #129), pinned |
| L48 | 48 | 116261051 | 96 | round 51's anchor item; round 51 yes/no digest `068bc6a1fb0620fb` + round 55 name digests vendored |
| L32A | 32 | 84261011 | 64 | round 55's anchor item; round 55 name digest vendored |

- `name` cells on L64: mid band `j = 8, 16, 24, 32` (row C1) and deep band `j = 40, 48, 56, 64`
  (row C3, the extension past 48).
- `off_end` controls: `j = k + 1` from the query source on L64 and L48 (gold NONE).
- `dead_end` controls: the OTHER path's tail (out-degree zero, never the walk's own terminal)
  asked for one step, on L64 and L48 (gold NONE). Row C2 scores them two-part.
- Anchor cells (row C4): `L48_j16`, `L48_j32`, `L48_j48`, `L32A_j32`, prompts byte-identical to
  the vendored round 55 digests; round 55 delivered `L48_j16` (883 tok) and `L32A_j32` (951 tok)
  correct on the flash class and censored `L48_j32` and `L48_j48`.
- Budget rung: the `j = 64` query at `max_tokens` 256.
- `dup` re-dispatches of `L64_j48` and `L64_j64` (row C5, issue #100).

19 dispatches of the 40-call cap, plus one census health call and one calibration call (`L64_j8`,
dispatched after the gate freeze and before the first experimental cell; it confirmed the format
parses on this class: a name was declared in 1,487 completion tokens, finish `stop`; it is not
experimental data and is not in `raw.jsonl`). `temperature 0.0`, every requested cap at most
2,048. Instrument selftest: 49 checks, green before dispatch, with planted negatives (an off-by-one
gold must score wrong, a censored record must be a non-delivery rather than a wrong answer, an
empty pseudo-gold must not read as present, a false name on a delivered control must invalidate the
tier, and a censored control must NOT invalidate it, and the tier rule must land on each of its
four tiers under planted record sets).

## What fired

[RESULTS PENDING]

## Result

[RESULTS PENDING]

## Findings

[RESULTS PENDING]

## Limits

- One endpoint, one class, one firing: `Executed`, exploratory, n = 1 per cell (two cells at
  n = 2 via the duplicate re-dispatches).
- The name arm is a different task from the archived yes/no arm. It cannot show that the yes/no
  task is solvable at `k = 64`; it shows what this endpoint produces about the same fact graph
  when the answer space is a name.
- The prompt states the step count, so the task is "walk `j` edges", not "decide entailment". Any
  depth claim from it is a claim about production under an explicit horizon.
- The gold terminal is present in the fact block, so a model could in principle reach it by a
  positional rule ("the entity with no outgoing edge") rather than a walk. That shortcut is worth
  about 1/2 at `j = k` (two tails per item) and about zero at the intermediate `j` cells, which
  is why the curve, not the deepest cell, carries the claim.
- The k = 64 item is pinned to the current generator revision (235 of 400 items in the per-item
  scan); a generator fix per issue #129 changes the corpus and must be re-pinned.
- The firing's agent session restarted once mid-round (after the gate freeze, before the
  dispatch). The endpoint was re-probed at session start per the round 22 discipline (model list
  plus a 256-token chat probe, both healthy), and the dispatch ran the full plan from an empty
  archive, so the restart cost nothing but this disclosure.
- Trace exposure (issue #105): [CENSUS PENDING].

## Reproduce

```
python3 research/nightly-2026-11-09-0417/name_depth_probe_r56.py --selftest
python3 research/nightly-2026-11-09-0417/name_depth_probe_r56.py --dry-run
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
  python3 research/nightly-2026-11-09-0417/name_depth_probe_r56.py --run
python3 research/nightly-2026-11-09-0417/name_depth_probe_r56.py --rescore
```

Prompts are not stored in `raw.jsonl`: each record carries `(level, seed, j, cap, kind)` plus the
prompt sha256, and the prompt re-renders byte-identically from the seed base, so the digests are
the check. `run.log` stays local.

## Landing note (added 2026-11-19 when this record was landed; everything above is as-shipped)

This directory is a stranded record from the audit filed as issue #150. The 2026-11-09 04:17
firing froze its gate, dispatched, scored and wrote its artifacts into the runner's working copy,
but never created a branch and never posted a summary to #65, so none of it was reachable from the
remote until this PR. The sections "What fired", "Result" and "Findings" above were left as
`[RESULTS PENDING]` by that firing. They are kept verbatim under the forward-only errata rule
(issue #120): what follows reads the frozen aggregates mechanically and adds no new analysis.

| Item | Value, read from the shipped artifacts |
|------|----------------------------------------|
| Records | 19 in `raw.jsonl` (16 dispatched cells, 2 duplicates, 1 dead-end control, 1 end-of-ladder control), kinds `name`, `dead_end`, `off_end`, `dup` |
| Tier | `name_space_ceiling_below_64` |
| Flags | `delivery_bound_loss`, `trace_provenance_refused` |
| C1 mid band j = 8..32 | 3 correct of 4, pass |
| C2 refusal | 2 correct refusals of 4, 2 delivered, 0 false names, pass |
| C3 deep band j = 40..64 | 0 correct of 4, verdict `ceiling` |
| C4 anchor reproduction | 2 of 2 round-55 delivered anchors correct, 0 wrong names, pass |
| C5 self-agreement | 2 of 2 duplicate pairs agree on the name, pass |
| C6 trace provenance | inadmissible: pseudo-rate 1.0 against gold-rate 0.8571 on 7 records, gap -0.1429, fail |
| D1 delivery | delivery-bound: shallow 0.75, deep 0.0, drop 0.75 |
| Trace exposure (issue #105) | All 19 records carry the field set `["content", "reasoning_content", "role"]` with `reasoning_field = reasoning_content`, i.e. trace exposed on this firing |

Label: **Executed**, exploratory. Small n per level (4 cells per band, 2 duplicate pairs), so no
row here is a study verdict, and the thesis reading of the ladder ceiling stays with the
pre-registered analysis (#11).

Provenance of `summary.json`, stated plainly: the file in this record is the deterministic
`--rescore` derivative produced during the 2026-11-19 verification described on #150, not the
bytes the firing wrote. That verification ran `--selftest` and `--rescore` against the only copy
without a byte backup first, and `--rescore` rewrites `summary.json` in place, so the shipped file
is lost and its differing fields can no longer be named. The shipped file hashed
`3263cb282d846bfa721c63fe...` (prefix as recorded on #150 before the overwrite); the file in this
PR hashes `4afff024185cb035057e6e655f278c3f4a45c2fe7a60858d0a101c0020a7db89`. The rescore writer
does not carry the `dispatch` block over, which accounts for the whole size difference (1,647 to
1,465 bytes); every aggregate `run.log` printed at dispatch time is reproduced by the derived
file, including the tier and both flags. Every other file in this directory is byte-unchanged
since the firing (`gate.json` `e1198df5c8d24aba902310ff066cb583`, `raw.jsonl`
`1594c4aef15ea60401599e8f0c3b31f9`, `health.json` `af9f26761c457f678607982256ea9ad3`, instrument
`a68bf12aebb905463d08cd3e6b0ccf9f`); the as-shipped `README.md` hashed
`dda1bdc0e9d319feca05262ff2f78dd862f50f828f569d0ad87c3c9398b796e2` before this appended note.
`run.log` stays local per the research contract.
