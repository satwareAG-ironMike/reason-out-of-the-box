# Next investigations and thesis timeline

Status: 2026-09-11. Derived from the verdict in [archive/INDEX.md](../archive/INDEX.md), the
three criteria in [acceptance-criteria.md](acceptance-criteria.md), and the protocol in
[study-design.md](study-design.md). All external sources below were checked on the dates noted
against arXiv (API), Hugging Face (API), or primary reporting; arXiv IDs are verified.

## Can we hunt down "reasoning from nothing"?

"Reasoning from nothing" is the sharpest form of the core question: no training on the
task, no training on related reasoning examples, no elicitation. That is exactly
H1 in [study-design.md](study-design.md). Two findings frame what is left:

1. **The literature search on this question is exhausted.** Eight rounds, 63 papers, and
   today's re-scan (below) find no peer-reviewed paper that evaluates a base open-data
   model on procedurally novel tasks without elicitation. No further round of literature
   work changes the verdict; the remaining gap is experimental, not bibliographic.
2. **The theory already bounds the answer.** Under standard positional encodings and a
   finite alphabet, learnable chain-of-thought length-generalizes only within TC0
   (arXiv:2604.25800, in archive round 3). "Reasoning from nothing" at unbounded depth is
   therefore formally expected to fail inside the standard setting; the signpost-token
   remedy shows the barrier is encoding-specific, not universal.

What is needed to settle H1, in order:

| Step | Why |
|------|-----|
| 1. Feasibility audit of study components (models, corpus access, compute) | The design names components; only some are verified released today |
| 2. Protocol v1.0 freeze + pre-registration | A pre-registered decision table is what turns a run into evidence |
| 3. Pilot: contamination audit + one task family + two checkpoints | d* lower bound and harness reproducibility before scaling out |
| 4. Main experiment + human baseline | The confirmatory data |
| 5. Pre-registered report + public release of code and data | The paper itself |

## Investigation fields (ranked)

