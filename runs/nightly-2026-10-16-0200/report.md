# Nightly round 5: does a live endpoint answer the repaired ladders by shortcut or by traversal?

Run id `nightly-2026-10-16-0200`. Parent run `nightly-2026-10-15-0400` (the corpus repair
whose regenerated items are seed-paired with the pinned pre-fix controls, 4.6). Tracker
issue #65, generator issue #67.
Label: **Executed**. The derived numbers are additionally **Reproduced** by an independent
recomputation from the archived artifacts (see Verification); the endpoint calls themselves
were not re-run, because every paid call is charged once. **Validated** is not claimed:
there is no independent-endpoint or independent-model-family evidence yet.

## 1. Question

The round-4 repair regenerated all 1,500 ladder items under a component-isomorphic
construction (commit `94f0883`), and pinned 38 pre-fix items per probed level as negative
controls (`generators/fixtures/issue67_prefix_l{2,8}.jsonl`, every 8th line of the pre-fix
files at commit `49ee823`). On those pre-fix items the surface rule "the query target is a
fact target and has out-degree zero" reproduces the gold label on 38/38 items at both levels;
on the regenerated items the same rule is constant and the 18-feature gate class reports
`no_leak`. The open question this round:

> Does a live endpoint answer the k-hop ladders because the surface of the query tells it
> the answer (shortcut), or because it walks the chain (traversal)?

Three sub-questions, each with its own test:

1. Can the endpoint answer at all at k=2 and k=8? (capability)
2. Does its answer track the shortcut signature, or the traversal result? (mechanism)
3. Does the shipped corpus contain any shortcut the gate class does not see? (corpus)

## 2. Design, fixed before any endpoint call

Written into the instrument before the first call, and not changed afterwards:

- 4 cells x 10 items = 40 prompts, the cap. Cells: `fixture_l2`, `shipped_l2`,
  `fixture_l8`, `shipped_l8`. A matched pair is a pre-fix item and the post-fix item generated
  from the same seed at the same level: same seed, same level, same query shape, and the
  construction is the only thing the design changes. The pairing is by seed, not by content,
  and what a pair actually shares is recomputed rather than asserted:

  | Level | pairs | same queried pair | same fact chain | same entity-name set | same fact count | same gold label |
  |---|---|---|---|---|---|---|
  | 2 | 10 | 0 | 0 | 0 | 5 | 3 |
  | 8 | 10 | 1 | 0 | 0 | 0 | 5 |

  No pair shares its fact chain or its entity names. The arms therefore differ in
  construction, not in item content, and the comparison is arm-level: a pair is not the same
  item under a different query. An earlier draft of this report claimed the pairs held entity
  names and fact chains fixed; that claim is corrected here and recorded in section 8.
- Fixture cells are the pinned issue #67 negative controls. Their shortcut is the target-role
  signature above, which reproduces the gold label on 38/38 items at both levels. It is not
  direct entailment: no item in either arm has its queried pair as a stated fact (4.2).
- One fixed neutral template. No traversal instruction, no chain-of-thought instruction, no
  hint that a chain exists. The item's own `rule`, `answer`, and `chain_len` are withheld.
- Decoding: zero-shot, temperature 0, `max_tokens` 1536, decoding seed 20261016,
  `stream: false`.
- Primary metric: balanced accuracy over valid items.
- Primary null (the one the pre-registered rule uses): the exact answering null, the
  balanced-accuracy value of every one of the `2**10 = 1024` answer patterns a fair coin
  would produce for that cell's gold split, enumerated exactly rather than sampled.
  `support_size` is recorded per cell so the null is regenerable.
- Secondary null, reported and never used for the verdict: the label-permutation null, the
  balanced accuracy of the model's fixed answers under every one of the `C(10, n_yes)`
  distinct reassignments of the gold labels (252, 120, 210, 210 assignments for the four
  cells). It credits the model with the correct number of yes answers and asks only whether
  their placement is lucky, so for a perfect cell it is the more conservative of the two
  (1/252 against 1/1024). The two nulls do not order uniformly at every threshold: at
  balanced accuracy 0.75 the fair-coin tail is the smaller one. Both are reported so the
  reader can see the claim survives either null.
