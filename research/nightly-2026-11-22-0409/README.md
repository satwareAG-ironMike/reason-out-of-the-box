# Round 81 (2026-11-22 04:09): the weekly compute cap is spent in 2026-W47, so this firing dispatches nothing - a zero-prompt kill report (issue #195)

Nightly firing 2026-11-22 04:09 (pool slot 6/8), a 27B-class local endpoint
whose serving build is pinned as `model_digest` `26df9af5972ff312` (the build
rounds 54, 63, 72, 75 and 77 measured; no serving id in any artifact). Tracker
issue #65. This round dispatched **zero prompts**: the weekly compute cap is
spent on both lanes for the firing's ISO week, and the cap's kill rule is that
a spent cap stops the loop and reports. State: **Executed** (the audit ran;
no experiment arm ran, and nothing that did not run is reported as a result).

## Question

Does this firing dispatch prompts? The weekly compute cap in
`research/AGENTS.md` (issue #195, codified 2026-11-21) caps the nightly lane
at 80 dispatched prompts a week and the exploratory loop in `explore/` at 400,
with a 40-prompt cap per round. Both caps are contractual: when spent, the
loop stops and reports, and the next ISO week starts a fresh count. This
firing sits in ISO week 2026-W47, which the cap had been in force for. One
question, decided by the record rather than by memory: **how many prompts did
each lane dispatch in 2026-W47, and is this firing inside the dispatch
window?**

## Selection rule

A firing with a spent cap does not spend prompts and does not design an
experiment; it re-counts the week from the public record, ships the counting
instrument, and posts the kill report. Re-counting is the whole round
because the week's records live in two places the record-keeping must join:
the in-tree `raw.jsonl` files (the merged rounds) and the dated open-PR
dispatch records that exist only in unmerged heads (issue #150 class - the
rounds of PR #201, #203, #204 and #210). The in-tree total alone understates
the week by exactly the open-PR dispatches, so an audit that walks only the
merged tree would clear a lane that the record shows spent.

## Instrument

[cap_audit.py](cap_audit.py), stdlib only. `--selftest` runs 17 checks before
any output: the in-tree counting, the open-PR deduplication (a record whose
round directory is already in-tree must never be added again, so a merge
cannot double-count the week), an out-of-week record that must not enter the
totals, the round-cap violation scan on a planted 480-prompt round, the
spend boundary (a total exactly at the cap is unspent, one over is spent),
and the ISO-week boundary cases (Sunday 2026-11-22 belongs to 2026-W47,
Monday 2026-11-23 to 2026-W48, New Year's Day 2026 to 2026-W01). `--audit`
re-counts the live tree, merges the deduplicated open-PR records, and writes
[cap_audit.json](cap_audit.json). The open-PR records carry their public
provenance in-file and are asserted by the selftest; the round-79 README
already records the weekly nightly total as 157, and the audit reproduces it
from parts instead of by citation.

## Result

The audit for 2026-W47 (generated on the firing, [cap_audit.json](cap_audit.json)):

| Lane | Cap (week) | In tree | Open PRs | Total | Spent? | Over by | Next dispatch window |
|------|-----------:|--------:|---------:|------:|:-------|--------:|:--------------------|
| nightly | 80 | 117 | 40 (PR #204; PR #201 dispatched 0 of 40) | **157** | yes | 77 | 2026-W48 |
| explore | 400 | 57 | 488 (PR #203: 8, PR #210: 480) | **545** | yes | 145 | 2026-W48 |

In-tree per round, nightly lane: `nightly-2026-11-16-0219` 8,
`-0412` 25, `nightly-2026-11-17-0401` 17, `nightly-2026-11-18-0423` 17,
`nightly-2026-11-19-0401` 21, `nightly-2026-11-20-0400` 29 (117). Explore
lane in tree: `2026-11-21-r78-cross-ask` 29, `2026-11-21-r79-cross-ask` 28
(57). This firing adds 0. The two open-PR totals check against the record:
117 + 40 = 157 is the round-79 README's own weekly figure, and PR #210's body
accounts for its 480 as 200 calibration + 40 novelty-band + 240 max_tokens=8
failure-record completions.

The per-round 40-prompt cap is also scanned: one violation, the round 81
directory (PR #210) at 480 dispatched prompts, 440 over. No in-tree round
exceeds 40.

## Findings

1. **The kill rule fires on both lanes in 2026-W47.** Nightly 157 of 80 and
   explore 545 of 400. The loop stops and reports: no dispatch on either
   lane until 2026-W48 (first firing 2026-11-23 02:00). The cap counts the
   whole ISO week, the way the round-79 README already counted it; the two
   open-PR records are the difference between "the merged tree looks
   unspent" and the record's truth.
2. **The 40-prompt round cap and the frozen judge's exploratory minimum do
   not compose.** The judge requires 40 items per arm for an exploratory
   round; a judge-conformant round with one calibration arm plus one
   novelty arm is at 80 prompts before any failure record, and round 81
   spent 480. The cap's own arithmetic (400 a week "as 10 rounds at the
   40-prompt cap") assumed 40 a round, which the judge-conformant shape
   cannot meet. Owner adjudication owed in issue #195 (with #194): either
   the per-round cap follows the judge's arm count, or the judge's
   exploratory minimum is relaxed for pool builds. This round only
   registers the mismatch; it changes nothing.
3. **The 2026-11-22 02:00 firing (round 80) is a zero-dispatch failure
   record.** It died at the runner's model resolution on a pool slot whose
   model column is stale against the live registry; its surviving record is
   the runner's fallback line on #65 and the local log. Filed as issue
   #211 (runner-side; the pool and runner live outside this repository).
4. **The shared primary checkout re-broke in the #205 class between this
   week's repair and this firing** (its `core.bare` flag set `true` again
   after the 2026-11-21 04:48 repair). Repaired at execution time this
   firing, recorded on issue #205; this round worked in its own worktree
   branched from `origin/main`, the ownership rule #205 proposes.

## How to reproduce

```
python3 research/nightly-2026-11-22-0409/cap_audit.py --selftest
python3 research/nightly-2026-11-22-0409/cap_audit.py --audit
```

The committed `cap_audit.json` was generated on the 2026-11-22 04:09 firing
(ISO week 2026-W47). Re-running `--audit` from 2026-11-23 onward records the
fresh week instead; the open-PR records dedupe themselves out as their PRs
merge, so the instrument stays correct across the boundary with no edits.

## Outtakes

- This summary comment on #65 (the round's record; a zero-prompt round has no
  `raw.jsonl`, and the surviving record is `cap_audit.json` plus this README).
- Issue #211: the 2026-11-22 02:00 zero-dispatch firing, stale pool model
  column (deduped against the open list before filing; the 2026-10-26
  drift class has no open issue of its own).
- Recurrence comment on issue #205 (the shared-checkout `core.bare` re-break).
- The finding 2 mismatch goes to issue #195 with #194 for owner adjudication
  (a #195 comment, not a new issue: the cap's wording already lives there).

## Disclosure and limits

Zero prompts this firing; no endpoint call of any kind, so no transport,
sampler or readout facts are recorded here. The open-PR record counts are
the public bodies and raw archives of PR #201, #203, #204 and #210 as of
2026-11-22; when those PRs merge, the tree walk absorbs their counts and the
deduplicated records drop out, so a later week's audit must not read the
now-in-tree directories through the stale records. A round that could not
run its experiment arm says so: the experiment arm of this firing is the
weekly-cap kill report, and it ran to completion.
