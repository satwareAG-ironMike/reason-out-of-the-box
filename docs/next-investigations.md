# Next investigations and thesis timeline

Status: 2026-09-03. Derived from the verdict in [archive/INDEX.md](../archive/INDEX.md), the
three criteria in [acceptance-criteria.md](acceptance-criteria.md), and the protocol in
[study-design.md](study-design.md). All external sources below were checked today against
arXiv (API), Hugging Face (API), or primary reporting; arXiv IDs are verified.

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
| 2 | Feasibility: models, data, compute | Partially verified today (findings below) | Close remaining release verifications (OLMo 3, Apertus 1.5) |
| 3 | Literature round 9: 2026 latent-reasoning updates | Executed 2026-09-05: 15 papers added (6 reasoning traces + the issue #1 list incl. corrected Akyurek ID 2211.15661) | Closed; future 2026 updates go to round 10 |
| 4 | ARC-AGI-2 process level | Scores verified; no peer-reviewed process-level analysis exists | Monitor 2026 competition; audit winner write-ups when available |
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

### ARC-AGI-2: verified scores, no process analysis

- ARC-Prize-verified semi-private results as of today: GPT-5.6 Sol 92.5% (maximum
  reasoning), Claude Opus 5 90.4%, Claude Fable 5.1 90.0%, Gemini 3.7 Flash 84.6%,
  DeepSeek V4 61.4%/61.3%. These replace the archive's ">90% claimed 2026 (unreviewed)"
  line with verified figures (the 24% 2025 winner line, NVARC 24.03% private, remains
  correct).
- 2026 competition: $700k pool; $150k bonus for the first eligible solution at >=85%.
  Whether the 92.5% result counts as an eligible competition submission is not
  established; a model evaluation and a prize-winning open solution are different things.
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
| OLMo 2 base | Public: 7B and 13B only (`allenai/OLMo-2-1124-7B/13B`, HTTP 200). No 32B in the release; the design's "OLMo 2 32B" was a conflation with OLMo 3 (verified 401) |
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
DCLM replication arm re-targeted to OLMo 3/Dolma 3 or Apertus 1.5.

## Thesis timeline (milestones and exit criteria)

| Milestone | Due | Content | Exit criteria |
|-----------|-----|---------|---------------|
| M1 Protocol freeze + pre-registration | 2026-09-30 | study design v1.0; feasibility audit closed; IRB submission (week 0 of the 12-week estimate); OSF computational layer + AsPredicted timestamp; statistical analysis plan | Timestamped pre-registration live; IRB submitted; model list frozen |
| M2 Pilot | 2026-10-31 | contamination audit on one task family (d* lower bound + canary calibration); task generators (reuse 2404.07353 / ARC-GEN for the ARC family); inference harness (arms A and B); pilot run on Pythia-2.8B + OLMo 2 7B | Go/no-go: audit recall calibrated; harness reproducible; d* established for one family |
| M3 Main experiment | 2026-12-31 | all checkpoints x all three families x arms A/B; activation patching on 7B/13B; process tests (answer-probability control, irrelevant clauses, instantiation variance) | Complete raw-output archive, all runs reproducible from the pre-registered spec |
| M4 Human baseline + analysis | 2027-02-28 | human data collection (N >= 40 per family); faithfulness controls on secondary arms; apply the pre-registered decision table | One of H1 / H0-a / H0-b / mixed, per the decision table; deviations documented |
| M5 Paper + release | 2027-04-30 | pre-registered report; public release of code, generated tasks, and raw outputs | Submission to target venue (registered-report format); artifacts public |

Total: about 7 months. The design's 12-week estimate covers M2-M4 including IRB lead time;
M1 and M5 are protocol and publication overhead. Timeline risk: OLMo 3 / Apertus 1.5
release verification (affects only the conditional 32B checkpoint, not the confirmatory
design, which is defined at the verified scales).

## Open questions for the feasibility audit

1. OLMo 3 7B/32B + Dolma 3: do the official repos contain the complete corpus shards,
   document-level metadata, and training manifests? (Determine the 32B slot.)
2. Apertus 1.5: same completeness check (replication candidate).
3. Does the 92.5% ARC-AGI-2 result count as an eligible 2026 competition submission
   (determines the $150k bonus outcome)?
4. Compute: one 8x80GB node suffices for 7B/13B inference + activation patching
   (design claim); verify in the M2 pilot before the M3 commitment.
5. Dolma audit: recall calibration via planted canaries (red-team item 1) - which
   continued-pretraining budget makes the calibration runnable inside M2?

## Source notes

- arXiv IDs verified via the arXiv API on 2026-09-03: 2504.13837, 2504.19483,
  2512.16902, 2404.07353, 2511.00162, 2608.05148, 2310.20707.
- Hugging Face API checks on 2026-09-03: `allenai/OLMo-2-1124-7B` (200),
  `allenai/OLMo-2-1124-13B` (200), `allenai/OLMo-2-1124-32B` (401, not in release),
  `allenai/dolma` dataset (200, ODC-BY).
- ARC-AGI-2 figures: ARC Prize leaderboard/results pages via secondary benchmark
  reporting; treat the ARC Prize site as the final authority before citing in the paper.
- OLMo 3 and Apertus 1.5 release claims rest on secondary pages and official blogs;
  marked unverified pending the audit.
