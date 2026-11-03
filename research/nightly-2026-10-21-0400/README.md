# Round 16 (2026-10-21 04:00): cell-paired cross-class probe of the repaired ladders family

Tracker: issue #65. Serves: #71 (depth-ceiling placement per (family, endpoint)), #78
(matched-pair instrument across endpoint classes on the repaired corpus), #73 (transport
policy reuse), #69 (the repair measured here). Summary comment: issue #65 of 2026-10-21.

## Question

Round 15 ran the matched-pair probe on the repaired (component-isomorphic) ladders family
at k = 12, 16, 24 on a flash-next-class local endpoint: the directed-traversal verdict
held (36/36) and every 2048-token truncation landed on a negative arm (the output budget,
not reachability, is the scarce resource at k = 24). Rounds 10/11/14 ran the same
design on the pre-repair corpus, so no cell-paired cross-class comparison exists on the
repaired family. Two questions: (1) does the round-15 repaired-instrument verdict hold on
a second endpoint class - a 27B-class local endpoint (the pool slot round 14 measured
pre-repair)? (2) On the identical corpus, are the two endpoint classes cell-agreeing, and
does the negative-arm truncation signature at k = 24 replicate?

## Method and selection rule

`fixed_corpus_crossclass.py` (stdlib only; port of round 15's `fixed_corpus_probe.py`,
lineage declared in the script header). Three subcommands after `--selftest` (74 checks,
0 failures): `--gate` (corpus verification, 15-rule direction-blind battery + 2 chain
references, exact label-shuffle nulls, `gate.json`), `--probe` (36 prompts, temperature
0, max_tokens 2048, two-phase transport per issue #73 unchanged: two sequential cells
measure the endpoint, remaining 34 at concurrency 4; 900 s per-item deadline; one retry
per arm under a global 40-attempt cap; incremental fsynced `raw.jsonl`), `--analyze`
(read-only aggregates to `summary.json`).

