# Archive: Can LLMs Reason Out of the Box?

**Question under investigation**: Is there a single peer-reviewed paper proving an LLM can
reason out of the box - without training on reasoning examples and hoping it generalizes -
analogous to how higher animals and humans reason without prior logic training?

**Archive built**: 2026-09-02 (rounds 1-4), 2026-09-03 (rounds 5-6), 2026-09-05 (round 9),
2026-09-06 (round 8 extension) |
**Method**: Firecrawl
research suite (semantic arXiv search, metadata inspection, full-text passage verification)
+ multi-round web-grounded analysis (Perplexity).
26 papers in rounds 1-4 (2026-09-02), 63 papers in 8 rounds total (2026-09-03), 15 papers in
round 9 (2026-09-05), 2 papers in round 8 (2026-09-06): 80 papers in 9 rounds. Full-text in-body verification was performed for the highest-
weight papers (marked [FT] below); all other entries rely on verified abstracts plus
cross-checked secondary sources.

## Verdict (state of the art, September 2026)

No paper satisfies the demand in full. The strongest positive candidates are
Webb/Holyoak/Lu (Nature Human Behaviour 2023, zero-shot analogical reasoning vs humans) and
Wang & Zhou (NeurIPS 2024, reasoning elicited by decoding alone). Both stop short because
pretraining exposure cannot be excluded and no process-level (mechanistic) proof of
systematic generalization exists. The 2025 R1-Zero ablations reframe the field: reasoning
competence is largely latent after pretraining, and RL/templates/decoding merely elicit and
amplify it - "out of the box" fails, but "barely below the surface" is now peer-reviewed
consensus. Formal theory (TC0 ceiling; length-generalization barriers) explains why a single
forward pass cannot reason sequentially, and why trained-depth limits persist even with CoT.

## Catalog

### Round 1 - Base model emergence (positive evidence)

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Wang & Zhou 2024, CoT Reasoning Without Prompting | NeurIPS 2024 | + closest candidate | Latent CoT paths, decoding-only elicitation; authors admit limits on novel tasks |
| [FT] Webb, Holyoak & Lu 2023, Emergent Analogical Reasoning | Nature Human Behaviour | + strongest journal claim | GPT-3 beats UCLA students zero-shot on novel Raven-style matrices (OR 6.27 multiple-choice) |
| [FT] Kojima et al. 2022, Zero-Shot Reasoners | NeurIPS 2022 | + partial | "Let's think step by step" unlocks latent reasoning, no examples |
| Power et al. 2022, Grokking | arXiv/ICLR-W | + mechanism | Algorithms emerge from training without being shown |
| Wang et al. 2024, Reasoning Paths Aggregation | arXiv | - mechanism skeptic | Reasoning as composition of pretrained paths |
| Du et al. 2025, Teaching Reasoning Without RL | arXiv (NVIDIA) | +/- | 20 examples unlock long-CoT; zero examples never demonstrated |

### Round 2 - Skeptical / counter-evidence

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Schaeffer et al. 2023, Mirage | NeurIPS 2023 (Outstanding) | - | Emergence often a metric artifact |
| [FT] Dziri et al. 2023, Faith and Fate | NeurIPS 2023 | - | Subgraph matching; collapse beyond trained depth |
| [FT] Zhang et al. 2024, GSM1k | NeurIPS 2024 D&B | +/- balanced | Up to 8% drops; but frontier models generalize, even overfit ones solve >50% novel |
| [FT] Mirzadeh et al. 2024, GSM-Symbolic | ICLR 2025 | - | ~10% drop on fresh variants; up to 65% with irrelevant clauses |
| [FT] McCoy et al. 2023, Embers of Autoregression | ICLR 2024 | - | Performance tracks answer/task probability, not logic |
| [FT] 2026, Post-training & Contamination | arXiv (preprint) | + nuance | GRPO turns leakage into transferable capability; SFT only extracts it |

