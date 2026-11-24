# research

## Purpose

Per-round artifacts of the nightly consciousness research rounds (tracker issue #65): the
exact script, prompts, raw model responses and scores behind each round's summary comment,
so any round can be re-run and audited instead of being taken on trust.

## Ownership

The nightly agent that ran the round writes its own round directory and its PR. The
maintainer owns deletion or relocation. Durable conclusions do not stay here: they move to
`docs/` (ledgers, study design), `archive/` (papers), `CHANGELOG.md`, or an issue.

## Local Contracts

- One directory per firing, named `nightly-YYYY-MM-DD-HHMM` in the firing timezone, matching
  the round branch `research/nightly-YYYY-MM-DD-HHMM`. Never reuse a directory.
- Contents of a round that ran an experiment: `README.md` (question, method, selection rule,
  how to reproduce, results), the script (stdlib-only, `--selftest` with arithmetic and
  negative controls, house style), `raw.jsonl` (one record per prompt: prompt, raw response,
  score), `summary.json` (aggregates), `run.log` stays local (it can carry endpoint noise).
  A round whose dispatch plan was selected by a frozen pre-dispatch rate measurement
  (standing round-61 rule, from round 63) also keeps that measurement record
  (`measure.json`, pre-gate census and calibration calls plus the plan selection) in the
  directory; the frozen gate's dispatch block carries the same data as its input.
- Sanitized by construction, public-only rule: no hostname, IP, endpoint URL, credential,
  device name, or model file path in any file, including model output text; scripts strip
  them before writing. Refer to a serving model by public name only. Scripts read
  `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`, `NIGHTLY_API_KEY` from the environment and never
  write them anywhere.
- Model-resolution precondition (issue #211, fail-loud at dispatch): before any prompt is
  sent, the configured model column MUST resolve against the live registry of the slot's
  serving endpoint (one trivial-prompt probe, or the registry's model list when it exposes
  one). If it does not - `Model unavailable`, stale column, empty identity (issue #200) -
  the round writes its record and stops; a round that dispatches on a model the registry no
  longer serves poisons every downstream score and hour. A frozen gate whose `model_digest`
  pins the predecessor firing's build is refused by construction on a rotating pool
  (issue #200): re-measure on the live build and re-freeze, never carry the stale digest.
- Caps from the round protocol are contractual, not advisory: at most 40 prompts,
  `max_tokens <= 2048`, free scholarly APIs only, no metered or hosted providers.
- Panel selection premise check (issue #126): before re-freezing a cap-bound panel, the lane
  re-verifies the panel's selection premise on the current builds - on 2026-11-24 the
  2048-token truncation wall had collapsed to zero on both classes, which voids the cap-bound
  selection premise of the archived panel. A panel frozen on a premise the current build no
  longer satisfies is spend, not signal: the re-freeze MUST cite the re-verified premise in
  the round README and the frozen gate's dispatch block.
- Weekly compute cap (issue #195): the nightly rounds above are capped at 2 firings a week x
  40 prompts x `max_tokens <= 2048` = at most 80 dispatched prompts a week, and the exploratory
  loop in `explore/` (issue #195) adds at most 400 dispatched prompts a week (10 rounds at the
  40-prompt cap). The cap is a kill rule for the loop, not a target; when it is spent the loop
  stops and reports, and the next week starts a fresh count. The cap does not apply to owner
  actions (PROMOTE runs, confirmatory runs on the OLMo 2 / Pythia pins), which are not part of the
  loop. A local self-hosted endpoint is the only serving path the cap assumes; no metered or
  hosted provider key is ever used under this cap.
- Evidence label per `docs/agent-execution.md`: a nightly run is `Executed` unless an
  independent second implementation reproduces it (`Reproduced`) or the pre-registered
  decision table covers it (`Validated`). Small n per level is exploratory and must say so.
- Identity contract (issue #73, R82 review): a dispatch lane names every model cell with the
  registry's exact key - the pinned name verbatim, never a composite label like
  `alias (pin NAME)`. A scorer that matches no registry key must record the mismatch in the
  gate record instead of silently down-classifying the run; the README and gate cause text
  cite the cause recorded on the pin record, never boilerplate for a different known cause
  (frozen rule addendum 1, issue #207 review F3).
- Reasoning tooling: advanced reasoning on agent execution - decomposing a round's design,
  planning multi-firing experiments, resolving cross-issue dependencies - runs through the
  `sequential-thinking` MCP tool. Its step graph is the durable record: one thought per
  node, links between nodes, so a later lane resumes or audits the chain instead of
  re-deriving it. Simple single-step work stays inline; the tool is for the multi-step case.
- A round directory is append-only after its PR opens; a later round opens a new directory.
- Same-firing resume: immutability of `raw.jsonl`, `summary.json` and `gate.json` binds from the
  moment the round's PR opens. A resume inside the same firing may rebuild `summary.json` and
  re-emit `gate.json` only if `raw.jsonl` and the gate blob are byte-unchanged by the rebuild, the
  instrument change is disclosed in the README, and any column added after the dispatch carries a
  `registered: false` marker and a planted-slip selftest control. No registered row or tier may move
  in a resume.
- Errata carve-out (issue #120): forward-only errata may annotate a merged round's
  `README.md` prose and the matching CHANGELOG entry, and may edit instrument docstrings
  (comment-only, no code change); `raw.jsonl`, `summary.json` and `gate.json` stay
  immutable in all cases.
- Trace-exposure census (issue #105): from round 40 onward every round's `raw.jsonl` carries the
  field census (per-record message field names plus the reasoning-supplying field, merge rule
  `reasoning_content` if non-empty, else `reasoning`, else empty). Cross-class and cross-firing
  trace claims must state the exposure setting of each side; a claim against a zero-trace
  deployment is an answer-level claim only. A class-level trace statement for a class needs at
  least one same-class pair with the channel exposed on both sides.
- Unattributed artifacts (left by a killed firing, no round directory) must not be swept in
  by `git add -A`; they get provenance or deletion as an owner decision.
- Row-and-blob guard (issue #137), round-side until the repo-level checker lands: a round script may
  expose `--check-readme`, which fails that round's own `README.md` when it quotes a gate-row id the
  frozen `gate.json` does not define (criterion ids, the health id, and an item shorthand that
  prefixes a cell label are defined; a cell label like `L48_j40` is not a row id), when its pinned
  blob differs from the compact sorted-key sha256 of `gate.json` with its own `blob` field removed,
  when any `raw.jsonl` record carries a different blob, or when it cites a 64 hex blob that is
  neither this gate's nor a certified archive's.

## Verification

- `python3 research/<round>/<script>.py --selftest` on the round branch
- `python3 research/<round>/<script>.py --check-readme` where the round ships the issue #137 guard
- artifact scan: `git grep -n -E "https?://|([0-9]{1,3}\.){3}[0-9]{1,3}" -- research/<round>`
  returns nothing but allowed public reference links (arXiv, DOI, the repository itself) and the
  sanitizer fixtures a `--selftest` needs (RFC 5737 documentation addresses, `.invalid` domains,
  dummy paths); a real endpoint, host or address never appears
- repo parity: `scripts/check_archive.py`, `scripts/check_links.py`, strict dash scan,
  CHANGELOG entry

## Child DOX Index

| Path | Scope | File |
|------|-------|------|
| - | nightly round artifact directories, none durable yet | - |
