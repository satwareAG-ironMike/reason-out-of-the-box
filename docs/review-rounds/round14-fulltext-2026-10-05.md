# Full-text verification record - round 14 (2026-10-05)

Scope: the 15 arXiv entries in [archive/round14-latent-reasoning-2026/](../../archive/round14-latent-reasoning-2026/),
verified this pass against the arXiv HTML full texts (not abstracts). Follows
[docs/agent-execution.md](../agent-execution.md) section 5; this pass is separate from the
2026-09-28 abstract-level review ([round14-2026-09-28.md](round14-2026-09-28.md)).
Outcome: 15/15 entries upgrade to `[FT]`, 0 discrepancies.

## Method

- Each paper's full text was fetched on 2026-10-05 from `https://arxiv.org/html/<id>` (all 15
  had HTML renderings; titles matched the entry records).
- HTML was converted to plain text (tags stripped). First conversion also stripped `<math>`
  element contents; numeric claims rendered as MathML in 2609.00738 and 2609.16055 were then
  re-extracted with math annotations (`annotation`/LaTeX) preserved before verdicts. A plain
  `grep -i` with `.` as wildcard initially masked a `1.34`/`2.51` miss in 2609.16055; the
  literal-regex re-check caught it. Lesson: verify numeric claims with literal patterns and
  math-preserving conversion.
- Each entry's "Key findings" claims were checked against the full text: numeric equality,
  bounded wording ("up to"), benchmark and model names, direction of effects.
- Venue / peer-review metadata was not re-adjudicated (arXiv comments-level evidence only;
  unchanged from the 2026-09-28 record, incl. the retracted working-note claim on 2609.13997).

## Per-entry confrontation (against full text)

| Entry | Load-bearing claims checked | Full-text evidence | Disposition |
|---|---|---|---|
| 2305.10601 ToT (Yao et al.) | Game of 24 4% CoT -> 74% ToT; exploration/backtracking; three tasks | Abstract + Table 2: "IO 7.3%, CoT 4.0%, ToT (b=5) 74%"; backtracking described in method | accepted |
| 2412.06769 Coconut (Hao et al.) | Hidden state fed back as input embedding; BFS over multiple next steps; beats CoT on logical tasks | "continuous thought can encode multiple alternative next reasoning steps, allowing ... breadth-first search ... rather than prematurely committing" | accepted |
| 2604.22709 Abstract-CoT (Ramji et al.) | Up to 11.6x fewer tokens; reserved abstract vocabulary; warm-up + RL; power law | "10.4-11.6 (MATH-500), 1.9-2.2 (AlpacaEval), 4.0-4.3 (HotpotQA)"; "emergent power law distribution over the abstract vocabulary" | accepted |
| 2608.30462 Cross-lingual SAE (Song et al.) | Suppression impairs, activation partially restores target-language reasoning | "suppressing them should impair source-language reasoning, while activating them should partially recover target-language" | accepted |
| 2609.00738 BASIN (Cheng) | +22pp Game of 24, +6.7pp MuSR over ToT, matched budgets | Abstract (math annotation): "by up to +22 pp on Game of 24 and +6.7 pp on MuSR"; body: "+22pp" Qwen3-27b setting | accepted |
| 2609.01117 LRT (Chen & Fu) | Frozen decoder + small recurrent reasoner; identical budget comparison; beats non-thinking CoT at fraction of compute | "under an identical decoder, prompt, data, and training budget"; "at a small fraction of its inference compute" | accepted |
| 2609.03342 GAR (Zheng et al.) | Cosine gradient reward, <9% overhead; decomposition; Qwen3-4B/8B, GPQA Diamond, MMLU-Pro | "dense, reasoning-aware reward with less than 9% wall-clock overhead"; "multiplicative decomposition into prediction-error and ..."; "On Qwen3-4B and 8B base models" | accepted |
| 2609.03633 Spurious CoT termination (Koh et al.) | Injected EoT does not switch phases; attention is operative (EAB); 4 LRMs, 5 benchmarks, 2 methods | "Across four LRMs, five benchmarks, and two early-exit methods, increasing attention to the injected EoT reduces spurious CoT ..." | accepted |
| 2609.05111 Bayesian unification (Fan) | One Bayes/Gibbs + forward-KL template; granularity prediction; reward-weighted equivalence chain | "few-shot ICL is an amortized projection onto the Bayes posterior predictive, and reward-weighted SFT, reward-weighted ICL, and advantage-weighted SFT are forward-KL projections of reward-induced Gibbs poste..." | accepted |
| 2609.07821 A*-Thought-V2 (Xu et al.) | +2.6% avg acc, ~2x shorter, 2.29x ACU; Qwen3.5-9B/Qwen3.6-27B | "Up to 2.6% accuracy gain and 2.29 ACU improvement"; "reducing response length by up to half, increasing Accuracy per Computation Unit by 2.29" | accepted |
| 2609.12317 DF-Sample (Mi & Huang) | GPQA 45.6 vs 38.9 power sampling vs 39.9 GRPO; training-free; 3 models 4 benchmarks | "DF-Sample achieves 45.6% accuracy, surpassing power sampling (38.9%) and GRPO (39.9%)"; "Across three models and four benchmarks" | accepted |
| 2609.13997 Teacher RLVR (Zhu et al.) | 128 unsolvable ~ 2,000-corpus GRPO (~16x); backward chaining; Monotone Frontier Curriculum | "Training on only 128 unsolvable problems matches or exceeds GRPO trained on a full 2,000-problem corpus (~16x data efficiency)" | accepted |
| 2609.16055 State of Thought (Gong et al.) | 582-param controller; 1.34x-2.51x gains; -62.6% tokens, -44.6% latency; 38.2%/36.5% retained | Math annotations: "1.34x ... 2.51x", "reducing generated tokens by 62.6% and end-to-end latency by 44.6%", "retains 38.2% / 36.5% mean accuracy gains"; "582-parameter controller" | accepted |
| 2609.19717 ATC (Gatmiry et al.) | No scratchpad supervision; parity theory under single-layer softmax attention; graph reachability + arithmetic | Sections "ATC for Predicting Parity", "Shortcut-controlled Graph Reachability Benchmark", "ATC for arithmetic tasks" | accepted |
| 2609.27284 Hunyuan-A13B (Tencent) | 80B total / 13B active MoE; 20T filtered corpus; SFT + RL; dual-mode | "total parameter count of 80 billion ... activating only 13 billion"; "pretrained on a rigorously filtered 20T token corpus with enhanced STEM-focused data curation"; dual-mode fast/slow thinking | accepted |

## Verdict

- 15/15 accepted, 0 corrections: every "Key findings" claim matches the paper's own full text.
- All 15 entries marked `[FT]` (heading "verified from full text", Archived line
  "full text verified 2026-10-05"); INDEX round-14 rows prefixed `[FT]`.
- Verdict unchanged: none of the 15 meets the five acceptance conditions; the core H1 gap
  (genuinely novel procedural reasoning, zero elicitation) remains unfilled.
- Caveat kept: `[FT]` attests that the entry's claims match the paper, not that the paper's
  results replicate.
