# Nightly round 10 (2026-10-18 04:00): matched-pair probe, traversal versus connectivity

State: **Executed** (probe completed, 36/36 arms answered, gate verified before any prompt was
spent) and **Reproduced at the analysis level**: an independent verifier re-ran `--gate` and
`--analyze` in a sandbox and regenerated `gate.json` and `summary.json` byte-identically. Not
Validated: one endpoint, one run, no second endpoint, no independent re-run of the probe. The
verification record is `docs/review-rounds/nightly10-2026-10-18.md`; the claims it corrected are
listed under Errata.

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

Nine real shipped items: the first three usable items per level at k = 4, 6, 8, in file order, which
is the rule recorded in `gate.json` as `items_per_level: 3` (usable = gold-yes query witnessed by a
simple in-degree <= 1, out-degree <= 1 chain of length >= 4, plus a second component holding a
terminal node whose name length equals the chain terminal). Facts, entity names, fact count, and the
prompt rendering are the shipped item's, unchanged; the rule sentence and the question line are
byte-identical to the rounds 8 and 9 probes. Only the queried pair changes.

Four arms per item, 36 cells, gold 18 yes / 18 no:

| Arm | Query | Gold | Connectivity says | Reachability says |
|---|---|---|---|---|
| F1 | (p_1, p_k) forward, one edge short of the terminal | yes | yes | yes |
| R1 | (p_k, p_1) **reverse** | no | **yes** | **no** |
| F2 | (p_2, p_{k+1}) forward, shifted by one edge | yes | yes | yes |
| X | (p_2, m) terminal `m` of another component | no | no | no |

The witnessed chain has k edges and k+1 nodes p_1, ..., p_{k+1}, and the arms are read off that path,
so F1, R1 and F2 all sit at undirected hop distance k - 1 (7 hops at k = 8) while X has no undirected
path at all.

The 9 disagreeing cells are exactly the R1 cells: same component, same undirected hop distance,
opposite gold. Matched-pair invariants are enforced as **fatal checks**, not as reported results:
per direction family the name multiset, undirected distance, component membership, endpoint degree
profile, and prompt length must match and the gold labels must be opposite; per component family
connectivity must differ while the shared endpoint, name length, and terminal out-degree 0 hold.
`invariant_violations` is empty in `gate.json`.

### Direction-blind battery

15 rules offered as direction-blind, plus 2 reference rules that express edge direction. A rule
"fires" when it both beats its exact label-shuffle null (an upper tail, P(hits >= observed), screened
at the Bonferroni alpha = 0.05 / 15 = 3.333e-03) and reaches 0.90 accuracy. Nulls are exact: per-item
gold-label permutation for the matched corpus (exact convolution over items), global gold-label
shuffle for the shipped corpus (hypergeometric; per-item shuffling is degenerate there because each
item carries exactly one queried pair). No Monte Carlo anywhere.

Direction-blindness is a claim about the battery, not a measured property of it, and the independent
review measured it: reversing every edge in the corpus leaves 10 of the 15 rules unchanged, while
`target_is_fact_target` and `source_is_fact_source` flip on all 1500 items, `endpoint_in_degree_zero`
and `endpoint_out_degree_zero` flip on 754, and `source_is_first_fact_source` flips on 271. Those five
read fact order or endpoint degree, which tracks direction on this generator even though none of them
walks an edge. No firing decision changes, but the label is overstated; see Errata.

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
- The Shipped p column is an underflowed float, not a measured zero. For the five perfect rules the
  exact tail is 1 / C(1500, 746), about 10^-450, and `float()` renders it as 0.0.
- The Matched p column is the one-sided upper tail. Doubled for a two-sided reading, `same_component`,
  `undirected_connectivity_only` and `target_is_fact_target` sit at 3.906e-03, above the 3.333e-03 bar.
  "No rule fires" is carried by the 0.90 accuracy bar, not by the significance screen.
- `gate.json` also records `null_min_hits` and `null_max_hits` for each shipped null, and those bounds
  are the naive intersection bounds rather than the true support [|a + y - n|, n - |a - y|] of the hit
  count over K in [max(0, a + y - n), min(a, y)], where a is the rule's yes cells and y the gold-yes
  cells. At least one bound is wrong for all 15 rules: the minimum for 12 (for example 0 instead of 8
  for `same_component`, 0 instead of 754 for `all_no`) and the maximum for the other 3 (`all_yes`,
  `source_is_fact_source`, `endpoint_in_degree_zero`, each recorded as 1500 instead of 746). Means,
  standard deviations, observed hits, z values and p values are all correct, and no firing decision
  depends on the bounds. They cannot be retrofitted into this round's artifacts because the gate hash
  is embedded in every `raw.jsonl` record and in `summary.json`; the fix ships with a fresh gate in the
  round that re-runs the battery. See Errata and issue #77.