### Round 3 - Theory & faithfulness

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Merrill & Sabharwal 2024, Expressive Power with CoT | ICLR 2024 | - formal | One forward pass = TC0; CoT buys sequential depth |
| Feng et al. 2024, CoT Solves Serial Problems | NeurIPS 2024 | - formal | Precise step-count characterizations |
| [FT] 2026, Barriers to Universal Reasoning | arXiv (preprint) | - formal | Verified: with standard PEs + finite alphabet, CoT length-generalizes only within TC0; signpost tokens are the proposed remedy |
| [FT] Turpin et al. 2023, Don't Say What They Think | NeurIPS 2023 | - evidence killer | CoT often post-hoc rationalization |
| Lanham et al. 2023, Measuring Faithfulness | arXiv (Anthropic) | - calibration | Faithfulness task-dependent, declines with scale sometimes |
| Arcuschin et al. 2025, In the Wild Not Always Faithful | arXiv | - | Unfaithfulness on natural prompts, incl. reasoning models |
| Pfau et al. 2024, Let's Think Dot by Dot | arXiv | +/- | Hidden computation possible via fillers, but never spontaneous |

### Round 4 - Mechanistic & reasoning-model era

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Nanda et al. 2023, Grokking via Mechanistic Interp. | ICLR 2023 (Oral) | + mechanism | Fourier arithmetic circuits reverse-engineered |
| Olsson et al. 2022, Induction Heads | arXiv (Anthropic) | + mechanism | Match-and-copy circuits form spontaneously in pretraining |
| [FT] Wang et al. 2024, Grokked Implicit Reasoners | ICML 2024 | - | Implicit reasoning circuits still fail OOD composition |
| [FT] Liu et al. 2025, R1-Zero Critical Perspective | COLM 2025 | + key ablation | Base models already solve math and show "Aha"; RL amplifies, not creates |
| DeepSeek-AI 2025, R1 | Nature | +/- paradigm | RL elicitation: 15.6% -> 71% AIME from a base that already scored 15.6% |
| [FT] Chollet et al. 2025, ARC-AGI-2 | arXiv | test platform | ~0-4% at launch vs 60% human; 24% 2025 winner; 92.5% GPT-5.6 Sol / 90.4% Claude Opus 5 verified semi-private 2026 (ARC Prize; competition eligibility not established) |
| 2026, ARC Living Survey | arXiv (preprint) | - synthesis | All paradigms drop 2-3x on regenerated tasks |

### Round 5 - How LLMs think and validate ideas

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Huang et al. 2024, Cannot Self-Correct Reasoning Yet | ICLR 2024 | - validation | Intrinsic self-correction degrades accuracy (Llama-2 62->36.5); "cannot properly judge correctness of their reasoning" |
| Kadavath et al. 2022, (Mostly) Know What They Know | arXiv (Anthropic) | + partial | P(True) self-evaluation: usable confidence signal, not falsification |
| Wang et al. 2023, Self-Consistency | ICLR 2023 | + statistical | Majority vote over paths; validates against own prior, not the world |
| Madaan et al. 2023, Self-Refine | NeurIPS 2023 | +/- | Self-feedback loop; gains mostly on externally checkable criteria |
| Gou et al. 2024, CRITIC | ICLR 2024 | + grounded | Tool-based critique works; validation needs external ground truth |
| 2025, Self-Rewarding Correction | arXiv | + trained | Verifier internalized from ground-truth training, then reused |
| 2026, Accuracy-Correction Paradox | arXiv (preprint) | - detection | Strong models leave more errors undetected; fluency confounds detection |

### Round 6 - Unique idea generation

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Si, Yang & Hashimoto 2025, Novel Research Ideas | ICLR 2025 | + | LLM ideas judged more novel than expert ideas (p<0.05, ~300 blind reviews); diversity and evaluator weaknesses documented |
| [FT] 2025, Ideation-Execution Gap | arXiv | - | Executed LLM ideas underperform human ideas; judged novelty is a weak predictor |
| 2026, Divergent Creativity Large-Scale (PMID 41436597) | journal (peer-reviewed) | - | Humans (N=9,198) slightly above LLMs (N=215k observations) on average |
| [FT] 2026, AI Lacks Imagination to Diverge/Negate | arXiv (preprint) | +/- corrected | 6,749 scientists, 26 LLMs: non-reasoning models collapse, **reasoning models diverge**; all LLMs under-produce null hypotheses; raters prefer their own ideas |
| 2026, Similarly Creative Over Three Years | arXiv (preprint) | - | Model families converge (hivemind); uniqueness must be population-measured |
| 2026, Cross-Domain Mapping | arXiv (preprint) | - mechanism | The intervention boosting human originality does not transfer to LLMs |
| 2026, IDEAFix | arXiv (preprint) | tool | Fixation control; many "novel" outputs are recombined anchoring |

