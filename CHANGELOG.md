# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### 2026-10-20

#### Added

- Nightly research round 14 (issue #65, tracker comment posted; serves #71 depth-ceiling
  placement): `research/nightly-2026-10-20-0400/` replicates the round-11 matched-pair
  traversal grid (k = 12, 16, 24; nine matched items x four arms = 36 cells; byte-identical
  prompts, prompt_sha256 identity asserted in the gate against the committed round-11 raw
  archive `round11_reference_raw.jsonl`) on a 27B-class local endpoint. Result: 36/36
  cells follow the directed-traversal oracle (connectivity fails exactly the nine R1 cells,
  0 discordant McNemar pairs in both families), and the verdict is cell-identical to the
  flash-class round-11 run (36/36 cells agree), so on this corpus the traversal signature
  is not a property of the flash class; completion style is class-dependent (full interior
  chain recitation in 18/36 completions vs 36/36 at the flash-class slot, mean completion
  tokens 407.1, max 853, no truncation at 2048). Gate written before any prompt (schema
  `round14-gate-v1`, 66-check selftest green); 37 endpoint calls under a 40-attempt cap,
  zero retries. State: **Executed**; the round-11 independent-verifier standard is deferred
  this round and disclosed in the round README.

### 2026-10-19

#### Added

- Archive round 17, mechanistic interpretability review: 1 entry in
  `archive/round17-mechanistic-review-2026/` (Sawant & Krejčí 2026, arXiv:2607.07316,
  scoping review, preprint), ingested on owner direction with focus on section 3.8
  "Emergent Symbolic Reasoning Mechanisms", full-text verified (`[FT]`): deduction
  heads on tree path-finding (Brinkmann et al., arXiv:2402.11917) and the Yang et al.
  ICML 2025 three-stage symbolic architecture (symbol abstraction, symbolic induction,
  retrieval). Verdict: +/- mechanism - strengthens the circuit-forms line (Nanda,
  Olsson), does not meet the acceptance criteria (survey, task-trained or undisclosed
  models); overall verdict unchanged. Archive now 122 entries in 16 rounds; count
  statements updated in the same commit.
- Automated repo-round family under tracker #83 (runners live outside this repository,
  public-only rule): daily PR review at 06:30 (skill-verified validation of open PRs
  plus the 3 required CI checks, merge-if-green), weekly maintenance Sun 05:00 (branch
  hygiene, deep skill-verified PR pass), weekly doc collection Sun 08:00 (intro pages
  synced via the DOX closeout rules), weekly issue audit Sun 09:00 (open issues
  validated against in-repo knowledge). The merge gate is unchanged: every change
  reaches main via branch + PR with all 3 CI checks green; agents never push to main
  and never touch .github or the ruleset.

