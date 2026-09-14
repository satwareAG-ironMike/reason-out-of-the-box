# IRB protocol draft: human baseline for procedural-novelty task families (issue #7)

Status: draft 2026-09-14, issue #7, M1 work package. M4 data collection (issue #13) consumes
this protocol. This document is the in-repo source of the human-subject layer of the two-
layer pre-registration (issue #11); it freezes together with [version-lock-manifest.md](version-lock-manifest.md)
at the timestamp when a submission path exists.

## Purpose and scope statement

The study tests whether base LLMs match trained humans without task training (study-design
v0.4 Condition 2; red-team item 5 scope statement). The human baseline anchors T1
(non-inferiority vs human accuracy) and HUM(f) per family ([analysis-plan.md](analysis-plan.md)
Sections 2 and 10). The biological no-training claim is a separate question and is out of
scope for this protocol.

## Design

| Element | Specification |
|---------|---------------|
| Task families | Digit matrices (Webb-style Raven analogues), compositional ladders (k-hop), ARC-style grid transforms - study-design v0.4 Condition 2 table |
| Items per participant per family | 60 (analysis-plan Section 10) |
| Participants per family | N >= 40 (Webb et al. standard); target N = 45 per family to absorb exclusion rate, total up to ~135 recruited |
| Inference unit | Participant; per-participant accuracy over the 60 items, aggregated to family grand mean |
| Allocation | Random assignment of participants to family condition; within-participant item order randomized from the solvability-checked pool per participant |
| Presentation | Web-based task UI rendering the generated items; no personal identifiers collected by the UI |

## Sample size and precision target

- N >= 40 per family reproduces the Webb et al. Nature Human Behaviour baseline scale.
- Per-participant accuracy is a proportion over 60 items; family grand mean and SD reported
  with Wilson 95% CI (analysis-plan Section 10).
- Precision target: Wilson CI half-width <= +/-8 percentage points on HUM(f) at the design
  assumptions; T1 is CI-based non-inferiority against a pre-registered margin of one SD of
  the participant distribution (analysis-plan Section 3), not an effect-size threshold.
- The precision target and margin are re-derived from pilot data before M4 freeze and fixed
  in this document; changes before M4 follow the amendment path.

## Population and eligibility

| Criterion | Rule |
|-----------|------|
| Population | Trained adults (undergraduates explicitly acceptable per red-team item 5) |
| Inclusion | Age >= 18; fluent in English (task instructions); normal or corrected-to-normal vision |
| Exclusion | Prior exposure to this study's generated item pools; self-reported inability to complete a session |
| Rationale | Scope is base LLMs vs trained humans without task training - years of schooling are accepted and made explicit in reporting |

## Recruitment and compensation

- Recruitment source: university participant pools where available; otherwise public online
  recruitment (Prolific-class platforms under institutional review if a partner institution
  provides one) - recruitment channel recorded with dates in the data-quality log.
- Compensation: fixed per completed session, stated in advance in the consent form; rate set
  to at least local minimum-wage equivalent for estimated session length; partial payment
  for incomplete sessions prorated if attention checks were passed up to that point.
- No deception: participants are told they are completing reasoning puzzles for a study on
  human versus AI performance.

## Consent

- Written informed consent obtained before any task item is shown: purpose, procedure,
  estimated duration, compensation, data handling, right to withdraw with no penalty,
  contact for questions.
- Withdrawal: participant may withdraw at any time; data collected up to withdrawal is
  excluded unless separate consent for partial use is obtained.

## Data handling and privacy

- Participant records carry only an anonymous participant ID assigned by the collection
  platform; no name, email, IP or device identifiers are stored with responses.
- Raw responses are archived outside this repository in anonymized form (public-only rule:
  this repository holds no personal data - AGENTS.md).
- Only family-level aggregate statistics enter this repository or any publication.
- Access: anonymized response archive is retained for re-scoring and audit; deletion on
  request within applicable retention windows.

## Scoring and quality gates

| Step | Rule |
|------|------|
| Primary scoring | Programmatic exact match against generated answer keys; no human judgment enters model scoring (analysis-plan Section 10) |
| Judgment re-score | Second rater re-scores a pre-registered random 10% subset wherever free-form judgment is required; target Cohen's kappa >= 0.8, reported |
| Attention checks | Pre-registered attention-check items interspersed; failures recorded with counts in the data-quality log |
| Exclusions | Pre-registered only: attention-check failures and incomplete sessions, with counts and reasons; NO post-hoc participant drops |

## Stopping rule

Pre-registered stopping rule: recruitment for a family stops when either (a) >= N completed,
passing sessions are collected, or (b) an interim check after N/2 shows attention-failure
rate > 25%, triggering a review of item clarity before continuing. Triggered stoppages are
documented with date and reason in the data-quality log and reported in M4.

## IRB path decision

The execution environment is an independent research POC without a host institution and has
no IRB submission path as of the decision date.

Decision (2026-09-14): proceed with a two-track approach -

1. **Documented alternative**: rely on published human baselines where they already exist for
   comparable material (Webb et al., Nature Human Behaviour 2023 digit matrices) as a sanity
   anchor, and run the dedicated M4 collection under institutional review only if a partner
   institution becomes available before M4.
2. **Protocol readiness**: this document plus the consent form and task instructions remain
   submission-ready so that any institutional IRB path can accept them without redesign.

This decision is recorded on issue #7 and will be revisited at M4 kickoff (issue #13); if an
IRB path materializes, submission happens before any data collection.

## Relationship to the pre-registration

- Human-layer registration content lives here; computational-layer content lives in
  [preregistration.md](preregistration.md) and [version-lock-manifest.md](version-lock-manifest.md).
- Analysis of human data follows [analysis-plan.md](analysis-plan.md) Section 10 exactly;
  deviations are numbered addenda reported as exploratory.

## References

- [study-design.md](study-design.md) v0.4: Condition 2, Red-team items 5 and 7
- [analysis-plan.md](analysis-plan.md): Sections 2, 3, 10
- [preregistration.md](preregistration.md): two-layer registration mapping
