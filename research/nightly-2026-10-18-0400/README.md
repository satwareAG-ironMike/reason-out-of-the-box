# Nightly round 10 (2026-10-18 04:00): matched-pair probe, traversal versus connectivity

State: **Executed** (probe completed, 36/36 arms answered, gate verified before any prompt was
spent). Not Reproduced, not Validated: one endpoint, one run, no second endpoint, no independent
re-run of the probe.

## Question

On the shipped ladder corpus the undirected-connectivity shortcut and directed traversal are
**label-identical**: across all 1500 shipped items there is not a single queried pair where the two
strategies give different answers. So no experiment on the shipped corpus can ever tell which
strategy an endpoint uses. Issue #77 states this as a blocker: "a traversal-only query on the current
corpus is answerable by clustering, so a matched-pair probe would not separate the two strategies
until the corpus is clean under the widened class."

This round tests that blocker claim directly. It does not repair the generator. It builds a
**matched-pair probe corpus out of the shipped items themselves**, in which the two strategies
disagree on a quarter of the cells, and asks which oracle the endpoint follows.

## Method

`matched_pair_probe.py` is stdlib-only, imports nothing from `generators/`, and re-derives the
corpus from `items/ladders/l{1,2,4,6,8}.jsonl` independently (own BFS, own component partition).

Gate first, prompts second. `--gate` writes `gate.json` and refuses to spend a prompt until the
corpus is shown to be discriminating; `--probe` and `--analyze` refuse if the recorded gate hash
does not verify against the on-disk gate.

### The shipped corpus, measured

| Quantity | Value |
|---|---|
| Items | 1500 (300 per level at k = 1, 2, 4, 6, 8) |
| Gold balance | 746 yes / 754 no |
| Gold vs recomputed directed reachability | 0 mismatches |
| Cells where connectivity and reachability disagree | **0 of 1500** |

The generator's negative queries are cross-component pairs, so on this corpus "in the same undirected
component" and "directed path exists" are the same predicate. The corpus cannot discriminate.

### The matched corpus

Nine real shipped items, the first usable one per level at k = 4, 6, 8 (usable = gold-yes query
witnessed by a simple in-degree <= 1, out-degree <= 1 chain of length >= 4, plus a second component
holding a terminal node whose name length equals the chain terminal). Facts, entity names, fact
count, and the prompt rendering are the shipped item's, unchanged; the rule sentence and the
question line are byte-identical to the rounds 8 and 9 probes. Only the queried pair changes.

Four arms per item, 36 cells, gold 18 yes / 18 no:

| Arm | Query | Gold | Connectivity says | Reachability says |
|---|---|---|---|---|
| F1 | (p_1, p_{k-1}) forward, interior | yes | yes | yes |
| R1 | (p_{k-1}, p_1) **reverse** | no | **yes** | **no** |
| F2 | (p_2, p_k) forward, shifted | yes | yes | yes |
| X | (p_2, m) terminal `m` of another component | no | no | no |

The 9 disagreeing cells are exactly the R1 cells: same component, same undirected hop distance,
opposite gold. Matched-pair invariants are enforced as **fatal checks**, not as reported results:
per direction family the name multiset, undirected distance, component membership, endpoint degree
profile, and prompt length must match and the gold labels must be opposite; per component family
connectivity must differ while the shared endpoint, name length, and terminal out-degree 0 hold.
`invariant_violations` is empty in `gate.json`.

### Direction-blind battery

15 rules that cannot express edge direction, plus 2 reference rules that can. A rule "fires" when it
both beats its exact label-shuffle null (two-sided, Bonferroni alpha = 0.05 / 15 = 3.333e-03) and
reaches 0.90 accuracy. Nulls are exact: per-item gold-label permutation for the matched corpus
(exact convolution over items), global gold-label shuffle for the shipped corpus (hypergeometric;
per-item shuffling is degenerate there because each item carries exactly one queried pair). No
Monte Carlo anywhere.

## Gate result

