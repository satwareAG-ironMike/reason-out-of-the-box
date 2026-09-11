# Statistical analysis plan (pre-registration candidate)

Status: draft v1.0-candidate (2026-09-11), issue #10, M1 work package. Derived from
[study-design.md](study-design.md) v0.4 (decision table, Conditions 1-5, Amendments v0.4)
and the frozen model list in [next-investigations.md](next-investigations.md)
(feasibility audit, closed 2026-09-10). This document is frozen at the issue #11
pre-registration timestamp; the amendment path is at the bottom. All confirmatory
results in M4 (#14) are computed exactly per this plan; anything not specified here
is exploratory by definition.

## 1. Units of analysis and data model

| Level | Unit | n | Notes |
|-------|------|---|-------|
| Model runs | item response (one forward pass or one decoding tree over one generated item) | 300 items x 5 depth levels x 3 families x 2 primary arms per checkpoint | Items are independent given the checkpoint: fresh context per item, fixed decoding policy, no cross-item state |
| Cell | (checkpoint, family, depth, arm) | 300 item responses | The reporting unit for all accuracy statistics |
| Human baseline | item response, aggregated to participant | >= 40 participants x 60 items per family | Participant is the inference unit for human statistics (within-participant dependence is absorbed by aggregation) |
| Cross-model | confirmatory checkpoint | 7 (OLMo 2 7B/13B/32B; Pythia 1B/2.8B/6.9B/12B `-deduped`) | Model is a unit only in the scale-trend analysis (Section 7) |

Replication checkpoints (OLMo 3 7B/32B) run the identical pipeline; their results are
reported separately and never pooled into the confirmatory verdict (Section 11).

## 2. Primary outcomes and estimands

- **ACC(m, f, d, a)**: per-cell accuracy = correct items / 300, with a two-sided Wilson
  95% confidence interval. Correctness is programmatic (exact-match on the generated
  answer key); no human judgment enters model scoring.
- **d\*(m, f)**: trained-depth ceiling per checkpoint per family, produced by the
  contamination audit (#3) as a LOWER BOUND, with per-layer recall figures (corpus-side
  n-gram/embedding/rule-signature plus model-side raw-completion probes, Amendment v0.4
  item 2). The audit must hold out by domain, not only by time: temporal hold-outs do not
  remove pretraining-domain familiarity (2609.10357). LLM-as-batch-auditor is prohibited
  in the audit pipeline (2609.09696: batch recall collapses with confident fabrication).
- **HUM(f)**: human grand mean accuracy for family f = mean over participants of each
  participant's accuracy across 60 items; **SD_H(f)** = between-participant SD.
- All confirmatory statistics are functions of these three quantities only.

## 3. Pre-registered definitions (decision rules are threshold-based, CI-based, deterministic)

| Term | Definition |
|------|------------|
| Human-level at d* | Wilson 95% CI lower bound of ACC(m, f, d*, a) >= HUM(f) - SD_H(f) (pre-registered non-inferiority margin: one between-participant SD) |
| Retention (H1 criterion) | ACC(m, f, d*+2, a) >= 0.80 x ACC(m, f, d*, a), counted ONLY where ACC(m, f, d*, a) >= HUM(f) (red-team item 6) |
| Cliff at d*+1 | ACC(m, f, d*+1, a) < 0.50 x ACC(m, f, d*, a) (Faith-and-Fate collapse signature) |
| Probability invariance | Embers control: for matched logical structure with high- vs low-corpus-frequency answers, the difference ACC_high - ACC_low has a Wilson 95% CI contained in [-10, +10] percentage points (delta = 10 pp pre-registered) |
| Shared iterative circuit | Activation-patching primary specification (Section 8) identifies a component set whose ablation degrades ALL rule types of a family AND whose activation count or pattern scales with depth d (causal signature of iteration, red-team item 3); grid-agreement rule: the same conclusion holds in a strict majority (> 50%) of the pre-registered specification grid |
| Secondary-arm-only competence | Human-level at d* holds under the verbal-trigger secondary arm but fails under BOTH primary arms (A greedy, B CoT-decoding) |

## 4. Confirmatory test battery

Every test below is confirmatory; each has one null and one decision rule. alpha = 0.05
via the Wilson intervals throughout; no additional multiplicity correction is applied
because the verdicts are CONJUNCTIONS of independently pre-specified criteria
(conjunction is conservative; see Section 6).

| # | Test | Null | Decision rule | Verdict use |
|---|------|------|---------------|-------------|
| T1 | Human-level at d* (per checkpoint, family, primary arm) | CI lower bound < HUM - SD_H | Definition Section 3 | H1 / H0-b / H0-a input |
| T2 | Retention at d*+2 | ACC(d*+2) < 0.80 x ACC(d*) | Definition Section 3, gated on ACC(d*) >= HUM | H1, mixed |
| T3 | Cliff at d*+1 | no cliff | Definition Section 3 | H0-a, H0-b, mixed |
| T4 | Probability invariance (Embers control) | \|ACC_high - ACC_low\| CI excludes [-10, +10] pp | Definition Section 3 | H1 (invariance), H0-a (sensitivity) |
| T5 | Shared iterative circuit (7B/13B only) | no component set satisfies the causal signature in the primary specification | Definition Section 3 + grid agreement | H1, mixed vs H0-a |
| T6 | Irrelevant-clause invariance (GSM-NoOp style) | accuracy drop CI excludes [-10, +10] pp | Same margin as T4 | Triangulation (reported, not verdict-gating) |
| T7 | Numeric instantiation variance (GSM-Symbolic) | between-instantiation SD of cell accuracy > 10 pp | Pre-registered threshold | Triangulation (reported, not verdict-gating) |
| T8 | Replication concordance (OLMo 3) | verdict class differs between OLMo 2 and OLMo 3 at matched scales | Verdict-class equality per family | Confirmatory secondary claim |
| T9 | Scale trend | see Section 7 | Spearman rho of ACC vs log(params) per family at d*, with sign and CI | Asymmetry rule, confirmatory |

Faithfulness metrics for the secondary arms are confirmatory as specified in Section 9
(FUR parametric unlearning + filler substitution); Lanham truncation and
mistake-insertion are DESCRIPTIVE only (Amendment v0.4 item 4: the step-removal metric
anti-correlates with human faithfulness labels where models are wrong, 2607.23458).

## 5. Hypotheses restated as statistical claims

- **H1**: for checkpoint m, families f1 != f2, primary arm a: T1 holds for (m, f1),
  (m, f2); T2 holds for both; T4 invariance holds; T5 shared iterative circuit holds
  (where patching is in scope: 7B/13B); no T3 cliff.
- **H0-a**: T1 fails in all arms at d*; T4 sensitivity holds; T5 finds rule-specific
  pathways (ablation effects do not transfer across rule types).
- **H0-b**: secondary-arm-only competence (Section 3) holds and T3 cliff in both
  primary arms.
- **Mixed (algorithmic, depth-bound)**: T5 holds but T3 cliff at d*+1; supports the
  TC0/length-generalization reading (2604.25800), reported next to the pre-registered
  automaton classification of each family (Amendment v0.4 item 5, decision procedure of
  2608.13433, RoPE caveat stated).

## 6. Decision table (operationalized; deterministic evaluation order)

Per confirmatory checkpoint m, evaluate in this fixed order; stop at the first match:

1. **H1 supported (m)**: Section 5 H1 criteria met on >= 2 of 3 families (T5 required
   only where patching is in scope for m: 7B/13B; for 32B and Pythia checkpoints, H1
   requires the behavioral criteria T1+T2+T4 on >= 2 families AND T5 held at the nearest
   patched scale of the same family lineage, reported as such).
2. **H0-b (m)**: secondary-arm-only competence on >= 2 families AND T3 cliff in both
   primary arms on those families.
3. **H0-a (m)**: T1 fails at d* in every arm on >= 2 families AND (T4 sensitivity OR
   rule-specific T5).
4. **Mixed (m)**: T5 holds (or behavioral T1+T2 pattern at d* only) AND T3 cliff at d*+1.
5. **Inconclusive (m)**: none of the above; the cell pattern is reported descriptively.

**Study-level verdict** (pre-registered asymmetry, red-team item 4):

- If ANY confirmatory checkpoint yields H1 supported: study verdict = **H1 supported**
  (a positive result at any tested scale supports H1).
- Else the study verdict is the majority verdict class across the 7 checkpoints, and a
  negative verdict is BOUNDED: "no out-of-the-box reasoning detected at 1B-32B scale on
  the tested families"; it cannot refute H1 at untested (frontier) scales.
- T8/T9 are reported alongside every study-level verdict.
- The verdict and every deviation are recorded in #14; deviations are dated, reasoned,
  and downgrade the affected analysis to exploratory - never confirmatory.

## 7. Scale-trend analysis (confirmatory, red-team item 4)

Per family f and depth level d: Spearman rank correlation between ACC(., f, d, primary
arm) and log(checkpoint parameters) across the 7 confirmatory checkpoints, with a
bootstrap 95% CI (10,000 resamples, fixed seed per the version-lock manifest). Report
sign, rho, CI per (family, depth). Pythia `-deduped` and OLMo 2 points are reported both
pooled and per-lineage (different corpora); the pooled trend is the confirmatory one, the
per-lineage split is descriptive. A monotone-increasing trend with T1 still failing at
the top scale is reported as "competence rising, not yet human-level at tested scales".

## 8. Activation-patching analysis (Amendment v0.4 item 3)

Scope: OLMo 2 7B and 13B only (compute budget). The pipeline is fixed HERE, before any
run: progress-measure definition (Nanda-style, 2301.05217), ablation type, position set,
attribution threshold, and the iteration-signature statistic (activation count or pattern
scaling with depth d). Because circuit-level claims flip in 73.2% of defensible analytic
specifications (2608.13754), results are reported over a pre-registered specification
grid: ablation type x position-set granularity x threshold = the full cross product
listed in the version-lock manifest, with ONE primary specification designated now
(metric: logit-difference progress measure; ablation: zero-ablation at top-k attributed
positions; threshold: top 1% of attribution mass). The confirmatory claim uses the
primary specification; the grid is reported as a robustness table; the agreement rule of
Section 3 (> 50% of grid cells) gates any circuit claim. Attribution methodology may be
paired with direct read/write attribution (2609.10210) as a DESCRIPTIVE cross-check.

## 9. Faithfulness analysis (Condition 4, Amendment v0.4 item 4)

Applies to the secondary (verbal-trigger) arm and any arm producing intermediate tokens:

- **Confirmatory**: FUR parametric unlearning of a reasoning step (2502.14829, EMNLP
  2025): unlearning step i must degrade answers that require step i, with the degradation
  CI excluding 0; filler-token substitution rate (Pfau): accuracy under CoT-replaced-by-
  dots vs intact CoT, difference CI reported.
- **Descriptive only**: Lanham truncation rates, mistake-insertion flip rates. The
  anti-correlation warning (2607.23458) is stated next to every reported value.
- No CoT text is used as evidence for any confirmatory claim anywhere in this plan.

## 10. Human baseline statistics (#7 -> #13 inputs)

- N >= 40 participants per family (Webb et al. standard); 60 items per participant per
  family; item sets are the generated families' human-solvability-checked pools (hash-
  pinned in the version-lock manifest).
