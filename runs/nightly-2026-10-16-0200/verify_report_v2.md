# Independent verification record v2 (nightly-2026-10-16-0200)

Verifier: a fresh agent session with no shared context with the round agent, instructed to
recompute every manifest and report number from the raw artifacts with its own code, to
audit surface features on the shipped corpora, and to measure its own defect recall with
seeded defects in throwaway copies. It imported nothing from `generators/` or from
`runs/nightly-2026-10-16-0200/analyze_run.py` (both were read for definitions only), made
no network calls, no LLM endpoint calls, and no git or forge calls. It worked read-only on
the repository except for this single file, and kept its own drivers and evidence outside
the repository in a scratch directory.

Verifier model: qwen3.8-flash-next-class (strata). Independence limit: this is the same
model id that served the probe endpoint per `environment.json`. The implementation is
independent; the model is not.

This record supersedes nothing; [verify_independent.md](verify_independent.md) (v1) stays as
the prior record. v2 re-runs v1's scope with a stronger battery: full manifest confrontation
(84 fields), independent prompt rebuild (40/40), both nulls, a 16-feature surface audit on
seven corpora, a structural audit, and a seeded-defect recall measurement with three
tamper-wash variants.

## Verdict summary

- Artifact integrity: PASS. Every pinned hash reproduces; 40/40 prompt hashes rebuild from
  the corpus facts.
- Manifest recomputation from raw artifacts: PASS. 84 numeric and label fields confronted;
  76 exact; 8 residuals are pure rounding (stored 0.001 vs exact 0.0009765625).
- Report numbers: PASS for all quantitative claims checked, with three description errors
  and one off-by-one tool claim (register items D8, D9, D10, D11).
- Surface features: the pinned instrument reports (`audit_shipped.json`,
  `audit_fixtures.json`) reproduce exactly with independent code; the shipped-level
  conjunction hypothesis is a constant rule, not a leak.
- Seeded-defect recall: 8/9 required and extra defects caught by semantic checks alone;
  9/9 with hash assistance in the naive variant. The one semantic miss (latency swap) has
  no independent ground truth in the archive.

## Method

Own drivers (throwaway, outside the repository): a shared verifier library plus
`task1_recompute.py` (recomputation and manifest confrontation), `task2_gate_audit.py`
(surface features), `task2b_structure.py` (structural audit), `make_copies.py` and
`run_copies.py` (seeded-defect copies). JSON evidence for every step was kept in the
scratch directory.

Inputs read: `probe_raw.jsonl` (40 records), `probe_manifest.json`, `attempts.json`,
`environment.json`, `calibration.json`, `report.md`, `audit_shipped.json`,
`audit_fixtures.json`, `items/ladders/l1.jsonl`, `l2.jsonl`, `l4.jsonl`, `l6.jsonl`,
`l8.jsonl`, `generators/fixtures/issue67_prefix_l2.jsonl`, `issue67_prefix_l8.jsonl`,
`issue67_prefix.manifest.json`.

Definitions chosen by the verifier and stated up front:

- Own leak signature: the queried pair is entailed by a single stated fact
  (`any(s == q_src and t == q_tgt)`). The instrument's signature (`qt` is a fact target
  AND out-degree 0) was separately replicated to explain manifest fields.
- Restatement bound, two variants. Variant A: `sum(len(s) + len(r) + len(t) + 4)` per
  fact. Variant B: `sum(max(len(s), len(t)) + len(r) + 4)` per fact, matching the report's
  prose "longest name first".
- Two nulls. The label-permutation null (all assignments of the cell's gold labels to the
  10 items) and the manifest's fair-coin answering null (2^10 answer patterns).
- Baselines replicated from the instrument's source semantics: `B_direct` answers yes iff
  the query pair is itself a stated fact; `B_leak_sig` answers yes iff `qt` is a fact
  target and has out-degree 0; `B_majority` answers the cell's most frequent gold label
  (`Counter(golds).most_common(1)`, ties resolve to first seen).

## 1. Artifact integrity (PASS)