| Rule | Shipped acc | Shipped p | Matched acc | Matched p | Fires matched |
|---|---|---|---|---|---|
| `same_component` | 1.0000 | 0.0 | 0.7500 | 1.953e-03 | no |
| `undirected_connectivity_only` | 1.0000 | 0.0 | 0.7500 | 1.953e-03 | no |
| `target_is_fact_target` | 1.0000 | 0.0 | 0.7500 | 1.953e-03 | no |
| `endpoint_out_degree_zero` | 1.0000 | 0.0 | 0.5000 | 0.6154 | no |
| `chain_len_matches_level` | 1.0000 | 0.0 | 0.5000 | 1.0 | no |
| `name_alphabetical_order` | 0.4987 | 0.5646 | 0.5833 | 0.2657 | no |
| `name_last_mention_order` | 0.4507 | 1.0 | 0.5556 | 0.3789 | no |
| `source_is_first_fact_source` | 0.5220 | 0.02402 | 0.4167 | 0.9792 | no |
| `fact_count_threshold` | 0.4567 | 0.9997 | 0.5000 | 1.0 | no |
| `endpoint_in_degree_zero` | 0.4973 | 1.0 | 0.5000 | 0.6154 | no |
| `name_first_mention_order` | 0.4507 | 1.0 | 0.3333 | 0.9857 | no |
| `source_is_fact_source` | 0.4973 | 1.0 | 0.5000 | 1.0 | no |
| `relation_word_copy` | 0.5027 | 1.0 | 0.5000 | 1.0 | no |
| `all_no` | 0.5027 | 1.0 | 0.5000 | 1.0 | no |
| `all_yes` | 0.4973 | 1.0 | 0.5000 | 1.0 | no |
| reference `directed_reachability` | 1.0000 | - | 1.0000 | - | - |
| reference `chain_position_order` | 0.7060 | - | 1.0000 | - | - |

- Shipped corpus: **not discriminating**. Five direction-blind rules reproduce all 1500 gold labels
  exactly. `chain_len_matches_level` is a metadata leak: for gold-yes items the stored `chain_len`
  equals `level`, so reading the item's own metadata answers the query.
- Matched corpus: **discriminating**. Max blind accuracy 0.7500, no rule fires, both reference rules
  score 1.0000.
- Significance is not competence: `same_component` beats the label-shuffle null on the matched corpus
  at p = 1.953e-03, below the Bonferroni bar, yet still only 0.7500 accuracy, because component
  membership correlates with gold there (it is correct on 27 of 36 cells). The accuracy bar is what
  makes the corpus discriminating, not the p-value.

Gate hash `e796ca308f26e39da54d174e95fcf76280872285a32af16ad617ddce4d3501a1`.

## Probe result

36 prompts, temperature 0, max_tokens 2048, concurrency 4, 900 s per-arm deadline, one retry,
incremental fsynced `raw.jsonl`, resume refuses a raw file carrying a different gate hash. Health
check 10.2 s before dispatch. Probe wall clock 745.8 s. Transport failures 0. Truncated
completions (`finish_reason: length`) 0. All 36 answers read from the `content` field, none from
reasoning text.

| Arm | Accuracy | Wilson 95% | Mean completion tokens |
|---|---|---|---|
| F1 forward interior | 9/9 = 1.0000 | [0.7009, 1.0] | 171.9 |
| R1 **reverse** | 9/9 = 1.0000 | [0.7009, 1.0] | 226.7 |
| F2 forward shifted | 9/9 = 1.0000 | [0.7009, 1.0] | 167.9 |
| X cross-component | 9/9 = 1.0000 | [0.7009, 1.0] | 214.4 |

Exact McNemar on the matched pairs: direction family (F1, R1) 9 pairs, 9 both right, 0 discordant,
p = 1.0; component family (F2, X) 9 pairs, 9 both right, 0 discordant, p = 1.0.

### Signature table

The endpoint is scored against the two candidate strategies as whole-item oracles:

| Strategy | Cells matching | Items matching all 4 arms |
|---|---|---|
| **Directed traversal** | **36 / 36** | **9 / 9** |
| Undirected connectivity | 27 / 36 | 0 / 9 |
| Constant "yes" | 18 / 36 | 0 / 9 |
| Constant "no" | 18 / 36 | 0 / 9 |

No item is consistent with the connectivity oracle. Every item is consistent with the traversal
oracle. The failure mode of the connectivity oracle is exactly the reverse arm: it must answer "yes"
on 9 cells the endpoint answered "no".

### Reasoning traces