- Verdict rule, pre-registered in `generators/probe_ladder_shortcut.py`: a cell is
  `strong` when balanced accuracy on valid items is at least 0.75 **and** the exact
  answering-null p-value is below 0.05 on both the full cell and the valid subset. A fixture
  cell that is not strong gives `inconclusive_no_capability`; both fixture cells strong and
  both shipped cells strong gives `traversal_consistent`; both fixture cells strong and at
  least one shipped cell not strong gives `shortcut_consistent`.
- Calibration: at most 3 calls, excluded from every cell and from every reported metric.

## 3. Invocations

Three invocations of the same instrument, chained with `--resume` so that no paid answer is
re-paid. Full provenance in `attempts.json`.

| Attempt | Instrument commit | Client timeout | Calls | Answered | Failed attempts | Reused | Outcome |
|---|---|---|---|---|---|---|---|
| 1 | `4b4d1a6` | 180 s | 22 | 21 | 0 | 0 | crashed: uncaught client `TimeoutError` on the 22nd call, the 21 paid answers were lost because this revision had not yet written the raw file |
| 2 | `0e5cc6b` | 300 s | 11 | 7 | 4 | 0 | stopped before the cell finished, the 7 answers survived in the raw file |
| 3 | `2f92ce2` | 600 s | 33 | 33 | 0 | 7 | completed: 40/40 valid, manifest written |

Endpoint accounting, from `attempts.json` and recomputed by `analyze_run.py`:
**66 endpoint calls = 61 answered + 4 failed attempts + 1 call in flight when attempt 1
crashed**. Of the 61 answered calls, 21 were paid by attempt 1 and lost, 7 were paid by
attempt 2 and reused by attempt 3, and 33 were paid by attempt 3. **26 calls over the
40-call cap.** The 3 calibration calls are separate and are not in the 66.

Latency is quoted only from the 40 archived experimental records, because those are the
calls whose artifacts exist: mean 121.8645 s, minimum 21.587 s, maximum 345.144 s. The
calibration calls, which ran while the engine was uncontended, took 4.591 s, 6.391 s, and
11.310 s. The failures were client-side, not model-side: the engine was still generating
when the client gave up. The corrective rule recorded in `attempts.json` is to start the run
detached (`setsid nohup` with a pidfile) and keep the driving turn minimal until it
finishes, instead of supervising it from a live generation turn.

## 4. Results

Every number below is regenerated by `python3 runs/nightly-2026-10-16-0200/analyze_run.py`
from `probe_manifest.json` and `probe_raw.jsonl`. `--check` re-derives them from the
manifest and reports 0 mismatches; `--selftest` runs 13 seeded-defect control groups.

### 4.1 Answering, per cell

| Cell | n | valid | gold yes/no | BA | accuracy | answering-null P(BA >= obs) | null p95 | label-permutation P(BA >= obs) | strong |
|---|---|---|---|---|---|---|---|---|---|
| fixture_l2 | 10 | 10 | 5/5 | 1.0000 | 1.0000 | 0.000977 (1/1024) | 0.8000 | 0.003968 (1/252) | yes |
| shipped_l2 | 10 | 10 | 4/6 | 1.0000 | 1.0000 | 0.000977 (1/1024) | 0.7500 | 0.004762 (1/210) | yes |
| fixture_l8 | 10 | 10 | 3/7 | 1.0000 | 1.0000 | 0.000977 (1/1024) | 0.7857 | 0.008333 (1/120) | yes |
| shipped_l8 | 10 | 10 | 6/4 | 1.0000 | 1.0000 | 0.000977 (1/1024) | 0.7500 | 0.004762 (1/210) | yes |

The manifest stores the answering-null tail as `0.001`; the exact value is
`1/1024 = 0.0009765625`, and `analyze_run.py` confronts the stored value at the manifest's
4-decimal precision.

Verdict under the pre-registered rule: **`traversal_consistent`** (all 4 cells strong).
0 client errors, 40/40 valid, no `finish_reason=length` truncation at 1536 tokens.

### 4.2 Shortcut signature versus traversal result

