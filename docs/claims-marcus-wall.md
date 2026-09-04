# Claim ledger: "Deep learning is hitting a wall" (Gary Marcus, 2022)

Status: 2026-09-04. Primary sources ingested in full text: the Nautilus essay and two
author retrospectives (Substack). Evidence judged against the archive rounds and
2025-2026 frontier-model studies. Companion to `claims-hinton-lemoine.md`: both ledgers
track prominent public claims about what deep learning can and cannot do.

## Sources

| Date | Source | Kind |
|------|--------|------|
| 2022-03-10 | Marcus, G., "Deep Learning Is Hitting a Wall", Nautilus (nautil.us/deep-learning-is-hitting-a-wall-238440) | Public essay, not peer-reviewed |
| 2025-02-08 | "Five ways in which the last 3 months - and especially the DeepSeek era - have vindicated DLHW", garymarcus.substack.com | Author retrospective |
| 2025-04-07 | "Deep Learning, Deep Scandal", garymarcus.substack.com | Author retrospective |

## What the essay actually claimed (full-text verified)

The essay is routinely misquoted in both directions. It never claims deep learning will
stop improving; it claims pure scaling of the LLM architecture will not reach AGI and
that new techniques are required.

| # | Claim | In-essay evidence cited |
|---|-------|------------------------|
| 1 | Deep learning is pattern recognition: strong at low-stakes interpolation, brittle on outliers | Hinton radiology prediction unmet by 2022; Tesla stop-sign failure; GPT-3 "You are now dead" completion |
| 2 | Scaling laws are empirical observations, not physical laws | Kaplan et al. 2020 vs. Moore's law slowdown |
| 3 | Scaling was already faltering (2022) on reasoning, truthfulness, toxicity, common sense | Gopher report (arXiv:2112.11446): reasoning gains least from scale; LaMDA report (arXiv:2201.08239) |
| 4 | Symbol manipulation cannot be abandoned; hybrid neurosymbolic systems are the way forward | NetHack Challenge Dec 2021: pure symbolic entry beat best deep learning 3:1; AlphaGo and AlphaFold as existing hybrids |
| 5 | Explicit agnosticism about further leaps | Closes: "for the first time in 40 years, I finally feel some optimism about AI" - via hybrids |

## How the claims aged (against 2026 evidence)

| Claim | Verdict | Key evidence |
|-------|---------|--------------|
| 1: brittleness, outlier failure | **Held** | ARC-AGI-2 (2025-03): humans ~100%, frontier reasoning models 0-4%; contamination and pattern-matching rows of rounds 1-2 |
| 2: scaling laws not universal laws | **Held, now mainstream** | Nadella 2024-11 and Sutskever NeurIPS 2024 repeat it; GPT-5-era pretraining deltas small |
| 3: scaling faltering on reasoning | **Held with refinement** | Pretraining returns diminished post-GPT-4, but progress resumed on a new axis: test-time compute and RL (o1 2024, o3 2024, R1 2025). The wall was routed around, not removed |
| 4: need neurosymbolic hybrids | **Held, demonstrated in constrained domains** | AlphaGeometry (Nature 2024), AlphaProof + AG2 (IMO 2024 silver); R1's rule-based reward system is a proto-neurosymbolic verifier |
| 5: one more leap, then no GPT-4-scale jump | **Broadly consistent** | GPT-5 (2025-08) judged underwhelming; no across-the-board GPT-4-scale jump since 2023 |

Author scorecards confirmed where independently checkable: o3 hallucinated 33% (PersonQA)
to 51% (SimpleQA) and o4-mini 48% to 79% (OpenAI, 2025-04); OpenAI's 2025-09 paper
(arXiv:2509.04664) derives hallucination from training/eval incentives. One Marcus data
point remains unverified and must not be cited as fact: the 2025-04 Llama 4
benchmark-gaming rumor, flagged by Marcus himself as unverified.

## Papers uncovered: archive-worthiness assessment

None of the essay's citations are positive out-of-the-box reasoning evidence, so none
changes the verdict. Assessed against the acceptance criteria (peer-review status,
no reasoning-example training, disclosed data):

| Paper | Status | Assessment |
|-------|--------|-----------|
| Kaplan et al., Scaling Laws for Neural Language Models (arXiv:2001.08361, 2020) | Preprint | Context for claim 2; superseded by Chinchilla-era work; not verdict-relevant |
| Rae et al., Gopher (arXiv:2112.11446, 2021) | Preprint | Negative evidence: logical reasoning benefits least from scale; precursor of archive round 2 skepticism |
| Thoppilan et al., LaMDA (arXiv:2201.08239, 2022) | Preprint | Already referenced in `claims-hinton-lemoine.md`; no separate entry needed |
| Razeghi et al., Pretraining Term Frequencies on Few-Shot Reasoning (arXiv:2202.07206, 2022) | Preprint | Direct precursor of the contamination row (numeric frequency correlates with GSM8K accuracy); overlaps 2305.18654 and 2410.05229 |
| Bender et al., On the Dangers of Stochastic Parrots (FAccT 2021, doi:10.1145/3442188.3445922) | Peer-reviewed | Canonical negative position; a defensible round 2 addition, but round 2 already covers stronger empirical versions |
| Schaeffer et al., Are Emergent Abilities of LLMs a Mirage? (arXiv:2304.15004) | Peer-reviewed (NeurIPS 2023, outstanding paper) | **Strongest new candidate**: benchmark-measurement critique, directly relevant to evidence quality across all rounds |
| Trinh et al., AlphaGeometry (Nature, 2024, PMC10794143) | Peer-reviewed | Neurosymbolic positive, but trains on reasoning examples - does not qualify for the central claim; context for hybrid discussion |
| Kalai et al., Why Language Models Hallucinate (arXiv:2509.04664, OpenAI 2025) | Preprint | Structural hallucination theory; reliability row, not reasoning-origin row |

Bottom line: the ingest uncovered no verdict-relevant paper missed by the archive. Two
candidates would pass provenance review if a round 9 (scaling-debate context) is ever
opened: 2304.15004 and the Nature AlphaGeometry paper. Neither meets the central
claim's bar, so the recommended state remains: 63 entries, verdict unchanged.
