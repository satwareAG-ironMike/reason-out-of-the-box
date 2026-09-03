# Study design: does a base LLM reason out of the box?

Status: draft v0.2 (2026-09-03), red-teamed (see Red-team findings). Pre-registration candidate. Derived from the 5-condition
spec in [archive/INDEX.md](../archive/INDEX.md) and the failure modes catalogued in rounds
1-7.

## Hypotheses

- **H1 (out-of-the-box reasoning)**: a base LLM, with no instruction tuning, no RL, and no
  reasoning-template prompting, solves procedurally novel reasoning tasks at human level,
  generalizes to depths absent from its pretraining data, and does so via an internal
  algorithm rather than retrieval of training patterns.
- **H0-a (retrieval)**: performance tracks training-pattern coverage and answer probability;
  collapses one step beyond trained depth (Faith and Fate, Embers).
- **H0-b (elicited-only)**: the competence exists but expresses only under elicitation
  (CoT-decoding, templates, RL) - the R1-Zero/Wang-Zhou reading.

The design must be able to separate all three. Most published work cannot.

## Condition 1: base model, no elicitation

| Choice | Rationale |
|--------|-----------|
| Models: OLMo 2 (7B, 13B, 32B) base checkpoints; Pythia suite as scale control | **Open pretraining data (Dolma)** is mandatory - contamination cannot be audited on closed models |
| Primary arm A: standard `Q: ... A:` greedy decoding | The Wang-Zhou baseline; QA format only because bare base models continue the question |
| Primary arm B: CoT-decoding (top-k=10 first-token branches, confidence selection) | Inference-time only - no parameter updates, no task-specific prompt tokens - so it counts as out of the box; greedy alone hides latent paths (red-team item 2) |
| Secondary arm (analysis only): "let's think step by step" | Quantifies the verbal-trigger gap (H0-b) without contaminating the primary claim |
| Excluded: instruct/RL variants, few-shot exemplars | Any of these turns the study into a test of elicitation |

## Condition 2: novel tasks, contamination-audited

Three task families, all **generated after the model's training cutoff from held-out
generator seeds**, with human baselines (N >= 40 per family, Webb et al. standard):

| Family | Generator | Depth knob | Contamination audit |
|--------|-----------|------------|---------------------|
| Digit matrices (Webb-style Raven analogues) | Rule grammar over 3x3 digit grids: constant, progression, distribution-of-3, AND/OR/XOR | 1-4 simultaneous rules | Regex + embedding search of Dolma for any 3x3 digit-grid puzzle; report instance count per rule type |
| Compositional ladders (Faith-and-Fate style) | Multi-digit multiplication, DP puzzles, k-hop relation composition with synthetic entities | k = 1..8 hops | Exact n-gram and structural search for k-hop chains in Dolma; the deepest k found in data defines the trained-depth ceiling d* |
| ARC-style grid transforms | Held-out ARC-AGI-2 generator seeds (ARC Prize private-style) | Number of composed transforms | By construction unpublished; verify no leak via generator-seed hash |

Synthetic entities (random strings) for the ladders defeat factual memorization; digit
matrices reuse Webb's exact rule set so results are comparable with the Nature Human
Behaviour baseline.

## Condition 3: process-level evidence (algorithm vs retrieval)

| Test | Prediction under H1 | Prediction under H0-a |
|------|---------------------|-----------------------|
| Depth generalization: accuracy at d*+1, d*+2 vs d* | Flat or graceful degradation | Cliff at d*+1 (Faith and Fate signature) |
| Answer-probability matching (Embers control): same logical structure, answers of high vs low corpus frequency | No accuracy difference | Low-frequency answers fail |
| Activation patching across rule types (Nanda-style progress measures) | Shared circuit reused across rules; ablating it hurts all rule types | Rule-specific memorized pathways; ablation effects do not transfer |
| Irrelevant-clause injection (GSM-NoOp style) | Accuracy invariant | Drops of 10-65% |
| Numeric instantiation variance (GSM-Symbolic) | Low variance across instantiations | High variance |

The activation-patching test is the only one that directly answers "algorithm or
retrieval"; the behavioral tests triangulate it.

## Condition 4: faithfulness controls

For any arm that produces intermediate tokens (secondary arms only):

- Lanham truncation and mistake-insertion: does corrupting step i change the answer?
- Filler-token substitution (Pfau): does replacing the CoT with dots preserve accuracy?
  If yes, the verbal chain is not the computation.
- Report the faithfulness rate; never use CoT text as evidence of reasoning.

## Condition 5: depth generalization beyond any training pattern

This is the decisive test and the one the 2026 length-generalization barrier
(arXiv:2604.25800) predicts fails under standard positional encodings:

1. Establish d* per model per task family from the Dolma audit (Condition 2).
2. Evaluate d*+1 through d*+4.
3. Pre-registered criterion: H1 requires >= 80% of d* accuracy retained at d*+2 on at
   least two task families, with the activation-patching circuit shared across depths and
   showing depth-scaling iteration. Retention counts only where d* accuracy is at or
   above the human mean for that family.

## Decision table (pre-registered)

| Outcome pattern | Verdict |
|-----------------|---------|
| Human-level at d*, retained at d*+2, shared circuit, probability-invariant, primary arm | **H1 supported**: first evidence of out-of-the-box reasoning |
| Human-level at d* only under secondary arms; cliff at d*+1 in primary | **H0-b**: latent but elicited-only (current consensus) |
| Below human at d*; probability-sensitive; rule-specific circuits | **H0-a**: retrieval |
| Mixed: shared circuit but cliff at d*+1 | Algorithmic but depth-bound: supports the TC0/length-generalization theory; reasoning exists inside a formal ceiling |

## Power and cost

- Tasks: 300 items per family per depth level; 3 families x 5 depths x 300 = 4,500 items
  per model. Human baseline: 40 participants x 60 items per family.
- Models: 3 OLMo 2 sizes + 4 Pythia sizes = 7 checkpoints, all open weights, one 8x80GB
  node suffices for inference; activation patching on the 7B and 13B only.
- Dolma audit: n-gram index over the pretraining corpus (existing infrastructure: WIMBD /
  infini-gram).
- Estimated wall time: 12 weeks including IRB lead time and human data collection.

## Red-team findings

Adversarial pass over the atomic claims of v0.1 (method: decompose, attack, severity,
mitigation). Changes adopted into v0.2 are marked.

1. **Attack**: "Open pretraining data makes contamination auditable." An n-gram audit of
   Dolma misses paraphrased, prose-described, or translated instances of the same puzzle
   structure. Severity: high - d* would be underestimated and "beyond training depth"
   overstated. Mitigation (adopted): add embedding search and rule-signature search;
   calibrate audit recall with planted canaries in a short continued-pretraining run;
   report d* as a lower bound.

2. **Attack**: The primary arm (greedy `Q:/A:`) is known to hide latent CoT paths (Wang &
   Zhou). A negative result there is a decoding artifact, not a capability absence.
   Severity: high. Mitigation (adopted): define "out of the box" as *no parameter updates
   and no task-specific tokens in the prompt*; decoding strategy is inference, not
   training. CoT-decoding (top-k branch selection) is therefore promoted to a second
   primary arm. Verbal triggers ("let's think") stay secondary.

3. **Attack**: "Shared circuit across depths" is underdetermined - shared components may
   be shared retrieval infrastructure (induction heads serve both memorization and
   algorithms). Severity: medium. Mitigation (adopted): require the causal signature of
   iteration, i.e. a component whose activation count or pattern scales with depth d,
   not mere overlap of ablation effects; use Nanda-style progress measures.

4. **Attack**: A null result on open-data models (<= 32B) may reflect scale, not
   architecture. Severity: medium-high. Mitigation (adopted): pre-register asymmetry - a
   positive result at any scale supports H1; a negative result is bounded to the tested
   scales and cannot refute H1 at frontier scale. Report scaling trends across the seven
   checkpoints.

5. **Attack**: The human baseline (undergraduates) has years of schooling; the comparison
   tests level, not "reasoning without prior training." Severity: medium, conceptual.
   Mitigation (adopted): scope statement - the study tests whether base LLMs match
   trained humans without task training; the biological no-training claim is a separate
   question (child arm listed as future work).

6. **Attack**: "80% retention at d*+2" is meaningless when d* accuracy is already low.
   Severity: medium. Mitigation (adopted): retention counts only where d* accuracy is at
   or above the human mean for that family.

7. **Attack**: 6-8 weeks on one node is optimistic given activation patching at 32B and
   IRB lead time for 120 participants. Severity: low. Mitigation (adopted): 12 weeks;
   IRB submission in week 0.

## What would still be missing after a positive result

- Generalization to natural-language reasoning beyond synthetic families.
- A biological-comparison arm (child data on the same digit matrices) to test the data-
  efficiency disanalogy, not just the accuracy one.
- Replication on a second open-data model family (DCLM) to rule out OLMo-specific
  pretraining artifacts.

## Provenance

Every design choice traces to an archive entry: Condition 1 to 2402.10200 and 2503.20783;
Condition 2 to 2212.09196, 2405.00332, 2505.11831; Condition 3 to 2305.18654, 2309.13638,
2301.05217, 2410.05229; Condition 4 to 2307.13702, 2404.15758; Condition 5 to 2604.25800
and 2405.15071.