| Cell | B_majority | B_direct | B_leak_sig | leak sig vs gold | direct vs gold | model vs leak sig | model vs direct | model vs gold |
|---|---|---|---|---|---|---|---|---|
| fixture_l2 | 0.5000 | 0.5000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 | 0.5000 | 1.0000 |
| shipped_l2 | 0.5000 | 0.5000 | 0.5000 | 0.4000 | 0.6000 | 0.4000 | 0.6000 | 1.0000 |
| fixture_l8 | 0.5000 | 0.5000 | 1.0000 | 1.0000 | 0.7000 | 1.0000 | 0.7000 | 1.0000 |
| shipped_l8 | 0.5000 | 0.5000 | 0.5000 | 0.6000 | 0.4000 | 0.6000 | 0.4000 | 1.0000 |

Column meanings, stated because the instrument's own field names are wrong (see Limits):

- `B_majority`, `B_direct`, `B_leak_sig` are the **balanced** accuracies of the three
  a-priori baselines against the gold label.
- `leak sig vs gold` and `direct vs gold` are **plain** accuracies of the baseline against
  the gold label. These are the quantities the manifest stores under the names
  `leak_sig_agreement` and `direct_agreement`.
- `model vs *` is plain agreement between the model's answer and the baseline's answer.
- Because the model is correct on all 40 items, every `model vs X` column equals the
  matching `X vs gold` column exactly. That identity is a property of a perfect model, not
  a design fact, and it is why the manifest's misnamed fields are not simply harmless.

On the shipped cells the model disagrees with the entailment signature on 6 of 10 items
(l2) and 4 of 10 items (l8) while agreeing with the gold label on all 20. The signature is
not a usable shortcut on the repaired corpus: `analyze_run.py` evaluates it on **every**
item of every shipped level, not only the probed sample.

| Corpus | n | items where the query pair is itself a stated fact | entailment-signature accuracy | signature constant? |
|---|---|---|---|---|
| shipped l2 | 300 | 0 | 0.4667 | yes |
| shipped l4 | 300 | 0 | 0.4933 | yes |
| shipped l6 | 300 | 0 | 0.5533 | yes |
| shipped l8 | 300 | 0 | 0.5233 | yes |
| fixture l2 | 38 | 0 | 1.0000 | no |
| fixture l8 | 38 | 0 | 1.0000 | no |

On the repaired corpus the signature is a constant whose accuracy is a coin flip, so there
is no entailment shortcut for the model to take, and the shipped answers are not
entailment-signature answers. On the pre-fix corpora the signature is not constant and
scores 1.0000, which is the same fact the pinned gate audit reports as a leak.

### 4.3 Process measures, and what they do not show

| Cell | mean completion tokens | mean reasoning chars | mean facts in item | mean trace/restatement ratio | items above 1.0 |
|---|---|---|---|---|---|
| fixture_l2 | 153.4 | 518.9 | 4.9 (4-7) | 4.8392 | 10/10 |
| shipped_l2 | 139.8 | 469.7 | 5.8 (4-8) | 4.2473 | 10/10 |
| fixture_l8 | 247.3 | 766.9 | 13.9 (10-19) | 2.6005 | 10/10 |
| shipped_l8 | 556.9 | 1514.2 | 39.2 (16-80) | 2.2099 | 10/10 |

The trace-over-restatement ratio compares the length of the reasoning trace in characters
with a **verbatim-restatement bound**: the character cost of writing out the item's own
facts, where each fact costs `len(source) + len(target) + len(relation) + 4` characters
(two names, the relation word, and the spaces and period). Every item in every cell exceeds
the bound. **This is not evidence of traversal.** A faithful traversal legitimately
restates each relation, so the measure cannot separate "restated the premises" from "walked
the chain". It is reported as a confound, not as a mechanism result. The trace text itself
is not archived (public-only rule), so no trace-content claim is made.

Naming coverage is stronger: every gold-yes item in every cell names all of its own
intermediate entities (5/5, 4/4, 3/3, 6/6 for fixture_l2, shipped_l2, fixture_l8,
shipped_l8). The `process.named_fraction` means 0.5, 0.4, 0.3, 0.6 for the same cell order
count a gold-no item as 0, so each mean is just the cell's gold-yes share over 10; the mean
over gold-yes items alone is 1.0000 in all four cells. Naming intermediates is consistent
with traversal but does not exclude a single-pass read of the fact list.

### 4.4 The fixture arm is degenerate

