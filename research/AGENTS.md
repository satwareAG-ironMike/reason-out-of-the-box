# research/

## Purpose

Working record of the nightly consciousness-research rounds (tracker issue #65): one
directory per round holding that round's script, its machine-readable report, and its
README. Consolidated durable findings live in `docs/`, not here.

## Ownership

- Each `nightly-*` directory belongs to the round that created it and is not edited after
  the round except to correct an error, in which case the correction is dated in the README.
- Root `AGENTS.md` owns the round protocol (timer, dedup, branch plus PR, no merge) and the
  public-only rule. This file owns the layout and quality bar of a round directory.

## Local Contracts

- Directory name: `nightly-YYYY-MM-DD-HHMM`, matching the timer slot it ran in.
- Every round directory carries `README.md` with: question, method, results, findings,
  limits, reproduce.
- Round scripts are stdlib-only, deterministic, and import nothing from `generators/`: a
  round's measurement must be an independent verifier of the corpus, not a re-run of the
  generator that produced it (`docs/agent-execution.md`, verifier independence).
- Every round script ships `--selftest` with negative controls (planted leak, planted
  negative, synthetic branching, seed determinism, and a check against the corpus it
  measures). Numbers are reported only after the controls pass.
- Every report pins the sha256 of each corpus file it measures.
- State the label honestly: Executed, Reproduced, or Validated. A round with no model arm
  claims neither Reproduced nor Validated.
- No hostname, IP, device name, model-file path, credential, or session state in any file
  or in history (public-only rule). Endpoint behaviour may be described in timings only.
- A published error is corrected by a dated correction, in the tracker comment and in the
  README. Do not silently rewrite a posted number.
- Findings that become durable move to `docs/next-investigations.md` and cite the round
  directory they came from.

## Verification

- `python3 <round script> --selftest` passes before any number is reported.
- Root CI parity before pushing: `scripts/check_archive.py`, `scripts/check_links.py`, and
  the dash scan, per root `AGENTS.md`.

## Child DOX Index

| Path | Scope | File |
|------|-------|------|
| - | no durable sub-boundary yet | - |
