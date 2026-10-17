# Nightly round 5: does a live endpoint answer the repaired ladders by shortcut or by traversal?

Run id `nightly-2026-10-16-0200`. Parent run `nightly-2026-10-15-0400` (the corpus repair
that created the matched pairs). Tracker issue #65, generator issue #67.
Label: **Executed**. The derived numbers are additionally **Reproduced** by an independent
recomputation from the archived artifacts (see Verification); the endpoint calls themselves
were not re-run, because every paid call is charged once. **Validated** is not claimed:
there is no independent-endpoint or independent-model-family evidence yet.

## 1. Question

The round-4 audit repaired 186 leaky ladder items and shipped 60 matched pairs: 30 items
whose queried pair is directly entailed by a single fact, and 30 items with the same seeds
whose queried pair is not. The leak gate now beats the class's own label-permutation null,
so the corpus is clean under an 18-feature class. The open question this round:

> Does a live endpoint answer the k-hop ladders because the surface of the query tells it
> the answer (shortcut), or because it walks the chain (traversal)?

Three sub-questions, each with its own test:

1. Can the endpoint answer at all at k=2 and k=8? (capability)
2. Does its answer track the shortcut signature, or the traversal result? (mechanism)
3. Does the shipped corpus contain any shortcut the gate class does not see? (corpus)

## 2. Design, fixed before any endpoint call

Written into the instrument before the first call, and not changed afterwards:

- 4 cells x 10 items = 40 prompts, the cap. Cells: `fixture_l2`, `shipped_l2`,
  `fixture_l8`, `shipped_l8`. The shipped cells are matched pairs: identical seeds,
  identical entity names, identical fact chains, differing only in whether the queried pair
  is one of the facts.
- Fixture cells are the pinned issue #67 negative controls, where the queried pair is
  entailed by a single fact on every item.
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
(l2) and 4 of 10 items (l8) while agreeing with the gold label on all 20. On the full
shipped corpus the entailment signature itself scores 0.4667 (l2) and 0.5233 (l8), that is,
it is a coin flip: there is no entailment shortcut on the shipped corpus for the model to
take. So the shipped answers are not entailment-signature answers.

### 4.3 Process measures, and what they do not show

| Cell | mean completion tokens | mean reasoning chars | mean facts in item | mean trace/restatement ratio | items above 1.0 |
|---|---|---|---|---|---|
| fixture_l2 | 153.4 | 518.9 | 4.9 (4-7) | 4.8392 | 10/10 |
| fixture_l8 | 247.3 | 766.9 | 13.9 (10-19) | 2.6005 | 10/10 |
| shipped_l2 | 139.8 | 469.7 | 5.8 (4-8) | 4.2473 | 10/10 |
| shipped_l8 | 556.9 | 1514.2 | 39.2 (16-80) | 2.2099 | 10/10 |

The trace-over-restatement bound counts the shortest possible restatement of the item's own
facts (one mention per fact, longest name first) and compares it with the number of entity
mentions in the reasoning trace. Every item in every cell exceeds it. **This is not
evidence of traversal.** A faithful traversal legitimately restates each relation, so the
measure cannot separate "restated the premises" from "walked the chain". It is reported as
a confound, not as a mechanism result. The trace text itself is not archived (public-only
rule), so no trace-content claim is made.

Naming coverage is stronger: every gold-yes item in every cell names all of its own
intermediate entities (5/5, 3/3, 4/4, 6/6), and `process.named_fraction` means are 0.5,
0.4, 0.3, 0.6 for fixture_l2, shipped_l2, fixture_l8, shipped_l8. Naming intermediates is
consistent with traversal but does not exclude a single-pass read of the fact list.

### 4.4 The fixture arm is degenerate

On the pinned fixture corpora in `generators/fixtures/issue67_prefix_l{2,8}.jsonl` (38 items
per level, sha256 `1917b2735e82cee4...` and `d1df8a93e9394752...`) the leak signature equals
the gold label on 38/38 items at both levels, so answering by signature scores 1.0 and
answering by traversal scores 1.0. The fixture arm therefore cannot discriminate shortcut
from traversal at all. It is a capability control: it shows the endpoint answers single-hop
entailment perfectly, which is what makes the shipped-arm perfect score informative. This is
a design defect in the arm, recorded here and on issue #67.

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
- The fixture arm cannot test shortcut use (4.4).
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

## 8. Verification

- `python3 runs/nightly-2026-10-16-0200/analyze_run.py --selftest`: 13 seeded-defect control
  groups (scorer polarity and leak-signature reproduction, exact null values, shuffled-label
  confrontation, flipped answers in one cell, rewritten raw file hash, planted budget lie,
  clean-artifact confrontation, fixture-arm degeneracy, shipped-arm entailment chance level,
  tampered per-record prompt hash, tampered manifest task hash, tampered pinned environment
  hash, tampered pinned battery report and battery verdict, planted corpus item that breaks
  connectivity plus cross-implementation agreement of the two component implementations on
  all 1276 corpus items), 0 mismatches on clean artifacts.
- `python3 runs/nightly-2026-10-16-0200/analyze_run.py --check`: 0 mismatches. It
  re-derives every reported number from the raw records, rebuilds all 40 prompts from the
  corpus and compares them with the archived prompt hashes, confronts the pinned
  environment hashes against the working tree, and confronts the stored battery report
  against a fresh in-process run of the battery.
- `python3 runs/nightly-2026-10-16-0200/name_channel_audit.py --selftest`: 5 control groups
  (planted name leak detected, seeded label shuffle leaves nothing significant, connectivity
  shortcut detected on the shipped corpus, determinism, fixtures reproduce the pre-fix
  pattern), exit 0.
- Independent verification: `verify_independent.md` in this directory records a second agent
  configuration that recomputed the cell metrics, the raw-file hash, the record-versus-
  manifest consistency, the full-corpus connectivity accuracy, the full-corpus baseline
  behaviour, and the seeded-defect recall, using code that does not import any project
  script. It found 3 prose errors in the first draft of this report, all corrected above:
  the null was described as a label-permutation null, the 4.2 column meanings were stated
  wrongly, and the latency was quoted from calls whose artifacts do not exist.
