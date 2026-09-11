# Pre-registration (issue #11): OSF computational layer + AsPredicted timestamp

Status: draft 2026-09-11, issue #11, M1 work package. NOT yet submitted; the external steps
are owner-gated (Submission checklist below). This document is the in-repo source of the
registration content; it freezes together with the [version-lock manifest](version-lock-manifest.md)
at the timestamp. Sources: [study-design.md](study-design.md) v0.4,
[analysis-plan.md](analysis-plan.md) (v1.0-candidate),
[next-investigations.md](next-investigations.md) (feasibility audit, closed 2026-09-10).

## Two layers (issue #11 scope)

| Layer | Registration | State |
|-------|--------------|-------|
| Computational | OSF registration; AsPredicted timestamp as the public verification URL | Content assembled (this document); submission pending |
| Human subject | Registration aligned with the IRB protocol, or documented alternative | Tracked in #7 |

## Registered content (computational layer)

The registration freezes the following repository artifacts:

| Item | Source | Frozen form |
|------|--------|-------------|
| Study design v0.4: decision table, Conditions 1-5, red-team items 1-7, Amendments v0.4 | `docs/study-design.md` | document SHA-256 in the manifest |
| Frozen model list + corpus mapping (7 confirmatory checkpoints, replication family, second candidate) | `docs/next-investigations.md`, feasibility audit closed 2026-09-10 | snapshot extracted at freeze, then hashed (manifest Section 1) |
| Statistical analysis plan: T1-T9 battery (Section 4), definitions and margins (Section 3), decision table (Section 6), scale trend (Section 7), patching primary + grid (Section 8), faithfulness split (Section 9), human statistics (Section 10), confirmatory/exploratory split (Section 11), amendment path (Section 13) | `docs/analysis-plan.md` | document SHA-256 in the manifest |
| Task item selection: generated families, domain hold-out requirement, human-solvability checks | study design + #4 generators | generator code, seeds, and item-set hashes at freeze |
| Decoding and seed policy: arms A/B/secondary, fixed decoding policy, bootstrap seed | #5 harness + analysis plan | configuration and seed hashes in the manifest |
| Version lock | `docs/version-lock-manifest.md` | committed as-is at the freeze commit |

## AsPredicted mapping

The AsPredicted submission maps the registered content to the form areas:

| Form area | Content from |
|-----------|--------------|
| Hypotheses | analysis-plan Section 5 (H1, H0-a, H0-b, mixed) |
| Design and arms | study design Conditions 1-3; arms A (greedy), B (CoT-decoding), secondary verbal-trigger |
| Primary outcomes | analysis-plan Section 2 (ACC, d*, HUM, SD_H) |
| Analyses | analysis-plan Sections 4 and 6 (T1-T9, deterministic decision table) |
| Exclusions and stopping | analysis-plan Section 10 (pre-registered exclusions only; pre-registered stopping rule) |
| Units and sample sizes | analysis-plan Sections 1 and 7 (units of analysis, n per cell) |

## Deviation policy

- Before the timestamp: changes arrive by PR with a CHANGELOG entry; the analysis-plan draft
  version increments (Section 13).
- After the timestamp: the registered versions are immutable. Amendments are numbered
  addenda with date, reason, and exact scope; any analysis they touch is reported as
  EXPLORATORY, never confirmatory; the deviation log lives in #14.
- Immutable post-timestamp elements (analysis-plan Section 13): decision-table evaluation
  order, confirmatory/exploratory membership, T1 margin, retention threshold, primary
  patching specification, study-level asymmetry rule.
- Original retained: the OSF registration keeps the registered versions, the repository
  history keeps the registered text, and the manifest keeps the frozen hashes.

## Submission record (owner-gated, filled at submission)

| Field | Value |
|-------|-------|
| OSF registration URL | TBD |
| AsPredicted timestamp URL | TBD |
| Freeze date | TBD |
| Manifest hashes re-captured | TBD (immediately before submission) |

## Submission checklist

- [ ] Re-capture every hash in the version-lock manifest immediately before submission
- [ ] Create the OSF registration (public); record the URL in the table above
- [ ] Submit AsPredicted; record the timestamp URL in the table above
- [ ] Record the human-layer decision (IRB path or documented alternative) in #7
- [ ] Record the freeze date; then #10 closes (its acceptance requires the timestamp) and
      #11 closes when the URLs are recorded