- Inference unit: participant (per-participant accuracy over 60 items); report grand
  mean, SD, Wilson 95% CI per family.
- Scoring is programmatic (exact match); a second rater re-scores a pre-registered 10%
  random subset wherever any judgment is required (free-form answers only); target
  agreement Cohen's kappa >= 0.8, reported.
- Exclusions: pre-registered attention-check failures and incomplete sessions only, with
  counts and reasons in the data-quality log; NO post-hoc participant drops; the
  pre-registered stopping rule (if triggered) is documented with date.
- Effect sizes: Hedges' g of (model cell accuracy treated as a single proportion) vs the
  participant accuracy distribution is reported descriptively; the confirmatory
  human-level test is T1 (CI-based non-inferiority), not an effect-size threshold.

## 11. Confirmatory / exploratory split

**Confirmatory** (exhaustive): T1-T9 as specified; Sections 3, 6, 7, 8 (primary
specification + grid-agreement rule), 9 (FUR + filler), 10 (descriptives feeding T1).

**Exploratory** (everything else, by definition): mixed-effects reanalyses; per-rule-type
or per-hop breakdowns beyond the pre-specified contrasts; post-hoc depth-curve fitting;
recirculation or any inference-time architectural intervention (Amendment v0.4 item 6:
excluded from primary arms; analysis-only); Pythia-vs-OLMo cross-lineage pooling beyond
Section 7; any subgroup, threshold, or margin not fixed in this document; the replication
checkpoints' internal analyses (the concordance test T8 is confirmatory; anything beyond
it is not). Exploratory results are labeled as such in every output; they never enter the
decision table of Section 6.

