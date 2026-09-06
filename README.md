# reason-out-of-the-box

[![CI](https://github.com/satwareAG-ironMike/reason-out-of-the-box/actions/workflows/ci.yml/badge.svg)](https://github.com/satwareAG-ironMike/reason-out-of-the-box/actions/workflows/ci.yml)

Research POC answering one question with peer-reviewed evidence:

> Is there a single peer-reviewed paper proving an LLM can reason out of the box - without
> training on reasoning examples - analogous to how higher animals reason without prior
> logic training?

## Verdict (2026-09-02)

No paper satisfies that demand in full. Nearest candidates:
[Webb, Holyoak & Lu 2023](archive/round1-base-model-emergence/2212.09196-webb-holyoak-lu-analogical.md)
(Nature Human Behaviour, zero-shot analogical reasoning vs humans),
[Wang & Zhou 2024](archive/round1-base-model-emergence/2402.10200-wang-zhou-cot-decoding.md)
(NeurIPS, reasoning elicited by decoding alone). The 2025 R1-Zero ablations reframe the
field: reasoning competence is largely latent after pretraining; RL and prompting elicit and
amplify it rather than create it. Every positive result rests on models with undisclosed
training data, so contamination cannot be excluded; the only fully transparent evidence that
transformers learn real algorithms is toy-scale. The strict claim is therefore unmet
([acceptance criteria](docs/acceptance-criteria.md)); the experiment that would settle it is
in [docs/study-design.md](docs/study-design.md).

## Layout

| Path | Content |
|------|---------|
| `archive/` | 78 peer-reviewed and preprint papers, 9 thematic rounds, per-paper entries |
| `archive/INDEX.md` | Master catalog, verdict, evidence matrix, open-problem spec |
| `docs/acceptance-criteria.md` | The three criteria (peer-reviewed, no reasoning-example training, disclosed training data) and a transparency audit |
| `docs/study-design.md` | Pre-registrable protocol for the experiment that would settle the question |
| `docs/next-investigations.md` | 2026-09-03 re-scan: investigation fields, feasibility findings, thesis timeline (M1-M5) |
| `docs/claims-hinton-lemoine.md` | Claim ledger: Hinton "AI thinks" and Lemoine/LaMDA, judged against 2026 evidence |
| `docs/claims-marcus-wall.md` | Claim ledger: Marcus "Deep Learning Is Hitting a Wall" (2022), judged against evidence through 2026 |
| `CHANGELOG.md` | Change history |

## Method

Built with web-grounded multi-round analysis (Perplexity) plus the Firecrawl research suite
for arXiv discovery (`search-papers`), metadata inspection (`inspect-paper`), and full-text
passage verification (`read-paper`). Entries marked `[FT]` in the INDEX contain quotes
verified against the paper's full text; all other entries rest on verified abstracts and
cross-checked secondary sources.

## Key evidence map

| Claim | Papers |
|-------|--------|
| Positive: latent reasoning, elicitation only | 2402.10200, 2212.09196, 2205.11916, 2503.20783, 2504.13837, 2504.19483 |
| Negative: pattern matching, contamination | 2305.18654, 2405.00332, 2410.05229, 2309.13638 |
| Formal limits of a forward pass | 2310.07923, 2402.12875, 2604.25800 |
| Mechanistic: real algorithms do form | 2301.05217, 2209.11895 |
| How LLMs validate ideas (self-correction) | 2310.01798, 2207.05221, 2112.00101, 2303.17651, 2305.11738 |
| Unique idea generation | 2409.04109, 2506.20803, 2606.08251, 2608.19437 |
| Embodied agents: brain + body + herd | 2305.16291, 2606.15497, 2506.24019, 2607.02329, 2303.11366, 2308.10144, 2302.04761, 2304.03442 |
| Do LLMs think or feel (Hinton, Lemoine) | PMID 38769463, PMID 39471222, PMID 41551539, 2601.01828, 2601.15334, 2303.07103, 2210.13966, PMID 40013231 |
| Novel-task testbed | 2505.11831, 2603.13372 |
| Reasoning traces: hidden-monitor inference, error detection, planning | 2603.16928, 2505.11824, 2502.07202, 2608.03291, 2603.21286, 2604.06427 |
| ICL as algorithm (bounds and mechanisms) | 2208.01066, 2211.15661, 2512.16902 |
| Task generators + corpus audit (study infrastructure) | 2404.07353, 2511.00162, 2310.20707, 2608.05148 |

## Status

Public research archive at https://github.com/satwareAG-ironMike/reason-out-of-the-box
(`main` is branch-protected). The 2026-09-03 re-scan re-confirmed the verdict: the
remaining gap is experimental, not bibliographic. The thesis program (study design
execution on open-data models) is tracked in the [issue board](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues)
under milestones M1 (protocol freeze + pre-registration, 2026-09-30) to M5 (paper +
public release, 2027-04-30); see [docs/next-investigations.md](docs/next-investigations.md).
University students can join the thesis program: apply via bewerbung@satware.com or
message https://github.com/satwareAG-ironMike.
