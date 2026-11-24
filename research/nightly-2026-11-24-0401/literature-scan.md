# Literature scan - round 85 (2026-11-24 04:01 firing, nightly lane, issue #65)

Question this scan serves: at or past a build's measured depth wall, do the four
instruction arms (baseline, ban, negated ban, permission) change the verdict, or only
the delivery surface? (The round's README carries the full statement.)

Tools and call count. OpenAlex API only (free scholarly API), title-and-abstract
search, three queries. The three queries were run once during instrument design
(pre-dispatch recon) and once again after dispatch (the recorded set below): six
OpenAlex calls total this round, inside the 12-call scholarly-API cap. No arXiv or
Crossref calls this round. Dates: 2026-11-24.

## Query 1: "overthinking large language model reasoning"

| Record | Year | Relevance |
|---|---|---|
| BadThink: Triggered Overthinking Attacks on Chain-of-Thought Reasoning in Large Language Models (arXiv:2511.10714; AAAI 2026, 10.1609/aaai.v40i38.40486) | 2025/2026 | Nearest prior art on instruction-induced reasoning-length change: prompt triggers that force extra reasoning. Its design tests the over- side of the length knob only; a ban arm (less reasoning) is not part of it. |
| Mitigating Overthinking in Large Reasoning Language Models via Reasoning Path Deviation Monitoring (arXiv:2603.14251) | 2026 | Monitoring-based mitigation that cuts a reasoning path when it deviates. Confirms a length knob exists; the knob there is a post-hoc monitor, not a pre-registered instruction arm on a frozen build. |
| Reasoning or Overthinking: Evaluating Large Language Models on Financial Sentiment Analysis (10.1145/3768292.3770341) | 2025 | Domain evaluation; not relevant to the instruction-arm contrast. |
| Addressing Overthinking in Large Vision-Language Models via Gated Perception-Reasoning Optimization (arXiv:2601.04442) | 2026 | VLM training-side fix; out of scope for a frozen-build probe. |

## Query 2: "reasoning length accuracy large language model"

| Record | Year | Relevance |
|---|---|---|
| AALC: Large Language Model Efficient Reasoning via Adaptive Accuracy-Length Control (arXiv:2506.20160) | 2025 | The explicit accuracy-length control family: length is a control knob and accuracy tracks it. AALC adapts per example; this round instead holds the instruction fixed and moves the task past the build's own wall, so the knob is not the variable - the depth is. |
| Improving Reasoning Accuracy in Large Language Models via Length-Calibrated Reward (AIBDF 2025, 10.1109/aibdf67964.2025.11440733) | 2025 | RL-side length calibration; supports the accuracy-length coupling as a known training quantity. |
| Reasoning Trace Length and Accuracy in Large Language Models: A Structured Meta-Analysis of Published Benchmarks (SSRN, 10.2139/ssrn.6306758; a ResearchGate copy 10.13140/rg.2.2.24806.08008) | 2026 | Meta-analysis of published benchmarks on trace length vs accuracy. Its tasks sit inside the trained models' distributions; this round's tasks are procedurally novel and past the build's measured wall. |
| Least-to-Most Prompting Enables Complex Reasoning in Large Language Models (arXiv:2205.10625) | 2022 | Classic decomposition result; background only. |
| Fast-Slow Thinking GRPO for Large Vision-Language Model Reasoning (10.52202/085713-5712) | 2025 | Training-side; out of scope. |

## Query 3: "chain of thought length generalization depth"

| Record | Year | Relevance |
|---|---|---|
| Transformers Provably Learn Chain-of-Thought Reasoning with Length Generalization (10.52202/085713-4230) | 2025 | Same title family as the TC0 bound result already in archive/INDEX.md (arXiv:2604.25800); identity between the DOI record and the archived entry was not verified this round. The theoretical bound that motivates placing a panel at the wall. |
| An Asymptotic Theory of Chain-of-Thought in In-Context Learning (arXiv:2606.03217) | 2026 | Asymptotics of CoT length; theoretical prior that length and depth travel together. |
| PAR: Progress-Aligned Recurrence for Length Generalization in State Tracking (arXiv:2610.27628) | 2026 | Architecture-side length generalization; out of scope for a frozen build. |
| The Synergy Dilemma of Long-CoT SFT and RL (arXiv:2507.07562); SABER (AAAI 2026, 10.1609/aaai.v40i41.40799) | 2025/2026 | Post-training trade-offs; out of scope for a frozen build. |

## Novelty narrowing (house convention, per round 84)

- Ironic negation in LLMs is already published (arXiv:2511.12381, ReboundBench; the
  round 84 framing), and forced extra reasoning (overthinking) is a published target
  family (BadThink; the AALC / length-calibrated-reward line).
- This round's delta: (a) the four instruction arms placed at the build's own measured
  depth wall, beyond the frozen grid, where verdicts actually move, instead of on
  solvable benchmark items; (b) the ban arm is part of the contrast - the published
  overthinking family tests only the over- side of the length knob; (c) a per-record
  self-stop band readout (this build's 1,556-1,558 completion-token band) as a
  build-level delivery signature, tracked across arms.
- No archive entry: none of the scanned records evaluates a frozen open build on
  procedurally novel tasks beyond its measured wall under instruction arms. The
  round ships with no archive addition (no verdict change), matching the round 84
  outtake.
