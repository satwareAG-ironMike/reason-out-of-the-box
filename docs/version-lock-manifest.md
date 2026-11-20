# Version-lock manifest (issue #11)

Status: draft 2026-09-11, issue #11, M1 work package. NOT yet frozen; the freeze happens at
the issue #11 pre-registration timestamp (OSF + AsPredicted). Refreshed 2026-09-14:
document hashes re-captured (unchanged), current Hub revisions captured as draft values.
Re-captured 2026-11-20 (issue #11 prep, refs #83): `docs/analysis-plan.md` and
`docs/study-design.md` hash unchanged from the 2026-09-14 capture, and all eleven Hub
revisions in section 2 re-fetch identical via the public API (access date 2026-11-20); the
capture therefore needs no value change. A further re-capture immediately before submission
remains required by the freeze semantics below. Submission URLs and the freeze
date are recorded in [preregistration.md](preregistration.md). Public-only rule: this
manifest records hashes, identifiers, and versions only - no secrets, no private
infrastructure.

Purpose: pin every artifact the pre-registered analysis depends on, so that re-running the
analysis on the archived raw outputs reproduces every confirmatory number bit-for-bit
([analysis-plan.md](analysis-plan.md) Section 12). Section references below point to
[analysis-plan.md](analysis-plan.md) unless stated otherwise.

## Freeze semantics

- Hashes are captured AT the timestamp; the "Captured" column states the last verification
  date. Immediately before the OSF/AsPredicted submission every hash is re-captured; after
  the timestamp nothing here changes except through the amendment path (Section 13).
- Model checkpoints are pinned to exact Hub repository revisions at freeze, with the access
  date recorded in this file. A checkpoint without a pinned revision does not enter the freeze.
- The freeze commit is the repository commit current at the timestamp; the hashes below
  describe the artifacts in that commit.

## 1. Frozen documents

| Artifact | Path | SHA-256 | Captured |
|----------|------|---------|----------|
| Statistical analysis plan | `docs/analysis-plan.md` | `54a6d0f2a777b7961814845c79bba00c1849a0a7c5fa8f10b36c62aadc46460a` | 2026-09-11, re-captured 2026-09-14 (unchanged), re-captured 2026-11-20 (Addendum 1: OLMo/Pythia confirmatory scope, pass@k arm, GSM-Symbolic T7 distinct from #77 leaky hop_chain; refs #177, #169, #174), re-capture at freeze |
| Study design | `docs/study-design.md` | `27b0f34543ab50a6547afcc04aee704e41a27dec7cec6a1752895928ccce85a3` | 2026-09-11, re-captured 2026-09-14 (unchanged), re-capture at freeze |
| Frozen model list | `docs/next-investigations.md`, feasibility audit section (closed 2026-09-10) | living document - extract to a frozen snapshot at freeze, then hash it | - |

## 2. Model checkpoints (Hub IDs + revisions)

All IDs below returned HTTP 200 on 2026-09-10 (feasibility audit, issue #2). Current Hub
revision (API `sha`) per checkpoint captured 2026-09-14 as draft values; the final pin is
re-captured and recorded at freeze.

| Role | Hub ID | Current revision (captured 2026-09-14) |
|------|--------|-----------------------------------------|
| Confirmatory, OLMo 2 | `allenai/OLMo-2-1124-7B` | `7df9a82518afdecae4e8c026b27adccc8c1f0032` |
| Confirmatory, OLMo 2 | `allenai/OLMo-2-1124-13B` | `3fefddc1bf18a30e1d9b91000271630718f2aa8b` |
| Confirmatory, OLMo 2 | `allenai/OLMo-2-0325-32B` | `cc9d3cf9c7230b86ee6b84607b37db1c01e3f1ed` |
| Confirmatory, scale control | `EleutherAI/pythia-1b-deduped` | `7199d8fc61a6d565cd1f3c62bf11525b563e13b2` |
| Confirmatory, scale control | `EleutherAI/pythia-2.8b-deduped` | `7d977fed8c4ce9649816af8cd5fe36a639cbe5b2` |
| Confirmatory, scale control | `EleutherAI/pythia-6.9b-deduped` | `372b1c08d9b5b0fc18ce86bbf294930e26e66ed5` |
| Confirmatory, scale control | `EleutherAI/pythia-12b-deduped` | `39c1bd94f9dbe4ebd1d191f364cb33a2e5c47707` |
| Replication | `allenai/Olmo-3-1025-7B` | `a81bae42db3975be1671e27b9c9a56da1a9f980f` |
| Replication | `allenai/Olmo-3-1125-32B` | `c2b61dae89a1ad10e4ad5653d0e46b590902607b` |
| Second replication candidate | `swiss-ai/Apertus-8B-2509` (base) | `3162c99675aa588097cecd4a24b9aa1f712af477` |
| Second replication candidate | `swiss-ai/Apertus-70B-2509` (base) | `379311a08b6e691f7b5cfbc1c408e8fc0c172981` |

Corpora for the contamination audit (d*): `allenai/olmo-mix-1124` + `allenai/dolmino-mix-1124`
(OLMo 2), `EleutherAI/the_pile_deduplicated` (Pythia), `allenai/dolma3_mix-6T-1025-7B` (OLMo 3
7B). The OLMo 3 32B training mix is assumed/unverified - it is not pinned until verified.

## 3. Prompts and decoding configuration (M2, TBD)

Placeholders filled from #5 harness artifacts at freeze: prompt set per family and arm
(A greedy, B CoT-decoding, secondary verbal-trigger), decoding configuration, run manifests.
Rule: every prompt file and configuration file is hashed here at freeze; anything not hashed
is not covered by the pre-registration.

## 4. Task generators, seeds, item sets (M2, TBD)

- Generator code hash at freeze (#4).
- Generator seeds per family recorded here at freeze.
- Generated item sets (300 items x 5 depth levels x 3 families): manifest hash per set at freeze.
- Human-solvability-checked item pools (Section 10): hash-pinned before M4.

## 4a. Cross-ask family instrument pin (round 78, issue #166 fix)

The #166 gate/code-divergence fix landed in the round-78 instrument (PR #184): the
`tail_copy_downgrade` trigger is registered at `n_X >= 2 AND every delivered arm-X record
emitted the draft's last vocabulary name`, with the `n_X == 0` case documented as
`no_recovery` by definition. Pinned here so the next cross-ask-family round inherits the
aligned trigger:

| Artifact | Path | SHA-256 | Captured |
|----------|------|---------|----------|
| Round-78 cross-ask instrument | `research/nightly-2026-11-21-0200/cross_ask_r78.py` | `9517226bb0cb2e59856ba2c9f192f7b26fbb5afa02f9c7f1bbebe4d39a60123b` | 2026-11-20 |
| Round-78 frozen gate | `research/nightly-2026-11-21-0200/gate.json` | see below | 2026-11-20 |

The gate.json hash is recorded at the round's own gate freeze (the instrument emits it);
this pin is the instrument code only.

## 4b. Addendum 1 literature pins (2026-11-20, issue #177)

Four arXiv IDs verified live via the arXiv export API on 2026-11-20 (the #65 free-scholarly-APIs
protocol; firecrawl not available on the maintainer host):

| ID | Title (verified) | Addendum 1 role |
|----|------------------|-----------------|
| `2504.13837` | Does Reinforcement Learning Really Incentivize Reasoning Capacity in LLMs Beyond the Base Model? (Yue et al., NeurIPS 2025) | pass@k arm (chain vs answer scored separately) |
| `2506.18880` | OMEGA: Can LLMs Reason Outside the Box in Math? | confirmatory-scope triangulation |
| `2506.10947` | Spurious Rewards: Rethinking Training Signals in RLVR | OLMo/Pythia confirmatory scope (model-family-specific RLVR) |
| `2410.05229` | GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in LLMs | T7 surface-perturbation triangulation arm |

## 4c. Confirmatory model-card metadata (2026-11-20, OLMo 2 / Pythia, refs #177)

Verified live via the Hugging Face Hub public API and model cards on 2026-11-20
(firecrawl not available on the maintainer host; the API + raw model card are the
free-scholarly-APIs protocol per #65):

| Model | Hub repo | Metadata verified | Source |
|-------|----------|-------------------|--------|
| OLMo 2 7B | `allenai/OLMo-2-1124-7B` | 7B, 32 layers, hidden 4096, 32 heads, ctx 4096, 4T training tokens, OLMo-mix-1124 + Dolmino-mix-1124, arXiv:2501.00656 | Hub API + raw model card |
| OLMo 2 7B Instruct (RLVR) | `allenai/OLMo-2-1124-7B-Instruct` | RLVR final model; tag `dataset:allenai/RLVR-GSM-MATH-IF-Mixed-Constraints`; DPO -> RLVR pipeline | Hub API |
| OLMo 2 32B Instruct | `allenai/OLMo-2-0325-32B-Instruct` | RLVR final model; tag `dataset:allenai/RLVR-GSM-MATH-IF-Mixed-Constraints`; base DPO, arXiv:2501.00656 + 2411.15124 | Hub API |
| Pythia (70M-6.9B) | `EleutherAI/pythia-{70m,160m,410m,1.4b,2.8b,6.9b}` | GPT-NeoX architecture, Pile dataset, arXiv:2304.01373 (Pythia: A Playground for Fine-Tuning and Interpretability) | Hub API |

The OLMo 2 confirmatory scope (Addendum 1) is the RLVR-Instruct variant, not the
base model: the `RLVR-GSM-MATH-IF-Mixed-Constraints` dataset tag on the Instruct
repos confirms the RLVR training step is part of the model family, so the
confirmatory-scope triangulation (arXiv:2506.10947, spurious rewards in RLVR)
applies to the OLMo 2 family specifically.

## 5. Activation-patching specification grid (Section 8)

Primary specification (fixed by the analysis plan NOW; immutable post-freeze):
logit-difference progress measure, zero-ablation at top-k attributed positions, threshold
top 1% of attribution mass.

Grid cross product (DRAFT values - to be finalized in this manifest before freeze; reported
as a robustness table; the > 50% grid-agreement rule gates any circuit claim):

| Dimension | Draft values | Primary cell |
|-----------|--------------|--------------|
| Progress measure | logit-difference, probability-difference | logit-difference |
| Ablation type | zero, mean, resample | zero |
| Position-set granularity | top-k attributed positions (k = 10, 25, 50) | fine per-position set |
| Attribution threshold | 1%, 5%, 10% of attribution mass | 1% |

## 6. Analysis seeds and resampling (Sections 7, 12)

- Bootstrap: 10,000 resamples; fixed seed value recorded here at freeze.
- Scoring, Wilson/bootstrap routines, decision-table evaluator, robustness-grid reporter:
  code hashes recorded when committed (before M4 per Section 12).

## 7. Analysis code and environment (TBD, before M4)

- Analysis code commit hash at freeze-of-analysis.
- Environment manifest: Python version, dependency lock hashes.
- Raw-output archive: #5 run manifests (checkpoint hash + seed + config per run).

## 8. Deviation policy

Post-timestamp: numbered addenda only (date, reason, exact scope); any affected analysis is
reported as exploratory. Immutable elements (Section 13): decision-table evaluation order,
confirmatory/exploratory membership, T1 margin, retention threshold, primary patching
specification, study-level asymmetry rule.

## Capture procedure

```bash
# Document hashes (re-capture immediately before the timestamp):
sha256sum docs/analysis-plan.md docs/study-design.md

# Hub revision per checkpoint at freeze (access date recorded in this file):
# curl -s https://huggingface.co/api/models/<id> | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])'
```