| Artifact | sha256 | Pinned in | Result |
| --- | --- | --- | --- |
| `probe_raw.jsonl` | `a836abc1dd8a8f438b133a9f1eb4db050370b660ce785a54c244f12ac06d7b34` | manifest `artifact_hashes` | match |
| `items/ladders/l2.jsonl` | `0bf2e99d311fceaff02d2186305b5ad0e0ed77b066a67df56b57b849ede16db4` (300 items) | `environment.json` | match |
| `items/ladders/l8.jsonl` | `8b4e36e96651c077e49cd76d5158a54af112610fb5c8f12e51f3357cc9948dd6` (300 items) | `environment.json` | match |
| `generators/fixtures/issue67_prefix_l2.jsonl` | `1917b2735e82cee4e08a1d064ddd3679b689b6895c1f77ef2c907c0963cd8488` (38 items) | `environment.json` | match |
| `generators/fixtures/issue67_prefix_l8.jsonl` | `d1df8a93e9394752601fd6a51d8fb5b77075bb1e1976c21581ec104ceb560272` (38 items) | `environment.json` | match |

All 9 hashes pinned in `environment.json` (corpora, fixtures, run artifacts) match the
files on disk. The manifest `prompt_hash` and `task_hash` recompute to
`63c29820976bc3fd16667f6ff1fa60a329776cdaa697a311d21975ecc517ccd9` (match), and all 40
per-item prompt hashes rebuild from the corpus facts block plus blank line plus instruction.

Seed policy: seeds reproduce as `20261005 + 2_000_000 * level + 8 * idx` for the fixture
files (every-8th-line extractions) and `+ 1 * idx` for the shipped files. `seed_hash`
reproduces as `sha256("ladders|hop_chain|level|seed")[:16]` on 676/676 corpus items
(300 + 300 + 38 + 38); the documented form `sha256("family|level|seed")[:16]` matches 0/676
(register D1).

## 2. Record-level confrontation (40/40 PASS)

For every archived record: cell, level, seed, `seed_hash`, gold label vs corpus answer,
gold label vs own BFS reachability, `n_facts` vs corpus fact count, model answer vs
`correct` flag, and the three baseline flags (`b_direct_correct`, `b_leak_sig_correct`,
`b_majority_correct`) all match own recomputation. 0 client errors, 0
`finish_reason=length` (all 40 `stop`), `parse_method=last_word` on 40/40.

Attempt accounting: 33 records `attempts=1, resumed=false`; 4 records `attempts=2,
resumed=true`; 3 records `attempts=1, resumed=true`. The 7 resumed records equal
`items_reused_from_prior_attempt: 7`; the 4 records with `attempts=2` equal the 4
`failed_attempts` in `attempts.json` (invocation 2: 11 calls, 7 answered, 4 failed).
Manifest `retries_used: 0` is invocation-3 scoped (33 calls, 33 answered, 0 failed)
(register D7). Totals block: 66 endpoint calls, 61 answered, 5 calls without an answer
(4 recorded failures plus 1 in-flight call), 40 experimental items answered, 26 over-cap
calls, 3 calibration calls, 69 including calibration.

Records carry no `item_id` field; identity is seed plus seed_hash plus query (register D5).

## 3. Cell recomputation (all PASS against the manifest)