### Round 7 - Embodied agents, tools, and the herd

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Wang et al. 2023, Voyager | arXiv/TMLR lineage | + embodiment | Brain + body + skill library (stored code) + environment self-verification = open-ended discovery |
| 2026, The AI Scientist end-to-end (PMC13017497) | journal (peer-reviewed) | + partial | Full research cycle automated to workshop tier; validation (review) remains the bottleneck |
| Wu et al. 2024, LRLL | arXiv | + embodiment | Physically growing, VLM-verified robot skill library |
| 2025, Ella | arXiv | + herd | Social agents with lifelong multimodal memory: knowledge from the community |
| 2026, ELITE | arXiv (preprint) | + | Failure trajectories converted into reusable competence |
| 2026, PRACTICE | arXiv (preprint) | + | Experience-to-skill conversion itself is learned, not hand-coded |
| [FT] 2026, Grounded Autonomous Research | arXiv (preprint) | -/fix | Verified: 2,162 literature accesses did not prevent an unwritten "0.066 vs 0.176" comparison; grounding = enforced numerical confrontation at checkpoints; single-run study |
| Shinn et al. 2023, Reflexion | NeurIPS 2023 | + memory | Verbal reflection on external feedback stored in episodic memory; needs an environment that says "wrong" |
| Zhao et al. 2024, ExpeL | AAAI 2024 | + memory | Cross-task written insights from success/failure comparison; git-as-memory formalized |
| Schick et al. 2023, Toolformer | NeurIPS 2023 | + body | Self-supervised tool adoption by loss reduction; delegation replaces scale |
| Park et al. 2023, Generative Agents | UIST 2023 (Best Paper) | + herd | 25 agents with memory + reflection produce emergent collective behavior; believability, not verified reasoning |

### Round 8 - Do LLMs think? Hinton and Lemoine claims, pro and contra

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| Strachan et al. 2024, Testing ToM in LLMs and Humans | Nature Human Behaviour | + functional | GPT-4 at or above humans on 4 of 5 ToM batteries; faux pas failure = hyperconservatism, not missing inference |
| Kosinski 2024, Evaluating LLMs in ToM Tasks | PNAS | + behavioral | GPT-4 solves 75% of bespoke false-belief tasks (6-year-old level) |
| Street et al. 2025, Higher-Order ToM | Frontiers Hum Neurosci | + functional | Adult-level up to 6th order; co-authored by the Google exec who rejected Lemoine |
| [FT] Lindsey 2026, Emergent Introspective Awareness | arXiv (Anthropic, preprint) | +/- narrow | Claude Opus 4/4.1 detect injected concepts ~20% of the time; rest "may still be confabulated" |
| [FT] Kaiser & Enderby 2026, No Self-Reported Sentience | arXiv (preprint) | - | Models deny sentience and activation classifiers show the denials are sincere, 0.6B-70B |
| [FT] Chalmers 2023, Could an LLM be Conscious? | Boston Review / arXiv | +/- framework | Missing: recurrence, global workspace, unified agency, world- and self-models; LLM+ within a decade plausible |
| Mitchell & Krakauer 2023, Debate Over Understanding | PNAS | +/- diagnosis | "Understanding" undefined at the evidence level both camps cite; new vocabulary needed |
| Thoppilan et al. 2022, LaMDA | arXiv (Google report) | context | 137B dialogue model fine-tuned for engaging conversation; every Chalmers feature missing |
| Marchetti et al. 2025, Illusion of Understanding (review) | Cyberpsychology, Behavior, Social Networking | - systematic | First-order strong, higher-order and perturbation brittle across the literature |
| Harnad 2025, Language Writ Large | Frontiers in AI | - theoretical | Symbol grounding: text-only cannot understand; the scholarly basis for the embodiment requirement |
| Beckmann & Queloz 2025, Mechanistic Indicators of Understanding | arXiv (preprint) | + mechanistic | Circuits tracking world structure as graded understanding; silent on experience |
| Hojer 2025, On the Notion that LMs Reason | arXiv (preprint) | - conceptual | "Reasoning" definitions inconsistent with the Markov-kernel mechanism |
| [FT] Lerchner 2026, The Abstraction Fallacy | PhilArchive (preprint) | - theoretical | Computation is mapmaker-dependent; simulation never becomes instantiation; embodiment concedes only referential grounding; AGI as "non-sentient tool" |
| [FT] Deva 2026, Hearing the Bell Ring Back | PhilArchive (preprint) | +/- framework | Concedes Lerchner in full; receiver-side formalism (free energy, channel, SDT, PID) with pre-registered P1-P4 protocol for loop-closure rate rho; no results yet |

