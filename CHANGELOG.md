# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### 2026-09-04

#### Added

- `docs/claims-marcus-wall.md`: claim ledger for Marcus's "Deep Learning Is Hitting a
  Wall" (Nautilus, 2022-03-10), judged against evidence through 2026; full-text ingest
  of the essay plus two 2025 author retrospectives; archive-worthiness assessment of 8
  papers surfaced by the essay and its verification trail (no verdict-relevant paper
  missed; 2304.15004 and the Nature 2024 AlphaGeometry paper flagged as round 9
  candidates only)
- GitHub Actions CI (`.github/workflows/ci.yml`) running on push and PR with three
  read-only jobs: archive consistency and provenance (`check_archive.py --selftest`,
  metrics report, consistency), markdown hygiene (repo-wide em/en dash check plus new
  `scripts/check_links.py` relative-link checker with selftest), and a full-history
  gitleaks 8.30.1 secret scan (checksum-pinned binary, redacted output). Single action
  pinned by SHA; no third-party actions

### 2026-09-03 (second entry, SOD)

#### Added

- `docs/next-investigations.md`: 2026-09-03 online re-scan (arXiv API + Hugging Face
  API verified). Findings: the strict claim is still unmet (no peer-reviewed
  open-data base-model study on procedurally novel tasks); ARC-AGI-2 verified scores
  (92.5% GPT-5.6 Sol, 90.4% Claude Opus 5, ARC-Prize verified semi-private); reusable
  task-generator infrastructure (2404.07353, ARC-GEN 2511.00162); corpus audit tooling
  (WIMBD 2310.20707); OLMo 2 public base confirmed at 7B/13B only (no 32B in the
  release); two-layer pre-registration practice (OSF + AsPredicted). Ranked
  investigation fields and the thesis timeline M1-M5.
- GitHub thesis board: milestones M1 protocol freeze + pre-registration (2026-09-30),
  M2 pilot (2026-10-31), M3 main experiment (2026-12-31), M4 human baseline + analysis
  (2027-02-28), M5 paper + public release (2027-04-30); 14 work-package issues
  (#1-#14, incl. M4 human data collection and decision-table analysis) with labels
  thesis/research/infra/data/experiment/analysis/publication. All milestone descriptions
  carry the student application line (bewerbung@satware.com or
  https://github.com/satwareAG-ironMike); harness gap on the gh milestone failure chain
  filed as git.satware.ai issue #628

#### Changed

- `docs/study-design.md` to v0.3: model list corrected after release verification
  (OLMo 2 7B/13B + Pythia 1B/2.8B/6.9B/12B; OLMo 3 32B conditional pending official
  repo verification), DCLM replication arm re-targeted to OLMo 3/Dolma 3 or Apertus 1.5
- `README.md`: status now points at the thesis program and the issue board; layout
  lists `docs/next-investigations.md`
- Root `AGENTS.md` Child DOX Index: docs/ scope lists next investigations + thesis timeline

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

#### Changed

- Published to github.com/satwareAG-ironMike/reason-out-of-the-box (public,
  `main` branch-protected, issues enabled)

#### Removed

- All non-public material (local experiment artifacts, session state, discussion
  transcripts); repository history rebuilt from the clean tree. Only public resources
  (papers, open repositories) remain
