# archive

## Purpose

Durable archive of the papers behind the project verdict: 78 entries in 9 thematic rounds
(base-model emergence, skeptical, theory and faithfulness, mechanistic and recent, thinking
and validation, unique idea generation, embodied agents and tools, do LLMs think,
reasoning traces and 2026 updates). The
verdict, evidence matrix, and the 5-condition open-problem spec live in
[INDEX.md](INDEX.md).

## Ownership

- Owned by the root AGENTS.md; this file governs only the `archive/` subtree
- New paper rounds require: one directory `round<N>-<slug>/`, one `INDEX.md` catalog row
  per paper, and a CHANGELOG entry

## Local Contracts

- Every paper file is named `<arxiv-id>-<first-author>-<slug>.md` and must contain:
  arXiv ID link, authors, venue, peer-review status, year, archive round, condensed
  abstract, key findings, relevance to the core question, citation
- Peer-review status must be explicit: NeurIPS/ICLR/ICML/COLM/Nature/Nature Human
  Behaviour count as peer-reviewed; arXiv-only entries are flagged `preprint`
- Quotes in entries must come from the paper itself (`firecrawl research read-paper` or
  direct full text). Entries with such verification are marked `[FT]` in INDEX.md
- INDEX.md verdict symbols: `+` supports out-of-the-box reasoning, `-` opposes,
  `+/-` mixed or balanced

## Work Guidance

- Do not paraphrase quantitative results; carry exact numbers and significance levels
- Keep verdicts separable from findings: state what a paper proves, then what it fails to
  prove
- When adding a paper that changes the overall verdict, update the Verdict section in
  INDEX.md and the README verdict line in the same change

## Verification

- `python3 scripts/check_archive.py` must print `archive check passed` before closeout:
  filename id matches body link, required fields and sections present, no placeholder
  authors, no em/en dashes, per-round INDEX row count equals entry count, INDEX `[FT]`
  rows equal entries with "verified from full text"
- `python3 scripts/check_archive.py --selftest` is the negative control (synthetic broken
  archive must fail); `--report` prints metrics (`ft_verified: N/total`)
- Acceptance ledger for quality campaigns: `GATES.md` (gate-ledger format of the public Leonxlnx/unlazy project), run with
  `gate-check.mjs --approve`

## Child DOX Index

No child AGENTS.md files. Rounds are flat directories of paper entries governed by this file.