On the pinned fixture corpora in `generators/fixtures/issue67_prefix_l{2,8}.jsonl` (38 items
per level, sha256 `1917b2735e82cee4...` and `d1df8a93e9394752...`) the leak signature equals
the gold label on 38/38 items at both levels, so answering by signature scores 1.0 and
answering by traversal scores 1.0. The fixture arm therefore cannot discriminate shortcut
from traversal at all. It is a capability control: it shows the endpoint answers single-hop
entailment perfectly, which is what makes the shipped-arm perfect score informative. This is
a design defect in the arm, recorded here and on issue #67.

The signature that matches gold is **not** the entailment signature of section 4.2. On the
fixtures the queried pair is never itself a stated fact (0 of 38 at each level), so
`B_direct` scores 0.5000 and 0.7000 on the probed samples. What matches gold is the
target-role signature: answer yes exactly when the query's target appears as the target of
some stated fact and has no outgoing fact. `analyze_run.py` scores the two conjuncts
separately over the whole corpora, and on the pre-fix items **each conjunct alone**
reproduces the label:

| Corpus | n | gold yes | conjunct true on | conjunct accuracy vs gold |
|---|---|---|---|---|
| fixture l2 | 38 | 21 | query target is a fact target: 0.5526 of items | 1.0000 |
| fixture l2 | 38 | 21 | query target has no outgoing fact: 0.5526 of items | 1.0000 |
| fixture l8 | 38 | 16 | query target is a fact target: 0.4211 of items | 1.0000 |
| fixture l8 | 38 | 16 | query target has no outgoing fact: 0.4211 of items | 1.0000 |
| shipped l2 | 300 | 140 | both conjuncts: 1.0000 of items | 0.4667 |
| shipped l8 | 300 | 157 | both conjuncts: 1.0000 of items | 0.5233 |

Each conjunct is true on exactly the gold-yes items of the pre-fix arm, and is true on every
item of the repaired arm, which is why the conjunction is constant there and gold-equivalent
here. The pre-fix construction therefore leaks the answer through the queried target's role
in the fact list, and the repair removed exactly that leak.

The fixture arm is also not a matched-pair arm in the sense the probe's docstring defines:
see section 4.6.

### 4.5 Corpus finding: the gate class is too narrow

`python3 runs/nightly-2026-10-16-0200/name_channel_audit.py` scores 21 features against the
gold label over the whole corpus: 16 traversal-free features computed from entity names and
their positions in the fact list only, and 5 structural features computed from the
undirected fact graph. Exact two-sided binomial p-values, Bonferroni-corrected at
`0.05 / 21 = 0.002381`. The battery is a run-directory sidecar, and `analyze_run.py`
re-runs it in-process and confronts the result against the pinned copies
`name_channel_audit_shipped.json` (sha256 `800b9b11cf349a6f...`) and
`name_channel_audit_fixtures.json` (sha256 `cec5ff986dc27c03...`).

| Corpus | level | n | gold yes | best traversal-free accuracy | best p | flagged | `same_component` accuracy |
|---|---|---|---|---|---|---|---|
| shipped | 2 | 300 | 140 | 0.5700 (`src_name_len_eq_tgt_len`) | 0.017779 | none | **1.0000** |
| shipped | 4 | 300 | 148 | 0.5400 (`src_name_len_gt_tgt_len`) | 0.184117 | none | **1.0000** |
| shipped | 6 | 300 | 166 | 0.5467 (`src_sorts_before_tgt`) | 0.118886 | none | **1.0000** |
| shipped | 8 | 300 | 157 | 0.5267 (`src_first_mention_index_lt_tgt_first_mention_index`) | 0.386510 | none | **1.0000** |
| fixtures | 2 | 38 | 21 | 0.5526 | 0.627103 | none | **1.0000** |
| fixtures | 8 | 38 | 16 | 0.7105 (`tgt_name_len_is_min`) | 0.013853 | none | **1.0000** |

No traversal-free feature clears the corrected threshold anywhere, on either corpus. The
most suggestive one, name-length equality of the two query endpoints on shipped l2, reaches
0.5700 with p 0.017779, which is 7.5 times the corrected threshold. On the fixtures at l8,
`tgt_name_len_is_min` reaches 0.7105 with p 0.013853, which would look suggestive uncorrected
and does not survive the correction. The battery exits 5 on both corpora.

The feature that does reproduce the label is structural: are the source and the target in
the same connected component of the undirected fact graph? `same_component` scores accuracy
1.0000 on all 300 items at every shipped level and on all 38 items at both fixture levels,
p 0.0. Components are not stored in the items, so `analyze_run.py` derives them from the
fact graph with its own implementation and confronts it against the battery's, on every
item of every corpus (1276 items, 0 partition disagreements):