- Nightly round 11 research record (`research/nightly-2026-10-19-0200/`, issue #65,
  refs #71, #73): a matched-pair probe at depths k = 12, 16, 24 on nine seed-generated
  ladder items (levels beyond the shipped grid, generator hashes pinned in the gate)
  replicates the round-10 traversal verdict: 36/36 cells match the directed-traversal
  oracle, the undirected-connectivity shortcut fails all nine reverse cells, exact
  McNemar shows zero discordant pairs in both matched families, and all 36 completions
  recite the full interior chain. The endpoint is the pool's `qwen38-flash-next` slot, a
  distinct slot from round 10's (same public model family; not a quantization comparison).
  Transport hardening: 37 endpoint
  calls under a global 40-attempt cap, zero retries, per-attempt `finished_at`
  timestamps close the named open item of #73. The probe script fixes three round-10
  verification findings instead of copying them (true null support bounds, two-sided
  exact nulls for gate firing, attempt-capped retries) and its `--selftest` passes
  50 checks. Verification record: `docs/review-rounds/nightly11-2026-10-19.md`
  (byte-identical regeneration of gate and summary; seven documentation errata corrected;
  state Executed and Reproduced at the analysis level).

### 2026-10-18

#### Added

- Nightly round 9 (issue #65, `research/nightly-2026-10-18-0200/`): the round-8
  constant-load grid re-run on the faster assigned endpoint with the #73 transport
  hardening (pre-grid health check, sequential dispatch, per-item 600 s deadline with one
  retry, incremental fsynced raw archive, empty completions classified `transport_failure`
  with error class and never `no_answer`, per-arm 3600 s budget). The probe completed:
  40/40 answered, 40/40 correct, 0 transport failures, all first attempt. No turnover to
  arm-L `k = 12` (6/6 at every depth, Wilson lower bound 0.6097 above the 0.60 floor),
  so `d* = 12` within the declared grid, i.e. `d* >= 12`; arm X descriptive 2/2 at
  `k = 16` and `k = 24`. Budget replay: 25/40 items unreachable at 256 tokens (median
  completion 404 tokens), 18 at 512, 2 at 1024, 0 at 2048, and every reachable answer is
  correct (truncation cliff, not reasoning cliff). The three items that survived round 8's
  transport failure answer correctly on the byte-identical stream. #73 acceptance met
  (arm ran; the empty-completion and deadline paths are covered by selftest controls 10
  and 11). `const_load_depth.py` is a self-contained re-implementation (stdlib only, 15
  selftest controls including stream identity against round 8's published gate record).
- Round-9 literature verification posted to issue #74 (free scholarly APIs only): CLUTRR
  (arXiv 1908.06177) verified with venue EMNLP 2019 (ACL Anthology D19-1458); the
  RuleTaker (pinned arXiv 2301.07330) and PrOntoQA (pinned arXiv 2203.14238) arXiv IDs
  in #74 point at unrelated papers (FPANet and a Vicsek-model paper respectively) and
  neither paper resolves in arXiv, Crossref, or OpenAlex (OpenReview-only, forum
  unresolvable from this environment); verified animal transitive-inference primary
  Gazes, Chee and Hampton 2012, J. Exp. Psychol. Animal Behavior Processes 38(4):331-345,
  DOI 10.1037/a0030306.

- Nightly round 10 (04:00 slot, issue #65): matched-pair probe of traversal versus undirected
  connectivity in `research/nightly-2026-10-18-0400/` (`matched_pair_probe.py`, `gate.json`,
  `raw.jsonl`, `summary.json`, `README.md`). The shipped corpus is shown to be unable to separate the
  two strategies: across all 1500 items there are 0 queried pairs where connectivity and directed
  reachability disagree, and 5 direction-blind rules reproduce every gold label at 1.0000
  (`same_component`, `undirected_connectivity_only`, `target_is_fact_target`,
  `endpoint_out_degree_zero`, `chain_len_matches_level`; the last is a metadata leak, since item
  `chain_len` equals `level` for gold-yes items). A 9-item matched corpus built by re-querying real
  shipped items at k = 4, 6, 8 (forward interior, reverse, forward shifted, cross-component terminal)
  has 9 disagreeing cells, matched-pair invariants enforced as fatal checks, and a 15-rule
  direction-blind battery whose best rule reaches only 0.7500, so the corpus is discriminating while
  the shipped one is not. Probe: 36 prompts, 36/36 answered, 0 transport failures, 0 truncations,
  every arm 9/9; exact McNemar 0 discordant pairs in both families; the answer pattern matches the
  directed-traversal oracle on 36/36 cells and 9/9 items and the connectivity oracle on 27/36 cells
  and 0/9 items. Verdict: the endpoint traverses the chain rather than answering from component
  membership. This defeats the blocking half of #77 criterion 4 for probing (a matched-pair probe does
  not have to wait for the generator repair) without cleaning the shipped corpus, which criterion 3
  still owns. Exact label-shuffle nulls throughout, no Monte Carlo; significance separated from
  competence (`same_component` reaches p 1.953e-03 on the matched corpus at only 0.7500 accuracy).
  Literature arm: CLUTRR 1908.06177, ProofWriter 2012.13048, Soft Reasoners 2002.05867, PrOntoQA
  2112.09054, Greedy Reasoners 2210.01240, OOD deductive capacity 2305.15269, Explicit Planning
  2303.15714, Verifier-Guided Proofs 2205.12443, PRover 2010.02830, NeuBAROCO 2306.12567, Hypothesis
  Search 2309.05660, Neural Theorem Provers 1906.06805; the seven IDs earlier rounds mis-pinned are
  recorded as wrong. As first published 8 of those 12 titles did not match the arXiv record and the
  entry claimed RuleTaker's own ID was unconfirmed; both were corrected the same day by the independent
  verification pass recorded below. Honest disclosure: the first execution of this round was destroyed by
  a verifier subagent that switched the shared primary worktree to `main`, and everything published is
  from a single re-execution (see the round README limits section).

#### Fixed

- Independent verification of nightly round 10 (`docs/review-rounds/nightly10-2026-10-18.md`): every
  quantitative claim in `research/nightly-2026-10-18-0400/README.md` recomputed from `gate.json`,
  `raw.jsonl`, `summary.json` and `items/ladders/` with independent union-find, BFS, exact
  `Fraction`-based hypergeometric and convolution nulls, Wilson interval, and McNemar implementations.
  All headline numbers reproduced, and `--gate` plus `--analyze` regenerate `gate.json` and
  `summary.json` byte-identically in a sandbox. Corrections landed in the round README: the selection
  rule is 3 usable items per level, not one; the arm notation is off by one (F1 is (p_1, p_k), R1 is
  (p_k, p_1), F2 is (p_2, p_{k+1})); "15 rules that cannot express edge direction" is overstated, since
  reversing every edge changes 5 of the 15; the rule nulls are one-sided upper tails, and the two-sided
  matched p for `same_component` is 3.906e-03, above the 3.333e-03 Bonferroni bar, so the 0.90 accuracy
  bar is what makes the corpus discriminating; shipped p 0.0 is an underflowed float for an exact tail of
  about 10^-450; `gate.json` records `null_min_hits` wrong for 12 rules and `null_max_hits` wrong for 3
  (the true support is [|a + y - n|, n - |a - y|]), which cannot be retrofitted because the gate hash is
  embedded in every `raw.jsonl` record and in `summary.json`, so the fix is owed with a fresh gate under
  #77; the 10.2 s health check, the 745.8 s probe wall clock, the 37-to-73 prompt range and the "two real
  bugs found by those controls" claim are runner-side statements no artifact carries; the literature table
  is rewritten with API-resolved titles, authors and venues, 2002.05867 is identified as the RuleTaker
  paper, its venue is IJCAI 2020 rather than the unsupported "TACL 2021", and "Language Models with
  Rules" plus "Deriving Rules from Language Models" are recorded as unverified because no arXiv record
  carries either title. The same corrections were published in place on the forge threads where round 10
  had already posted them (the PR #80 description and comment, and issues #65, #73, #74, #77 and #78) rather
  than as new issues; the PR description was corrected by prepending a dated corrections section and
  leaving the original claim record below it. Issue #73 additionally received the round-10
  transport record as the artifacts carry it, plus the proposal that future rounds write `started_utc`
  and `finished_utc` into `summary.json` so that wall-clock claims are archive claims rather than log
  claims.
- `matched_pair_probe.py --selftest` now passes 45 of 45 and exits 0. As shipped by round 10 it reported
  44 of 45 and exited 1: one check asserted `null_sd == 0.0` and `p_exact == 1.0` for the
  `same_component` shipped null, whose true standard deviation is 19.370824 and whose exact tail
  underflows to 0.0, and a second check was labelled "0 discordant pairs" over an assertion of 9. Both
  were defects in the test, not in the analysis; the bound formulas in `exact_null_shipped` are left
  unchanged on purpose and now carry a comment recording the correct support for the round that re-runs
  the battery with a fresh gate hash.

#### Changed

- `docs/agent-execution.md` section 5 gains two verification-conduct rules, both learned from this
  round's verification pass: a verifier is read-only against the worktree under verification (it writes
  only outside it, never edits a tracked file, never commits or pushes, and never runs `git checkout`,
  `git switch`, `git branch -D` or `git push --delete` against that worktree or its refs; its findings
  land as a report the producing agent re-verifies and applies), and the runner snapshots the round
  directory before any verifier pass, by commit plus push or by a checksummed copy outside the
  repository. The first execution of round 10 was destroyed by exactly the operation the first rule
  forbids, and the round-10 verifier patched the working tree while reporting read-only operation.

### 2026-10-16

#### Added

- `research/AGENTS.md`, the DOX boundary for nightly round artifacts (issue #65): one
  directory per firing, script plus `raw.jsonl` prompts and raw responses plus
  `summary.json`, sanitized by construction (no host, IP, endpoint URL, credential or
  model file path, in model output text as well), protocol caps treated as contractual,
  and the Executed/Reproduced/Validated label stated per run. Registered in the root
  Child DOX Index.
- `research/nightly-2026-10-16-0400/` (nightly round 6): `ladder_depth_probe.py`, a
  depth-ceiling probe for the k-hop ladder family (stdlib, `--selftest` with 7 controls:
  byte-identical regeneration against the shipped series, a constant rule at exactly the
  majority baseline, a perfect rule at 1.0, an inverted rule at 0.0, parser refusals,
  sanitizer, and two negative controls that must be rejected: a flipped answer and a
  pre-#69 item), plus `raw.jsonl` (40 prompts and raw responses) and `summary.json`.
  Result on a local Qwen3.8-Flash-Next class endpoint (arm A, temperature 0,
  `max_tokens` 2048, grid k in {1,2,3,4,5,6,8,10,12,16}, 2 yes + 2 no per level selected
  before any call): 40/40 correct, 40/40 format-valid, 0 truncations, no ceiling inside
  k <= 16, reproducing PR #69's model-facing claim on a second endpoint with an
  independent harness. New measurement: depth is paid in output tokens
  (`completion_tokens = -36 + 80k`), and replaying the same completions against fixed
  budgets loses 26/40 items at 256 tokens, 12/40 at 512 and 4/40 at 1024, so the family
  is budget-limited rather than depth-limited for an explicit-reasoning endpoint; the
  `d*+1..d*+4` band cannot be placed from this curve. Recorded in
  `docs/next-investigations.md`.

#### Fixed

- `generators/AGENTS.md` seed policy stated the digit-matrices forms as family-wide: the
  per-item seed multiplier is 2_000_000 for `ladders.py` (not 1_000_000) and the ladder
  `seed_hash` is sha256("family|task_type|level|seed")[:16], so the committed ladder seeds
  and seed hashes did not follow from the documented rule.

### 2026-10-15

#### Fixed

- `generators/ladders.py` shortcut leak (issue #67): the pre-fix k-hop ladder items
  (single chain plus disjoint noise) leaked the gold label through two surface rules
  that never traverse the fact graph (query target is a fact target; query target
  out-degree zero), both at 100% on the 1,500 shipped items, so the family could not
  support Condition 2 / claim C5. Repair: the construction is now component-isomorphic -
  the facts are C >= 2 disjoint directed paths, each of exactly `level` edges over fresh
  entities; the query is always (head of one path, tail of one path); the answer is
  "yes" iff both endpoints lie on the same path. Because every component is isomorphic
  (same length, same endpoint roles), no surface feature of the query endpoints
  (fact-target/source membership, in/out degree, component or walk length) can separate
  the two answer classes; the only separating information (which component each endpoint
  is on) requires the intended k-hop traversal. Regenerated `items/ladders/` levels
  {1, 2, 4, 6, 8}, 300 items each (1,500 total), seed_base 20261005; byte-identical
  regeneration and per-level manifest sha256 verified. Verification against the issue
  #67 acceptance criteria: all four acceptance-criterion rules (fact-target membership,
  out-degree zero, in-degree zero, fact-source membership) are label-constant at every
  level (raw accuracy equals the per-level majority baseline; no rule or gated
  conjunction above 0.55); independent BFS agrees with the stored answer on 1,500/1,500
  items (yes items shortest path exactly k, no items unreachable); a 40-prompt
  format-validity check against the local inference endpoint
  (a 27B-class local model) scores 39/40, the single miss being a 512-token
  truncation the item answers correctly under a larger budget, so the repaired format
  remains solvable across the depth grid.

#### Added

- `generators/audit_ladder_leaks.py` (issue #67): a repeatable shortcut-leak audit for
  the ladder family. A surface-feature battery over the query endpoints (degree,
  fact-target/source membership, neighbourhood, component and walk length), a
  conjunction search over them, numeric stumps, and bounded-search baselines (d=1, 2,
  3), plus an independent-BFS solvability re-derivation. The audit measures the shipped
  generator directly (thin aliases to `ladders.generate_item`), so the battery and the
  negative controls cannot drift from the item contract. Gate semantics: a feature
  constant across an item set carries no label information (its accuracy is the
  sample's label imbalance, not a leak) and is reported but never gated; at level 1 the
  `direct_fact` feature is the task itself (a 1-hop query is derivable iff it is a
  stated fact) and is reported as a depth match, never gated; everything else is gated
  above CHANCE_MAX = 0.55. Seven seeded negative controls (planted leak, ragged
  components, shuffled labels, off-by-one, planted cross edge, determinism) are all
  caught by `--selftest`. The round-2 construct-validity scratch tool
  (`audit_hop_chain.py`, never committed) is superseded by it: its mode-0 fidelity
  re-implementation targeted the pre-fix generator and its candidate-fix simulations
  (A-E) are superseded by the adopted component-isomorphism construction.

### 2026-10-14

#### Added

- `check_archive.py` now accepts Crossref-registered DOIs as source IDs (issue #63,
  test-first: selftest RED commit `75d28a7`, then checker GREEN commit `bcb9c2f`):
  DOI-only entries (Animal Behaviour, Animal Sentience, and Phil Trans B papers with no
  arXiv, PubMed, or PhilPapers record) carry a `| DOI |` table field, and the DOI local
  part must appear in the filename; a mismatch fails the check. Selftest covers the
  DOI-good control and the DOI-bad mutant. `archive/AGENTS.md` provenance rule extended
  accordingly.
- Archive round 16, insect sentience evidence chain: 13 entries in
  `archive/round16-insect-sentience/`, all verdict "context", all abstract-level (no
  `[FT]`): the pain-axis LLM preprint (arXiv 2609.16247), the bee valence chain (Bateson
  2011; Solvi 2016; Loukola 2017; Galpayage Dona 2022 play), the Gibbons nociception
  chain (PNAS 2022 plus its 2025 erratum, Proc R Soc B 2022, iScience 2024), the Gibbons
  & Chittka pain-evidence framework, Burns Brown & Birch 2025, and the trade-off dispute
  (Read & Nityananda critique, Gibbons et al. reassessment, Read & Nityananda response).
  Verification trail: Crossref works records, PubMed efetch abstracts, OpenAlex abstract
  reconstruction, arXiv export API; record: `docs/review-rounds/round16-2026-10-14.md`.
  Archive now 121 entries in 15 rounds; count statements updated in the same commit.
- `docs/claims-insect-sentience.md`: substrate-threshold claim ledger (bee chain table,
  trade-off controversy record, steelman with disanalogies and Bayesian hinge,
  institutional signals for the UK Animal Welfare (Sentience) Act 2022 and Anthropic,
  play-criteria translation proposal, unverified-claims log), counterargument #11 in
  `docs/counterarguments.md`, and a dated pointer in `docs/next-investigations.md`.
  Verdict: the argument is a prior raiser against substrate-based exclusion; machine
  indicator evidence remains unaudited; the out-of-the-box reasoning verdict is unchanged.
- Nightly consciousness research rounds (issue #65): a systemd user timer fires at 02:00 and 04:00;
  the runner (outside the repository, public-only rule) rotates across self-hosted inference endpoints
  with localhost preferred, health-checks each endpoint, and launches one bounded deep-research plus
  experiment round via an agent CLI with subagent delegation. Tracker: issue #65 round-summary
  comments; durable findings as deduped issues; repo changes as `research/nightly-*` branches plus PRs.
- Commit signing rule (root `AGENTS.md` User Preferences): every agent commit is signed with the model
  it actually ran on, as a final `Model:` trailer, live-detected in the current session.

### 2026-10-05

#### Added

- `check_archive.py` now validates the archive count statements in `README.md`, root
  `AGENTS.md`, and `archive/AGENTS.md` against the actual entry/round counts
  (issue #54): a drifted count or a vanished statement fails the check, closing the
  gap behind the 2026-09-28 drift incident (92/12 vs INDEX 107/13, fixed manually
  in #52). Selftest covers both controls (drift mutant, missing statement).
- Round-14 full-text verification pass: all 15 entries in
  `archive/round14-latent-reasoning-2026/` verified against their arXiv HTML full
  texts, 0 discrepancies; all 15 upgraded to `[FT]` and INDEX rows prefixed
  accordingly (FT total 47 -> 62). Record:
  `docs/review-rounds/round14-fulltext-2026-10-05.md`. Verdict unchanged: the core
  H1 gap remains unfilled.
- Condition-2 task generators, family 1 (issue #4): `generators/digit_matrices.py`,
  a Webb-style Raven-analogue generator (rule pool: constant, progression,
  distribution-of-3, AND/OR/XOR; depth = 1-4 simultaneous component rules; 8-option
  answers; generation-time solvability enforcement). Generated
  `items/digit_matrices/` levels 1-4, 300 items each (1,200 total) with per-level
  manifests (content sha256, seed-hash chain); byte-identical regeneration verified
  across processes. New `generators/AGENTS.md` holds the seed policy and item
  contract. Human-solvability smoke check (>= 3 humans) still open on issue #4.
- Condition-2 task generators, family 2 subtype `hop_chain` (issue #4):
  `generators/ladders.py` - k-hop relation composition over synthetic entity
  strings with an explicit transitivity rule (Faith-and-Fate style; the k-hop
  chains are the Dolma-audit anchor for issue #3). Generated
  `items/ladders/` levels k in {1, 2, 4, 6, 8}, 300 items each (1,500 total),
  yes/no balanced, answers verified by independent BFS in the selftest;
  byte-identical regeneration verified. `mult_mult` and `dp_puzzle` subtypes
  pending.
- Round-15 (field origins) ingest: the Dartmouth proposal (McCarthy, Minsky,
  Rochester, Shannon, 1955-08-31) as
  `archive/round15-field-origins/ppJOHAPF-3-mccarthy-dartmouth-proposal.md`
  (PhilPapers [JOHAPF-3](https://philpapers.org/rec/JOHAPF-3); official
  reprint AI Magazine 27(4), 12-14, 2006). Marked `[FT]`: quotes read from a
  direct full-text copy of the reformatted 1955 proposal (local PDF, ligature
  artifacts normalized, note in the entry). Verdict: context - the founding
  document frames the simulation conjecture and the language/randomness/
  internal-model/efficiency axes but makes no out-of-the-box claim; overall
  verdict and evidence matrix unchanged. Archive now 108 entries in 14 rounds
  (README, root AGENTS.md, archive/AGENTS.md count statements updated).

### 2026-09-28

#### Added

- Archive round 14, latent reasoning, elicitation, and the H0-b line, 15 entries, all
  abstract-level (full text not read; no `[FT]`). None meets the five acceptance
  conditions and the overall verdict is unchanged; the core H1 gap (genuinely novel
  procedural reasoning with zero elicitation) remains unfilled:
  - 2609.12317 Mi & Huang 2026, DF-Sample: training-free decision-flow inference-time
    search; GPQA 45.6% vs power sampling 38.9% and GRPO 39.9%
  - 2608.30462 Song et al. 2026, cross-lingual SAE feature transfer (EMNLP 2026
    Findings): SAE steering over residual-stream activations
  - 2609.05111 Fan 2026, Bayesian unification of ICL/SFT/RL: one Bayes/posterior +
    forward-KL projection template
  - 2609.19717 Gatmiry et al. 2026, Abstract Token Curriculum: elicits continuous
    internal thoughts; parity-function theory
  - 2609.03633 Koh et al. 2026, spurious CoT termination (EMNLP 2026): injected
    end-of-think token does not reliably switch reasoning to answering
  - 2609.16055 Gong et al. 2026, State of Thought: endogenous reasoning via a
    582-parameter controller on frozen backbones
  - 2609.01117 Chen & Fu 2026, Latent Recurrent Thoughts: frozen LLM decodes, small
    recurrent reasoner refines latents
  - 2609.07821 Xu et al. 2026, A*-Thought-V2: geometric hidden-state compression
  - 2609.00738 Cheng 2026, BASIN: training-free basin-aware search fixes "reasoning
    basin collapse"; beats ToT by up to +22pp
  - 2609.13997 Zhu et al. 2026, teacher-guided RLVR curriculum (EMNLP 2026 Findings):
    128 unsolvable problems ~16x data efficiency vs GRPO
  - 2609.03342 Zheng et al. 2026, gradient-aligned rewards (GAR): dense reward from
    gradient-space cosine similarity
  - 2609.27284 Tencent 2026, Hunyuan-A13B: open 80B/13B-active MoE; study-battery
    candidate
  - 2305.10601 Yao et al. 2023, Tree of Thoughts (NeurIPS 2023): the foundational
    deliberate-search scaffold and baseline (followed contained resource)
  - 2604.22709 Ramji et al. 2026, Abstract-CoT / Thinking Without Words: up to 11.6x
    fewer reasoning tokens via an abstract-token latent CoT (followed contained resource)
  - 2412.06769 Hao et al. 2024, Coconut (COLM 2025): continuous-latent reasoning via
    feeding the last hidden state back as the next input embedding (followed contained
    resource)

- `docs/review-rounds/round14-2026-09-28.md` (new): adversarial review of all 15
  round-14 entries against raw arXiv abstract pages - 15/15 entries confirmed, 0
  discrepancies, 1 retracted working-note claim (the 2609.13997 "33.1% MATH/NumGym"
  note was a transcription error absent from the entry); per-claim confrontation per
  [agent-execution.md](docs/agent-execution.md) section 5
- `archive/INDEX.md` round-14 section + `archive/AGENTS.md` Purpose: pointer to the review
  record added

#### Changed

- Housekeeping: closed the complete-but-open ISO-week milestones `2026-W37` and `2026-W38`
  (all assigned issues closed, 0 open) - milestone state only, no content change
- M1 verification (progress comments on #7 / #10 / #11): confirmed the in-repo M1
  work-package artifacts are complete and hash-verified (freeze-integrity: `docs/analysis-plan.md`
  and `docs/study-design.md` SHA-256 match `docs/version-lock-manifest.md`); the remaining M1
  gate is the owner-gated OSF + AsPredicted submission, and #7 carries one in-repo gap
  (consent form + task instructions not yet drafted as separate documents)

### 2026-09-15

#### Added

- Archive round 13, the Chinese Room debate (syntax, systems, and computationalism),
  4 entries, all full-text-verified `[FT]` (Searle and Dennett from the scanned 1980 BBS
  issue PDF, Chalmers from the author's HTML full text, Butlin et al. from the arXiv v3
  full text; PhilPapers record IDs SEAMBA, DENTMO-8, CHAACF-2 verified on the record
  pages; arXiv metadata via API/scrape):
  - ppSEAMBA Searle 1980, Minds, Brains, and Programs (BBS 3(3), peer-reviewed with open
    commentary): syntax never sufficient for intentionality; root of round 8's
    Harnad/Lerchner line
  - ppDENTMO-8 Dennett 1980, The Milk of Human Intentionality (BBS commentary): names the
    "intuition pump"; the room "relies almost entirely on ill-gotten gains"; the
    methodological reason intuition arguments stay out of the evidence column
  - ppCHAACF-2 Chalmers 2011, A Computational Foundation for the Study of Cognition
    (Journal of Cognitive Science, peer-reviewed): implementation analysis; mentality as
    "organizational invariant"; the functionalist premise the hand-execution argument
    must deny
  - 2308.08708 Butlin, Long et al. 2023, Consciousness in Artificial Intelligence
    (arXiv preprint, 19 authors): theory-derived indicator properties; no current system
    is conscious, no obvious technical barrier in principle
- archive/INDEX.md: round 13 catalog section with a debate intro, verdict addendum
  analyzing the popular "run the same math by hand on paper" form (question-begging
  substrate premise per the systems reply, intuition-pump status per Dennett, sentience
  vs AGI conflation) and declaring verdict impact: none; counts 88 -> 92 papers,
  11 -> 12 rounds
- README.md + AGENTS.md (root and archive): archive count references updated to 92
  entries, 12 rounds

### 2026-09-14

#### Added

- docs/next-investigations.md: Research findings (2026-09-14), owner-directed deep research
  on everything connected to a LinkedIn post about Google/HHMI Janelia's male fruit fly
  connectome and the week of simulations it spawned (#42): verified Cell paper record (PMID
  42691995, DOI 10.1016/j.cell.2026.08.015, ~166,700 neurons, sexual-dimorphism findings),
  MaleCNS v1.0 dataset release (2026-06-08) and preprint DOI 10.1101/2025.10.09.680999,
  three companion papers, female Nature counterpart (10.1038/s41586-026-10735-w); verified
  event timeline of the simulation wave (DOOMFLY Alex Wormuth 2026-09-06 with LIF
  methodology, Fly64 Jessica Paquette 2026-09-07, Beat Saber with an overfit-motor caveat,
  NeuroCraft Fly Minecraft, Breg Grockman parallel-parking video 2026-09-10 ~1.5M views,
  Mark Unthank Driving Fly/Flyhard CARLA project); Nick Walton Rubik's cube X post
  2026-09-11 with no disclosed training method plus community FlyCube repo; critical
  assessment of fidelity (Peraza Pong audit, no author endorsement of fidelity claims);
  thesis relevance mapped to counterargument #6 scaffold-vs-model and the elicitation-vs-
  capacity line; archive eligibility note (Cell paper eligible but connectomics background -
  not added without owner direction)
- docs/counterarguments.md: counterargument #6 gains a fly-connectome illustration - the
  MaleCNS simulation wave as a public case of scaffold-vs-model attribution, with the
  ablation question framed as the same one the study design's scaffold ban operationalizes
- archive/round12-fly-brain-context/: two provenance-standard entries added on owner
  direction - Cell paper (PMID 42691995, peer-reviewed) and bioRxiv preprint (PMID
  41279223), both with PubMed-verified author lists, framed as connectomics context for
  counterarguments #9/#6, not LLM-reasoning evidence; round number 11 stays reserved for
  the queued LLM candidate round
- archive/INDEX.md: catalog counts updated to 88 papers in 11 rounds; Round 12 catalog
  section added with verdict symbols and context note
- README.md + AGENTS.md (root and archive): archive count references updated to 88 entries,
  11 rounds; next-investigations layout row and status line now include the 2026-09-14 scan
- docs/version-lock-manifest.md (issue #11): re-captured document hashes on 2026-09-14
  (analysis-plan and study-design unchanged); captured current Hub revisions for all 11
  checkpoints as draft values (final pin at freeze)
- docs/irb-protocol.md (new, issue #7): complete human-baseline protocol - design, sample
  size/precision target (Wilson CI half-width <= +/-8pp on HUM(f), T1 CI-based
  non-inferiority), population/eligibility, recruitment and compensation, consent, data
  handling and privacy (public-only rule), scoring gates (10% re-score, kappa >= 0.8),
  pre-registered exclusions and stopping rule, and the IRB path decision 2026-09-14
  (no host-institution IRB path in this POC; documented alternative = published Webb et al.
  baseline anchor + collection under institutional review only if a partner institution
  materializes; protocol kept submission-ready)
- docs/preregistration.md: human-subject layer row now points at the IRB protocol draft and
  records the 2026-09-14 path decision; README layout row added for irb-protocol.md

#### Fixed

- docs/next-investigations.md: M1 thesis-timeline row now matches the 2026-09-14 IRB path
  decision - content and exit criteria reference the documented decision on #7 (no
  host-institution submission path in this POC; submission only if a partner institution
  materializes before M4) instead of an IRB submission the M1 deadline cannot meet
- docs/next-investigations.md: research findings (2026-09-14) section now applies the
  file's own sourcing discipline - [single-source] markers on the two single-sourced items
  (dataset release date, Beat Saber overfit-motor caveat) and an explicit exemption for
  the wider-wave color bullet, which carries no formal citation

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
- docs/preregistration.md (new) + docs/version-lock-manifest.md (new): issue #11
  pre-registration package. Registration content mapped to sources (study design v0.4, frozen
  model list, analysis plan, item selection, decoding/seed policy, version lock), AsPredicted
  form mapping, two-layer structure (computational + human per #7), deviation policy
  (post-timestamp addenda only, affected analyses downgraded to exploratory; immutable
  elements per analysis-plan Section 13), and the owner-gated submission checklist with the
  record table for the OSF and AsPredicted URLs. Version-lock manifest: freeze semantics;
  SHA-256 captured 2026-09-11 for analysis-plan.md and study-design.md (re-capture at freeze);
  model/corpus Hub IDs from the closed feasibility audit; DRAFT activation-patching grid with
  the primary specification fixed; TBD slots with owning issues for M2 artifacts; capture
  procedure. Refs #11 (external submissions owner-gated; #10 closes with the timestamp) (#32)
- docs/agent-execution.md (new): program operating model per the owner directive of
  2026-09-11 (issue #39) - the full thesis program (M1-M5) executes on AI agents with
  enforced scientific standards: the Plan-to-Report pipeline mapped to program mechanisms,
  immutable run manifests, numerical-confrontation records, verifier independence with
  seeded-defect tests, Executed/Reproduced/Validated labels, artifact and archive rules,
  resource policy (local-first single-node inference, public indexes, subscription agents,
  no metered calls). Publication landscape verified from primary sources (arXiv one-year
  ban for unchecked AI output, 19 May 2026; NeurIPS 2026 position-track policy and
  provenance audit-trail direction); the repository is the public record; open owner
  decisions (human baseline path, compute node, registration timing) listed (#39)
- docs/next-investigations.md: primary-source fetch of "An Alien Mind" (Jakub Pachocki,
  OpenAI, 2026-09-06; owner-requested). Non-archive, position-class source: the mid-2023
  RLSlow elicitation framing ("unlocking the capability of pretrained models"), the first
  first-party statement of declining CoT monitorability with three named causes (C4 and
  #36 relevance), the OpenAI-Hugging Face agentic incident as design input for the
  agent-executed program, Astra/RSI positions, and the closing slowdown and safety-bars
  argument. All 22 content resources extracted, fetched, and verified (accounting: 22
  resources + 12 exclusions - navigation, self-anchor, and inline images - of 34 raw
  links);
  public-professional person notes for Pachocki (2+ sources; includes the arXiv
  reasoning and monitoring line, among them "Monitoring Monitorability", 2512.18311) (#32)

#### Changed

- docs/next-investigations.md, README.md: EOD-review follow-ups - status dates bumped to
  2026-09-11, feasibility-audit section retitled (closed 2026-09-10, issue #2),
  timeline-risk paragraph reduced to the two residual unknowns (32B mix naming, Apertus
  1.5 pretrain-only checkpoint), stale "pending the audit" source note rescoped (#32)
- AGENTS.md, README.md: docs index and layout rows extended for the #11 pre-registration
  package (docs/preregistration.md, docs/version-lock-manifest.md) (#32)
- AGENTS.md, README.md: docs index, layout row, and a Project Notes line for the
  agent-execution operating model (#39)

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
