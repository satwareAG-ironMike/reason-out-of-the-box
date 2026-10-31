# Round 38 (2026-10-31 02:28): inside one firing the answer is byte-stable and the dispatch mode
moves the trace but never the verdict; what fails across firings is the delivery of the deepest
load cell, whose arm-X prompt sat 5 tokens inside the 2048 ceiling and now truncates every time

Question, method and verdict summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is
the reproducible record: script, gate, prompts, raw responses, scores.

## Question

Issue #100 names the gap: "every cell verdict this program has placed comes from a single run",
and no archived measurement separates decoding noise from firing-level noise, so no archived
ceiling can be quoted with a run-level uncertainty. Round 33 measured same-class repeatability
across two firings three days apart (32 of 36 completions token-identical, cost slopes within
2.6 percent, the same silent digest); round 37 measured it on the other class (0 of 36 identical,
one cell verdict moved, the depth slope came back at 0.35x of the reference) and concluded that a
band test cannot be scored without a same-run noise floor. Neither round could say WHERE the
variation comes from, because both compared two unknown deployments with each other. Both also
left issue #100's acceptance criteria 1 and 2 unmet: no raw archive in this program stores a
per-cell self-agreement pair (raw output and parsed answer), and no archived cell stores a Wilson
interval next to its accuracy.

This round holds the firing fixed and varies the conditions inside it, so the variance can be
attributed instead of assumed.

> On one firing of one endpoint, at temperature 0, how much of an archived cell verdict is
> decoding noise, how much is dispatch mode (serialized versus the concurrency the archived
> rounds used), and how much is the firing itself - and does the deepest load cell of the archived
> frontier still deliver its answer?

Chosen because it is the cheapest experiment that can bound the archived (k, E) verdicts from
inside a single session, because it is the only way to get the per-cell self-agreement pair and
the per-cell Wilson interval that #100 asks for without spending a second full grid, and because
the answer it produces either certifies the published load-arm ceiling at (8, 160) or does not.

## Instrument