| Metric | fixture_l2 | shipped_l2 | fixture_l8 | shipped_l8 |
| --- | --- | --- | --- | --- |
| n_items / n_valid / n_client_error | 10 / 10 / 0 | 10 / 10 / 0 | 10 / 10 / 0 | 10 / 10 / 0 |
| gold yes / no | 5 / 5 | 4 / 6 | 3 / 7 | 6 / 4 |
| balanced accuracy | 1.0 | 1.0 | 1.0 | 1.0 |
| plain accuracy | 1.0 | 1.0 | 1.0 | 1.0 |
| label-permutation null support | 252 | 210 | 120 | 210 |
| exact tail P(BA >= observed) | 0.003968254 | 0.004761905 | 0.008333333 | 0.004761905 |
| manifest tail (stored) | 0.004 | 0.0048 | 0.0083 | 0.0048 |
| answering-null p95 (support 1024) | 0.8 | 0.75 | 0.785714 | 0.75 |
| answering-null tail (manifest 0.001; exact) | 0.0009765625 | 0.0009765625 | 0.0009765625 | 0.0009765625 |
| mean completion_tokens (max) | 153.4 (230) | 139.8 (229) | 247.3 (371) | 556.9 (1024) |
| mean reasoning_chars (= mean trace chars) | 518.9 | 469.7 | 766.9 | 1514.2 |
| mean n_facts | 4.9 | 5.8 | 13.9 | 39.2 |
| mean latency_s (max) | 97.197 (193.564) | 130.1691 (232.62) | 120.5621 (211.952) | 139.5296 (345.144) |
| restatement ratio mean, variant A | 4.8392 | 4.2473 | 2.6005 | 2.2099 |
| restatement ratio mean, variant B | 6.0479 | 5.3423 | 3.2608 | 2.7153 |
| items with ratio > 1.0 | 10/10 | 10/10 | 10/10 | 10/10 |
| manifest named_fraction_mean | 0.5 | 0.3 | 0.4 | 0.6 |
| own mean over non-null named_fraction | 1.0 | 1.0 | 1.0 | 1.0 |
| gold-yes items naming every intermediate | 5/5 | 4/4 | 3/3 | 6/6 |
| direct_agreement (own signature) | 0.5 | 0.6 | 0.7 | 0.4 |
| leak_sig_agreement (instrument signature) | 1.0 | 0.4 | 1.0 | 0.6 |
| baselines_balanced B_direct | 0.5 | 0.5 | 0.5 | 0.5 |
| baselines_balanced B_leak_sig | 1.0 | 0.5 | 1.0 | 0.5 |
| baselines_balanced B_majority | 0.5 | 0.5 | 0.5 | 0.5 |
| cell majority label | no | no | no | yes |

Global latency over the 40 archived records: mean 121.86445 s, min 21.587 s, max 345.144 s
(report 3 quotes 121.8645 / 21.587 / 345.144: PASS).

Manifest confrontation: 84 fields checked, 76 exact matches, 8 residuals are the stored
answering-null tails rounded to 0.001 (exact one-sided upper tail 0.0009765625; a two-sided
fair-coin tail would be 0.001953125). The instrument's own `--selftest` reports 0 mismatches
on clean artifacts, so it evidently compares with tolerance; the residuals are rounding, not
disagreement (register D3).

Baseline semantics note (confirms report 6): `b_direct_correct` and friends are
"baseline answer equals gold" flags, not baseline answers. `B_direct` answers no on all 40
probed items (no queried pair is a stated fact), so its plain accuracy equals the gold-no
share (0.5 / 0.6 / 0.7 / 0.4) and its balanced accuracy is 0.5 everywhere. `B_leak_sig`
answers yes on all 40 shipped-arm items but discriminates perfectly on the fixtures, which
is why `baselines_balanced.B_leak_sig` is 1.0 on the fixture cells and 0.5 on the shipped
cells. `direct_agreement` and `leak_sig_agreement` are baseline-vs-gold plain accuracies;
they numerically equal model-vs-baseline agreement only because the model is correct on all
40 items.

## 4. Report claim confrontation (report.md)

PASS (recomputed independently): all 40 items answered correctly; gold counts 5/4/3/6;
completion-token means 153.4 / 139.8 / 247.3 / 556.9 and the 1024 max at shipped_l8 with no
item hitting the cap (max completion_tokens 1024 with `finish_reason=stop` and 0
`finish_reason=length`); reasoning-char means 518.9 / 469.7 / 766.9 / 1514.2; n_facts means
4.9 / 5.8 / 13.9 / 39.2; per-cell and global latency; restatement ratios 4.84 / 4.25 / 2.60
/ 2.21 and 10/10 items above 1.0 in every cell (variant A); named every intermediate on all
18 gold-yes items; label-permutation supports 252 / 210 / 120 / 210 with p 0.0040 / 0.0048 /
0.0083 / 0.0048; answering null over 1024 patterns with max 1.0, mean 0.5, p95 0.8 / 0.75 /
0.7857 / 0.75 and tail 0.001; the 66 = 61 answered + 4 failed + 1 in-flight accounting; the
4.4 named_fraction values (under null-as-zero semantics); the 4.2 column meanings as
clarified in the shipped report.

