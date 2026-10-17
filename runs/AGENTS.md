# runs

## Purpose

Executed-run record: run manifests, raw per-prompt model responses, calibration
records, and the round report. This is the in-repo audit trail that
[agent-execution.md](../docs/agent-execution.md) section 6 requires; raw output
lives here only while it is small enough to review by hand, otherwise it is
external and hash-pinned from here.

## Ownership

Agent-maintained. One directory per run id, written by the instrument that ran the
experiment, never hand-edited afterwards. Reports are written by the round agent
and verified by a different agent configuration.

## Local Contracts

- One directory per run id, named `nightly-YYYY-MM-DD-HHMM`. A directory is
  complete when it holds the manifest, the raw per-prompt records, the calibration
  record when the instrument used one, and `report.md`.
- Manifests are immutable once written. A field the instrument could not read from
  the endpoint (weights hash, serving revision) is recorded as `null` with a note,
  never invented. Anything established later goes in a named sidecar and is
  declared in `report.md` as a dated deviation.
- Sidecars are allowed in the run directory and are the only way to add material
  after a run: an analysis script that regenerates the report numbers, a battery or
  audit script established after the run, pinned copies of gate reports the report
  cites, and an attempts record for a run that needed more than one invocation.
  A sidecar never edits the manifest or the raw records, and a sidecar that
  supersedes an ad-hoc number makes the earlier number uncitable.
- Raw records: one JSON object per prompt, sorted keys, carrying prompt sha256,
  item seed and seed hash, gold label, parsed answer plus parse method, finish
  reason, token counts, latency, and the process indicator. Nothing is dropped:
  truncated, invalid, and unparseable responses are recorded as what they are.
- Public-only rule: no endpoint host, port, path, IP, device name, or model file
  path in any artifact. Model identity is the public label plus the provider model
  id. Item seeds and prompt hashes are public.
- Budget discipline: the experimental prompt budget is fixed in the instrument
  before any endpoint call. Calibration and instrument-validation calls are
  reported separately and never counted as experimental data. Any deviation from
  the planned budget is dated in the report.
- Labels are never collapsed (agent-execution section 5): *Executed* (the run
  completed), *Reproduced* (an independent rerun regenerates the numbers within a
  pre-declared tolerance), *Validated* (independent evidence supports the reading).
- Every number in a report is regenerable from the artifacts in the same directory
  by the named script. A number with no generating script does not enter the report.

## Work Guidance

- Report shape: question, design fixed in advance, what actually ran, results,
  verdict under the pre-registered rule, limits, next step.
- State the verifier-independence limit honestly when the verifier ran on the same
  model family as the run.
- Negative controls are part of the deliverable: a run that cannot show its
  instrument detects the failure it claims to detect has no result to report.

## Verification

- manifest `artifact_hashes` equal `sha256sum` of the files in the directory
- report numbers equal the manifest fields they cite, and equal the output of the
  run directory's own regeneration script
- regeneration scripts carry a seeded-defect selftest and a `--check` mode that
  re-derives the report numbers from the archived artifacts and exits 3 on any
  mismatch
- repo parity: `scripts/check_links.py`, dash scan, CHANGELOG entry

## Child DOX Index

| Path | Scope | File |
|------|-------|------|
| `runs/nightly-2026-10-16-0200/` | matched-pair ladder shortcut probe (issue #67): manifest, raw responses, calibration record, attempts and environment sidecars, pinned gate reports, regeneration scripts, round report | [report.md](nightly-2026-10-16-0200/report.md) |
