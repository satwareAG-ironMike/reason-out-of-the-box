# explore

## Purpose

The open exploratory loop (owner objective 2026-11-21, issue #195). Agents run one experiment
per round against the frozen judge (`evaluation/frozen/`, issue #194), score it, and pick the next
experiment by expected information gain toward the decision rule. Confirmatory promotion is the
owner's step only and lives in PROMOTE PRs, never here.

## Ownership

Agents own this lane: designing the rounds, running them, scoring them, merging after green CI and
a verdict at head. The owner owns promotion, the frozen instrument, and the README verdict.

## Local Contracts

- One directory per round: `YYYY-MM-DD-<slug>/`. Never reuse a directory. The slug names the
  hypothesis family, not the date.
- Contents of a round that ran: `HYPOTHESIS.md` (what is tested and the one paragraph of
  expected-information-gain reasoning that justified picking this round next), `INSTRUMENT.md`
  (task family, generator seed policy, the non-reasoning prompt builders, sampler settings
  temperature/top_p/max_tokens/seed, and the round's prompt budget), `prompts/`, `raw.jsonl`
  (one record per prompt: prompt, raw response, score), `summary.json` (aggregates),
  `gate.json` (frozen gate), `score.json` (the frozen scorer's checkpoint report), `README.md`
  (results). A round that cannot run an arm says so in the ledger row and keeps the failure
  record; a timed-out arm is never reported as a result.
- Prompts are non-reasoning: no chain-of-thought scaffolds, no "think step by step", no
  few-shot reasoner traces. The model gets the item surface and an answer format, nothing else.
- Every round carries the pinned model hash, seed, sampler, and serving build. No host, port,
  endpoint, model file path, or serving build digest in anything public.
- Rounds here are exploratory. A confirmatory claim on the same task family is a PROMOTE PR
  (draft only, owner merges after reading it), pre-written before the run.

## Work Guidance

Before designing a round, read `explore/LEDGER.md` and the frozen rule, then write the
`HYPOTHESIS.md` paragraph that names which unresolved part of the decision rule this round moves
and what would make the round worthless. A round that cannot name that does not run.

The scorer's checkpoint status is recorded verbatim in `score.json`; it is not a verdict. The
verdict is claim-level only, and a claim recomputes every gate from the cell records.

## Kill rule

The loop stops and reports when either

- 10 consecutive rounds add no information gain (measured: the round changed no cell gate, closed
  no distance item in `distance_to_claim`, and added no new blocker or refutation), or
- the weekly compute cap in `research/AGENTS.md` is spent.

## Verification

Local CI parity before pushing in this subtree: `python3 scripts/check_archive.py --selftest &&
python3 scripts/check_archive.py`, `python3 scripts/check_links.py --selftest && python3
scripts/check_links.py`, the strict dash scan, `python3 scripts/check_serving_ids.py --selftest
&& python3 scripts/check_serving_ids.py`, and the two frozen-instrument guards when the round
touches `evaluation/frozen/` (it should not).

## Child DOX Index

| Path | Scope | File |
|------|-------|------|
| `explore/2026-11-21-r78-cross-ask/` | Round 78, cross-ask family: the #166 `tail_copy_downgrade` trigger fix instrument, exploratory (moved from `research/nightly-2026-11-21-0200` by owner objective, 2026-11-21) | - |
| `explore/2026-11-21-r79-cross-ask/` | Round 79, cross-ask family: #139/#94/#145 trigger fixes, exploratory (moved from `research/nightly-2026-11-21-0400` by owner objective, 2026-11-21) | - |