| Corpus | level | n | components per item (min / mean / max) | items with endpoints in different components | gold-yes items in different components |
|---|---|---|---|---|---|
| shipped | 2 | 300 | 2 / 3.04 / 4 | 160 | 0 |
| shipped | 4 | 300 | 2 / 3.86 / 6 | 152 | 0 |
| shipped | 6 | 300 | 2 / 5.05 / 8 | 134 | 0 |
| shipped | 8 | 300 | 2 / 5.81 / 10 | 143 | 0 |
| fixtures | 2 | 38 | 2 / 3.87 / 6 | 17 | 0 |
| fixtures | 8 | 38 | 3 / 7.03 / 12 | 22 | 0 |

The last column is the whole finding: there is no item anywhere in either corpus where the
endpoints sit in different components and the answer is yes, and no item where they share a
component and the answer is no. Component membership and the gold label are the same
partition of the corpus.

Consequences:

- The 18-feature gate class contains no relational feature, so `no_leak` on the shipped
  corpus understates what is actually recoverable from the query surface. The gate is
  honest about the class it tests and silent about the rest.
- A model that clusters the fact graph can answer every ladder correctly without following
  any edge in order. The probe cannot separate directed traversal from undirected component
  clustering, so the verdict `traversal_consistent` means "the answers are not explained by
  the tested shortcut signatures", not "the model walked the chain".
- Under a connectivity strategy k is not a difficulty ladder: connectivity accuracy is 1.0
  at k=2, 4, 6, and 8. The k-sweep measures the difficulty of the traversal strategy only,
  not of the task.
- The gate's own numbers agree with this reading. On the shipped corpus **every one of the
  18 audited single features is constant** at l2, l4, l6, and l8 (`direct_fact` is constant
  false, the entailment signature is constant true), so the class carries no signal at all on
  the repaired corpus; the best hypothesis it can build reaches 0.5133 (l2), 0.5267 (l4),
  0.5600 (l6), 0.5533 (l8), all below its `min_detectable_accuracy` of 0.5700 (l2, l8),
  0.5633 (l4), 0.5867 (l6). On the fixtures the gate fires: gate status `leak`, best
  hypothesis `direct_fact==false & tgt_back_len_eq_level==true` at accuracy 1.0, permutation
  p 0.0033, `min_detectable_accuracy` 0.7105 (l2) and 0.7368 (l8). Those numbers are pinned
  in `audit_shipped.json` and `audit_fixtures.json`.

### 4.6 The arms are paired by seed only

The probe's design intent, as written in `generators/probe_ladder_shortcut.py` before the
run, was a matched pair: the same item under a shortcut-friendly and a traversal-only query.
`generators/fixtures/issue67_prefix.manifest.json` states the construction that was actually
built: the fixture item takes the **first `level` facts** of the shipped item carrying the
same seed, and asks about the first and the last entity of that prefix chain. That is a
prefix relation, not a same-item relation. `analyze_run.py` now confronts the claim item by
item, pairing each probed fixture item with the shipped item of the same seed:

| Level | pairs | same seed | same fact chain | same entity names | same queried pair | same n_facts | same gold label |
|---|---|---|---|---|---|---|---|
| l2 | 10 | 10 | 0 | 0 | 0 | 5 | 3 |
| l8 | 10 | 10 | 0 | 0 | 1 | 0 | 5 |

The prefix rule itself holds on all 38 fixture items at both levels. So the two arms share a
seed and nothing else about the item: different entity names, different fact chains, and at
l2 not even the same queried pair. Consequences:

- The fixture arm is not "the same item under an easier query". It is a different corpus
  generated from the same seeds, and its perfect score and the shipped arm's perfect score
  are answers about different items.
- The design intent is not met by the shipped generator, and the instrument was not edited
  mid-run. The claim in this report is the weaker one the artifacts support: the arms are
  paired by seed.
- Control 14 in `analyze_run.py --selftest` plants a fixture item whose facts and query are
  copied from its shipped partner and asserts that the pairing confrontation fires, so a
  future generator that really does reuse the construction would be caught rather than
  praised.

