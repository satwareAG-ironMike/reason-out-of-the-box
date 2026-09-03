# Acceptance criteria and transparency audit

The project answers a challenge that recurs in public debate: show one peer-reviewed paper
proving an LLM can reason out of the box, without training it on reasoning examples and
hoping it generalizes, the way higher animals reason without prior logic training. A
second, sharper objection follows whenever vendor papers are cited: training data is not
disclosed, so independent verification is impossible. Referee 1 of the DeepSeek-R1 Nature
peer review (published with the paper, Nature 645:633-638, 2025) put it this way:

> "That said, the lack of transparency in the exact training data mixture used may limit
> the reproducibility of this work, and many of the decisions made in the model's
> development are not backed by empirical results explaining their efficacy."

The same review made the authors reduce anthropomorphizing language, add contamination
mitigations, and release a 1,000-example SFT subset; the base training data remained
described as "from the internet."

## Criteria

| # | Criterion | Why it matters |
|---|-----------|----------------|
| 1 | Peer-reviewed | Vendor claims without review do not count |
| 2 | No training on reasoning examples; no prompting tricks | "Trained on examples and hoping it generalizes" is the disputed point |
| 3 | Training data disclosed | Without it, contamination cannot be excluded and independent verification is impossible |

## Verdict (2026-09-03): the strict claim is unmet

No paper in the archive meets all three criteria. Transparency audit of the archive's
positive evidence:

| Positive result | Model | Training data | Criterion 3 |
|-----------------|-------|---------------|-------------|
| Webb, Holyoak & Lu 2023 (Nature Human Behaviour) | GPT-3 text-davinci-003 | closed | no |
| Wang & Zhou 2024 (NeurIPS) | PaLM-2, Mistral-7B | closed | no |
| Kojima et al. 2022 (NeurIPS) | GPT-3 | closed | no |
| Liu et al. 2025 (COLM) | Qwen2.5 base, DeepSeek-V3-Base | closed; the authors themselves suspect QA-text pretraining | no |
| DeepSeek-R1 2025 (Nature) | DeepSeek-V3-Base | "from the internet"; 1k SFT samples released | partial |
| Si, Yang & Hashimoto 2025 (ICLR) | Claude 3.5 Sonnet agent | closed | no |
| Strachan 2024, Kosinski 2024, Street 2025 | GPT-4, LLaMA2, Flan-PaLM | closed | no |
| Lindsey 2026 (introspection) | Claude Opus 4/4.1 | closed | no |
| **Nanda et al. 2023 (ICLR)** | toy transformer, modular arithmetic | **fully known** | **yes, toy scale only** |

Open-data models with published corpora exist (OLMo 2 on Dolma, Pythia on the Pile,
DCLM). No positive out-of-the-box reasoning result on any of them is in the literature.
The experiment that would satisfy all three criteria is specified in
[study-design.md](study-design.md) and requires exactly such models.

## What the peer-reviewed record does establish

- Not parrots: even overfit models solve most guaranteed-unseen GSM1k problems (Zhang et
  al., NeurIPS 2024); RL elicits competence already present after pretraining rather than
  creating it (Liu et al., COLM 2025); real algorithms form under training (Nanda et al.,
  ICLR 2023; Olsson et al. 2022).
- Not proven reasoners: pattern matching collapses beyond trained depth (Dziri et al.,
  NeurIPS 2023); accuracy tracks answer probability (McCoy et al., ICLR 2024) and breaks on
  irrelevant clauses (Mirzadeh et al., ICLR 2025); one forward pass is TC0 (Merrill &
  Sabharwal, ICLR 2024); learnable CoT does not length-generalize past TC0 under standard
  encodings (Kraus et al. 2026, preprint).
- Unique ideas: rated more novel than expert ideas in blind review (Si et al., ICLR 2025)
  but underperform when executed (Si et al. 2025 follow-up); at population scale, human
  divergent creativity is slightly higher (Wang, Huang, Shen & Uzzi 2026).
- The animal analogy cuts both ways: evolution is the training run. The surviving
  disanalogy is data efficiency: a child infers a rule from two examples; o3 needed
  massive test-time compute per ARC-AGI-1 task (December 2024).
