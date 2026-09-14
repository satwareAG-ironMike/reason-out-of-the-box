# Version-lock manifest (issue #11)

Status: draft 2026-09-11, issue #11, M1 work package. NOT yet frozen; the freeze happens at
the issue #11 pre-registration timestamp (OSF + AsPredicted). Refreshed 2026-09-14:
document hashes re-captured (unchanged), current Hub revisions captured as draft values.
Submission URLs and the freeze
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
| Statistical analysis plan | `docs/analysis-plan.md` | `9ef9b061944cc4d3c5937ee2f0f93f3984f394304d565ae56b8a6573ec68e0d7` | 2026-09-11, re-captured 2026-09-14 (unchanged), re-capture at freeze |
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