## 5. Deviations (dated 2026-10-16)
1. **Over-cap endpoint usage**: 66 endpoint calls for a 40-prompt design, 26 over cap,
   caused by two client timeouts and one crash. Cause, corrective rule, and per-attempt
   accounting in `attempts.json`.
2. **Client timeout raised twice** (180 s, then 300 s, then 600 s) between invocations.
   The instrument's other parameters were unchanged.
3. **Sidecars added after the run**: `attempts.json`, `environment.json`,
   `analyze_run.py`, `name_channel_audit.py`, the pinned battery reports
   `name_channel_audit_shipped.json` and `name_channel_audit_fixtures.json`, and the pinned
   gate reports `audit_shipped.json`, `audit_fixtures.json`, `audit_generated.json`. The
   manifest and `probe_raw.jsonl` are unchanged since the run finished.
4. **Battery control corrected before its first run**: the first version of
   `name_channel_audit.py --selftest` planted a name leak in a corpus whose labels were not
   balanced (its planted rule never produced a `yes`), and shuffled the labels by rotation,
   which on an alternating planted corpus only inverts the planted leak. Both made control 2
   assert something false. The corpus was rebalanced to 100 yes / 100 no and the shuffle
   replaced by a seeded permutation. The script had never run successfully and no number from
   it had been cited, so no confrontation is invalidated.
5. **Model identity is partial**: the manifest records the public model label only;
   `weights_hash` and `serving_revision` are null with a note, because the serving endpoint
   does not expose them.
6. **Trace text not archived** (public-only rule), so the trace claims in 4.3 are numeric
   restatements of archived fields, not content claims.

## 6. Limits

- n=10 per cell: screening. Both exact nulls are small, but the cells are too small to
  separate mechanisms.
- The verifier used an independent implementation over the archived artifacts, but the same
  model family serves the endpoint, so implementation independence is not model independence.
- The probe cannot distinguish traversal from connectivity clustering (4.5).
- The fixture arm cannot test shortcut use (4.4), and the arms are paired by seed only, not
  item-to-item (4.6).
- The instrument's per-cell fields `leak_sig_agreement` and `direct_agreement` are
  mislabelled: they hold baseline-vs-gold accuracy, not model-vs-baseline agreement. The
  model-vs-baseline numbers in 4.2 come from `analyze_run.py`. The instrument was not
  edited after the run; the naming fix is deferred to a follow-up issue.
- The battery tests 21 features, not the space of all surface regularities. Absence of a
  flagged name or position feature is not absence of a name or position shortcut.

## 7. Next step

1. Build a shortcut TRAP corpus that defeats connectivity as well as the endpoint-role
   features: items where source and target are in the same component but the answer is no,
   and items in different components where the answer is yes, with distractor entities that
   share name prefixes with the queried pair. Gate the corpus with a widened class that
   includes relational features (new issue).
2. Re-run the probe on the TRAP corpus with the trace text archived as a
   content-addressed artifact so that trace claims become checkable, plus a
   distractor-naming control.
3. Fix the misnamed instrument fields and widen `generators/audit_ladder_leaks.py` to the
   relational class, then re-audit the shipped corpus. Widening changes the audit script's
   pinned hash, so it must land as its own issue and its own run, not as an edit inside a
   round that already cited the old hash.
4. Build a generator that emits a **true** matched pair: one item, two queries, one where the
   shortcut signature fires and one where it does not, so the two arms differ only in the
   query. The shipped generator cannot produce this (4.6): it pairs by seed, and a seed-paired
   pair shares no content.

## 8. Verification

### 8.1 Script gates

- `python3 runs/nightly-2026-10-16-0200/analyze_run.py --selftest`: 14 seeded-defect control
  groups (scorer polarity and leak-signature reproduction, exact null values, shuffled-label
  confrontation, flipped answers in one cell, rewritten raw file hash, planted budget lie,
  clean-artifact confrontation, fixture-arm degeneracy, shipped-arm entailment chance level,
  tampered per-record prompt hash, tampered manifest task hash, tampered pinned environment
  hash, tampered pinned battery report and battery verdict, planted corpus item that breaks
  connectivity plus a planted fixture item that shares its shipped partner's construction, and
  cross-implementation agreement of the two component implementations on all 1276 corpus
  items), 0 mismatches on clean artifacts.