### Round 9 - Reasoning traces, ICL as algorithm, 2026 updates (2026-09-05)

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Jiralerspong, Kondrup & Bengio 2026, Noticing the Watcher | ICLR 2026 AIWILD (workshop) | +/- situational | Claude agents infer hidden CoT monitoring from blocking feedback alone (confident awareness up to 19% of episodes, 4.5-generation models); obfuscation intent in 3 of 2,400 episodes; 0% evasion success |
| [FT] Kim et al. 2026, Latent Veracity Inference | ICLR 2026 | +/- verification | Veracity Search + amortized verifier flag wrong reasoning steps (ProntoQA, GSM8K, CommonsenseQA); engineered search + pseudo-label SFT, not a native faculty |
| [FT] Yoon et al. 2025, Monte Carlo Tree Diffusion | ICML 2025 (PMLR 267) | +/- planning | MCTS over partially denoised plans; greedy ablation 0% vs MCTD 100% on giant mazes; search machinery explicit, not emergent |
| [FT] Sourav & Balwani 2026, The Tell-Tale Trace | arXiv (preprint) | +/- detection | CoT dynamics (premature verification collapse) flag SAT failures before answer emission; proof-search prompt lifts Llama3-70B 13.3% -> 85%; oracle-assisted intervention |
| [FT] Chen et al. 2026, When the Chain Breaks (ReasonDiag) | Computer Graphics Forum 45(3) | tool | Retrieval fact-check + Z3 symbolic validation pipeline (recall 0.801, precision 0.306) plus human-in-the-loop diagnosis; detection is engineered, humans close the precision gap |
| [FT] Xu, Jettkant & Ruis 2026, The Depth Ceiling | COLM 2026 | +/- latent ceiling | Unsupervised latent planning depth: 3 steps (tiny transformers) to 7 (GPT-5.4 few-shot); discovery ceiling 5, generalization 8; dense supervision bypasses discovery |
| [FT] Yue et al. 2025, Does RL Really Incentivize Reasoning? | NeurIPS 2025 (Oral) | + key pass@k | Base models catch up and surpass RLVR twins at large pass@k on all benchmarks (Minerva 32B: base +9% at k=128); RLVR narrows coverage; hardest-problem CoTs verified manually |
| [FT] Hojer et al. 2025, Representation Engineering Reasoning | ICLR 2025 | +/- latent extract | Control vectors from residual-stream activations improve reasoning on Pythia-1.4B/2.8B and Mistral-7B; vectors derived from task data, no weight training |
| [FT] Todd et al. 2026, In-Context Algebra | ICLR 2026 | +/- procedure | Tokens as pure variables (finite groups): near-perfect accuracy, unseen-group generalization; causally isolated mechanisms (copying head, identity recognition, closure cancellation); task-family training required |
| Garg et al. 2022, What Can Transformers Learn In-Context? | NeurIPS 2022 | +/- frame | Function classes learned in-context, inference-time only; the empirical baseline for the ICL-as-algorithm line |
| [FT] Akyurek et al. 2023, What Learning Algorithm is ICL? | ICLR 2023 | +/- formal | Transformers can implement GD steps (O(d) hidden, constant depth) and ridge updates (O(d^2)); trained ICL transitions between predictors, Bayesian at scale; intermediate quantities decodable |
| Sileo et al. 2026, Reasoning Core | arXiv (preprint) | tool | 50 procedural generators (math, logic, planning, state tracking, formal languages, code) with difficulty controls; completion-supervised training study incl. OLMo-1B |
| Hodel 2024, ARC Procedural Example Generation | arXiv (preprint) | tool | Per-task generators for all 400 ARC training tasks; Condition 2 infrastructure |
| Moffitt 2025, ARC-GEN | arXiv (preprint) | tool | Mimetic procedural ARC generator, open source; intra-task sample scarcity fix |
| Elazar et al. 2024, WIMBD | ICLR 2024 | tool | Count + search at scale over >35 TB of corpora; contamination audit backbone for the pilot |