`samepanel_replicate_probe.py` (stdlib only, `--selftest` with 266 checks: arithmetic and planted
negative controls, the strict commitment rule, the echo-phrase test, the digest-true replay of the
archived corpus, and an independent recomputation of all four archived cost slopes) inherits its
construction, audit and readout stack verbatim from round 37's
`sameclass_frontier_retest_probe.py` (branch `research/nightly-2026-10-30-0400`, PR #102), which
inherits them from rounds 19 to 24: C disjoint directed paths of exactly k edges over fresh entity
names, one rule sentence (transitivity of `precedes`), E = k x C facts in shuffled order, one query
per prompt, answer required as exactly one word; gold from an unbounded BFS independent of the
generator plus a structural audit of every item; each graph asked twice over identical content
(arm F forward, gold yes; arm X cross-component, gold no) with the shared-content invariant
asserted per pair (#78). Readout stack: `content_only` (primary, scored), `delivered_or_strict`
(content, else the round-19 strict trace-commitment rule), `loose_fallback` (reported, never
scored), with the fallback provenance class of every record (#94).

The panel is the first matched pair (arm F and arm X) of each of round 24's six digest-pinned
cells, chosen by the archived selection order (pair index 0) before any outcome was known:

| Cell | k | C (paths) | E (facts) | round-24 status on this class |
|------|---|-----------|-----------|-------------------------------|
| L0   | 8 | 12        | 96        | maintained                    |
| L1   | 8 | 14        | 112       | maintained                    |
| L2   | 8 | 16        | 128       | maintained                    |
| L3   | 8 | 20        | 160       | maintained                    |
| D1   | 12 | 8        | 96        | maintained                    |
| D2   | 16 | 6        | 96        | inconclusive (5 of 6 delivered, one 2048-token truncation) |

12 prompts, dispatched three times in one session in an ABABA order:

- **P1** serialized, one request in flight (12 dispatches, elapsed 1191 s, 17,399 completion
  tokens, median 21.7 tok/s);
- **P2** at the concurrency the archived rounds on this class used, two in flight (elapsed 490 s,
  sum of per-attempt walls 941 s, 17,711 tokens, median 26.0 tok/s);
- **P3** serialized again (elapsed 291 s, 17,417 tokens, median 64.2 tok/s).

The two serialized passes bracket the batched pass, so agreement between them is the endpoint's
own determinism over an interval that *contains* the mode change, and a difference that appears in
P2 and persists in P3 is drift, not mode. Throughput tripled across the session (transport, not
measurement: the outputs are byte-identical on 11 of 12 prompts between P1 and P3).

Gate `eac3acca` (schema `round38-gate-v1`) written before any prompt was spent: `anchor_ok` true,
all six cells pass the leak audit, corpus blob `88a8633a`, `--selftest` green. Structural pin
fail-closed: all 36 prompt digests and all 6 pool blobs must equal round 24's gate, and the panel
digests are pinned individually, so the panel cannot silently drift off the corpus. The four
archived firings this round joins against (rounds 24 and 33 on this class, rounds 31 and 37 on the
other class) are carried as transcribed per-prompt constants, restricted to the 12 panel digests:
none of the four ancestor branches is on `main` at authoring time, so the post-merge tree verifies
every comparison without them. Round 31's transcription carries no raw-text hash, so every raw pair
involving it is counted as non-joinable rather than as disagreement. Per-prompt joins are on the
prompt digest.

## Declared predictions (fixed in `gate.json` before any prompt was spent)

- **N1 determinism**: serialized-versus-serialized raw-output agreement (TARr) at least 0.90 over
  the 12 same-mode replicate pairs and at least 0.50 in every cell (each cell carries 2 same-mode
  pairs, so at most one may disagree);
- **N2 dispatch mode**: the concurrency change moves nothing: serialized-versus-batched TARr 1.00
  and no prompt's completion length changes;
- **N3 parsed answer**: TARa 1.00 in every stratum;
- **N4 delivery**: all 36 dispatches answer in the answer field and all 36 are correct
  (`content_only`);
- **N5 cost law**: the panel load slope (k = 8) and panel depth slope (E = 96) of every pass inside
  the 0.5x to 2.0x house band around the round-24 panel reference (load 10.8545, depth 24.875);
- **N6 noise guard, the measurement rule**: a slope difference counts as a change only beyond the
  0.99 quantile of the same-class noise floor of its own stratum, the floor built by propagating
  that stratum's observed per-prompt length differences through the same slope estimator (4000
  draws, seed 20261031); a stratum whose floor rests on a single observed pair is reported as not
  separable, never as a change.

Reported alongside, not predicted: the per-cell self-agreement pair and Wilson interval (#100
criteria 1 and 2), per-item flip rates propagated to the probability that at least one of six items
moves on a re-run, the class-identity diagnostic, and the cross-class resolvability verdict.

## Results

Transport clean: endpoint healthy at session start (0.96 s at the 256-token budget), 37 of the
40-call cap (1 health + 36 panel dispatches), `max_tokens` 2048, `temperature` 0.0, zero retries,
zero transport errors, no item near the 600 s per-item deadline (slowest attempt 298.6 s), 52,527
completion tokens, 62,538 prompt tokens. Predictions: N1, N5, N6 pass; N2, N3, N4 fail, and the
three failures are the finding.

1. **N1 passes: within a session the endpoint is byte-deterministic on 11 of 12 prompts.**
   Serialized-versus-serialized TARr 0.9167 against a floor of 0.90. The single discordance is L3
   arm F (digest `4ed1d525026f`, 1756 tokens in P1, 1774 in P3, +1.0 percent), same gold, same
   correct answer; L3 therefore sits at exactly its per-cell floor of 0.50, held up only because
   both of its truncated arm-X completions are byte-identical to each other. Every other prompt is
   byte-identical.
2. **N2 fails: dispatch mode moves the trace, never the verdict.** Serialized-versus-batched TARr
   0.875. Two prompts move: D2 arm X (digest `de5ed21b3289`) grows from 1619 to 1913 tokens under
   concurrency (+294, +18.2 percent) and returns to 1619 when serialized in P3; L3 arm F grows
   1756 to 1774 in P2 and *stays* at 1774 in P3, so that one is within-session drift, not a mode
   effect, and the ABABA order is what separates the two. TARa is 1.00 in both within-run strata and
   no dispatch changes its delivered state: at temperature 0 on this class batching perturbs length,
   not the answer. Only the D2-X move exceeds the 10 percent material-change threshold.
3. **N5 passes and N6 with it: the cost slopes move, but not beyond their own noise floor.** Panel
   load slope 10.8946 (P1), 11.0393 (P2), 11.0393 (P3) against the round-24 panel reference 10.8545;
   panel depth slope 24.875, 43.25, 24.875 against 24.875. P2's depth slope is 1.74x the reference,
   entirely because the batched pass lengthened one D2 item; the house band (12.44 to 49.75 tokens
   per hop) swallows it, and the noise guard says the same: the P1-to-P2 depth difference of 18.375
   tokens per hop is inside the mode-change stratum's own floor (q99 24.545). Measured floors,
   tokens per fact / tokens per hop: serialized determinism 0.18 / 1.50; mode change 2.95 / 24.5;
   cross-firing up to 2.97 / 24.5. No within-run or cross-firing slope difference this round is
   certifiable as a change, which is the honest reading of the archived slope stability: round 33's
   2.6 percent agreement is inside a floor this round can now name.
4. **N4 fails: the deepest load cell no longer delivers.** L3 arm X (digest `d548b1f9681c`, k = 8,
   E = 160, 2443 prompt tokens) truncated at 2048 in **all three passes**, with byte-identical
   output in each (`output_sha256` `d8f96da2f21d`, finish reason `length`, answer field empty). In
   round 24 and round 33 the same prompt delivered its correct "no" at **2043 tokens**, five tokens
   inside the same budget. This firing does not reach the answer: the reasoning trace stops
   mid-sentence at 4603 characters, having established the correct chain, with the last commitment
   at 97.1 percent of the response (provenance class `mid_trace`). The correct answer is reachable
   only through the unscored reasoning fallback, so the item scores `trace_only` and is lost.
   Delivery 33 of 36, `content_only` accuracy 33 of 36. The archived maintained status of (8, 160)
   sits on a 5-token margin out of 2048, 0.24 percent of the budget.
5. **N3 fails on one item and one mechanism: every delivered answer agrees, across firings and
   across classes.** TARa 1.00 in the within-run strata, 1.00 cross-class (48 pairs), 0.9286
   cross-firing - and all six discordances are the same digest (`d548b1f9681c`, "no" in rounds 24
   and 33 versus no answer in P1, P2, P3). Restricted to pairs where both sides delivered, TARa is
   1.00 in all five strata: of the 180 per-prompt comparisons this round makes, every pair with two
   answers agrees, so there is no answer disagreement, only answer absence. Correctness is
   saturated (33 of 33 delivered answers correct); everything that moves is surfacing.
6. **Reproduction and class identity.** Against round 24, this firing is byte-identical on 30 of
   36 dispatches (P1 11/12, P2 9/12, P3 10/12) with median relative token deviation 0.0; against
   round 33, 27 of 36; against round 37 on the other class, 0 of 36 with median deviation 0.847;
   against round 31 raw hashes are non-joinable (median deviation 1.247). P1 reproduces round 24's
   panel exactly on depth (24.875) and to 0.4 percent on load (10.8946 against 10.8545). Class
   identity stays an inference from the pool slot and the served model id, and the byte agreement
   against the two firings of this class is the strongest evidence the archive can carry.
7. **Per-cell self-agreement pair and Wilson interval (#100 criteria 1 and 2), 2 items per cell.**

   | Cell | accuracy per item | Wilson per item (n = 2) | Wilson per dispatch (n = 6) | TARr same-mode | TARr mode-change | TARr / TARa cross-firing |
   |------|-------------------|-------------------------|-----------------------------|----------------|------------------|--------------------------|
   | L0   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 1.00             | 0.714 / 1.00             |
   | L1   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 1.00             | 1.00 / 1.00              |
   | L2   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 1.00             | 1.00 / 1.00              |
   | L3   | 0.5 (1/2)         | [0.095, 0.906]          | [0.188, 0.812]              | 0.50           | 0.75             | 0.286 / 0.571            |
   | D1   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 1.00             | 1.00 / 1.00              |
   | D2   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 0.50             | 0.857 / 1.00             |

   Both denominators are stored because they answer different questions and only one of them is
   honest per cell: six dispatches of two prompts is not six observations, so the dispatch-level
   interval is a measurement-precision statement about those two prompts and the item-level
   interval is the cell statement. A perfect cell at n = 2 cannot exclude 0.34. This panel is
   exploratory and places no cell verdict; the archived 6-per-cell verdicts stand or fall on their
   own archives.
8. **The flip rate a decision table inherits.** Per-pair flip rates with Wilson intervals:
   raw output 0.083 [0.015, 0.354] same-mode, 0.125 [0.043, 0.310] under the mode change, 0.191
   [0.121, 0.287] cross-firing; material length move 0.083 [0.023, 0.259] mode change and 0.024
   [0.007, 0.083] cross-firing; delivery and parsed answer 0.000 in both within-run strata and
   0.071 [0.033, 0.147] cross-firing. Propagated to a six-item cell under the independence
   assumption (only the within-run stratum tests it): the probability of at least one delivery flip
   on a re-run is 0.36 at the measured rate and 0.62 at the interval's upper bound; at least one
   material length move 0.13 and 0.40; at least one byte difference 0.72 and 0.87. A single-run
   n = 6 cell verdict is therefore one-in-three odds away from a different delivery surface, and
   that number is now measured rather than assumed.
9. **Readout provenance (#94).** 31 records `terminal`, 2 `instruction_echo` (both D2 arm X, P1 and
   P3, where the last commitment sits next to the prompt's own "yes or no" phrase; the same item
   reads `terminal` in P2 because its trace grew), 3 `mid_trace` (the three truncations). Strict
   trace tokens: 18 yes, 15 no, 3 absent, against a gold balance of 18 and 18. The
   `instruction_echo` to `terminal` flip caused by a length change is a direct demonstration of
   #94's point that the fallback token's position, not its value, is what needs the test.
10. **Cross-class resolvability, judged against both classes' own floors.** The load-axis gap
    between this class and the 27B-class endpoint is resolvable: deltas -13.6 and -16.6 tokens per
    fact against a union floor of 12.41. The depth-axis gap is not: deltas +43.8 and -51.1 tokens
    per hop against a union floor of 148.07, because the other class's own run-to-run depth floor
    (its two firings differ by 94.9 tokens per hop) is larger than the class difference. "Resolvable"
    here means beyond the largest noise either class has demonstrated, not beyond a replicated
    bound: the other class's floor rests on a single pair of firings.

## What this means for the program

- **For #71 and the frontier: the (8, 160) maintained verdict is a budget artifact, not a
  capability claim.** The cell's hardest prompt finished at 2043 of 2048 tokens in rounds 24 and 33
  and truncates at 2048 in all three passes here, reproducibly and byte-identically. Any statement
  about the load ceiling at E = 160 is a statement about `max_tokens`, so the ceiling must be
  re-placed under the pre-registered 4096-token budget (issue #12) before it can be quoted, and
  #71's budget-controlled framing is now mandatory rather than tidy.
- **For #100: acceptance criteria 1 and 2 are met in a nightly artifact** (per-cell TARr/TARa pair
  and Wilson intervals on both denominators, stored in `summary.json` and recomputable from
  `raw.jsonl`), and criterion 4 is met by this comment naming the agreement numbers. Criterion 3
  (one line in `docs/study-design.md` and `docs/analysis-plan.md`) is not this round's change and
  #100 stays open. The measured decomposition: decoding noise 0.18 tokens per fact and a maximum
  relative length deviation of 1.0 percent over 25 serialized minutes at fixed mode; the mode change
  adds up to 18.2 percent length on one prompt and nothing on the answer; the firing adds the
  delivery flip.
- **For #94: the provenance class of a fallback token is itself mode-sensitive** (D2 arm X reads
  `instruction_echo` serialized and `terminal` batched on identical gold), and the one lost item's
  correct answer survives only as an unscored mid-trace fallback. The scoring rule held: it is
  counted as lost.
- **For the thesis line: correctness saturates and surfacing is the whole measurement.** 33 of 33
  delivered answers correct, TARa 1.00 on every delivered pair in every stratum including
  cross-class (48 pairs), while lengths move 18 percent with a batch and a cell flips from delivered
  to `trace_only` across firings. The quantities this program can quote are delivery and budget, and
  both are now bounded by measurement rather than by assumption.

## Limitations

- 2 items per cell: every per-cell number here is exploratory, and the two Wilson denominators
  disagree by construction. No archived verdict is re-placed.
- One endpoint, one session, one host, and class identity is an inference from the pool slot and the
  served model id, not a fingerprint.
- The three passes share KV and scheduler state with each other; the serialized-versus-batched
  contrast is inside one warm session and is not a cold-start comparison. Throughput tripled across
  the session, so wall-clock is reported as transport only.
- The panel is 12 of round 24's 36 digests; the D2 cell's borderline content-silent digest (the
  third pair) is outside it, so this round cannot re-test that specific item.
- Cross-firing joins inherit whatever the deployment changed between firings (build, host, restart);
  that is exactly what the cross-firing floor carries and why it is never pooled with the within-run
  floors.

State: **Executed** (one endpoint, no independent second implementation, and the pre-registered
decision table does not cover this design; the selftest certifies the instrument's controls, the
digest-true replay of the pinned corpus and the recomputation of the four archived cost slopes).

## Reproducing

Point `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID` and `NIGHTLY_API_KEY` at a flash-next-class local
endpoint and run, in order (the session took about 35 minutes at 5.5 to 67 tokens per second):

    python3 samepanel_replicate_probe.py --selftest
    python3 samepanel_replicate_probe.py --gate --out gate.json
    python3 samepanel_replicate_probe.py --probe --out-dir .
    python3 samepanel_replicate_probe.py --analyze

`--probe` resumes from `raw.jsonl` under a matching gate hash and archives each record as it
finishes; `--analyze` rebuilds `summary.json` from the archived raw records alone, including every
noise floor (fixed bootstrap seed). The panel slope basis (2 items per cell) is deliberately not
comparable to the published full-design slopes (6 per cell), which the script carries as constants
and `--selftest` recomputes from the same archives.