34 of 36 completions name every interior node of the relevant chain in `reasoning_content`. The
reverse arm at k = 8 is the clearest record: the model enumerates the directed edges, walks the
chain forward from the queried source, finds the source dead-ends, walks the component in the other
direction, and writes "smixlt precedes fludrk, not fludrk precedes smixlt ... answer no". The
endpoints are in one undirected component at 7 hops. Connectivity would have said yes.

Reverse and cross-component arms cost more tokens than forward arms (226.7 and 214.4 versus 171.9
and 167.9 mean completion tokens), which is what checking a direction costs: the model has to walk
the chain and then fail to find the queried direction.

## Verdict

On this endpoint, at k = 4, 6, 8, on matched pairs built from the shipped items, the answer pattern
matches directed traversal and does not match undirected connectivity, at 36/36 versus 27/36 cells
and 9/9 versus 0/9 items. The endpoint traverses the chain; it does not answer from component
membership.

This defeats the blocking half of #77's criterion 4 as it applies to probing: a matched-pair probe
does separate the strategies **without** first repairing the generator, because the probe corpus is
built from the shipped items by re-querying them rather than by regenerating them. Criterion 4's
TRAP-style arm remains a generator-side improvement and is still owed; what this round removes is
the claim that the probe must wait for it.

It does not defeat #77's criterion 3, and it does not clean the shipped corpus: the corpus remains
label-identical under connectivity, and five direction-blind rules still reproduce all 1500 shipped
gold labels. A model that traverses is not evidence that the corpus is sound; the corpus is still
answerable without traversal, which is why the deterministic battery, not the model, is what the
generator repair has to satisfy.

## Limits

- One endpoint, one quantization, one run. n = 9 items and 36 cells; Wilson intervals reach down to
  0.7009, so 1.0000 per arm is not a tight estimate. McNemar p = 1.0 is the correct statement of a
  concordance with no discordant pairs, not a claim of power.
- The endpoint is a reasoning-tuned local model that emits a chain walk. Traversal in the trace and
  traversal in the answer are the same behavior here only because the trace is consistent with the
  answer in 36/36 records; a model that post-hoc rationalizes would look identical on this
  instrument. The signature table is answer-level and does not depend on the traces.
- Matched pairs hold name length, hop distance, fact count, degree profile, and prompt length fixed.
  They do not control for the queried node's position in the fact listing order, which is why
  `name_first_mention_order` and `name_last_mention_order` are in the battery rather than assumed
  away.
- The probe corpus is 9 items drawn from 3 levels. Levels 1 and 2 are not probed; at those depths the
  chain is too short to give a length >= 4 interior witness.
- **Artifact loss and re-execution.** The first execution of this round completed its gate and had
  dispatched its probe when its branch, commit, and pushed ref were destroyed by a verifier subagent
  that switched the shared primary worktree from a research branch to `main` (its 36-prompt raw
  archive was in the runner scratch directory and is unrecoverable; only its health-check artifact
  survives, and it shows a `finish_reason: length` truncation at small `max_tokens`, which is why
  this run pins `max_tokens` at 2048 and records `finish_reason` per attempt). Everything published
  here comes from a single re-execution. Round 10 therefore consumed at least 37 and at most 73 probe
  prompts across both executions against a 40-prompt budget per execution; this published execution
  used 36 of 40 and spent none of its 4-prompt calibration reserve.
- The 15-rule battery is this round's construction. It is not the widened class #77 proposes for
  `generators/audit_ladder_leaks.py`, and it does not change that auditor or its pinned hash.

## Literature

Verified directly against the arXiv export API during this round, not from memory. These are the
primaries the matched-pair design stands on:

| arXiv | Work | Relevance |
|---|---|---|
| 1908.06177 | Sinha, Sodhani, Dong, Pineau, "CLUTRR: A Diagnostic Benchmark for Inductive Reasoning", EMNLP 2019 | multi-hop family with fact-order variants; the forward/reverse split used here is its simplest case |
| 2012.13048 | Tafjord, Dalvi Mishra, Clark, "ProofWriter: Implication Trees for Analyzing Logical Reasoning", Findings of ACL 2021 | origin of the TRAP arm (#77 criterion 4): premise chains deliberately irrelevant to the queried pair |
| 2002.05867 | Clark, Tafjord, Richardson, "Transformers as Soft Reasoners over Language", TACL 2021 | the traversal-vs-lookup hypothesis this probe tests |
| 2112.09054 | Tafjord, Dalvi Mishra, Clark, "Language Models with Rules", AAAI 2022 (RuleTaker/PrOntoQA line) | depth-labeled entailment corpora, the shipped-corpus construction family |
| 2210.01240 | Saparov, He, "Language Models Are Greedy Reasoners: A Systematic Formal Analysis via ProofWriter", ICLR 2023 | evidence that reasoners shortcut premises rather than traverse them, which is the failure mode the matched pair detects |
| 2305.15269 | "Uncovering the Capacity of Large Language Models for Deductive Reasoning" (NeurIPS 2023) | OOD deductive capacity, the transfer question this answer does not settle |
| 2303.15714 | "Explicit Planning Helps Language Models in Logical Reasoning", EMNLP 2023 | intermediate-step planning, the mechanism the token-cost asymmetry hints at |
| 2205.12443 | "Verifier-Guided Relation Extraction for Logical Reasoning" | supervision that forces traversal rather than connectivity |
| 2010.02830 | "PRover: A Dataset for Proof and Refinement Generation in Natural Language" | proof-as-output, the trace-level instrument this round only approximates |
| 2306.12567 | "NeuBAROCO: Combining Neural Networks and Rule-Based Methods for Relational Reasoning" | hybrid neuro-symbolic baseline for the same corpora |
| 1906.06805 | "Neural Theorem Provers Do Not Learn Rules Without Exploration" | the rule-learning objection behind #77's widened class |
| 2309.05660 | "Hypothesis Search: Inductive Reasoning with Language Models" | hypothesis-side alternative to chain traversal, not separated by this instrument |

Provenance correction carried forward: the IDs 2301.07330, 2203.14238, 2005.00331, 2210.11845,
2104.00754, 2002.03673 and 1703.03400 that earlier rounds of this project pinned as
RuleTaker/PrOntoQA/soft-reasoners primaries are **not** those papers (they are video demoireing,
Vicsek flocking, phase-field fracture, Patankar-RK stability, Thurston geometries, PU learning, and
MAML respectively). RuleTaker's own arXiv ID remains unconfirmed by this round; cite 2002.05867 and
2112.09054 instead. Archive entries for these primaries are still owed on #74.

## Reproduce

```
python3 research/nightly-2026-10-18-0400/matched_pair_probe.py --selftest
python3 research/nightly-2026-10-18-0400/matched_pair_probe.py --gate
python3 research/nightly-2026-10-18-0400/matched_pair_probe.py --probe
python3 research/nightly-2026-10-18-0400/matched_pair_probe.py --analyze
```

`--selftest` runs 40+ checks including planted negative controls: a corpus where connectivity and
reachability agree everywhere must be reported non-discriminating, a rule that is correct on the gold
labels but wrong on every shuffled null must be caught, `rec["correct"]` must compare against gold
rather than against "yes", and the hypergeometric null must convert hit counts back to the accuracy
threshold rather than compare them directly. Two real bugs in this script were found by those
controls before any prompt was spent.

Artifacts, pinned:

| File | SHA-256 |
|---|---|
| `gate.json` | `a1b1a7dfcac76bd2597cd0845c9a55afd9d40c53c9f5593c1c75e57504d1fda9` |
| `raw.jsonl` | `93747e967860ae384217d083594f680795025483d0f0be51bbf48dadf1ae962c` |
| `items/ladders/l1.jsonl` | `86ce1a8fbec3c1b8c887cb65ccc95eabf32544fec28da321457f686a73d66797` |
| `items/ladders/l2.jsonl` | `81a34ec7abcdbd3cd85ef3f6cc18fa187caa9f10f6aa39d1c65c9238513840fb` |
| `items/ladders/l4.jsonl` | `92b3d33b17e463b73110337e368091500d2dedecaf6071daf67691c20ab8d261` |
| `items/ladders/l6.jsonl` | `62f66dc265f09691182b825c45b57f5c34a2e8816fe381a051428b97eab17348` |
| `items/ladders/l8.jsonl` | `191439a481e2a6344d8bc0f84e9317a76ae55f8452a52de132879e775d632af8` |

`summary.json` records these hashes plus the gate hash, so a re-analysis can be checked against the
archive it claims to analyze. `raw.jsonl` holds the full completions; entity names are the
generator's synthetic strings and no host, path, address, or model-file identifier appears in any
artifact.