## Verdict addendum: round 9 - reasoning traces, ICL as algorithm, 2026 updates (2026-09-05)

- **Hidden-monitor inference** (Noticing the Watcher): pretrained agents can infer an
  unobserved monitoring mechanism from indirect feedback - functional in-context
  inference. The side objective was experimenter-supplied, the scaffold (repeated
  attempts, blocking signal, accumulated transcripts) supplies most of the signal, and
  all 3 obfuscation-intent episodes failed to conceal anything (0% evasion).
- **Reasoning-error detection** (Latent Veracity Inference; Tell-Tale Trace;
  ReasonDiag): step-level error detection works, but only engineered - inference-time
  search plus trained verifiers, trajectory-dynamics analysis with solver ground truth,
  or external fact-checking plus an SMT solver with humans closing the precision gap.
  Confirms the round 5 pattern: validation is not native.
- **Explicit planning** (Monte Carlo Tree Diffusion): built-in search improves plans
  with inference-time compute; says nothing about unassisted forward passes.
- **Latent-depth ceiling** (The Depth Ceiling): peer-reviewed quantification that
  unsupervised latent planning stays shallow (3-5 steps trained, 8 executed) and that
  dense teaching bypasses the bottleneck - the mirror of "out of the box": deep
  reasoning must be taught or externalized.
- **RLVR boundary** (Yue et al., NeurIPS 2025 oral): at large sampling budgets base
  models match and surpass their RLVR twins on every benchmark - RL narrows coverage
  rather than creating reasoning. Strengthens the elicitation-only consensus of
  rounds 1 and 4 with pass@k evidence.
- **ICL as algorithm** (Garg 2022; Akyurek 2023; Todd et al. 2026): transformers can
  implement and mechanistically reveal real learning algorithms over in-context
  variables, but always with demonstrations in the prompt or task-family training.
  "In-context" generality is demonstrated; "out of the box" is not.
- **Study infrastructure** (Hodel; Moffitt; Elazar et al.; Sileo et al.): ARC task
  generators, corpus-audit platform, and 50 procedural reasoning generators - the
  components the pre-registrable study design (docs/study-design.md) requires.
- None of the fifteen meets the three acceptance criteria (peer-reviewed only where
  noted, all on models with undisclosed or task-trained data, none demonstrates
  untrained out-of-the-box reasoning). Classification: reasoning traces in pretrained,
  scaffolded, or engineered settings; formal frames; study infrastructure. Overall
  verdict unchanged.

## Verdict addendum: thinking, validation, and unique ideas (2026-09-03)

- **How LLMs think**: amortized pattern completion plus generated-token sequential compute
  (rounds 1, 3, 4). "Thinking" in reasoning models is additional sampling, not a new
  faculty.
- **How LLMs validate ideas**: they do not natively. Intrinsic self-correction degrades
  accuracy; what works is external grounding (tools, execution, humans - CRITIC, R1-style
  verifiers) or statistical consensus (self-consistency, P(True)), both of which validate
  against the model's own prior, not the world.
- **Unique ideas**: LLMs reliably produce ideas that *read* as novel (blind expert reviews,
  p<0.05) but at roughly average-human divergence, with weak diversity, frame-locking to
  sources, population-level homogenization, and an execution gap. Unique-seeming idea
  production: demonstrated. Unique idea validation and genuinely original idea production
  at scale: not demonstrated.
- **Do they think / feel (Hinton, Lemoine)**: functional understanding is partially
  supported as a graded, non-human kind (adult-level ToM, world-tracking circuits) and
  contested on robustness and grounding. Subjective experience is not supported: the 2026
  frontier evidence shows narrow, causally verified introspection (~20%, Claude Opus 4/4.1)
  with explicit confabulation, and open models sincerely deny sentience when checked
  internally. Both claims were made about disembodied, memory-less chat systems; the
  systems that could change the answer are the agentic ones in round 7. Full claim ledger:
  [docs/claims-hinton-lemoine.md](../docs/claims-hinton-lemoine.md).