Corpus: **byte-identical to round 15** (same generator module sha256 `b0d77efd...`,
same three regenerated blob pins at seed_base 20261019, same selection rule "first 3
usable items per level in generated file order", pool of 900 items at levels 12/16/24).
Cell pairing: all 36 prompt sha256 values verified against the round-15 archive in-tree
on this branch (its `gate.json` and `raw.jsonl` pinned by sha256) **before any prompt
is spent**; `--probe` refuses to run when pairing is unverified (fail-closed). The
lineage rounds 10/11/14/6 stay same-construction and directional (pre-repair corpora).

Three declared differences from round 15: (1) cell-paired reference to round 15 instead
of a declared lineage; (2) `--analyze` adds a cross-class section joining this round's
raw archive with the round-15 archive on (item_id, arm): answer agreement, exact
McNemar on the matched correct/incorrect outcomes, per-arm completion-token and
truncation-signature comparison; (3) endpoint class (27B class here, flash-next class in
round 15).

## Results (Executed; one endpoint, one run)

- Gate `a97f68f2ee694c5ad0ab2fc28056ebea0ac4db93df63159d3e8f3fa3ea181649` (schema
  `round16-gate-v1`), built and hashed before any prompt. The repair is visible in the
  battery (`target_is_fact_target` scores 0.5133 on the pool; the selftest's
  role-constancy control catches a planted pre-repair-style leak). Matched corpus
  discriminating: connectivity != reachability in exactly 9 cells (the R1 cells), best
  blind rule 0.7500, no rule fires under Bonferroni. Cell pairing verified 36/36;
  reference gate hash matches round 15's `10f569414bbf19b6...`.
- Probe: **total endpoint calls 40 including the health check** (36 cells + 1 health +
  3 retries on the three truncated X cells at k = 24), zero abandoned, zero cells
  lost. Health 8.813 s / 23 completion tokens; phase-1 walls 17.98 / 56.02 s,
  per-item estimate 112.0 s, concurrency 4; phase-2 wall 636.5 s.
- Answers: **33/33 answered cells correct** - F1, R1, F2 each 9/9 (Wilson 95% lower
  bound 0.701 per arm), X 6/9 answered with all six correct (Wilson lower bound 0.610).
  Three cells are unanswerable within the declared budget: the X cells of items L24-1,
  L24-2, L24-3 (2 attempts each at 2048 tokens, no parseable yes/no in `content` or
  `reasoning`: `truncated_no_answer`).
- Signature table: traversal 36/36 (under the disclosed default-match convention),
  connectivity 27/36 (fails exactly the nine R1 cells), constant-yes and constant-no
  18/36. Exact McNemar: direction family F1/R1 has zero discordant pairs (9/9
  both-right, p = 1.0); component family F2/X has zero discordant pairs on the 6 scored
  pairs (the 3 unanswered X cells at k = 24 are skipped, p = 1.0).
- **Cross-class (cell-paired to round 15, joined on (item_id, arm), 36/36 cells
  joined):** 33/33 agreement on all cells both classes answered, **zero discordant
  pairs** (exact McNemar on matched outcomes p = 1.0). The only cross-class outcome
  delta is the three X cells at k = 24: round 15 truncated at 2048 but had already
  emitted the correct "no" inside the reasoning trace (recovered by the declared
  parser), while round 16 truncated at 2048 on two attempts with no parseable answer in
  either field. The rescue-via-trace property does not transfer across classes: the
  same cells are answerable within budget on the flash-next class and not on the 27B
  class.
- Per-arm mean completion tokens, this round vs round 15: F1 317.1 / 899.8,
  R1 368.7 / 1336.9, F2 339.7 / 762.1, X 1380.4 / 1733.4; per level (k = 12/16/24)
  487.3 / 469.8 / 847.3 vs 1179.7 / 995.8 / 1373.7.
- Style, class-dependent: this endpoint is a light thinker - mean 469.97 tokens per
  answered cell (round 15: 1183.1), 99.8% of output characters in the reasoning field
  (mean content 2.5 characters), **all 33 answers from `content`** (0 reasoning
  fallback, round 15: 7); chain recitation 5/36 (round 15: 19/36; round 14: 18/36;
  round 11: 36/36). Mean latency is flat across depth: 46.1 / 50.6 / 46.4 s per level
  (round 15 rose 46.9 / 53.9 / 65.4 s). The k = 24 level mean (847.3 tokens) includes
  the three X cells that spent two full 2048-token attempts each; the nine answered
  cells at k = 24 average 447.1 tokens.
- Budget finding, refined: round 15 localized the scarce resource at k = 24 to the
  output budget on negative arms (all seven truncations negative arms, all rescued via
  the reasoning trace). Here the X cells at k = 24 are not merely budget-tight but
  unanswerable within 2 x 2048 tokens on this class, while the identical cells were
  answerable via the reasoning fallback on the flash-next class. R1 at k = 24 - a
  truncation site in round 15 - answers in 350-576 tokens here.

## Disclosure and limits

No independent verifier pass this round: state **Executed**, not Reproduced. n = 9 per
arm, exploratory. Two endpoint classes, one run each; cell-paired to round 15 only
(identical corpus; different endpoint classes). The declared parser reads the last
standalone yes/no in `content` with a `reasoning` fallback; **0** cells needed the
fallback this round (round 15: 7, all correct). Signature-table convention, disclosed:
an unanswered cell counts as "no" (the parser's missing-value convention), so the
traversal 36/36 includes the three X cells at k = 24 matching traversal, constant-no,
and connectivity by default; accuracy statistics are computed on answered cells only
(X: 6/9 answered). One endpoint per class (quantized local deployment, undisclosed
training data); not H1 evidence. Per-level token and latency comparisons to round 15
are cell-paired on outcomes but descriptive on style (different endpoint classes).
Cross-round token comparisons to rounds 11/14 remain same-construction and directional
(pre-repair corpora).

## Reproduce

```
python3 research/nightly-2026-10-21-0400/fixed_corpus_crossclass.py --selftest
python3 research/nightly-2026-10-21-0400/fixed_corpus_crossclass.py --gate   # compare gate_hash
python3 research/nightly-2026-10-21-0400/fixed_corpus_crossclass.py --analyze
```

`--probe` needs a served endpoint via `NIGHTLY_BASE_URL` / `NIGHTLY_MODEL_ID` /
`NIGHTLY_API_KEY` (never written to artifacts) **and the round-15 archive present
in-tree** (`research/nightly-2026-10-21-0200/`): the cell-pairing verification
references it, and `--probe` refuses to run when pairing is unverified. Files:
`gate.json` (pre-registration record including the cell-pairing verification),
`raw.jsonl` (36 records, sanitized raw responses, last attempt per cell),
`summary.json` (aggregates including the `cross_class` section), `transport.json`
(dispatch note).
