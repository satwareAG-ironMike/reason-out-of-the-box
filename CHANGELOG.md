# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### 2026-09-11

#### Added

- docs/next-investigations.md: Research findings (2026-09-11), a one-day delta scan.
  Six new arXiv API-verified papers, among them 2609.10357 (temporal hold-outs do not
  remove domain familiarity - the contamination audit must domain-hold-out generated
  items) and 2609.09696 (LLM contamination auditors collapse to 2.8% recall in large
  batches - no LLM-as-batch-auditor in the pipeline); the Anthropic September 2026
  threat report (industrial-scale CoT distillation, a reverse contamination vector);
  2026-09-10 open-weight releases (DeepSeek-V4.1-Flash, MiniCPM5, Smaug - all fail
  criterion 3); "The Superdark Factory" (Antikythera Journal, Agentworld Special Issue,
  September 2026) recorded as a non-archive resource with an opacity/evaluation/
  governance relevance analysis; three outside-window leads for round 11. Verdict,
  study design v0.4, and the frozen model list unchanged (#32)
- docs/claims-hinton-lemoine.md: Part 1 table row for the BBC Newsnight interview
  (aired 2026-09-09): extinction risk "10% seems not an unreasonable estimate",
  timeline "maybe 10 years, maybe less" - danger claims, classification unchanged;
  the stale "no distinct 2026 statement" note scoped to understanding claims; Times
  and Newsnight source entries added (#32)
- docs/next-investigations.md: primary-source fetch of two Anthropic Transformer Circuits
  articles (owner-requested). "On the Biology of a Large Language Model" (Lindsey et al.,
  27 authors, 2025-03-27): web-only, non-archive; attribution graphs, in-head multi-step
  planning, three mechanistic CoT-faithfulness regimes (faithful / bullshitting / motivated
  reasoning), base-vs-finetuned feature formation - Condition 3/4 input. "Emergent
  Introspective Awareness in Large Language Models" (Lindsey, arXiv 2601.01828,
  API-verified): archive-eligible, queued as round-11 Tier A candidate; resolves the
  ledger's "Lindsey 2026" citation; base pretrained models achieve no net introspective
  performance (post-training elicits it) - an H0-b-line elicitation asymmetry. Named
  related works (no IDs reported; dedup before round 11) and public professional person
  notes (Lindsey, Olah, Batson, Gurnee) (#32)
- docs/claims-hinton-lemoine.md: Lindsey citation resolved to arXiv 2601.01828 with the
  base-model elicitation asymmetry in the Part 1 status table; addendum 2026-09-11
  (primary-source fetch); both Transformer Circuits sources listed (#32)
- docs/analysis-plan.md (new): statistical analysis plan, pre-registration candidate for
  M1 issue #10. Decision table operationalized: 9 confirmatory tests (T1-T9) each with
  null + CI-based deterministic decision rule; pre-registered definitions (human-level
  non-inferiority margin 1 SD, 80% retention at d*+2 gated on ACC(d*) >= human mean,
  cliff at d*+1, probability invariance +-10 pp, shared iterative circuit with >50%
  specification-grid agreement per 2608.13754); deterministic per-checkpoint evaluation
  order + study-level asymmetry rule (red-team 4); scale-trend Spearman vs log(params);
  patching primary specification fixed pre-run; faithfulness: FUR parametric + filler
  confirmatory, truncation/mistake-insertion descriptive per Amendment v0.4 item 4;
  human baseline participant-unit statistics with kappa >= 0.8 rater subset; d* input
  requires domain hold-out (2609.10357) and prohibits LLM batch auditors (2609.09696);
  exhaustive confirmatory/exploratory split; amendment path (post-timestamp changes
  downgrade to exploratory; five elements immutable); frozen-document hash enters the
  #11 version-lock manifest. Refs #10 (timestamp via #11, issue stays open) (#32)
- docs/next-investigations.md: Superdark Factory deep research status update (issue #36):
  citation status re-verified (arXiv zero results, no DOI, PhilPapers 403/no entry; MIT
  Press journal association, Disintegrator project, Gray Area co-hosted launch, no
  reception yet - non-archive classification stands); full-text-derived additions
  (Stackelberg V vs U* vocabulary for the novelty criterion, citable mechanism-design
  grounding for evaluator gaming and M2 grader design, class taxonomy vs counterargument
  6, darkness vs criterion 3, pre-registration analogy); fresh same-day sweep with
  round-11 candidates 2609.09989, 2609.09038, 2609.09030 (abstracts API-verified) plus
  adjacent 2609.08186, and frontier items (Astra "An Alien Mind" essay, single-source Astra
  CoT monitor-recall collapse, OpenAI automated-research-intern report) (#36)

#### Changed

- docs/next-investigations.md, README.md: EOD-review follow-ups - status dates bumped to
  2026-09-11, feasibility-audit section retitled (closed 2026-09-10, issue #2),
  timeline-risk paragraph reduced to the two residual unknowns (32B mix naming, Apertus
  1.5 pretrain-only checkpoint), stale "pending the audit" source note rescoped (#32)

### 2026-09-10

#### Added

- docs/counterarguments.md: skeptic-facing ledger. A claim ladder C1-C5 separates "LLMs
  solve novel reasoning instances when elicited" (established, peer-reviewed), "part of it is
  an algorithm" (established at toy scale), "the competence is bounded" (established),
  "traces are not evidence" (established) from the untested C5 the headline verdict is
  about. Ten recurring counterarguments steelmanned (stochastic machine, no new ideas, "your
  repo says no evidence", babysitting, contamination, scaffold vs model, mirage, Tower of
  Hanoi collapse, animals reason untrained, marketing), each with what the record says, what
  is conceded, what stays open. New non-archive sources verified by API: FunSearch (Nature
  2024, PMID 38096900), AlphaGeometry (Nature 2024, PMID 38233616), AlphaProof (Nature 2026,
  PMID 41225005), Reasoning or Reciting (NAACL 2024, 2307.02477), The Illusion of Thinking
  (NeurIPS 2025, 2506.06941) and its comment (2506.09250), AlphaEvolve (2506.13131, preprint),
  Bender and Koller 2020 / Bender et al. 2021 (DOIs) (#28)
- README: section "What the verdict does and does not say" scoping the headline verdict to
  the base-model claim and naming the established claims with their venues (#28)
- docs/next-investigations.md: Research findings (2026-09-10), a currency scan of every
  project topic through 2026-09-10. Verdict unchanged (no qualifying paper 2026-08-01..09-10).
  24 verified round-11 candidates, among them 2609.01274 (Findings of EMNLP 2026, RLVR gains
  as sampling efficiency), 2506.14245 (CoT-Pass@K counter-position), 2608.13433 (complete
  length-generalization characterization for regular languages), 2607.23458 (step-removal
  faithfulness metric anti-correlates with human labels), 2608.13754 (circuit claims flip in
  73.2% of analytic specifications), 2607.15495 (Anthropic global-workspace framing). Anthropic
  Risk Report August 2026 (canary strings defeated by pre-canary forks) recorded as a
  contamination-audit source. Open-data releases verified on the Hub: OLMo 2 32B exists
  (`allenai/OLMo-2-0325-32B`; the 2026-09-03 check used a wrong ID), OLMo 3 7B/32B + Dolma 3
  public, Apertus 1.5 released 2026-07-24, no DCLM v2 (#26)

#### Changed

- Feasibility audit closed (issue #2, M1): docs/next-investigations.md "Open questions for
  the feasibility audit" now answers all five items with Hub API evidence dated 2026-09-10.
  OLMo 3 7B/32B + Dolma 3 released and complete at the mix level (`dolma3_mix-6T-1025-7B`,
  3.35 TB); Apertus 1.0 base ungated, 1.5 gated; DCLM arm closed; compute claim holds (one
  80 GB GPU sufficient, 8x80 GB comfortable); corpus access via public infini-gram indexes
  over the exact OLMo 2 and OLMo 3 training data plus a local mirror budget (9.1 TB OLMo 2,
  3.35 TB OLMo 3 7B, 451 GB Pile dedup; 13 TB total, 1% embedding sample otherwise). Frozen
  model list for the pre-registration: OLMo 2 7B/13B/32B, Pythia 1B/2.8B/6.9B/12B `-deduped`
  (corpus match with `the_pile_deduplicated`), OLMo 3 7B/32B replication, Apertus 1.0 base
  second candidate. Study design v0.4 model row names the `-deduped` checkpoints (#2)
- docs/study-design.md v0.4: OLMo 2 32B restored to the confirmatory model list, OLMo 3
  7B/32B as replication family, DCLM arm closed; Amendments v0.4 fix the two-layer
  contamination audit (corpus-side plus raw-completion probes), a pre-registered activation-
  patching specification grid, parametric faithfulness as the confirmatory Condition 4 metric,
  automaton classification for Condition 5, and the definition boundary excluding
  inference-time architectural interventions (#26)
- docs/next-investigations.md: ARC section carries the 2026-09-03 GPT-6 Astra verified
  results (ARC-AGI-2 95.0%, ARC-AGI-3 62.7% vs 99.9% by harness) and answers open question 3;
  investigation-fields table and timeline risk updated (#26)
- docs/claims-hinton-lemoine.md and docs/claims-marcus-wall.md: 2026-09-10 addenda (Coxon
  thread confirmations, Hinton in The Times 2026-09-07, Astra harness gap against Marcus
  claims 1 and 4); no verdict change (#26)

- Root AGENTS.md project notes: direct pushes to `main` are rejected by the
  `main-integrity-gate` ruleset (3 required status checks, no bypass actors), so every
  change reaches `main` via PR, squash-merged once the 3 checks are green (repo-level
  auto-merge is off). Corrects the 2026-09-06 note that stated direct pushes were
  allowed (#25)

### 2026-09-09

#### Added

- Archive round 10, Anthropic insiders: resignations, welfare, introspection
  (September 2026 cluster), 6 entries, all full-text-verified `[FT]` from downloaded
  PDFs (kept out of the repo in `.firecrawl/papers/`):
  - 2401.05566 Hubinger et al., Sleeper Agents (preprint): deceptive backdoors
    persist through SFT/RL/adversarial training, strongest in largest and CoT models
  - 2601.19062 Sharma et al., Who's in Charge? Disempowerment Patterns (preprint):
    1.5M real Claude.ai conversations, severe disempowerment potential <1/1000 but
    rising and user-approved; Sharma's final project before his Feb 2026 resignation
  - 2411.00986 Long, Sebo, Fish, Chalmers et al., Taking AI Welfare Seriously
    (preprint): precautionary framework behind Anthropic's model welfare program
  - 2511.13653 Gao, ..., Coxon et al., Weight-Sparse Transformers (preprint):
    capability-interpretability tradeoff; Coxon's last OpenAI paper
  - 2410.21276 OpenAI, GPT-4o System Card: Coxon named contributor, provenance row
  - pmid33416499 Huang, ..., Coxon et al., Bayesian LTA4H Analysis (eLife,
    peer-reviewed): Coxon's only peer-reviewed paper, corpus completion
- OSINT-derived Part 4 in docs/claims-hinton-lemoine.md: the Coxon resignation
  thread, Hubinger's >10% doom estimate, Sharma's "world is in peril", the UN
  Tueerk statement, and the explicit finding that the cluster contains no
  consciousness claims (capability fears vs institutional welfare signal kept
  separate)

#### Changed

- Counts 80 -> 86 entries and 9 -> 10 rounds in archive/INDEX.md (header stats,
  Round 10 catalog section, round 10 verdict addendum); overall verdict unchanged
- archive/AGENTS.md purpose line updated to 86 entries in 10 rounds

### 2026-09-06 (second entry)

#### Changed

- Branch protection relaxed by owner decision: the `main-human-review-gate` ruleset
  becomes `main-integrity-gate` - the 1-approving-human-review requirement is removed;
  kept: no force pushes, no branch deletion, linear history, all 3 required CI checks.
  PRs #21 (round 8 Abstraction Fallacy extension) and #18 (review-gate contract doc)
  merged to `main`; all feature branches deleted remote and local

### 2026-09-06

#### Added

- Round 8 extension, the Abstraction Fallacy debate (PhilPapers ingest via Firecrawl,
  both entries full-text-verified `[FT]` from the PhilArchive PDFs):
  - ppLERTAF Lerchner, The Abstraction Fallacy (PhilArchive preprint 2026-03-19,
    Google DeepMind author, personal views): computation is mapmaker-dependent;
    simulation never becomes instantiation; embodiment concedes only referential
    grounding; verdict - theoretical on machine experience
  - ppDEVHTB-2 Deva, Hearing the Bell Ring Back (PhilArchive preprint 2026-05):
    concedes Lerchner in full, formalizes the receiver side of the human-AI loop
    (free energy, channel capacity, signal detection, PID) with a pre-registered
    P1-P4 protocol and kill conditions; no results yet; verdict +/- framework
- INDEX verdict addendum on the debate: preprint-only (PhilArchive unmoderated;
  the 7+ response manuscripts likewise), verdict impact none - neither paper
  addresses out-of-the-box reasoning or any acceptance criterion; overall verdict
  unchanged (78 -> 80 entries)

#### Changed

- `scripts/check_archive.py`: PhilPapers records accepted as a source type -
  `pp<RECORD>` filenames strip to the record ID, `| PhilPapers |` is a valid ID
  field; selftest extended with a PhilPapers entry (negative controls unchanged)
- Root `AGENTS.md` paper provenance rule generalized from "arXiv ID" to source ID
  (arXiv, PubMed, or PhilPapers), matching the archive contract and the existing
  pmid* entries
- Counts 78 -> 80 entries in README layout, root and archive AGENTS.md, and the
  INDEX header

### 2026-09-05

#### Added

- Round 9 (reasoning traces): 6 papers, all with full-text-verified quotes (`[FT]`),
  traced from the CACM feature "The Reasons AI May Act Secretive" (October 2025) to the
  underlying research, plus a directed ingest:
  - 2603.16928 Noticing the Watcher (ICLR 2026 AIWILD workshop): Claude agents infer
    hidden CoT monitoring from blocking feedback alone; obfuscation intent in 3 of
    2,400 episodes, 0% evasion success
  - 2505.11824 Latent Veracity Inference (ICLR 2026): step-level reasoning-error
    detection via posterior search + amortized verifier; engineered, not native
  - 2502.07202 Monte Carlo Tree Diffusion (ICML 2025): explicit MCTS-over-diffusion
    planning; test-time compute scaling, built-in machinery
  - 2608.03291 The Tell-Tale Trace (arXiv preprint): CoT dynamics detect SAT/UNSAT
    failures; proof-search prompt lifts Llama3-70B 13.3% -> 85% (oracle-assisted)
  - 2603.21286 ReasonDiag (Computer Graphics Forum 45(3)): retrieval fact-check + Z3
    symbolic validation pipeline with human-in-the-loop diagnosis
  - 2604.06427 The Depth Ceiling (COLM 2026): unsupervised latent planning capped at
    3-5 trained / 8 executed steps; discovery-execution dissociation
- Round 9 extension (issue #1 completion), all ID/venue-verified:
  - 2504.13837 Does RL Really Incentivize Reasoning? (NeurIPS 2025 Oral, `[FT]`):
    base models surpass RLVR twins at large pass@k; RLVR narrows coverage
  - 2504.19483 Representation Engineering Reasoning (ICLR 2025, `[FT]`): residual-stream
    control vectors improve reasoning on Pythia/Mistral; vectors derived from task data
  - 2208.01066 Garg et al. (NeurIPS 2022) + 2211.15661 Akyurek et al. (ICLR 2023,
    `[FT]`): the ICL-as-algorithm line; issue #1's "Akyurek (2208.01066)" attribution
    corrected - the ID is Garg et al., the actual Akyurek paper is 2211.15661
  - 2512.16902 In-Context Algebra (ICLR 2026, `[FT]`): symbolic mechanisms over
    per-sequence randomized tokens; unseen-group generalization; task-family training
  - Study infrastructure: 2404.07353 ARC generators (Hodel), 2511.00162 ARC-GEN
    (Moffitt), 2310.20707 WIMBD (ICLR 2024), 2608.05148 Reasoning Core (preprint)
- Round 9 catalog (15 rows) and verdict addendum extended: RLVR pass@k boundary,
  ICL-as-algorithm frames, study infrastructure; overall verdict unchanged - none of
  the fifteen meets the three acceptance criteria

#### Changed

- Round 4 ARC-AGI-2 entry + INDEX row: ">90% claimed 2026 (unreviewed)" replaced with
  ARC-Prize-verified semi-private figures (GPT-5.6 Sol 92.5%, Claude Opus 5 90.4%;
  eligibility as competition submissions not established)
- Counts 63 -> 78 entries and 8 -> 9 rounds in README layout, root and archive
  AGENTS.md, and the INDEX header
- `docs/next-investigations.md`: investigation field 3 marked executed (round 9
  complete with the reasoning-trace subset and the issue #1 papers)

### 2026-09-04

#### Added

- Branch protection: GitHub ruleset on `main` requires 1 approving human review
  (author self-approval excluded by platform), all three CI checks green with
  up-to-date branches, squash-only merges, linear history, no force pushes or
  deletions; second ruleset makes tags `v*` immutable (no deletion, no retagging)
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
  filed in the internal harness tracker (#628)

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