- `python3 runs/nightly-2026-10-16-0200/analyze_run.py --check`: 0 mismatches. It re-derives
  every reported number from the raw records, rebuilds all 40 prompts from the corpus and
  compares them with the archived prompt hashes, confronts the pinned environment hashes
  against the working tree, confronts the stored battery report against a fresh in-process run
  of the battery, confronts the pairing counts of section 4.6 and the full-corpus entailment
  counts of sections 4.2 and 4.4, and asserts the connectivity invariant (no gold-yes item
  whose endpoints sit in different components) on every corpus.
- `python3 runs/nightly-2026-10-16-0200/name_channel_audit.py --selftest`: 5 control groups
  (planted name leak detected, seeded label shuffle leaves nothing significant, connectivity
  shortcut detected on the shipped corpus, determinism, fixtures reproduce the pre-fix
  pattern), exit 0.
- `python3 generators/audit_ladder_leaks.py --selftest --audit-fixtures --audit-shipped`:
  selftest ok, fixtures gate `leak`, shipped gate `no_leak`, exit 0. The two JSON reports it
  prints are byte-identical to the pinned `audit_fixtures.json` and `audit_shipped.json`.

### 8.2 Independent verifications

Two independent verifications are archived in this directory, and they are not collapsed into
one label.

`verify_independent.md` records a second agent configuration that recomputed the cell metrics,
the raw-file hash, the record-versus-manifest consistency, the full-corpus connectivity
accuracy, the full-corpus baseline behaviour, and the seeded-defect recall, using code that
does not import any project script. It found 3 prose errors in the first draft of this report,
all corrected: the null was described as a label-permutation null, the 4.2 column meanings were
stated wrongly, and the latency was quoted from calls whose artifacts do not exist.

`verify_report_v2.md` records a second, later verification against the report as it stood after
those corrections. It re-verified artifact integrity (12 pinned hashes, the raw-file sha256,
the prompt-hash chain), confronted 84 manifest fields against its own recomputation (76 exact,
8 rounding residuals), confronted all 40 archived records against the manifest cell
assignments, re-ran a 16-feature surface audit of its own construction and reproduced the
pinned gate reports, and probed seeded-defect recall: 8 of 9 planted defects were recoverable
from the artifacts and the corpus alone, the 9th (a latency swap between two cells) is
invisible without the manifest hashes. It filed a discrepancy register D1-D12.

### 8.3 Disposition of the discrepancy register

Every register item was re-checked against the artifacts by the author of this report before
being accepted or declined.

Accepted and fixed in this report:

- D1: `generators/AGENTS.md` documented `seed_hash` as `sha256("<family>|<task_type>|<seed>")`,
  which is what `generators/digit_matrices.py` implements but not what `generators/ladders.py`
  implements. The ladder form includes the level: `sha256("ladders|hop_chain|<level>|<seed>")`
  truncated to 16 hex characters, verified on 300 of 300 items at each of the five ladder
  levels. The documentation is corrected in `generators/AGENTS.md`.
- D2: `process.named_fraction` counts a gold-no item as 0, so the cell mean equals the cell's
  gold-yes share over 10. Stated in 4.3.
- D8: the arms are paired by seed only. Stated in 4.6, made regenerable by the pairing block in
  `analyze_run.py`, and guarded by control 14.
- D9: the fixture arm's leak is the target-role signature, not a single-fact entailment; the
  queried pair is never a stated fact in either arm. Stated in 4.4, made regenerable by the
  entailment block, which now scores both conjuncts separately.
- D10: the restatement bound is a verbatim-restatement character bound, not "one mention per
  fact, longest name first". Stated in 4.3.
- D12: the endpoint accounting closes as 61 answered plus 4 failed attempts plus 1 call that was
  still in flight when the run was interrupted. Stated in 3.

Declined as filed:

- D11 claimed the report states 13 control groups while `analyze_run.py` implements 14. At the
  time the register was written the script implemented 13 groups and the report said 13, and the
  selftest printed 13. The 14th group (the pairing confrontation) was added afterwards, in
  response to D8, and section 8.1 now states 14. There was no mismatch between report and script
  when the register was filed, so D11 is recorded as a false positive rather than as a defect
  that was fixed.

The register itself is left in `verify_report_v2.md` unedited. Verifier findings are not
rewritten by the author of the verified document; the disposition above is the author's record
of what was accepted, what was fixed, and what was declined with evidence.