FAIL or mislabelled: the three items in register D8 (matched-pair description), D9 (fixture
arm description in report 2 contradicting report 4.4), and D10 (restatement-bound prose in
4.3 inconsistent with the published numbers). D11: report line 90 claims `analyze_run.py
--selftest` runs 12 seeded-defect control groups; the selftest actually prints "13 control
groups, 0 mismatches on clean artifacts" (exit 0). The `name_channel_audit.py --selftest`
claim of 5 control groups is correct (verified: "selftest ok: 5 control groups", exit 0).

## 5. Task 2: surface-feature audit (own code, 16 features, 7 corpora)

Feature accuracy = share of items where the feature predicts the gold label (feature true
predicts yes, feature false predicts no). Constant features score at the majority share.

| Feature | shipped l2 (n=300, 140 yes) | shipped l8 (n=300, 157 yes) | fixture l2 (n=38, 21 yes) | fixture l8 (n=38, 16 yes) |
| --- | --- | --- | --- | --- |
| direct_fact (constant false at l2 and l8) | 0.5333 | 0.4767 | 0.4474 | 0.5789 |
| src_back_len_eq_level | 0.5333 | 0.4767 | 0.4474 | 0.5789 |
| tgt_back_len_eq_level | 0.4667 (constant true) | 0.5233 (constant true) | 1.0 | 1.0 |
| src_pref_in_target | 0.5333 | 0.4767 | 0.4474 | 0.5789 |
| tgt_pref_in_source | 0.5333 | 0.4767 | 0.4474 | 0.5789 |
| name_length min rule | 0.51 | 0.4967 | 0.4211 | 0.6316 |
| name_length max rule | 0.4833 | 0.4767 | 0.5263 | 0.6053 |
| name_length mean rule | 0.4733 | 0.49 | 0.4737 | 0.4737 |
| same_component (undirected) | 1.0 | 1.0 | 1.0 | 1.0 |
| conjunction: not direct_fact AND tgt_back_len_eq_level | 0.4667 (constant true) | 0.5233 (constant true) | 1.0 | 1.0 |
| conjunction two-sided binomial p vs 0.5 | 0.27263 | 0.45298 | 7.276e-12 | 7.276e-12 |
| n_facts mean / min / max | 6.08 / 4 / 8 | 46.48 / 16 / 80 | 4.87 / 3 / 7 | 14.03 / 10 / 19 |
| best n_facts threshold rule | NOT(>= 4), 0.5333, p 0.2726 | NOT(>= 40), 0.5533, p 0.0733 | NOT(>= 7), 0.6053, p 0.2559 | NOT(>= 10), 0.5789, p 0.4177 |

Reading: at the shipped levels the conjunction is a constant-yes rule (direct_fact is
constant false and tgt_back_len_eq_level is constant true at every shipped level), so its
accuracy is just the gold-yes share (140/300 and 157/300) and neither p is significant. On
the fixtures the conjunction is exactly the gold label (accuracy 1.0, p 7.276e-12), driven
by the target-role/chain-completeness signature, not by a direct fact: direct entailment of
the queried pair is 0/38 on both fixture files.

Own numbers reproduce the pinned instrument reports exactly: `audit_shipped.json` l2
(direct_fact 0.5333, tgt_back_len_eq_level 0.4667, constant_rule_accuracy 0.5333,
min_detectable 0.57, gold_yes 140) and l8 (direct_fact 0.4767, tgt_back_len_eq_level 0.5233,
best_hypothesis `n_facts < 40` at 0.5533); `audit_fixtures.json` (best_hypothesis
`direct_fact == false AND tgt_back_len_eq_level == true` at 1.0, gate_status `leak`,
min_detectable 0.7105 and 0.7368, gold_yes 21 and 16). The instrument's shipped-l2
best_hypothesis (`n_facts >= 8`, 0.5133) is its best non-constant rule; own best-threshold
search includes constant rules and returns 0.5333, equal to the instrument's
constant_rule_accuracy.

