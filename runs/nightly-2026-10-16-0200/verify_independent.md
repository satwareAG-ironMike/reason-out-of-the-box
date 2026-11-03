# Independent verification record (2026-10-16)

Verifier: a fresh agent session with no shared context with the round agent, instructed to
recompute the run's numbers with its own code and to import nothing from `generators/` or
from `runs/nightly-2026-10-16-0200/analyze_run.py`. It worked read-only from the landed
artifacts plus `items/ladders/l2.jsonl` and `items/ladders/l8.jsonl`, and wrote its throwaway
scripts outside the repository. Its own attempt to write a report file into this directory
failed (tool error), so its output is recorded here verbatim in the round agent's
sanitisation, with the throwaway directory path removed.

Independence limit: the verifier ran on the same model family that served the probe
endpoint. Its implementation is independent; its model is not.

## Recomputation against the manifest

All cell metrics matched: n, valid, client errors, balanced accuracy, plain accuracy,
`mean_completion_tokens`, `mean_trace_chars`, `mean_n_facts`, `named_fraction_mean`,
gold-yes items naming all intermediates (5/5, 4/4, 3/3, 6/6), the sha256 of
`probe_raw.jsonl`, and 40/40 record-vs-manifest consistency (cell, level, seed, seed hash,
gold label, `n_facts`, `resumed` count equal to `items_reused_from_prior_attempt`).

Three disagreements were found, and all three are description errors in the round report
rather than errors in the artifacts. They are corrected in [report.md](report.md):

1. The null. The verifier first used a balanced label-permutation null (C(10,5) = 252
   assignments) and got p = 0.00397 for fixture_l2 and p = 0 for the three cells with
   unbalanced gold splits, because under a balanced permutation the maximum attainable
   balanced accuracy is below 1.0 for a 4/6 or 3/7 cell. The instrument's null is the
   fair-coin answering null over 2^10 = 1024 answer assignments (`support_size: 1024` in
   the manifest). Re-running under that null the verifier reproduced the manifest exactly:
   p = 1/1024 = 0.000977 and null p95 0.8, 0.75, 0.7857, 0.75. The report now states the
   fair-coin null and records the balanced-permutation alternative and why it is not used.
2. Latency. The report quoted a mean over all 61 answered calls, which is not regenerable
   from archived artifacts. The archived 40 records give mean 121.8645 s, minimum 21.587 s,
   maximum 345.144 s, and per-cell means 97.197, 120.5621, 130.1691, 139.5296 s. The report
   now quotes only the archived numbers.
3. Baseline semantics. The manifest fields `leak_sig_agreement` and `direct_agreement` are
   the plain accuracy of the a-priori baseline against the gold label, not model-versus-
   baseline agreement, and `baselines_balanced` are balanced accuracies. The report now
   states both, and names the mislabelling as an instrument defect deferred to a follow-up.

Two further verifier notes are recorded as limits rather than corrections:

- The verifier could not recompute the fixture cells' trace-over-restatement ratios because
  its instructions limited it to the run directory and `items/ladders/`; the fixture corpora
  are archived in `generators/fixtures/`, and `analyze_run.py` reads them, so the ratios are
  regenerable. The verifier confirmed the 10/10 counts independently under a conservative
  character bound.
- The verifier's own "leak signature" was `direct_fact` (the queried pair appears verbatim
  as a fact), which is a different feature from the instrument's pre-fix signature rule
  (query target is a fact target AND has out-degree zero). Both are reported separately in
  the report, and both are constant on the repaired corpus.

## Independent corpus audit (verifier's own code)

| Feature | Level | Accuracy vs gold | Exact two-sided p | Reading |
|---|---|---|---|---|
| direct_fact (pair stated verbatim) | l2 | 0.5333 (160/300) | 0.27263 | feature constant false, accuracy equals the gold-no share |
| direct_fact | l8 | 0.4767 (143/300) | 0.45298 | feature constant false, accuracy equals the gold-no share |
| not direct_fact AND target back length equals level | l2 | 0.4667 (140/300) | 0.27263 | conjunction constant true, accuracy equals the gold-yes share |
| not direct_fact AND target back length equals level | l8 | 0.5233 (157/300) | 0.45298 | conjunction constant true, accuracy equals the gold-yes share |
| undirected connectivity (same component) | l2 | 1.0000 (300/300) | 9.82e-91 | deterministic shortcut, 2 to 4 components per item |
| undirected connectivity (same component) | l8 | 1.0000 (300/300) | 9.82e-91 | deterministic shortcut, 2 to 10 components per item |

The connectivity result reproduces `name_channel_audit.py` exactly, from code that shares
nothing with it.

## Seeded-defect recall (verifier's own checks)

| Planted defect | Caught | How |
|---|---|---|
| flipped one gold label (shipped_l8, seed 36261013) | yes | gold counts 5/5 against manifest 6/4, balanced accuracy 0.9 against 1.0, artifact hash changed |
| changed one `completion_tokens` value (fixture_l2, seed 24261005) | yes | cell mean 153.5 against 153.4, artifact hash changed |
| deleted one raw record (fixture_l8, seed 36261037) | yes | cell n 9 against 10, gold_no 6 against 7, record count 39 against 40 |

3 of 3 planted defects caught.
