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

## What the verdict does and does not say

The verdict is about one claim: that a **base** model, with no instruction tuning, no RL and
no reasoning prompt, reasons on procedurally novel tasks beyond its trained depth, on a model
whose training data is public. Nobody has shown that. It is not a verdict that LLMs cannot
reason. The peer-reviewed record establishes, with measured bounds, that LLMs solve novel
instances of reasoning tasks at human level when the competence is elicited (Webb et al.,
Nature Human Behaviour 2023; Wang and Zhou, NeurIPS 2024), that real algorithms form inside
trained transformers (Nanda et al., ICLR 2023), that the competence collapses beyond trained
depth and tracks answer frequency (Dziri et al., NeurIPS 2023; McCoy et al., ICLR 2024), and
that written reasoning traces are not evidence of the computation (Turpin et al., NeurIPS
2023). The claim ladder and the ten recurring counterarguments, each in its strongest form,
are in [docs/counterarguments.md](docs/counterarguments.md).

## Layout

| Path | Content |
|------|---------|
| `archive/` | 141 peer-reviewed and preprint papers, 19 thematic rounds, per-paper entries |
| `archive/INDEX.md` | Master catalog, verdict, evidence matrix, open-problem spec |
| `docs/acceptance-criteria.md` | The three criteria (peer-reviewed, no reasoning-example training, disclosed training data) and a transparency audit |
| `docs/counterarguments.md` | Claim ladder C1-C5 with evidence status, and the ten recurring counterarguments steelmanned against the archive |
| `docs/study-design.md` | Pre-registrable protocol for the experiment that would settle the question |
| `docs/analysis-plan.md` | Pre-registration candidate: operationalized decision table (T1-T9), confirmatory/exploratory split, amendment path |
| `docs/preregistration.md` | Pre-registration package (issue #11): OSF computational-layer content, AsPredicted mapping, deviation policy, owner-gated submission record |
| `docs/version-lock-manifest.md` | Version-lock manifest (issue #11): freeze semantics, artifact hashes, model Hub IDs, capture procedure |
| `docs/irb-protocol.md` | IRB protocol draft (issue #7): design, sample size/precision target, recruitment, consent, data handling, privacy, IRB path decision 2026-09-14 |
| `docs/agent-execution.md` | Program operating model (issue #39): full agent execution, 2026 scientific standards (confrontation, verifier independence, Executed/Reproduced/Validated), resource policy, M1-M5 mapping |
| `docs/next-investigations.md` | 2026-09-03, 2026-09-10, 2026-09-11 and 2026-09-14 scans plus the 2026-10-14 substrate-threshold pointer and the 2026-10-16 ladder-depth finding: investigation fields, feasibility audit (closed), frozen model list, round-11 candidates, thesis timeline (M1-M5), fly connectome research, insect-sentience ledger pointer, ladder family budget-limited not depth-limited, the 2026-11-04 ladder-ceiling class-tied reclassification (rounds 42/44/46), the late-2026 weight-space-programming scan and the 2026-11-20 related-work / T7 triangulation scan |
| `docs/claims-hinton-lemoine.md` | Claim ledger: Hinton "AI thinks" and Lemoine/LaMDA, judged against 2026 evidence |
| `docs/claims-marcus-wall.md` | Claim ledger: Marcus "Deep Learning Is Hitting a Wall" (2022), judged against evidence through 2026 |
| `docs/claims-insect-sentience.md` | Claim ledger: insect sentience as a substrate threshold, judged against the round-16 evidence chain |
| `docs/review-rounds/` | Round-level adversarial review records: 3 archive rounds, 2 nightly rounds |
| `generators/` | Condition-2 task generators (issue #4): digit matrices, k-hop ladders and the TRAP arithmetic arm (issue #77 T7), solvability and seed policy, permutation-calibrated leak gate with pinned negative-control fixtures |
| `runs/` | Executed-run record: manifests, raw per-prompt responses, calibration records, regeneration scripts, independent verification records, round report |
| `research/` | Nightly round artifacts (issue #65): one directory per firing with script, prompts, raw responses and scores |
| `explore/` | The open exploratory loop (issue #195): one directory per round with hypothesis, task family, non-reasoning prompts, sampler and budget, scored by the frozen judge; `LEDGER.md` logs one row per round; weekly compute cap and a kill rule on 10 no-gain rounds |
| `scripts/` | Archive consistency, markdown link and serving-id guard checks, each stdlib-only with a `--selftest` negative control |
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
| Mechanistic: real algorithms do form | 2301.05217, 2209.11895, 2607.07316 |
| How LLMs validate ideas (self-correction) | 2310.01798, 2207.05221, 2112.00101, 2303.17651, 2305.11738 |
| Unique idea generation | 2409.04109, 2506.20803, 2606.08251, 2608.19437 |
| Embodied agents: brain + body + herd | 2305.16291, 2606.15497, 2506.24019, 2607.02329, 2303.11366, 2308.10144, 2302.04761, 2304.03442 |
| Do LLMs think or feel (Hinton, Lemoine, and the 2026 scepticism anchor) | PMID 38769463, PMID 39471222, PMID 41551539, 2601.01828, 2601.15334, 2303.07103, 2210.13966, PMID 40013231, 10.1038/d41586-026-03313-7 |
| Novel-task testbed | 2505.11831, 2603.13372 |
| Reasoning traces: hidden-monitor inference, error detection, planning | 2603.16928, 2505.11824, 2502.07202, 2608.03291, 2603.21286, 2604.06427 |
| ICL as algorithm (bounds and mechanisms) | 2208.01066, 2211.15661, 2512.16902 |
| Task generators + corpus audit (study infrastructure) | 2404.07353, 2511.00162, 2310.20707, 2608.05148 |
| Animal analogy: transitive inference and its controls | 1908.06177, 2002.05867, 2210.01240, 2410.20200, 2506.04289, 2611.00387, PMID 18423898, PMID 16248338, PMID 16503340, PMID 28333486 |
| Weight-space programming: obstacle removal, not new reasoning | 2611.05341 |

## Status

Public research archive at https://github.com/satwareAG-ironMike/reason-out-of-the-box
(`main` is branch-protected). The 2026-09-03, 2026-09-10, 2026-09-11 and 2026-09-14 scans,
the 2026-11-04 weight-space-programming field scan and the 2026-11-20 related-work re-scan
re-confirmed the verdict: the late-2026 weight-editing line reads as loop-obstacle removal
rather than a new general reasoning module, so it is no counterexample to the "from nothing"
claim, and the 2026-11-20 related-work re-scan added no study meeting all three acceptance
criteria (its closest "out of the box" framing, OMEGA 2506.18880, uses closed models only and
controls no training data). The 2026-10-16 research finding records the first merged
experimental record, the ladder family being budget-limited rather than depth-limited.

Since 2026-10-16 the research program (issue #65) has recorded rounds to 81 on `main`: the
newest nightly firings in tree are `research/nightly-2026-11-21-0440` (`d_hat` on a pool
endpoint, the round 79 record) and `research/nightly-2026-11-22-0409` (round 81, a zero-prompt
kill report), and since 2026-11-21 the open exploratory loop (issue #195, `explore/`, scored
by the frozen judge of issue #194 and logged one row per round in `explore/LEDGER.md`) carries
the r78, r80 and r81 rows. The weekly compute cap is 80 dispatched prompts a week on the
nightly lane and 400 on the exploratory lane, kill rule 10 consecutive no-gain rounds or the
cap spent; the 2026-W47 audit closed that week over budget on both lanes, 157 of the 80 and
545 of the 400 dispatches, so round 81 ran the kill report and the next dispatch window is
2026-W48 (issue #195). Across the ladder work the measured wall sits in the deployment's
encoding and output
budget rather than in task complexity (round 61 theory mapping): the curve that bends with
depth at constant load is the delivery curve, so the depth ceiling d* cannot be placed from
accuracy (round 50, issue #71); the 2048 cap-bound panel premise is refuted on the current
builds (issue #126) and the generator's k = 49 ceiling is an item-size artifact, not a depth
ceiling (issue #129). The round-51 load-floor reading carries a forward-only erratum (issue
#135). The per-firing ledgers and the round-by-round narrative are in
[CHANGELOG.md](CHANGELOG.md). Two record-integrity rules bind every reading of that archive,
the trace-exposure rule (issue #105) and the forward-only errata rule over immutable raw
records (issue #120), both operative in [research/AGENTS.md](research/AGENTS.md).

The remaining gap is experimental, not bibliographic, and the confirmatory track is blocked: it
has no pinned checkpoint to run on because the local pool serves exploratory-class models only
(issue #196). The open experimental problems are named on the board: the ladder depth ceiling
d* (#71), the missing same-prompt self-agreement control (#100), the audited leak class not
yet widened to relational features (the TRAP corpus arm is shipped, the class widening is
owed, #77), the refuted cap-bound panel premise (#126) and the entity-pool ceiling as an
item-size artifact (#129). The thesis program (study design execution on open-data models) is
tracked in the [issue board](https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues)
under milestones M1 (protocol freeze + pre-registration, 2026-09-30) to M5 (paper + public
release, 2027-04-30); as of 2026-11-22 the M1 computational-layer package is closed in-repo
(issue #11: version-lock manifest pinned, analysis-plan Addendum 1, GATES-M1 ledger) while the
OSF/AsPredicted submission stays owner-gated and the M1 milestone stays open on the IRB path
(#7), M2 (pilot #8, generator half issue #4 partly shipped) is past its 2026-10-31 due date and
open, and M3 is due 2026-12-31; see [docs/next-investigations.md](docs/next-investigations.md).
University students can join the thesis program: apply via bewerbung@satware.com or
message https://github.com/satwareAG-ironMike.