Structural audit (own code, 1576 items across 7 corpora): reverse directed paths 0
everywhere; undirected connectivity equals directed forward reachability equals the gold
label on every item (direction never decides); BFS distance equals the level for every
reachable item; query endpoints never absent; direct entailment of the queried pair 0 at
shipped l2, l4, l6, l8 and 0 on both fixtures, 148 at shipped l1; component-size histograms
match report 4.5 (shipped l2 {2:100, 3:88, 4:112}; shipped l8 sizes 2..10; fixture l2 sizes
2..6; fixture l8 sizes 3..12).

## 6. Task 3: seeded-defect recall (own checks, throwaway copies only)

Design: 9 defects planted in 3 wash variants each (27 copies in the scratch directory; the
repository was never modified). Variants: `naive` (defect only; manifest and environment
sidecar untouched), `washed` (manifest `artifact_hashes` and the `environment.json` sha256
block recomputed, two passes because the sidecar pins the manifest), `deep` (also recomputes
manifest `prompt_hash` and `task_hash` from the tampered corpus with the recipe own code
reproduced). Only `deep` silences every hash check, so semantic recall is read from
`washed` and `deep`.

| Defect | naive | washed | deep |
| --- | --- | --- | --- |
| a. flip corpus answer label (`items/ladders/l2.jsonl` seed 24261013, no to yes) | caught | caught | caught |
| b. completion_tokens 229 to 230 (fixture_l2 seed 24261005) | caught | caught | caught |
| c. raw seed 24261013 to 24261014 (shipped_l2) | caught | caught | caught |
| d. delete one raw record (fixture_l8 seed 36261021) | caught | caught | caught |
| e. redirect fixture l8 seed 36261013 fact 3 (`prat precedes trackx` to `prat precedes zzqx`; n_facts unchanged, queried pair unreachable) | caught | caught | caught |
| f. self-consistent label tamper (shipped l8 seed 36261013 gold flipped in corpus and raw, model_answer follows the new gold, process block nulled) | caught | caught | caught |
| g. swap two latency_s values inside fixture_l2 (seeds 24261005 and 24261013) | caught by pinned file hash only | NOT caught | NOT caught |
| h. compensating reasoning_chars pair in fixture_l2 (+1 and -1, cell mean preserved) | caught | caught | caught |
| i. raw n_facts 7 to 8 (fixture_l2 seed 24261021) | caught | caught | caught |

Semantic recall 8/9; hash-assisted recall 9/9 (defect g only in the naive variant).

Which checks fired: record-vs-corpus confrontation (a, c, d, e, i), gold re-derived by own
BFS (c, e, f), baseline flag confrontation (e, f), manifest aggregate recomputation (a, b,
c, d, e, f), cell metric diff (a, b, c, d, e, f, h), surface feature audit diff (a, e, f),
structural audit diff (a, e, f), manifest prompt contract hash (e, f under corpus tamper).
Defect h was caught only by an own derived metric: `fixture_l2.mean_trace_over_restatement`
moves from 4.839208158771736 to 4.8396248254384036 while zero manifest fields move. Defect
g is invisible to every semantic check because the archive contains no independent latency
ground truth; the cell mean and max are unchanged by a swap.

Interpretation: the manifest's own hash pinning catches naive tampering, but semantic recall
depends on checks that re-derive gold from the corpus (own BFS), recompute aggregates, and
diff derived metrics. A verifier that only hashes artifacts would miss defects b, c, d, e,
f, h, and i in the washed and deep variants.

## 7. Discrepancy register

- D1. `seed_hash` implementation vs documentation. `generators/AGENTS.md` documents
  `sha256("family|level|seed")[:16]`; `generators/ladders.py:71` implements
  `sha256("ladders|hop_chain|level|seed")[:16]`. The implemented form matches 676/676 corpus
  items; the documented form matches 0/676. Documentation error, artifacts consistent.