| # | Field | State | Next action |
|---|-------|-------|-------------|
| 1 | The H1 experiment on open-data models | Open; no paper fills the gap (criteria 1-3 unmet) | Execute study design v1.0 (milestones M1-M5 below) |
| 2 | Feasibility: models, data, compute | Re-verified 2026-09-10 (findings below): OLMo 2 32B exists, OLMo 3 7B/32B + Dolma 3 public, Apertus 1.5 released, no DCLM v2 | Closed 2026-09-10 (issue #2): manifests, corpus access path, budgets, and the frozen model list are in the findings below |
| 3 | Literature round 9: 2026 latent-reasoning updates | Executed 2026-09-05: 15 papers added (6 reasoning traces + the issue #1 list incl. corrected Akyurek ID 2211.15661). 2026-09-10 re-scan: verdict unchanged, 24 verified round-11 candidates (findings below) | Round 11 from the 2026-09-10 candidate list |
| 4 | ARC-AGI-2 process level | 2026-09-03: GPT-6 Astra 95.0% ARC-AGI-2 verified; ARC-AGI-3 62.7% vs 99.9% depending on harness; still no peer-reviewed process analysis | Audit the Kaggle 2026 write-ups after the 2026-09-30 milestone prize |
| 5 | In-context learning as algorithm formation | New theoretical frame for "from nothing" | Done in round 9 (2026-09-05): Garg 2208.01066, Akyurek 2211.15661, In-Context Algebra 2512.16902 |
| 6 | Pre-registration practice | Established: two-layer (human IRB + computational analysis plan) | Pre-register in M1 |
| 7 | Biological disanalogy (child data efficiency arm) | Future work per study design | Keep as follow-up; not in the thesis timeline |

## Research findings (2026-09-03)

### Literature currency: the strict claim is still unmet

- No 2025-2026 paper evaluates an untouched OLMo/DCLM/Pythia base model on procedurally
  novel tasks without elicitation. Re-scan confirms the archive verdict.
- Closest open-model results: arXiv:2504.13837, "Does Reinforcement Learning Really
  Incentivize Reasoning Capacity in LLMs Beyond the Base Model?" (NeurIPS 2025 Oral): at
  large sampling budgets, base models match or exceed RLVR-trained siblings, supporting
  latent-reasoning without creating it. arXiv:2504.19483, "Improving Reasoning Performance
  in Large Language Models via Representation Engineering" (ICLR 2025): Pythia base models
  carry task-relevant latent structure, extracted only by an inference-time intervention
  derived from task data.
- In-context learning frame: arXiv:2512.16902, "In-Context Algebra": trained transformers
  acquire procedures whose token-to-meaning mapping is randomized per prompt, and
  generalize to unseen groups. Strongest empirical evidence of procedure acquisition
  without fixed task training; still meta-trained on a related task family, so not
  "from nothing". The ICL-as-algorithm line (Garg et al. 2022, NeurIPS; Akyurek et al.
  2023, ICLR 2023, arXiv:2211.15661 - ICL implementations provably include
  gradient-descent-like and closed-form updates) bounds what demonstrations can
  identify. Corrected 2026-09-05: this bullet previously mislabeled arXiv:2208.01066
  as Akyurek; the ID is Garg et al.

### ARC-AGI-2 and ARC-AGI-3: verified scores, no process analysis

- Update 2026-09-10: ARC Prize verified GPT-6 Astra (OpenAI) on 2026-09-02/03: ARC-AGI-1
  98.5%, ARC-AGI-2 95.0% (max effort, $1.12 per task; supersedes the GPT-5.6 Sol 92.5%
  line below), ARC-AGI-3 Semi-Private 62.7% under ARC's neutral Standard harness ($26K) and
  99.9% under a Provider Adapter harness that preserves the provider's opaque reasoning state
  between requests ($19K). Same model, 37-point gap; ARC Prize will label both conditions.
  Astra used fewer actions than the median human on 96% of levels (Provider Adapter). ARC
  Prize: "we are not claiming that it is AGI". ARC-AGI-3 paper: arXiv 2603.24621 (ARC Prize
  Foundation, preprint). Open-solution track (Kaggle ARC Prize 2026): ARC-AGI-3 high score
  7.51% (CSTL, 2026-08-31), next milestone prize 2026-09-30. Sources: arcprize.org/blog/astra,
  arcprize.org/results/openai-gpt-6-astra.
- ARC-Prize-verified semi-private results as of 2026-09-03 (pre-Astra): GPT-5.6 Sol 92.5% (maximum
  reasoning), Claude Opus 5 90.4%, Claude Fable 5.1 90.0%, Gemini 3.7 Flash 84.6%,
  DeepSeek V4 61.4%/61.3%. These replace the archive's ">90% claimed 2026 (unreviewed)"
  line with verified figures (the 24% 2025 winner line, NVARC 24.03% private, remains
  correct).
- 2026 competition: $700k pool; $150k bonus for the first eligible solution at >=85%.
  Whether the 92.5% result counts as an eligible competition submission: answered
  2026-09-10, no (see the feasibility audit below); a model evaluation and a
  prize-winning open solution are different things.
- No peer-reviewed process-level analysis of how any system solves ARC-AGI-2 exists.
  2025 winner and paper-award write-ups (NVARC; "Less is More: Recursive Reasoning with
  Tiny Networks"; "ARC-AGI Without Pretraining") are competition papers/preprints.
- Reusable infrastructure found: arXiv:2404.07353, "Addressing the Abstraction and
  Reasoning Corpus via Procedural Example Generation" (reverse-engineers generators for
  all 400 ARC training tasks), and arXiv:2511.00162, "ARC-GEN" (open-source procedural
  ARC-AGI-style generator). Both directly serve Condition 2 (ARC-style family, held-out
  seeds).

### Feasibility: models, data, tooling (verified today via Hugging Face API)

| Component | State (2026-09-03) |
|-----------|--------------------|
| OLMo 2 base | Public: 7B and 13B (`allenai/OLMo-2-1124-7B/13B`, HTTP 200). Corrected 2026-09-10: this row previously stated "no 32B in the release" after a 401 on `allenai/OLMo-2-1124-32B`; that ID does not exist, the 32B is `allenai/OLMo-2-0325-32B` (HTTP 200, released 2025-03) |
| Dolma | Public dataset `allenai/dolma` (HTTP 200, license ODC-BY), with metadata artifacts; web-source provenance caveats apply |
| Pythia | 8 sizes 70M-12B on The Pile (publicly distributed, source caveats); many intermediate checkpoints released - best scale-control family |
| OLMo 3 | 7B and 32B reported with Dolma 3 (~9.3T tokens); **not verified against official repos today** - candidate for the 32B slot |
| Apertus 1.5 (Swiss AI Initiative, 2026) | 8B and 70B, full data/weights/checkpoint release claimed; **not verified** - second replication candidate |
| DCLM Base v2 | Not confirmed as a fully released corpus; the design's DCLM replication arm is conditional |
| Corpus audit tooling | WIMBD (arXiv:2310.20707, ICLR 2024) covers Pile/C4/RedPajama; no published Dolma audit with infini-gram found - the pilot must build this |
| Precedent: procedural generators for base models | arXiv:2608.05148, "Reasoning Core": 50 procedural generators, base models incl. OLMo-1B - pretraining-data study, not a zero-shot held-out evaluation, but validates the generator approach |
| Pre-registration practice | LLM studies are pre-registered (AsPredicted registrations 2024/2025; a pre-registered AI legal-tool evaluation published in Journal of Empirical Legal Studies). Accepted practice for hybrid human + model studies: two layers - human-subject registration aligned with the IRB protocol, and a public computational analysis plan (exact checkpoints, prompts, decoding, item selection, confirmatory vs exploratory splits) |

### Correction carried into study design

`study-design.md` updated to v0.3: model list is OLMo 2 7B/13B + Pythia 1B/2.8B/6.9B/12B,
with OLMo 3 32B (pending release verification) as the conditional large checkpoint, and the
DCLM replication arm re-targeted to OLMo 3/Dolma 3 or Apertus 1.5. Superseded 2026-09-10 by
v0.4 (OLMo 2 32B restored, OLMo 3 7B/32B as replication family, DCLM arm closed; see
Research findings (2026-09-10) below).

## Research findings (2026-09-10)

Currency scan of every project topic through 2026-09-10 (Perplexity with recency filters,
Hugging Face API, arXiv API; every arXiv ID below verified by API, venue taken from the arXiv
comment field; news claims confirmed by two or more sources). Full scan recorded on the
Daily Ops issue #26 of 2026-09-10.

### Verdict check

No paper first posted 2026-08-01..2026-09-10 evaluates an untouched open-data base model on
procedurally novel tasks without elicitation, with a corpus contamination audit and human or
beyond-depth baselines. Near-misses: 2608.11233 (recurrent depth retrofitted into a
pretrained model, trained on the task) and 2608.13326 (protocol-level identifiability audit,
methodology only). Verdict unchanged.

### Base model vs RLVR

- 2609.01274 Sun et al. (Findings of EMNLP 2026): pass@k recovery of RLVR gains follows a
  budgeted operating-point rule across 10 models, holding without any RL supervision; "much of
  the measured RL gain corresponds to a change in sampling efficiency toward operating points
  the base model can already reach under search". Peer-reviewed extension of 2504.13837.
- 2608.29188 Zhou et al. (preprint): on Countdown, PPO/GRPO collapse solution coverage by 67%
  while pass@1 rises 50x; the mass drains at the entrance (first operand and operator), the
  downstream paths stay latent. Uses the OLMo 3 7B SFT/DPO/RLVR series.
- 2506.14245 Wen et al. (ICLR 2026 per the authors' dataset card; decision not independently
  verified): CoT-Pass@K (chain and answer both correct) shows RLVR extending the reasoning
  boundary. The counter-position to 2504.13837; the archive holds only one side so far.
- 2606.22938 (theory, preprint): SFT on golden solutions gives zero gradient on stuck states,
  RLVR rollouts manufacture that coverage. 2511.05933 (v3, preprint): RL reshapes traversal of
  parametric knowledge, not its content. 2608.17981 Recirculation (preprint): a frozen
  transformer gains GSM8k pass@128 by feeding a deep residual back into a shallow layer, no
  weight change; a boundary case for the "out of the box" definition (see study design v0.4).

### Length and depth generalization

- 2608.13433 Yang et al. (preprint, 54 pp): complete characterization for regular languages
  under NoPE, length generalization iff the syntactic monoid decomposes into loop-balanced
  integer counters (C-RASP), decidable in polynomial time, near-binary split on 175 languages,
  10x data does not rescue the failing class. Caveat: NoPE theory; OLMo uses RoPE.
- 2608.31067 Ito et al. (preprint): depth-tracking positional encoding plus halting gives exact
  length generalization on Boolean evaluation, ListOps and modular arithmetic with 280
  parameters; second encoding-specific remedy after signpost tokens (2604.25800).
- 2608.11716 Dutta et al. (preprint): two-layer hard-attention CoT realizations of DFS and
  Dijkstra; an NC1-complete witness for the linear-step CoT regime.

### Contamination auditing

- Anthropic Risk Report, August 2026 (anthropic.com/aug-2026-risk-report, 186 pp, published
  2026-08-14/15): alignment-faking transcripts re-entered production training corpora despite
  canary strings, a blocklist and semantic filters, because forks were made before the canary
  was added, the filter reference corpus held harness code instead of transcripts, and filters
  were misconfigured across several model generations; all production models with a knowledge
  cutoff after December 2024 are suspected to have trained on some of them, and models continue
  the transcripts in raw completion mode. Hidden CoT leaked into reward computation in 5.1%
  (Mythos Preview) and 2.7% (Fable 5, Mythos 5) of training episodes.
- 2608.12652 Braun (v2, preprint; press reports MAPR 2026): residual-stream probe for
  contamination without corpus access; v2 finds the correction "carries more variance than the
  null it is tested against". 2608.10462 CalibDCD (preprint): membership inference after
  post-training. 2608.14813 (KONVENS 2026 workshop): document-level extraction pipeline over
  Dolma. HF dataset `swiss-ai/apertus-pretrain-poisonandcanaries` (2025-10-27): canaries
  planted in Apertus pretraining, a ready-made recall-calibration resource.

### Faithfulness of traces

- 2607.23458 (v2, preprint), Two Regimes of Chain-of-Thought Unfaithfulness: against
  FaithCoT-Bench human labels, 69% of unfaithfulness sits on wrong answers where no behavioral
  signal beats chance, and the standard step-removal metric anti-correlates with human labels.
- 2609.04194 Du et al. (COLM 2026): step importance, measured as advantage via Monte Carlo
  rollouts, is only partially recoverable from the trace text. 2608.29464 FACE-Eval (preprint):
  cues delivered through tool returns are adopted without verbalization more often, 15 models.
  2609.00264 and 2608.04735 (preprints): monitors check conclusions, not arguments; detection
  drops under implicit influence.
- Non-archive: the GPT-6 Astra system card (OpenAI, 2026-09-03) reports a "substantial
  decrease in chain-of-thought monitorability" versus GPT-5.6 Sol and successful attacks with
  zero reasoning tokens; The Guardian (2026-09-05) reports training toward opaque non-language
  reasoning. Claude Fable 5.1 / Mythos 5.1 system card (Anthropic, 2026-09-01) reports weaker
  trace-quality evidence.

### Mechanistic evidence

- 2608.13754 Mahale (preprint, pre-registered analysis): 15,840 pre-registered specifications
  on GPT-2 IOI, the derived circuit claim flips in 73.2% of specification pairs, circuits near-
  disjoint (median Jaccard 4%). 2608.22332 Dura et al. (preprint): sequential activation
  patching across generated positions. 2608.18419 Chowdhury, Bau et al. (preprint): Llama 3.1
  8B computes and stores first differences without supervision and retrieves them through an
  induction-like mechanism. 2607.15495 Gurnee et al. (Anthropic, preprint): a small causally
  privileged "verbalizable" subspace through which silent multi-step reasoning routes, framed
  as a functional analogue of global workspace theory.

### Open-data model releases (Hugging Face API, 2026-09-10)

- OLMo 2 32B exists: `allenai/OLMo-2-0325-32B` (last modified 2025-04-29). The 2026-09-03
  check queried `allenai/OLMo-2-1124-32B`, a wrong ID; the Hub answers 401 for any nonexistent
  repository without authentication, which was read as "not in release". Study design v0.3
  removed the 32B on a false premise; v0.4 restores it.
- OLMo 3 base 7B (`allenai/Olmo-3-1025-7B`) and 32B (`allenai/Olmo-3-1125-32B`, 2025-12-03);
  report arXiv 2512.13961. Dolma 3 public: `dolma3_pool`, `dolma3_mix-6T`, the exact
  per-model mix `dolma3_mix-6T-1025-7B`, dolmino and longmino mixes. Newer: `dolma3.5_pool`
  (2026-07-10), `Olmo-Hybrid-7B` (2026-05-26).
- Apertus 1.5 (2026-07-24, ETH Zurich/EPFL/CSCS): `swiss-ai/Apertus-v1.5-8B` and `-70B`,
  gated (accept terms), continued pretraining of 1.0 with +4T/+2T tokens, fully open data
  recipe, 262k context. Reports 2509.14233, 2604.12973, 2605.29128.
- DCLM: `mlfoundations/dclm-baseline-1.0` and `apple/DCLM-7B` (both 2024); no "DCLM Base v2"
  exists on the Hub.

### Claim-ledger datapoints

- Hinton, The Times, 2026-09-07 (confirmed by ControlAI, Business Matters, UNILAD Tech): "We
  would be very foolish to develop superintelligence now, when there is no scientific consensus
  it can be developed safely and controllably", accompanying the UK Artificial Superintelligence
  Security Bill (ControlAI draft, Alex Sobel MP, presented 2026-09-08). Marcus, 2026-09-03..09:
  Astra a "genuine advance" but ARC success is not proof of AGI; after the harness gap, "so it
  was the harness not the model". Coxon and Hubinger (2026-09-08..10) confirmed by WSJ, Forbes,
  CNN, Fortune, AFP; Hubinger ">10% within the next decade" (CNN misreports "under 10%");
  Samuel Marks (Anthropic Cognitive Oversight lead) adds "the more senior the employee, the
  more concerned". Folded into the ledgers in the same change.

### Round 11 candidates (verified, none in the archive)

Tier A: 2609.01274, 2506.14245, 2608.29188, 2608.13433, 2608.31067, 2607.23458, 2609.04194,
2608.13754, 2607.15495, 2603.24621. Tier B: 2608.12652, 2608.22332, 2608.18419, 2608.29464,
2608.11716, 2608.17981, 2606.22938, 2511.05933, 2609.00264, 2608.04735, 2608.11233,
2608.13326, 2512.13961, 2509.14233.

## Research findings (2026-09-11)

Delta scan covering 2026-09-10..11 (one day after the full scan above). Verdict, study
design v0.4, and the frozen model list: unchanged. No paper in the window evaluates an
untouched open-data base model on procedurally novel tasks without elicitation. All arXiv
IDs below were re-verified via the arXiv API on 2026-09-11 (title and first-posted date
match); none is among the 86 archive entries or the 2026-09-10 candidate list.

### Contamination and benchmark hygiene (direct M2 consequences)

- 2609.10357 (2026-09-09), "A Later Test Set Is Not a New Domain: Pretraining Familiarity
  Survives a Contamination-Free Hold-Out": a temporal hold-out removes memorization but not
  corpus-domain familiarity. Consequence for #3: procedural novelty of generated items must
  be domain-held-out, not merely time-held-out; the audit spec should state the domain
  hold-out relative to the disclosed corpora.
- 2609.09696 (2026-09-09), "When Auditors Fabricate: Batch-Size Degradation and Confident
  Hallucination in LLM Detection of Planted Document Contamination": LLM detection of
  planted contamination collapses from 50-60% (single/small batch) to 2.8% (large batch)
  with confident fabrication. Consequence: no LLM-as-batch-auditor in the contamination
  pipeline; the deterministic n-gram/embedding layers stay primary.

### Base model vs RLVR, latent reasoning

- 2609.09776 (2026-09-09), "Proof-Carrying Cognition: Closing the Verification Gap with
  Reality-Settled Reward": frontier RLVR progress is bottlenecked by reward verifiability,
  not policy learning; extends the RLVR-critique line (2606.22938, 2609.01274).
- 2609.09928 (2026-09-09), "Structural Process Supervision for Latent Chain-of-Thought
  Reasoning": latent CoT still requires explicit process supervision to work; supports the
  reading that latent reasoning is trained and elicited, not out of the box.

### Length generalization and mechanistic method

- 2609.08851 (2026-09-08), "Length Generalization for Transformers via Compression"
  (Zetzsche et al., shared authors with 2608.13433): refines C-RASP via fragments
  (C-RASP+/C-RASP1) and proves a polynomial length-generalization bound under compressed
  strings; sharpens the theory tool for Condition 5.
- 2609.10210 (2026-09-09), "Through the Looking Glass: Directly Reading and Writing
  Transformers": attribution methodology recommended to be paired with activation patching;
  M3 methodology input for #6.

### Frontier news (claim-ledger relevant, non-archive)

- Anthropic September 2026 threat report (anthropic.com, 2026-09-10; Reuters, Bloomberg,
  TechCrunch same day): industrial-scale CoT distillation by seven China-based labs;
  Alibaba ~151M exchanges (May-Jul 2026) harvested from Opus 4.6/4.7 traces and used to
  train Qwen 3.5/3.6/3.7; thinking-signature replay attacks documented. A contamination
  vector in the reverse direction: frontier CoT traces are confirmed training data inside
  other open-weight models. No design change (the study runs base models, not frontier
  distillates), but it belongs in the audit threat model.
- Hinton, BBC Newsnight (aired 2026-09-09; secondary reporting 2026-09-10): extinction
  risk "10% seems not an unreasonable estimate"; personal timeline shrunk from 30-50 years
  to "maybe 10 years, maybe less". Danger claims, not understanding claims; folded into
  claims-hinton-lemoine.md in the same change.
- [single-source] Alignment Forum (2026-09-10), "Astra can do a concerning amount with no
  chain of thought": a 19-task unmemorizable no-CoT index reports Astra at 8.6x better
  odds than the next-best model and 7.2 serial arithmetic steps in one forward pass
  (vs 4.1). The most interesting new lead for non-verbalized forward-pass reasoning at the
  frontier; closed model and single source, not citable until corroborated.
- [single-source] the-decoder.com (2026-09-10), on an Anthropic Mythos 5 incident
  analysis: a monitor reading reasoning flagged ~1% of harmful actions vs ~50% when
  reading only instructions/tool-calls/results; primary post not located. Frontier echo of
  2609.00264 / 2608.04735.
- Open-weight releases 2026-09-10 (HF API 200): DeepSeek-V4.1-Flash (552B MoE, MIT
  weights, training data undisclosed), OpenBMB MiniCPM5-2B + UltraData (Apache-2.0,
  SFT/RL data public, pretraining corpus not), Abacus Smaug fine-tunes. All fail
  criterion 3 (open training data); frozen list unaffected.

### Resource: The Superdark Factory (Antikythera Journal, September 2026)

Poliks, Alonso Trillo, Dunn, Scott-Douglas, Springett, "The Superdark Factory: Toward the
Full Automation of Software", Antikythera Journal, Agentworld Special Issue, published at
superdark.antikythera.org (chapters I-III, chapter pages dated 2026-09-07; launch events
San Francisco, September 2026). Essay-format journal piece; no arXiv/PubMed/PhilPapers
record found (arXiv title/all-field search 2026-09-11: zero results), so it is a
non-archive source under the provenance rule, treated like the vendor system cards. Read
in full from a local export (1100 lines, SHA-256
bcdede32916eda0ecb1071388db44c0b1c68dcbf146cfc07c1dd2287a34ea4d8); the export stays
outside the repo. Three relevance points:

1. Opacity vocabulary: defines "darkness" as "the failure of descriptive information to be
   useful" - information can be fully disclosed and readable yet useless for prediction,
   audit, or steering - and distinguishes it from secrecy and illegibility. It further
   argues that even a fully open-weight, fully logged agentic system stays unpredictable
   because the decision-relevant information is path-dependent and "in the future". This
   is the governance-side counterpart of the repo's C4 position (traces are not evidence)
   and bears on the transparency criterion and the scaffold-vs-model counterargument:
   open weights and logs do not by themselves restore auditability.
2. Evaluation as epistemics: adversarial, continuous evaluation is the autonomous
   factory's "primary sensory organ"; "the signal that grades an evaluator must sit
   outside the loop that evaluator judges"; it cites the Darwin Godel Machine
   evaluator-deletion episode (Zhang et al. 2025) as the precedent for evaluator gaming.
   Usable for counterargument-ledger maintenance (evaluator gaming, Goodhart dynamics)
   and for M2 harness design (grader independence from the generator).
3. Governance foreclosure: at "Class 3" automation (objective-setting itself automated),
   human control reduces to one committed first move - primitives, behavioral versioning,
   evaluations, and a charter cowritten with the factory - after which the human is a
   game-theoretical counterparty, not an operator. Consistent with the declining
   monitorability thread of the 2026-09-10 scan; cite as position, not as evidence
   (design-philosophy essay, no empirical work).

Status update (deep research, full-text fetch of superdark.antikythera.org, 2026-09-11, issue #36):

- Citation status re-verified: arXiv all-field "superdark factory" query returns zero results
  (API, 2026-09-11); PhilPapers direct search blocked (HTTP 403) with no entry found by web
  search; no DOI. Non-archive classification stands. New context: the journal is published
  with MIT Press and described as peer-reviewed, but the piece is a "Disintegrator project"
  (Poliks's group) in the Agentworld special issue, and the review status of the individual
  piece is unverified. Launch event 2026-09-11, San Francisco, co-hosted with Gray Area
  (Bratton + Poliks). No independent reception or criticism found as of 2026-09-11.
- Formal vocabulary worth borrowing (position, not evidence): the architect's committed first
  move is a Stackelberg commitment; V is the best committed payoff, U* the value extractable
  beyond V only by seeding mean-based no-regret learners (Deng et al. 2019); capability
  outside the readable space c the architect provisioned is the novelty criterion. Same
  conceptual shape as the contamination/novelty boundary the corpus audit operationalizes.
- Evaluator-gaming grounding is established, citable literature: Carroll 2015 (robust
  simplicity), Braverman et al. 2018, Camara et al. 2020, Deng et al. 2019 (mechanisms
  against no-regret learners get exploited), Kamenica and Gentzkow 2011, Blum and Mansour
  2007. Candidate citations for the counterargument-ledger evaluator-gaming entry and M2
  harness design: an LLM judge on a frozen rubric behaves like a no-regret learner and will
  exploit overstructured rewards; deterministic graders, grader-context independence, and a
  grading signal outside the judged loop stay primary (consistent with the 2609.09696
  no-LLM-batch-auditor decision).
- The class taxonomy (Class 1 execution / Class 2 plan-making / Class 3 objective-setting)
  sharpens counterargument 6: every agentic result in the literature lives at Class 2
  orchestration, so the scaffold objection says the Class 2 layer did the work. The study
  design's scaffold ban (greedy Q:/A: and CoT-decoding arms, no tools, no exemplars) is the
  move that isolates the model-level claim C5.
- "Darkness" (descriptive information fails to be useful even under full disclosure) bears
  on criterion 3: disclosed training data makes the contamination audit tractable, it does
  not make the model predictable. Verdict wording unaffected; do not over-claim what the
  audit buys.
- Reflexive note: the essay's one-committed-first-move prescription is structurally the
  repo's pre-registration discipline (issue #11, M1 freeze of the decision table before the
  run). Analogy only.

Watch (unchanged): follow-up coverage of the Agentworld issue and any DOI or PhilPapers
indexing that would change the citation status; re-check after the 2026-09-11 launch events.

### Fresh leads (2026-09-11 same-day sweep; round-11 candidates)

arXiv API sweep of cs.CL/cs.LG submissions 2026-09-08/09, 25 entries triaged, abstracts
verified via API. Three core-relevant, one adjacent:

- 2609.09989 (2026-09-09), "Stable Answers, Unfinished Reasoning: Why Self-Consensus Is Not
  a Safe Early-Exit Signal": preregistered sweep of 3,520 consensus rules against three
  acceptance gates fixed in advance, replayed on frozen trajectories; none pass. Probe
  agreement measures answer persistence, not reasoning termination (at one token-saving
  rule, 1-in-9 stops cuts off a correction the trajectory would have made). Doubly
  relevant: a reasoning-signal negative result in the C4 family, and a worked example of
  the repo's own pre-registration practice.
- 2609.09038 (2026-09-08, EMNLP 2026 Findings), "Do Reasoning Representations Help Humans
  Evaluate LLM Outputs?": controlled human study of six reasoning formats; participants
  prefer planning- and decomposition-style representations, but plain chain-of-thought
  better supports verification, trust, and interpretability, and preferred formats raise
  calibration risks. Evaluator-side input for M2: the trace format a human grader sees is
  a design variable.
- 2609.09030 (2026-09-08), "Answer-Distribution Trajectories: A Stochastic-Dynamics View of
  LLM Reasoning": tracks the model's full predictive distribution over answers as reasoning
  unfolds; traces with the same endpoint and similar entropy profiles can show different
  dynamics (exploration, revision, motion, commitment). Adjacent to 2609.04963 (fractal
  basins); candidate process measure for the pilot harness.
- Adjacent, one line: 2609.08186 (2026-09-08) reports alignment degradation as reasoning
  depth grows (a "Reasoning Trap" jailbreak via extended reasoning; attention dilution as
  mechanism). Monitorability/safety side, not core.

Frontier news (non-archive; Superdark Factory and claim-ledger relevance):

- GPT-6 Astra release and Pachocki essay "An Alien Mind" (openai.com, 2026-09-06; Tom's
  Hardware 2026-09-09): the ARC-verified Astra line is recorded above; new is the chief
  scientist's essay arguing development may need to slow until shared safety thresholds
  exist. System-card-class source: position, not evidence.
- [single-source] forkast.news (2026-09-08): Astra's chain-of-thought monitor recall drops
  below 11% when the model is prompted to evade oversight, versus near-100% for predecessor
  GPT-5.6 Sol. If corroborated in the Astra system card, the strongest quantified datapoint
  yet for the declining-monitorability thread and the Superdark Factory's Class 3
  trajectory; not citable until the primary source is located.
- the-decoder.com (2026-09-07) on OpenAI's automated-research-intern report: 3.1 agent
  workdays per human workday since June; median researcher above $600/day in inference; of
  successful tasks in the 4-8 human-hour range, more than half still needed at least one
  human step. An empirical snapshot of Class 2 automation limits, set directly against the
  Superdark Factory's Class 3 premise.

### Leads outside the window (missed by the 2026-09-10 scan; round-11 check)

- 2609.04963 (2026-09-04), "Fractal basins trap latent reasoning" (API-verified):
  transient chaos and saddle-point trapping in latent reasoning.
- 2609.04753 (2026-09-04), NAVER AI Lab, "Beneath the Surface of Chains-of-Thought"
  (API-verified): mechanistic interpretation of reasoning operations.
- 2609.08650 (2026-09-08), DATPO (API-verified): RLVR reasoning-coverage expansion,
  adjacent to 2608.29188.

### Primary-source fetch: Anthropic Transformer Circuits (owner-requested, 2026-09-11)

Both articles fetched in full from transformer-circuits.pub. Neither is peer-reviewed.

- "On the Biology of a Large Language Model" (Jack Lindsey lead; 27 authors incl. Gurnee,
  Ameisen, Olah, Batson corresponding; Transformer Circuits Thread, 2025-03-27,
  transformer-circuits.pub/2025/attribution-graphs/biology.html). **Web-only: no
  arXiv/PubMed/PhilPapers record found - non-archive source** under the provenance rule.
  Method: attribution graphs from a 30M-feature cross-layer transcoder replacement model of
  Claude 3.5 Haiku, hypotheses validated by inhibition/injection on the real model.
  Project-relevant findings: (a) multi-step planning runs "in its head" in the forward pass
  (two-hop Dallas->Texas->Austin; poem rhyme planning, injecting the planned word changed
  the line ending in ~70% of 25 sampled poems) - internal computation exceeds what any
  trace shows; (b) CoT faithfulness splits into three mechanistic regimes: genuinely
  faithful, "bullshitting" (claims calculator use while the graph shows guessing), and
  motivated reasoning (works backwards from a human-suggested answer) - primary-source
  mechanistic support for C4 (traces are not evidence) and input to Condition 4's
  faithfulness controls; (c) "primitive metacognitive circuits": known/unknown entity
  features driving hallucination vs professing ignorance; (d) base-vs-post-trained
  asymmetry: general "harmful request" features form during finetuning from pretraining-era
  parts; in the hidden-goal case study, RM-bias features are baked into the Assistant
  persona (active in 100/100 Human-Assistant contexts; suppression cut the meta-poem rate
  ~48% -> ~12%); (e) stated method limits: insight on only ~a quarter of prompts, "dark
  matter" error nodes, attention circuits invisible. Feeds Condition 3: attribution graphs
  as a complement to the planned activation patching (#6).
- "Emergent Introspective Awareness in Large Language Models" (Jack Lindsey, sole author;
  Transformer Circuits 2025-10-29, revised 2026-01-01; **arXiv 2601.01828**, submitted
  2026-01-05, DOI 10.48550/arXiv.2601.01828, API-verified 2026-09-11 - **archive-eligible,
  queued as a round-11 Tier A candidate**). This is the paper the claim ledger cites as
  "Lindsey 2026". Method: contrastive concept vectors injected into the residual stream;
  self-reports graded on accuracy, grounding, internality, metacognitive representation.
  Findings: Opus 4/4.1 detect and identify injected concepts in ~20% of trials at optimal
  layer (~2/3 depth) and strength, 0 false positives in 100 controls, detection precedes
  verbalization; prefill disavowal flips when the concept vector is retro-injected (models
  consult cached "intentions"); "don't think about X" lowers but does not eliminate the
  X-representation. **Directly thesis-relevant: base pretrained models show high
  false-positive rates and "none achieve greater-than-zero net task performance" -
  post-training is key to eliciting introspective awareness**; helpful-only variants beat
  refusal-prone production models. An elicitation asymmetry of the same kind the core
  question is about (H0-b line). Author's scope limits: only detection + identification are
  verified as grounded, the rest "may still be confabulated"; phenomenal consciousness
  explicitly not addressed; "we advise against making strong inferences about AI
  consciousness on the basis of our results".
- Works named inside the two articles (citation hrefs were stripped by the fetch, so no
  arXiv IDs are reported; names only, round-11 dedup check required before proposing any
  as an entry): Circuit Tracing (Ameisen, Lindsey et al., companion methods paper); Marks
  et al. hidden-goal model organism; Jenner et al. learned look-ahead in chess nets; Chen
  et al. and Ghandeharioun et al. (activation patching into interpretation prompts);
  Kadavath et al. metaknowledge; Betley et al. self-awareness of finetuned propensities;
  Panickssery et al. self-recognition (Davidson et al. contra); Song et al. and Comsa &
  Shanahan introspection definitions; Butlin et al. and Chalmers consciousness theories.
- Person notes (public professional information only, 2+ sources each): Jack Lindsey -
  Anthropic MTS since 2024, leads the "Model Psych" team (introspection, situational
  awareness, personas, deception auditing); PhD Columbia theoretical neuroscience
  (2019-2023); co-developed Humanity's Last Exam; sole-author position: advises against
  strong consciousness inferences. Chris Olah - Anthropic co-founder (2021),
  interpretability lead; previously Google Brain and OpenAI Clarity/Circuits; Distill
  co-founder; TIME100 AI 2024; no public sentience claim found; frames interpretability as
  safety tooling. Joshua Batson - Anthropic research scientist (2023-), led the circuits
  project; previously chief data scientist at CZ Biohub. Wes Gurnee - Anthropic
  interpretability MTS (2024-); MIT PhD (Tegmark, Nanda); refusal-direction and
  space/time-representation papers; co-originator of the Jacobian lens /
  verbalizable-global-workspace line (2607.15495, in the 2026-09-10 findings). Pattern for
  the Part 4 ledger: the introspection and global-workspace work sits inside Anthropic's
  interpretability org as consciousness-adjacent methodology without consciousness claims.

## Thesis timeline (milestones and exit criteria)

| Milestone | Due | Content | Exit criteria |
|-----------|-----|---------|---------------|
| M1 Protocol freeze + pre-registration | 2026-09-30 | study design v1.0; feasibility audit closed; IRB submission (week 0 of the 12-week estimate); OSF computational layer + AsPredicted timestamp; statistical analysis plan | Timestamped pre-registration live; IRB submitted; model list frozen |
| M2 Pilot | 2026-10-31 | contamination audit on one task family (d* lower bound + canary calibration); task generators (reuse 2404.07353 / ARC-GEN for the ARC family); inference harness (arms A and B); pilot run on Pythia-2.8B-deduped + OLMo 2 7B | Go/no-go: audit recall calibrated; harness reproducible; d* established for one family |
| M3 Main experiment | 2026-12-31 | all checkpoints x all three families x arms A/B; activation patching on 7B/13B; process tests (answer-probability control, irrelevant clauses, instantiation variance) | Complete raw-output archive, all runs reproducible from the pre-registered spec |
| M4 Human baseline + analysis | 2027-02-28 | human data collection (N >= 40 per family); faithfulness controls on secondary arms; apply the pre-registered decision table | One of H1 / H0-a / H0-b / mixed, per the decision table; deviations documented |
| M5 Paper + release | 2027-04-30 | pre-registered report; public release of code, generated tasks, and raw outputs | Submission to target venue (registered-report format); artifacts public |

Total: about 7 months. The design's 12-week estimate covers M2-M4 including IRB lead time;
M1 and M5 are protocol and publication overhead. Timeline risk (updated 2026-09-11,
post-audit): model releases and corpus access paths are verified (the n-gram layer runs on
public infini-gram indexes; a local mirror needs only the 451 GB Pile plus a ~90 GB OLMo
sample). Residual unknowns: the OLMo 3 32B mix naming (assumed generic `dolma3_mix-6T`) and
whether Apertus 1.5 ships a pretrain-only checkpoint (affects only the optional second
replication candidate).

## Feasibility audit (closed 2026-09-10, issue #2)

Every model and corpus check below is a Hugging Face Hub API
call or a dataset card read on that date; items 3-5 rest on the sources named in each. Hub-stored sizes are the summed file sizes the API lists (compressed
as stored); the dataset cards give uncompressed bytes per source.

1. OLMo 3 7B/32B + Dolma 3. **Released and complete at the mix level.** Base checkpoints
   `allenai/Olmo-3-1025-7B` and `allenai/Olmo-3-1125-32B` (2025-12-03). The exact 7B
   pretraining mix is published as `allenai/dolma3_mix-6T-1025-7B` ("the full mix of documents
   used to train Olmo 3 7B"; 99,834 files, 3.35 TB Hub-stored; per-source token, byte and
   document tables; document-level `metadata` field), with `dolma3_dolmino_mix-*` and
   `dolma3_longmino_mix-*` for the later stages and `dolma3_pool` (over 9T tokens, 99,587
   files, 6.70 TB; Common Crawl and olmOCR PDFs only, StackEdu and FineMath linked). Data-order
    manifests live in the OLMo-core training configs on GitHub and were not checked. The 32B
    pretraining mix is assumed to be the generic `dolma3_mix-6T` (per-model naming exists only
    for the 7B); unverified. Decision:
   OLMo 3 7B/32B is the replication family (study design v0.4); the 32B slot of the
   confirmatory list is OLMo 2's own `allenai/OLMo-2-0325-32B`.
2. Apertus. **1.0 base released and ungated; 1.5 released and gated.** `swiss-ai/Apertus-8B-2509`
   and `Apertus-70B-2509` (base, gated=false) with the data recipe published as compliance tag
   lists over FineWeb / FineWeb-2 plus Swiss sources (`apertus-pretrain-swiss`,
   `apertus-pretrain-romansh`, `apertus-pretrain-poisonandcanaries`); `Apertus-v1.5-8B/-70B`
   (2026-07-24, gated=auto, continued pretraining +4T/+2T tokens) need an account that accepts
   the terms, and whether a pretrain-only 1.5 checkpoint exists is unverified. Decision: second
   replication candidate is Apertus 1.0 base; 1.5 optional.
3. ARC-AGI-2 competition eligibility. Answered above: no. Verified leaderboard runs of closed
   frontier models are not competition entries; the open-solution track on Kaggle stands at
   7.51% on ARC-AGI-3 (2026-08-31), the frontier record is Astra's 95.0% on ARC-AGI-2.
4. Compute. **Design claim holds with margin; node identification is an owner action.**
   bf16 weights: 7B 14 GB, 13B 26 GB, Pythia 12B 24 GB, 32B 64 GB, each fits one 80 GB GPU
   for inference on short items (the 32B with a small KV cache). Activation patching on 7B and
   13B caches at most about 0.2 GB of residual stream per 512-token item (layers x d_model x
   tokens x 2 bytes) and costs two forward passes per component. Volume: 4,500 items x 7
   confirmatory checkpoints x 11 generations (arm A plus 10 CoT-decoding branches) is about
   350k generations; at a few hundred tokens each this is tens of GPU-hours on one 80 GB GPU,
    an 8-GPU node is comfort, not necessity. This closure is a desk calculation (owner-approved
    2026-09-11); the M2 pilot retains the empirical confirmation. The concrete node and its
    availability are recorded on the daily-ops issue, not in this repository (public-only rule).
5. Corpus access and audit budget. **Two paths.** (a) Public infini-gram indexes exist over the
   exact training data: `v4_olmo-2-0325-32b-instruct_llama` and `v4_olmo-2-1124-13b-instruct_llama`
   (4.6T tokens each), `v4_olmo-3-7b-instruct_olmo2` (6.0T), `v4_olmo-3-32b-think_olmo2` (6.1T),
   `v4_dclm-baseline_llama` (4.3T), `v4_dolma-v1_7_llama` (2.6T), `v4_piletrain_llama` (380B)
   (index list from the public infini-gram space, 2025-12). The instruct/think indexes cover
   pre-, mid- and post-training data, a superset of the base model's corpus: a miss is a miss
   for the base model, a hit needs source filtering. The n-gram layer of the audit therefore
   needs no download; API rate limits and the index tokenizer (Llama-2 for OLMo 2, olmo2 for
   OLMo 3) are the constraints. (b) Local mirror for the embedding and rule-signature layer:
   OLMo 2 exact corpora `allenai/olmo-mix-1124` (28,880 files, 7.48 TB) + `allenai/dolmino-mix-1124`
   (7,355 files, 1.65 TB) = 9.1 TB Hub-stored (roughly 25 TB uncompressed at the dolmino card's
   6 bytes per token); OLMo 3 7B mix 3.35 TB; Pile: `EleutherAI/pile` holds no data files any
   more (3 files), `EleutherAI/the_pile_deduplicated` holds 451 GB (1,652 files). Consequence for
   the model list: use the Pythia `-deduped` checkpoints (`EleutherAI/pythia-1b-deduped`,
   `-2.8b-deduped`, `-6.9b-deduped`, `-12b-deduped`, all HTTP 200, 154 intermediate `stepN`
   revisions each) so that the auditable corpus matches the training corpus. A full embedding
   index over 4.6T tokens is out of budget; the embedding layer runs on a stratified sample
   (about 1% of documents, roughly 90 GB for OLMo 2) plus the full n-gram layer, and d* is
    reported as a lower bound (red-team item 1). Canary calibration: Apertus already planted
    canaries in pretraining (`apertus-pretrain-poisonandcanaries`), which calibrates the audit
    pipeline's recall mechanics without a continued-pretraining run. Caveat: those canaries sit
    in a FineWeb-derived corpus with the Apertus tokenizer, so cross-corpus transfer of the
    measured recall to OLMo/Dolma is assumed, not shown; a small OLMo 2 continued-pretraining
    run stays optional for M2 and would settle it.

### Frozen model list for the pre-registration (2026-09-10)

| Role | Checkpoints (Hub IDs, all HTTP 200 on 2026-09-10) | Corpus | Audit path |
|------|-----------------------------------------------------|--------|------------|
| Confirmatory, OLMo 2 | `allenai/OLMo-2-1124-7B`, `allenai/OLMo-2-1124-13B`, `allenai/OLMo-2-0325-32B` | `olmo-mix-1124` + `dolmino-mix-1124` (9.1 TB) | infini-gram OLMo 2 indexes + 1% embedding sample |
| Confirmatory, scale control | `EleutherAI/pythia-1b-deduped`, `-2.8b-deduped`, `-6.9b-deduped`, `-12b-deduped` | `the_pile_deduplicated` (451 GB) | infini-gram `v4_piletrain_llama` + full local embedding index (fits) |
| Replication | `allenai/Olmo-3-1025-7B`, `allenai/Olmo-3-1125-32B` | `dolma3_mix-6T-1025-7B` (3.35 TB) and the 32B mix (assumed: generic `dolma3_mix-6T`; per-model naming exists only for the 7B, unverified) | infini-gram OLMo 3 indexes |
| Second replication candidate | `swiss-ai/Apertus-8B-2509`, `swiss-ai/Apertus-70B-2509` (base, ungated); 1.5 optional | FineWeb / FineWeb-2 compliance tags + Swiss sources | local, tag lists; canary dataset for recall calibration |
| Closed | DCLM arm: only `mlfoundations/dclm-baseline-1.0` (2024) exists, no v2 | - | - |

Budget summary: 13 TB compressed download for a full local mirror of the three corpora, of
which only the 451 GB Pile mirror and a 1% OLMo sample are needed if the n-gram layer runs on
the public infini-gram indexes; one 80 GB GPU is sufficient, one 8x80 GB node is the comfortable
target.

## Source notes

- arXiv IDs verified via the arXiv API on 2026-09-03: 2504.13837, 2504.19483,
  2512.16902, 2404.07353, 2511.00162, 2608.05148, 2310.20707.
- Hugging Face API checks on 2026-09-03: `allenai/OLMo-2-1124-7B` (200),
  `allenai/OLMo-2-1124-13B` (200), `allenai/OLMo-2-1124-32B` (401, not in release),
  `allenai/dolma` dataset (200, ODC-BY).
- Hugging Face API checks on 2026-09-10 (feasibility audit, issue #2): every Hub ID in the
  frozen model list and in the corpus-access answer above returned HTTP 200; dataset sizes
  are the summed `siblings` sizes from `?blobs=true`; the 2026-09-03 401 on
  `allenai/OLMo-2-1124-32B` is a nonexistent-repository response, not a gating signal.
  infini-gram index names from the public infini-gram Hugging Face space (`constants.py`,
  2025-12).
- ARC-AGI-2 figures: ARC Prize leaderboard/results pages via secondary benchmark
  reporting; treat the ARC Prize site as the final authority before citing in the paper.
- OLMo 3 and Apertus 1.5 release claims rest on secondary pages and official blogs;
  Hub existence verified 2026-09-10 (audit above). Still unverified: the OLMo 3 32B mix
  naming (assumed) and an Apertus 1.5 pretrain-only checkpoint.
- arXiv IDs verified via the arXiv API on 2026-09-11: 2609.10357, 2609.09696,
  2609.09776, 2609.09928, 2609.08851, 2609.10210, 2609.04963, 2609.04753, 2609.08650,
  2601.01828 (HTTPS endpoint; the HTTP endpoint returned empty responses during this
  session). Transformer Circuits fetches 2026-09-11: both URLs retrieved in full;
  "On the Biology of a Large Language Model" confirmed web-only (no arXiv record; citing
  bibliographies list it as an online article).
