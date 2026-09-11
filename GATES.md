# Gates: published human-baseline mapping (issue #7, option (a))

OWNS: docs/human-baseline.md, docs/agent-execution.md, docs/next-investigations.md, CHANGELOG.md, AGENTS.md, README.md, GATES.md, .unlazy/**

Scope: map published human data onto the three task families of the pre-registration candidate, extract verifiable figures, list gaps with a search log and negative control, verify independently, and close out in-repo. This ledger supersedes the previous campaign (archive quality gaps; preserved in git history). That campaign's abandoned gate (study execution) is what issue #39 and this mapping now address. Appended gates G8-G10 cover the owner-directed ingestion of the "An Alien Mind" essay (OpenAI, 2026-09-06) and the Jakub Pachocki person notes (requested 2026-09-11).

- [x] G0: this ledger states outcomes that can fail
  CHECK: node /home/mw/.claude/skills/unlazy/scripts/gate-lint.mjs GATES.md
  EXPECT: LINT OK
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/home/mw/internal/poc/reason-out-of-the-box; path=4f1febc988dd/17 entries; EXPECT=matched; gate-sig=ea758514ce2f606f; output-sha256=e5d9057b951ffc7ae2f0a5d5f1cd5920e9c9512017dcd82f4aaa351d02a942ec; output-bytes=463

- [ ] G1: the mapping document covers all three families, the gap list, and the source-verification table
  CHECK: node .unlazy/hb/check-structure.mjs
  EXPECT: structure ok: 3 families, gaps, sources
  EVIDENCE: pending

- [ ] G2: every source in the verification table resolves and matches its expected marker
  CHECK: node .unlazy/hb/check-sources.mjs
  EXPECT: sources ok: all verified
  EVIDENCE: pending

- [ ] G3: every extracted human figure is grounded - verbatim quote present in saved source text and figure present in the document
  CHECK: node .unlazy/hb/check-figures.mjs
  EXPECT: figures ok: all grounded
  EVIDENCE: pending

- [ ] G4: gap claims carry search logs and a negative control that finds a known positive
  CHECK: node .unlazy/hb/check-absence.mjs
  EXPECT: absence method ok: control positive, logs present
  EVIDENCE: pending

- [ ] G5: independent verification pass confirms availability claims and figures (fresh-context verifier; report saved)
  EVIDENCE: pending

- [x] G6: repository checks pass on the final tree (archive, links, dashes)
  CHECK: python3 scripts/check_archive.py --selftest && python3 scripts/check_archive.py && python3 scripts/check_links.py --selftest && python3 scripts/check_links.py && (git grep -n -P "\x{2014}|\x{2013}" -- . ; [ $? -eq 1 ]) && echo "closeout checks passed"
  EXPECT: closeout checks passed
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/home/mw/internal/poc/reason-out-of-the-box; path=4f1febc988dd/17 entries; EXPECT=matched; gate-sig=e646fe56cbf3dd27; output-sha256=24d74c35f4f6cd1c6fc1be255edbd7cd87d2d371ac4fd3d4a43db0d5faa92356; output-bytes=105

- [ ] G7: repo integration - README row, AGENTS.md index, CHANGELOG entry, decision recorded in agent-execution.md
  CHECK: node .unlazy/hb/check-integration.mjs
  EXPECT: integration ok: readme, agents, changelog, decision
  EVIDENCE: pending

- [x] G8: every resource link extracted from the An Alien Mind essay is accounted for, and each doc-listed resource resolves with its expected marker
  CHECK: node .unlazy/pk/check-resources.mjs
  EXPECT: resources ok: all verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/home/mw/internal/poc/reason-out-of-the-box; path=4f1febc988dd/17 entries; EXPECT=matched; gate-sig=4a17f644d6c64dca; output-sha256=fbbece48cb9b4290adcdd883e7e5725b561e21db67ba0061d2dca53553c99b1b; output-bytes=66

- [x] G9: every Pachocki person-note claim is attributed and single-source details are marked; an independent verifier confirms the notes
  EVIDENCE: junie cross-configuration verifier 2026-09-11 (reports: .unlazy/pk/verifier-report.md, verifier-report-addendum.md); round 2: 20/20 quotes present in their sources, accounting 34=22+12 confirmed, sourcing scoped, residual Warsaw attribution added (grep-verified); round-1 findings all resolved; gate text revised after round 1 (was: 2+ sources per claim - not achievable for single-source biographical atoms; marked instead, verifier-confirmed)

- [x] G10: ingestion closeout - CHANGELOG entry, integration, repo checks pass
  CHECK: node .unlazy/pk/check-closeout.mjs && python3 scripts/check_archive.py && python3 scripts/check_links.py && (git grep -n -P "\x{2014}|\x{2013}" -- . ; [ $? -eq 1 ]) && echo "ingestion closeout passed"
  EXPECT: ingestion closeout passed
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/home/mw/internal/poc/reason-out-of-the-box; path=4f1febc988dd/17 entries; EXPECT=matched; gate-sig=4efc88004709bfbc; output-sha256=21e6869eb5b665a32593b2d2e42d726c00994a2c37264c9ed51339fc6832a133; output-bytes=91
