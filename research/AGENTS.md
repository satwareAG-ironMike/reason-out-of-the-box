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
- Sanitized by construction, public-only rule: no hostname, IP, endpoint URL, credential,
  device name, or model file path in any file, including model output text; scripts strip
  them before writing. Refer to a serving model by public name only. Scripts read
  `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`, `NIGHTLY_API_KEY` from the environment and never
  write them anywhere.
- Caps from the round protocol are contractual, not advisory: at most 40 prompts,
  `max_tokens <= 2048`, free scholarly APIs only, no metered or hosted providers.
- Evidence label per `docs/agent-execution.md`: a nightly run is `Executed` unless an
  independent second implementation reproduces it (`Reproduced`) or the pre-registered
  decision table covers it (`Validated`). Small n per level is exploratory and must say so.
- A round directory is append-only after its PR opens; a later round opens a new directory.
- Unattributed artifacts (left by a killed firing, no round directory) must not be swept in
  by `git add -A`; they get provenance or deletion as an owner decision.

## Verification

- `python3 research/<round>/<script>.py --selftest` on the round branch
- artifact scan: `git grep -n -E "https?://|([0-9]{1,3}\.){3}[0-9]{1,3}" -- research/<round>`
  returns nothing but allowed public reference links (arXiv, DOI, the repository itself)
- repo parity: `scripts/check_archive.py`, `scripts/check_links.py`, strict dash scan,
  CHANGELOG entry

## Child DOX Index

| Path | Scope | File |
|------|-------|------|
| - | nightly round artifact directories, none durable yet | - |