- D2. `named_fraction_mean` semantics. Manifest values 0.5 / 0.3 / 0.4 / 0.6 reproduce only
  if gold-no items (null named_fraction) count as 0, i.e. the value equals gold_yes/10 in
  this run; the mean over non-null values is 1.0 in every cell. Report 4.4's column label
  "mean over gold-yes items" is misleading; the numbers are right under null-as-zero.
- D3. Answering-null tail rounding. Manifest stores 0.001; exact one-sided upper tail is
  0.0009765625 (two-sided would be 0.001953125). Conservative rounding, 8 fields affected.
- D4. `process.gold_path_len` unit. For all 18 gold-yes records it is the entity count
  (BFS edges + 1), while corpus `chain_len` is the edge count and `intermediates` is edges
  minus 1. Naming consistency holds; the unit differs from the corpus field.
- D5. No `item_id` field in `probe_raw.jsonl`; identity is seed plus seed_hash plus query.
- D6. Item facts are not archived in `probe_raw.jsonl` (only `n_facts`), so "names every
  intermediate" is verifiable as counter consistency (n_named equals intermediates equals
  level minus 1), not against trace text.
- D7. Manifest `retries_used: 0` is invocation-3 scoped; 4 archived records carry
  `attempts: 2` and 7 carry `resumed: true`, matching `items_reused_from_prior_attempt: 7`
  and the 4 failed attempts of invocation 2.
- D8. Report 2's matched-pair description ("identical entity names, identical fact chains,
  differing only in whether the queried pair is one of the facts") is false at item level
  for the 20 probed seed pairs: query_same 0/10 at l2 and 1/10 at l8; facts_same 0/10 at
  both; entity-name sets identical 0/10; n_facts identical 5/10 at l2 and 0/10 at l8; gold
  identical 3/10 at l2 and 5/10 at l8. `issue67_prefix.manifest.json` states seed-level
  pairing only, which is what the data shows.
- D9. Report 2 describes the fixture arm as "the queried pair is entailed by a single fact
  on every item". Direct entailment is 0/38 at both fixture levels (own scan and
  `audit_fixtures.json` constant_features). The fixture leak is the target-role and
  chain-completeness signature (`tgt_is_fact_target`, `tgt_outdeg_zero`, `tgt_indeg_one`,
  `tgt_back_len_eq_level`, all accuracy 1.0). Report 4.4 states the arm correctly; report 2
  contradicts it.
- D10. Report 4.3 prose describes the restatement bound as "one mention per fact, longest
  name first", but the published ratios reproduce only under the `len(s) + len(r) + len(t)
  + 4` bound (variant A: 4.8392 / 4.2473 / 2.6005 / 2.2099); the longest-name-first bound
  (variant B) gives 6.0479 / 5.3423 / 3.2608 / 2.7153.
- D11. Report line 90 claims `analyze_run.py --selftest` runs 12 seeded-defect control
  groups; the selftest prints 13 control groups, 0 mismatches (exit 0). The
  `name_channel_audit.py --selftest` claim of 5 control groups is correct.
- D12. 66 calls minus 61 answered leaves 5 calls without an answer: 4 recorded
  `failed_attempts` plus 1 in-flight call. Consistent with `attempts.json`; noted so the
  arithmetic is explicit.

## 8. Not independently reproduced

- Report 4.5's 21-feature `name_channel_audit` table (best traversal-free accuracy 0.5700
  at shipped l2 with p 0.017779; 0.7105 at fixture l8 with p 0.013853; Bonferroni threshold
  0.002381). Own battery has 16 features and does not include the traversal-free feature
  set; own code does independently confirm the `same_component` accuracy 1.0 claim at every
  shipped level and on both fixtures, and confirms that the shipped conjunction degenerates
  to a constant rule.
- Trace text content (facts are not archived, see D6); the `weights_hash` gap is recorded by
  the environment sidecar itself.

## 9. Boundary statement

Every number in this record was recomputed from the archived artifacts with the verifier's
own code; nothing was taken from the round agent's analyzers except definitions read from
source. No endpoint was contacted and no model was queried during verification. The
verifier's model is the same model id that served the probe, so independence here is
implementation-level, not model-level. This file is the only repository file written by this
verification pass; no other file was modified or "fixed".