## 12. Analysis code, inputs, reproducibility

- Analysis code is committed to this repository BEFORE M4 data collection (#14
  acceptance): scoring, Wilson/bootstrap routines (fixed seeds), decision-table evaluator,
  robustness-grid reporter. Inputs = archived raw outputs only (run manifests with
  checkpoint hash + seed + config from the #5 harness); no interactive re-analysis in the
  confirmatory path.
- Environment manifest (Python version, dependency hashes) is part of the version-lock
  manifest (#11). Re-running the analysis on the archived outputs must reproduce every
  confirmatory number bit-for-bit.

## 13. Amendment path (issue #10 acceptance criterion)

- **Before the #11 timestamp**: this document changes by PR; every change gets a
  CHANGELOG entry; the draft version number increments.
- **After the timestamp**: the registered version is immutable. Amendments are appended
  as numbered addenda (date, reason, exact scope); any analysis touched by a
  post-timestamp amendment is reported as EXPLORATORY; the deviation log in #14 lists
  each addendum against the original text. What may NOT change post-timestamp under any
  circumstance: the decision-table evaluation order, the confirmatory/exploratory
  membership, the T1 margin, the retention threshold, the primary patching
  specification, and the asymmetry rule.
- The frozen document hash enters the version-lock manifest alongside prompt hashes,
  generator seeds, checkpoint Hub IDs + revisions, and analysis-code hash.

## Sources

Design inputs: study-design.md v0.4 (decision table, Conditions 1-5, red-team items 1-7,
Amendments v0.4) and the frozen model list (next-investigations.md, audit closed
2026-09-10). Method inputs, all arXiv-API-verified: 2212.09196 (Webb human baseline
standard), 2402.10200 (CoT-decoding arm), 2301.05217 (progress measures), 2604.25800
(length-generalization barrier), 2608.13754 (specification-grid requirement), 2607.23458
(truncation-metric warning), 2502.14829 (FUR parametric faithfulness), 2608.13433 and
2609.08851 (automaton classification), 2609.10357 (domain hold-out for d*), 2609.09696
(no LLM batch auditor), 2609.10210 (attribution cross-check).