Gate hash `e796ca308f26e39da54d174e95fcf76280872285a32af16ad617ddce4d3501a1`.

## Probe result

36 prompts, temperature 0, max_tokens 2048, concurrency 4, 900 s per-arm deadline, one retry,
incremental fsynced `raw.jsonl`, resume refuses a raw file carrying a different gate hash. Transport
failures 0 (36/36 records carry `transport_failure: false`). Truncated completions
(`finish_reason: length`) 0; all 36 attempts finish `stop` with no `error_class`. All 36 answers read
from the `content` field, none from reasoning text. The health-check latency of 10.2 s and the probe
wall clock of 745.8 s are runner-side observations from the round log and no artifact in this directory
carries them. What the archive does carry is per-attempt `wall_s`: 36 attempts, 9.97 s to 183.6 s each,
2892.8 s in total, which is consistent with 745.8 s of wall clock at concurrency 4 without recording
it.

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
- The matched invariants are per family, not global. Within the direction family (F1, R1) the name
  multiset, undirected hop distance (k - 1), component membership, endpoint degree profile, and prompt
  length are equal and the gold labels are opposite. Within the component family (F2, X) the shared
  endpoint, name length, and terminal out-degree 0 are equal while connectivity deliberately differs, so
  hop distance is not held fixed across that family. Neither family controls for the queried node's
  position in the fact listing order, which is why `name_first_mention_order` and
  `name_last_mention_order` are in the battery rather than assumed away.
- The probe corpus is 9 items drawn from 3 levels. Levels 1 and 2 are not probed; at those depths the
  chain is too short to give a length >= 4 interior witness.
- **Artifact loss and re-execution.** The first execution of this round completed its gate and had
  dispatched its probe when its branch, commit, and pushed ref were destroyed by a verifier subagent
  that switched the shared primary worktree from a research branch to `main` (its 36-prompt raw
  archive was in the runner scratch directory and is unrecoverable). Everything published here comes
  from a single re-execution. The published execution used 36 of its 40-prompt budget and none of its
  4-prompt calibration reserve, and `raw.jsonl` records exactly that. The wider claim that round 10
  consumed at least 37 and at most 73 prompts across both executions is a reconstruction from the
  runner log: no artifact here carries the destroyed execution's prompt count. The same applies to the
  report that only the first execution's health-check artifact survived, showing a
  `finish_reason: length` truncation at small `max_tokens`; that artifact is not in this directory and
  its content cannot be checked from the archive, so the `max_tokens` 2048 pin and the per-attempt
  `finish_reason` field stand as design decisions whose stated motivation is unverified. The operating
  model now forbids that verifier operation against the worktree under verification and requires the runner
  to snapshot the round directory before a verifier pass (`docs/agent-execution.md` section 5).
- The 15-rule battery is this round's construction. It is not the widened class #77 proposes for
  `generators/audit_ladder_leaks.py`, and it does not change that auditor or its pinned hash.

## Literature

Verified against the arXiv export API, not from memory. The table as first published carried eight
titles that did not match the arXiv record and one entry whose ID belongs to a different paper, so the
rows below were re-resolved by the independent review of this round (arXiv export API plus OpenAlex DOI
lookups; the resolution log is in `docs/review-rounds/nightly10-2026-10-18.md`). Venues are quoted from
the arXiv comment field unless a DOI resolves, and a venue that no record states is marked as such.
These are the primaries the matched-pair design stands on:

| arXiv | Work | Relevance |
|---|---|---|
| 1908.06177 | Sinha, Sodhani, Dong, Pineau, Hamilton, "CLUTRR: A Diagnostic Benchmark for Inductive Reasoning from Text", EMNLP 2019 | multi-hop family with fact-order variants; the forward/reverse split used here is its simplest case |
| 2012.13048 | Tafjord, Dalvi Mishra, Clark, "ProofWriter: Generating Implications, Proofs, and Abductive Statements over Natural Language", Findings of ACL 2021 | origin of the TRAP arm (#77 criterion 4): premise chains deliberately irrelevant to the queried pair |
| 2002.05867 | Clark, Tafjord, Richardson, "Transformers as Soft Reasoners over Language", IJCAI 2020 (arXiv comment; the record carries no journal reference or DOI) | the traversal-vs-lookup hypothesis this probe tests, and the RuleTaker paper itself: its abstract names the models RuleTakers |
| 2112.09054 | Richardson, Sabharwal, "Pushing the Limits of Rule Reasoning in Transformers through Natural Language Satisfiability", AAAI-2022 (PrOntoQA line) | depth-labeled entailment corpora, the shipped-corpus construction family |
| 2210.01240 | Saparov, He, "Language Models Are Greedy Reasoners: A Systematic Formal Analysis of Chain-of-Thought", ICLR 2023 | evidence that reasoners shortcut premises rather than traverse them, which is the failure mode the matched pair detects |
| 2305.15269 | Saparov, Pang, Padmakumar, Joshi, Kazemi, Kim, He, "Testing the General Deductive Reasoning Capacity of Large Language Models Using OOD Examples", NeurIPS 2023 | OOD deductive capacity, the transfer question this answer does not settle |
| 2303.15714 | Zhao, Wang, Yu, Mei, "Explicit Planning Helps Language Models in Logical Reasoning", EMNLP 2023 | intermediate-step planning, the mechanism the token-cost asymmetry hints at |
| 2205.12443 | Yang, Deng, Chen, "Generating Natural Language Proofs with Verifier-Guided Search", EMNLP 2022 | supervision that forces traversal rather than connectivity |
| 2010.02830 | Saha, Ghosh, Srivastava, Bansal, "PRover: Proof Generation for Interpretable Reasoning over Rules", EMNLP 2020 main conference (DOI 10.18653/v1/2020.emnlp-main.9) | proof-as-output, the trace-level instrument this round only approximates |
| 2306.12567 | Ando, Morishita, Abe, Mineshima, Okada, "Evaluating Large Language Models with NeuBAROCO: Syllogistic Reasoning Ability and Human-like Biases", NALOMA IV workshop (no DOI on the record) | hybrid neuro-symbolic baseline for the same corpora |
| 1906.06805 | de Jong, Sha, "Neural Theorem Provers Do Not Learn Rules Without Exploration", venue not stated on the arXiv record | the rule-learning objection behind #77's widened class |
| 2309.05660 | Wang, Zelikman, Poesia, Pu, Haber, Goodman, "Hypothesis Search: Inductive Reasoning with Language Models", ICLR 2024 | hypothesis-side alternative to chain traversal, not separated by this instrument |

Two titles this round leaned on have no record to cite. A title search for "Language Models with Rules"
and for "Deriving Rules from Language Models" returns no arXiv match, and none of Oyvind Tafjord's 63
arXiv submissions carries either title, so both are recorded as **unverified** rather than cited with a
venue: the RuleTaker/PrOntoQA work they were meant to point at is 2002.05867 and 2112.09054.

Provenance correction carried forward: the IDs 2301.07330, 2203.14238, 2005.00331, 2210.11845,
2104.00754, 2002.03673 and 1703.03400 that earlier rounds of this project pinned as
RuleTaker/PrOntoQA/soft-reasoners primaries are **not** those papers (they are video demoireing,
Vicsek flocking, phase-field fracture, Patankar-RK stability, Thurston geometries, PU learning, and
MAML respectively; the independent review re-checked all seven against the arXiv record and every one
of those identifications holds). The gap those IDs were filling is now closed rather than unconfirmed:
2002.05867 is the RuleTaker paper, because its own abstract introduces the models as RuleTakers, and
2112.09054 is the PrOntoQA paper, so no separate RuleTaker ID is outstanding. Archive entries for these
primaries are still owed on #74, and #74 must take the corrected titles above rather than the ones this
round first published.

## Errata

An independent verification pass (2026-10-18, `docs/review-rounds/nightly10-2026-10-18.md`) recomputed
every number in this README from `gate.json`, `raw.jsonl`, `summary.json` and `items/ladders/`, with
independent implementations of the component partition, the reachability search, the hypergeometric and
convolution nulls, the Wilson interval, and McNemar's test. Every headline number survived. What did not
survive is the control narrative and the citation table. The corrections below were drafted by the
verifier directly in the working tree, which contradicted its own read-only report and is recorded as a
rejected claim in the review record; the runner re-derived every number behind each edit from its own
independent implementations before adopting the text, and the two conduct rules the incident produced now
sit in `docs/agent-execution.md` section 5. Corrected in place above:

| Claim as first published | Recomputed |
|---|---|
| "the first usable one per level" | the gate selects 3 usable items per level, 9 items in total |
| Arm notation (p_1, p_{k-1}) and (p_2, p_k) | off by one: F1 is (p_1, p_k), R1 is (p_k, p_1), F2 is (p_2, p_{k+1}) |
| "15 rules that cannot express edge direction" | overstated: 5 of the 15 change predictions when every edge is reversed |
| Rule nulls labelled two-sided | they are one-sided upper tails; the two-sided matched p for `same_component` is 3.906e-03, above the 3.333e-03 bar |
| Shipped p = 0.0 | an underflowed float; the exact tail is 1 / C(1500, 746), about 10^-450 |
| `gate.json` shipped-null bounds | `null_min_hits` wrong for 12 rules and `null_max_hits` wrong for 3; owed with a fresh gate under #77 |
| Health check 10.2 s, probe wall clock 745.8 s, 37 to 73 prompts across two executions | runner-side observations, carried by no artifact |
| "Two real bugs found by those controls" | not carried by any artifact; the selftest as shipped failed 44 of 45 |
| 8 of 12 literature titles, 2112.09054 attributed to the wrong authors, 2002.05867 as "TACL 2021" | re-resolved against the arXiv export API; the record says IJCAI 2020 and TACL is unsupported |
| "RuleTaker's own arXiv ID remains unconfirmed" | false: 2002.05867 is the RuleTaker paper |

Two defects in `matched_pair_probe.py`'s selftest are fixed on this branch: the `same_component`
shipped-null assertion, and the discordant-pairs check whose label contradicted its own assertion. The
bound formulas in `exact_null_shipped` were deliberately left unchanged, because editing them would
change `gate.json` and every hash this round published; a comment now records the correct support so a
later round can fix them together with a fresh gate hash.

## Reproduce

```
python3 research/nightly-2026-10-18-0400/matched_pair_probe.py --selftest
python3 research/nightly-2026-10-18-0400/matched_pair_probe.py --gate
python3 research/nightly-2026-10-18-0400/matched_pair_probe.py --probe
python3 research/nightly-2026-10-18-0400/matched_pair_probe.py --analyze
```

`--selftest` runs 45 checks including planted negative controls: a corpus where connectivity and
reachability agree everywhere must be reported non-discriminating, a rule that is correct on the gold
labels but wrong on every shuffled null must be caught, `rec["correct"]` must compare against gold
rather than against "yes", and the hypergeometric null must convert hit counts back to the accuracy
threshold rather than compare them directly.

As published the selftest did **not** pass: on the commit this round shipped it reported 44 of 45 and
exited 1. One check asserted `null_sd == 0.0` and `p_exact == 1.0` for the `same_component` shipped
null, whose true standard deviation is 19.370824 and whose exact tail underflows to 0.0; another check
carried the label "0 discordant pairs" over an assertion that 9 discordant pairs appear. Both were
mistakes in the test rather than in the analysis, and both are fixed on this branch. The claim that the
controls found two real bugs in the script before any prompt was spent is a runner-side claim that no
artifact records; what the independent review could confirm is that the shipped-null hit count to
threshold conversion is implemented correctly.

`--gate` and `--analyze` regenerate `gate.json` and `summary.json` byte-identically to the published
files, which the independent review verified in a sandbox copy; running them in an archive checkout
would overwrite the published artifacts. `--probe` needs the inference endpoint and is not runnable
from an archive checkout.

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
archive it claims to analyze. The script is pinned separately because it changed after the probe ran: the
version that produced these artifacts is
`df3fe306920efbc165a8befacda7b51dbf8bea6a6c53ba9316ac4683d24bdaa1`, the corrected version on this branch
is `e455f4b1cfe542f5bf35eec64c89a0cb65e12849a509d7a3bbb76bf79f708ff1`, and `--gate` and `--analyze`
regenerate `gate.json` and `summary.json` byte-identically under both, verified in an archive checkout of
the shipped commit and in a sandbox copy of this branch. `raw.jsonl` holds the full completions; entity
names are the generator's synthetic strings and no host, path, address, or model-file identifier appears
in any artifact.
