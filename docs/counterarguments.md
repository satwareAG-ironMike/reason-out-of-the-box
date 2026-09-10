# Counterargument ledger: what the record says when someone says "no evidence"

Status: 2026-09-10. Companion to the [acceptance criteria](acceptance-criteria.md) and the
[archive verdict](../archive/INDEX.md). Every source below is either an archive entry (venue
and peer-review status as recorded there, `[FT]` = quotes verified against full text) or a
non-archive source whose identifier was verified by API on the date above (PubMed, arXiv,
DOI). The numbers are the ones carried in the archive; nothing here is paraphrased upward.

## Why this page exists

The headline verdict of this repository reads: the strict claim is unmet. That sentence is
routinely read as "there is no evidence that LLMs reason". The reading conflates five claims
of very different strength. Only the fifth is what the verdict is about. The first four have
peer-reviewed answers, and the answers cut in both directions: they refute the dismissal
("just a stochastic machine") as firmly as they refute the marketing ("it reasons like a
person"). This page separates the claims, states the evidence status of each, and then takes
the recurring counterarguments in their strongest form.

## The claim ladder

| # | Claim | Status | Evidence (archive unless marked) |
|---|-------|--------|----------------------------------|
| C1 | LLMs solve novel instances of reasoning tasks above chance, often at human level, when the competence is elicited (prompting, decoding, or RL) | Established, peer-reviewed | [Webb, Holyoak and Lu 2023](../archive/round1-base-model-emergence/2212.09196-webb-holyoak-lu-analogical.md) `[FT]`, Nature Human Behaviour: GPT-3 beats UCLA students zero-shot on novel Raven-style digit matrices. [Wang and Zhou 2024](../archive/round1-base-model-emergence/2402.10200-wang-zhou-cot-decoding.md) `[FT]`, NeurIPS 2024: reasoning paths surface by changing the decoding alone, no prompt. [Kojima et al. 2022](../archive/round1-base-model-emergence/2205.11916-kojima-zero-shot-reasoners.md) `[FT]`, NeurIPS 2022. [Zhang et al. 2024, GSM1k](../archive/round2-skeptical/2405.00332-zhang-gsm1k.md) `[FT]`, NeurIPS 2024: on guaranteed-unseen problems, drops of up to 8%, and even overfit models solve more than half. [DeepSeek-R1](../archive/round4-mechanistic-recent/2501.12948-deepseek-r1.md), Nature 2025 (PMID 40962978) |
| C2 | Part of what they do is an algorithm, not a lookup | Established at toy scale with fully known training data; suggestive at LLM scale | [Nanda et al. 2023](../archive/round4-mechanistic-recent/2301.05217-nanda-grokking-mechanistic.md) `[FT]`, ICLR 2023 oral: modular-arithmetic circuits reverse-engineered, Fourier features, from a training set that is fully known. [Olsson et al. 2022](../archive/round4-mechanistic-recent/2209.11895-olsson-induction-heads.md) (preprint): induction heads form spontaneously in pretraining. [Akyurek et al. 2023](../archive/round9-reasoning-traces/2211.15661-akyurek-what-learning-algorithm-is-icl.md), ICLR 2023, and [Garg et al. 2022](../archive/round9-reasoning-traces/2208.01066-garg-what-can-transformers-learn-in-context.md), NeurIPS 2022: in-context learning implements identifiable learning algorithms. [Liu et al. 2025](../archive/round4-mechanistic-recent/2503.20783-liu-r1-zero-critical.md) `[FT]`, COLM 2025: base models already solve the math problems that RL later "unlocks" |
| C3 | The competence is bounded, and part of it is pattern matching | Established, peer-reviewed | [Dziri et al. 2023, Faith and Fate](../archive/round2-skeptical/2305.18654-dziri-faith-and-fate.md) `[FT]`, NeurIPS 2023: collapse one step beyond trained depth. [McCoy et al. 2023, Embers](../archive/round2-skeptical/2309.13638-mccoy-embers-autoregression.md) `[FT]`, ICLR 2024: accuracy tracks answer probability. [Mirzadeh et al. 2024, GSM-Symbolic](../archive/round2-skeptical/2410.05229-mirzadeh-gsm-symbolic.md) `[FT]`, ICLR 2025: about 10% drop on fresh variants, up to 65% with an irrelevant clause. [Merrill and Sabharwal 2024](../archive/round3-theory-faithfulness/2310.07923-merrill-sabharwal-expressive-power.md) `[FT]`, ICLR 2024: one forward pass is TC0. [Kraus et al. 2026](../archive/round3-theory-faithfulness/2604.25800-barriers-universal-reasoning.md) `[FT]` (preprint): learnable CoT length-generalizes only within TC0 under standard positional encodings. Non-archive: Wu et al. 2024, Reasoning or Reciting (NAACL 2024, arXiv 2307.02477); Shojaee et al. 2025, The Illusion of Thinking (NeurIPS 2025, arXiv 2506.06941) |
| C4 | The written chain of thought is not reliable evidence of the computation | Established | [Turpin et al. 2023](../archive/round3-theory-faithfulness/2305.04388-turpin-dont-say-what-think.md) `[FT]`, NeurIPS 2023. [Lanham et al. 2023](../archive/round3-theory-faithfulness/2307.13702-lanham-faithfulness.md) (preprint). [Pfau et al. 2024](../archive/round3-theory-faithfulness/2404.15758-pfau-dot-by-dot.md) (preprint): filler tokens can carry hidden computation. Non-archive: Du et al. 2026, Legibility is Not Interpretability (COLM 2026, arXiv 2609.04194) |
| C5 | A base model, with no instruction tuning, no RL and no reasoning prompt, reasons on procedurally novel tasks beyond its trained depth through an internal algorithm, on a model whose training data is public so contamination can be excluded | **Untested.** No paper meets the [three criteria](acceptance-criteria.md) | This is the only claim the headline verdict is about. The experiment that would settle it is [study-design.md](study-design.md); the archive's positive results all run on closed-data models (transparency audit in the acceptance criteria) |

Reading rule: "LLMs cannot reason" is the negation of C1 and is refuted by peer-reviewed work.
"LLMs reason like people" claims more than C1-C4 support and is refuted by the same body of
work. "Nobody has shown a base model reasons out of the box" is C5 and is correct today.

## The counterarguments, steelmanned

Each entry gives the objection in its strongest form, what the record says, what this
repository concedes, and what remains open.

### 1. "It is a stochastic machine. Next-token prediction cannot reason."

- **Record.** The training objective does not bound the computation the network performs.
  Nanda et al. (ICLR 2023) reverse-engineered a trained transformer executing modular
  addition through a Fourier-basis algorithm that nobody wrote down; Olsson et al. showed
  induction circuits forming in pretraining; Akyurek et al. (ICLR 2023) and Garg et al.
  (NeurIPS 2022) showed in-context learning implementing gradient-descent-like and
  closed-form learners. Sampling from a distribution is how the output is produced, not a
  description of what computes it. The philosophical version of the objection, Bender and
  Koller 2020 (ACL 2020, DOI 10.18653/v1/2020.acl-main.463) and Bender et al. 2021
  (FAccT 2021, DOI 10.1145/3442188.3445922), is a claim about meaning and grounding, not a
  measurement of problem-solving.
- **Conceded.** At depth, the behavior has the signatures of pattern matching: cliffs one
  step beyond the trained depth (Dziri et al.), sensitivity to answer frequency (McCoy et
  al.) and to irrelevant clauses (Mirzadeh et al.). Both mechanisms coexist.
- **Open.** Whether the algorithmic part exists in a base model without elicitation and
  beyond its trained depth (C5).

### 2. "Show me one new idea that never appeared on the internet."

- **Record.** Machine-verified novel mathematics exists in peer-reviewed venues:
  Romera-Paredes et al. 2024, FunSearch (Nature 625:468-475, PMID 38096900) produced
  cap-set constructions larger than any previously known and improved bin-packing
  heuristics, each checked by construction; Trinh et al. 2024, AlphaGeometry (Nature
  625:476-482, PMID 38233616) solved 25 of 30 IMO geometry problems after training on
  synthetic data only, no human demonstrations; Hubert et al. 2026, AlphaProof (Nature
  651:607-613, PMID 41225005) reached IMO silver-medal level in formal mathematics with RL.
  AlphaEvolve (arXiv 2506.13131, preprint) reports a 48-multiplication algorithm for 4x4
  complex matrices, below the 49 of Strassen's 1969 construction. On ideas rather than
  theorems: LLM-generated research ideas were rated more novel than expert ideas in a
  blind review ([Si et al.](../archive/round6-unique-ideas/2409.04109-si-novel-research-ideas.md),
  ICLR 2025) but underperformed on execution
  ([follow-up](../archive/round6-unique-ideas/2506.20803-ideation-execution-gap.md)).
- **Conceded.** Every Nature result above wraps the model in search plus a formal verifier.
  None is a bare model, and none is a base model. That is precisely the elicitation
  distinction this repository draws. "A product I have not seen before" is not a scientific
  criterion; a construction that a checker accepts and that was not in any prior paper is.
- **Open.** Whether the model or the scaffold deserves the credit (see 6).

### 3. "Your own repository says there is no evidence."

- **Record.** The verdict sentence is about C5 only. The same archive holds the
  peer-reviewed evidence for C1-C4 and lists it in the README evidence map and in
  [acceptance-criteria.md](acceptance-criteria.md) under "What the peer-reviewed record does
  establish". The repository refutes two positions at once: the dismissal and the hype.
- **Conceded.** The README led with the negative verdict; this page and the README note
  added on 2026-09-10 make the scope explicit.
- **Open.** Nothing; this is a reading error, not an evidence gap.

### 4. "It needs babysitting. It is not autonomous."

- **Record.** Autonomy and reliability are different axes from reasoning. The verdict makes
  no autonomy claim. Reliability limits are documented in the archive: variance across
  instantiations and irrelevant-clause fragility (Mirzadeh et al.), unfaithful traces
  (Turpin et al., Lanham et al.). Agentic evidence lives in round 7 of the archive and is
  not part of the verdict.
- **Conceded.** Fully. Needing correction is compatible with reasoning; humans need it too.
  It is not evidence for or against C1-C5.
- **Open.** Reliability engineering, which is outside this repository's question.

### 5. "The benchmarks are in the training data."

- **Record.** Partly true and measured: GSM1k (NeurIPS 2024) puts the ceiling of the
  contamination effect at drops of up to 8% on guaranteed-unseen problems, with even
  overfit models solving more than half of them. Corpus-side audit tooling exists
  ([Elazar et al., WIMBD](../archive/round9-reasoning-traces/2310.20707-elazar-wimbd.md),
  ICLR 2024). Canary strings alone fail: Anthropic's August 2026 risk report documents
  safety-study transcripts re-entering production training data through forks made before
  the canary was added, with misconfigured filters across several model generations.
- **Conceded.** Contamination cannot be excluded on any closed-data model; that is criterion
  3 of the acceptance criteria and the reason the study design admits only models with
  public corpora (OLMo 2 on Dolma, OLMo 3 on Dolma 3, Pythia on the Pile, Apertus) and
  audits them corpus-side and model-side.
- **Open.** Audit recall for paraphrased or translated instances (study design red-team
  item 1).

### 6. "The scaffold does the work, not the model."

- **Record.** The objection is currently strongest on ARC-AGI-3: ARC Prize's verified
  results of 2026-09-03 put the same GPT-6 Astra at 62.7% under the neutral Standard
  harness and 99.9% under a harness that preserves the provider's opaque reasoning state
  between requests. Marcus reads it as "the harness not the model"; ARC Prize reads it as
  two different questions and now labels both. For the Nature discovery results (2), the
  search and verifier are integral.
- **Conceded.** Credit assignment between model and scaffold is unresolved. The study
  design therefore forbids scaffolds: two primary arms, greedy `Q:/A:` and CoT-decoding,
  no tools, no exemplars, no reasoning prompt.
- **Open.** The same question for every agentic result in the literature.

### 7. "Emergence is a mirage."

- **Record.** [Schaeffer et al. 2023](../archive/round2-skeptical/2304.15004-schaeffer-mirage.md)
  `[FT]`, NeurIPS 2023 outstanding paper: apparent discontinuities often come from
  discontinuous metrics. The result concerns the shape of the scaling curve, not the level
  reached; human-level accuracy under a continuous metric is not a metric artifact.
- **Conceded.** Emergence rhetoric is unreliable; the study design uses continuous accuracy,
  pre-registered thresholds, and reports scaling trends across seven checkpoints instead
  of announcing emergence.
- **Open.** Nothing specific to this repository.

### 8. "Reasoning models collapse on Tower of Hanoi (Apple)."

- **Record.** Shojaee et al. 2025, The Illusion of Thinking (NeurIPS 2025, arXiv
  2506.06941): accuracy collapses beyond a complexity threshold and reasoning effort falls
  near the collapse. A published comment (arXiv 2506.09250, preprint) disputes parts of the
  setup: output-token limits and unsolvable instances counted as failures. Both are cited
  here; the collapse pattern itself is consistent with Faith and Fate and with the TC0
  bound (C3).
- **Conceded.** Depth-bounded competence is the archive's own reading. Condition 5 of the
  study design is exactly a depth test with a pre-registered retention criterion (80% of
  accuracy at the trained depth retained two steps beyond it).
- **Open.** Whether the bound is architectural (positional encoding) or fundamental; the
  archive's theory round says architectural, with signpost tokens and depth-tracking
  encodings as the proposed remedies.

### 9. "Humans and animals reason without training on the task."

- **Record.** Webb et al. compared GPT-3 to students who had years of schooling; every
  human baseline does. Evolution is the training run for the animal case
  ([acceptance criteria](acceptance-criteria.md)). The surviving disanalogy is data
  efficiency: a child infers a rule from two examples; o3 needed massive test-time compute
  per ARC-AGI-1 task.
- **Conceded.** The study tests whether base models match trained humans without task
  training; the biological no-training claim is a separate question (study design red-team
  item 5, child arm listed as future work).
- **Open.** The data-efficiency comparison.

### 10. "This is a marketing era."

- **Record.** The repository holds public claims to the same standard as papers: the
  [Hinton and Lemoine ledger](claims-hinton-lemoine.md) and the
  [Marcus ledger](claims-marcus-wall.md) record what was said, with dates, and judge it
  against the archive. The verdict line is anti-hype by construction, and every archive
  entry carries an explicit peer-review flag; preprints are marked as such.
- **Conceded.** Vendor claims outrun the evidence; the acceptance criteria exclude them
  (criterion 1), and the transparency audit shows every positive result rests on closed
  data (criterion 3).
- **Open.** Nothing; the objection and this repository agree.

## Using this page in a debate

Ask which claim is meant. "LLMs cannot reason" is refuted by C1-C4 in peer-reviewed venues,
with bounds that the same literature measures. "A base model reasons out of the box with no
elicitation, beyond its trained depth, on auditable data" is C5: nobody has shown it, this
repository says so on its front page, and the pre-registered experiment to test it is the
thesis program tracked in the issue board.

## Sources (non-archive, verified 2026-09-10)

- Romera-Paredes et al., Mathematical discoveries from program search with large language
  models, Nature 625:468-475 (2024), PMID 38096900
- Trinh et al., Solving olympiad geometry without human demonstrations, Nature 625:476-482
  (2024), PMID 38233616
- Hubert et al., Olympiad-level formal mathematical reasoning with reinforcement learning,
  Nature 651:607-613 (2026), PMID 41225005
- Guo et al., DeepSeek-R1 incentivizes reasoning in LLMs through reinforcement learning,
  Nature 645:633-638 (2025), PMID 40962978 (archive entry 2501.12948)
- Novikov et al., AlphaEvolve: A coding agent for scientific and algorithmic discovery,
  arXiv 2506.13131 (2025, preprint)
- Wu et al., Reasoning or Reciting? Exploring the Capabilities and Limitations of Language
  Models Through Counterfactual Tasks, NAACL 2024, arXiv 2307.02477
- Shojaee et al., The Illusion of Thinking, NeurIPS 2025, arXiv 2506.06941; comment: arXiv
  2506.09250 (preprint)
- Du et al., Legibility is Not Interpretability: Comparing Judged and Actual Importance in
  Chain-of-Thought Reasoning, COLM 2026, arXiv 2609.04194
- Bender and Koller, Climbing towards NLU, ACL 2020, DOI 10.18653/v1/2020.acl-main.463;
  Bender et al., On the Dangers of Stochastic Parrots, FAccT 2021, DOI
  10.1145/3442188.3445922
- Anthropic, Risk Report August 2026 (anthropic.com/aug-2026-risk-report), section on
  alignment-faking transcripts re-entering training corpora
- ARC Prize, OpenAI's GPT-6 Astra on ARC-AGI-3 (arcprize.org/blog/astra, 2026-09-03) and
  verified results (arcprize.org/results/openai-gpt-6-astra)