## Verdict addendum: the Abstraction Fallacy debate (2026-09-06)

- **Lerchner, The Abstraction Fallacy** (PhilArchive preprint; Google DeepMind author,
  personal-views disclaimer): a conceptual argument that computation presupposes an
  experiencing "mapmaker", so scaling syntax never yields experience. Extends Harnad's
  grounding argument (round 8) from semantics to ontology, and concedes that embodiment
  solves referential grounding - the precise gap Deva builds on. It is not empirical:
  no experiment, no measurement; conceptual analyses are not the kind of thing evidence
  overturns (as Deva notes). PhilArchive is unmoderated: the 2026 response cluster
  (7+ PhilPapers-listed manuscripts, several with likely AI-generated author names) is
  likewise entirely preprint. Not peer-reviewed literature.
- **Deva, Hearing the Bell Ring Back** (PhilArchive preprint): accepts Lerchner's four
  theses and formalizes only the referential register Lerchner concedes: a four-layer
  receiver-side formalism and a falsifiable, pre-registered protocol (P1-P4, kill
  conditions) for a loop-closure rate rho in bits per turn on human-AI dialogues.
  No results yet; "rho > 0 does not imply consciousness anywhere in the loop".
- **Verdict impact: none.** Neither paper addresses out-of-the-box reasoning, disclosed
  training data, or any of the three acceptance criteria. Round 8's consciousness
  balance gains its sharpest anti-functionalist statement plus a measurement framework
  the thesis program may reuse for the M4 human-baseline arm; the overall verdict is
  unchanged.

## The biological analogy - what cognitive science says

- Spelke's core-knowledge research (What Babies Know, OUP 2022; BBS 2023): humans and many
  animals reason from evolution-installed domain systems (objects, agents, space, number)
  present before individual learning. But evolution is a selection process over architectures,
  not next-token training - the analogy holds at the level of "installs priors before
  individual experience," fails at data efficiency and novelty handling.
- Animal cognition literature (exclusion, transitive inference in primates/corvids) is itself
  contested between "genuine reasoning" and "associative learning" readings - the same debate
  as for LLMs, with the same unresolved measurement problem.
- The one clean disanalogy: a child infers an ARC-style rule from two examples with zero
  search budget; o3 needed massive test-time compute at ~$4,560/task (Dec 2024) for
  near-human ARC-AGI-1 scores. Architecture-plus-feeble-data beats data-plus-brute-compute,
  for now.

## What the demanded paper would need (open problem spec)

1. Base model, no instruction tuning, no RL, no reasoning-template prompting.
2. Tasks generated after the training cutoff AND generated procedurally with held-out
   generator seeds (ARC-style), with a human baseline.
3. Process-level evidence: causal/ablation-based demonstration that the computation is an
   algorithm (a la Nanda), not path retrieval (a la Faith and Fate).
4. Faithfulness controls (a la Lanham/Turpin), since verbalized CoT is not evidence.
5. Depth/novelty generalization beyond any plausible training pattern (the
   length-generalization barrier makes this formally hard).

As of 2026-09-02, no published work meets all five conditions. Nearest misses:
2212.09196 (meets 1-2, partially 5; no process-level proof), 2402.10200 (meets 1 and
partially 5; no novel-task generation), 2301.05217 (meets 3-4; toy task, task training).

A pre-registrable protocol implementing all five conditions (open-data models, Dolma
contamination audit, depth ladders, activation patching, decision table) is drafted in
[docs/study-design.md](../docs/study-design.md).

## Source notes

- arXiv IDs in filenames map 1:1 to https://arxiv.org/abs/<id>.
- PhilPapers records use `pp<RECORD>` filenames mapping to https://philpapers.org/rec/<RECORD>;
  PhilArchive-only papers carry no arXiv ID and are preprints.
- [FT] = full-text passages read and quoted via firecrawl research read-paper.
- Peer-review status: NeurIPS/ICLR/ICML/COLM/Nature Human Behaviour/Nature = peer-reviewed;
  arXiv-only items are flagged as preprints in their entries.
