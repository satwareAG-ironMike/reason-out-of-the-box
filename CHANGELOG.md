# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### 2026-09-03

#### Added

- Paper archive `archive/` with 63 entries in 8 thematic rounds:
  - round 1 base-model emergence (6), round 2 skeptical (6), round 3 theory and
    faithfulness (7), round 4 mechanistic and recent (7), round 5 thinking and validation
    (7), round 6 unique idea generation (7), round 7 embodied agents and tools (11),
    round 8 do LLMs think (12)
  - `archive/INDEX.md`: verdict, catalog with peer-review status, `[FT]` full-text
    verification markers (25 of 63), verdict addenda, biological-analogy assessment,
    5-condition open-problem spec
- `docs/acceptance-criteria.md`: the three criteria the project is judged against
  (peer-reviewed, no reasoning-example training, disclosed training data) and a
  transparency audit of all positive evidence
- `docs/study-design.md` v0.2: pre-registrable protocol on open-data models, red-teamed
- `docs/claims-hinton-lemoine.md`: dated claim ledger for "AI thinks" and the LaMDA
  sentience episode, judged against 2026 evidence
- `scripts/check_archive.py`: archive consistency checker with `--selftest` negative
  control and `--report` metrics
- `GATES.md`: acceptance ledger (6 of 7 gates met; executing the study abandoned as
  requiring a lab)
- DOX documentation hierarchy (`AGENTS.md`, `archive/AGENTS.md`)

#### Changed

- Four archive claims corrected after full-text verification: Voyager speedups, Turpin
  accuracy drop, Embers task counts, ARC-AGI-2 human baseline attribution; one 2026
  preprint verdict corrected (reasoning models diverge, non-reasoning models collapse)

#### Removed

- All non-public material (local experiment artifacts, session state, discussion
  transcripts); repository history rebuilt from the clean tree. Only public resources
  (papers, open repositories) remain
