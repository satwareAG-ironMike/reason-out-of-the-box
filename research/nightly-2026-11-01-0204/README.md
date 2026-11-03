# Round 40 (2026-11-01 02:04): the 27B class's zero-trace status is a deployment property, not a
class property - this firing exposes the full reasoning channel, so the cross-class byte comparison
the round-38 addendum declared unmeasurable is now measurable (and reads zero), while the panel's
(8, 128) arm X now truncates at 2048 where the two same-class firings and the flash class completed

Question, method and results summary posted on tracker issue #65
(`https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65`); this directory is
the reproducible record: script, gate, prompts, raw responses, scores.

## Question

The round-38 addendum (2026-10-31) closed the cross-class trace comparison with an
unmeasurability declaration: the other class's transcribed transcripts collapse to two hashes,
because that deployment answers with a bare "yes" or "no" and exposes no reasoning text at all,
so the round-38 cross-class TARr of 0.0 "says only that a several-hundred-token answer string is
not byte-identical to a five-character one", and "any cross-class trace claim needs the
reasoning text to be surfaced and archived on both sides, or it has to be stated as an
answer-level claim only".

This round's endpoint - a 27B-class local endpoint at pool slot 4/6, probed with the identical
inherited stack that already reads the reasoning field - returned a non-empty
`reasoning_content` of 151 characters on the 256-token health prompt, while the two archived
firings of the same class (rounds 31 and 37), probed with the same inherited stack, exposed zero
reasoning text. The question the pool rotation therefore posed for free:

> Is the 27B class's "zero-trace" status a class property (the class does not expose its
> reasoning channel) or a deployment property (that serving build did not expose it)? And if
> it is a deployment property, what does the cross-class byte comparison say now that the
> channel is exposed on both sides?

Chosen because it answers the follow-up the round-38 addendum left on the table at zero
additional panel cost (the same 12 digest-pinned prompts as round 38), because it decides
whether any trace-level quantity in this program can be attributed to the 27B class at all,
and because the addendum's unmeasurability condition can be met or not met on exactly this
panel.

## Instrument

`panel_trace_channel_probe.py` (stdlib only, `--selftest` with 98 checks: arithmetic, planted
negative controls, the round-24 structural pin, the leak audit on all six cells, the
deterministic verification of round 37's collapsed hashes, the hash-pinned transcription of
round 38 P1 with its out_sha recomputation, readout controls, billing flags, floors and bands)
inherits its construction, audit and readout stack verbatim from round 38's
`samepanel_replicate_probe.py` (branch `research/nightly-2026-10-31-0228`, PR #103), which
inherits them from rounds 19 to 24: C disjoint directed paths of exactly k edges over fresh
entity names, one rule sentence (transitivity of `precedes`), E = k x C facts in shuffled
order, one query per prompt, answer required as exactly one word; gold from an unbounded BFS
independent of the generator plus a structural audit of every item; each graph asked twice
over identical content (arm F forward, gold yes; arm X cross-component, gold no) with the
shared-content invariant asserted per pair (#78).

One declared extension of the inherited readout stack: the field census. Each archived record
carries the message field names of the response and which field supplied the reasoning text
(merge rule: `reasoning_content` if non-empty, else `reasoning`, else empty). It is declared
because this endpoint's health probe exposed a field name none of the archived firings of this
class did, so the census is the only difference between this round's instrument and the
inherited stack, and the selftest's readout controls cover every merge rule it exercises.

The panel is the same 12 digest-pinned prompts as round 38: the first matched pair (arm F and
arm X) of each of round 24's six digest-pinned cells, chosen by the archived selection order
(pair index 0) before any outcome was known:

| Cell | k  | C (paths) | E (facts) |
|------|----|-----------|-----------|
| L0   | 8  | 12        | 96        |
| L1   | 8  | 14        | 112       |
| L2   | 8  | 16        | 128       |
| L3   | 8  | 20        | 160       |
| D1   | 12 | 8         | 96        |
| D2   | 16 | 6         | 96        |

12 prompts, dispatched three times in one session in an ABABA order:

- **P1** serialized, one request in flight (12 dispatches, wall 216 s, 9,926 completion
  tokens);
- **P2** two in flight, the concurrency this class's archived rounds used (wall 180 s, 9,926
  tokens);
- **P3** serialized again (wall 179 s, 9,926 tokens).

The two serialized passes bracket the batched pass, as in round 38, so agreement between them
is the endpoint's own determinism over an interval that contains the mode change.

Gate `b8fb56ee` (schema `round40-gate-v1`) written before any prompt was spent: `anchor_ok`
true, all six cells pass the leak audit, corpus blob `88a8633a` (identical to round 38),
structural pin fail-closed (all 36 prompt digests and all 6 pool blobs must equal round 24's
gate, and the panel digests are pinned individually), `--selftest` green. The archived firings
this round joins against are carried as transcribed per-prompt constants restricted to the 12
panel digests, because none of the ancestor branches is on `main` at authoring time: round 38
P1 (flash class) with full content and reasoning text, its out_sha recomputed in the selftest;
round 37 (this class) content-only with the two collapsed hashes, whose determinism the
selftest verifies by recomputation (the two hashes are exactly the content-only digests of
"\n\nyes" and "\n\nno" with empty reasoning); round 31 (this class) billed tokens and parsed
answers; round 33 (flash class, second firing) as a billed-tokens table for the flash-class
noise floor. Round 31's transcription carries no raw-text hash, so every raw pair involving it
is counted as non-joinable rather than as disagreement. Per-prompt joins are on the prompt
digest.

## Declared predictions (fixed in `gate.json` before any prompt was spent)

- **T1 channel**: at least 11 of the 12 P1 dispatches expose non-empty reasoning text;
- **T2 enumeration**: at least 8 of the 12 P1 dispatches with a positive distractor-mention
  ratio and a mean ratio of at least 0.25, between this class's structural 0.0 on round 37
  and the flash class's near 1.0;
- **T3 billing**: zero billing anomalies (no dispatch billed below 1 token per 6 exposed
  characters, i.e. exposed text the billed length cannot account for even at an optimistic
  6-chars-per-token rate);
- **T4 cross-class**: full-text byte identity (TARr) against round 38 P1 of at most 3 of 12
  (no class-level byte identity), and parsed-answer agreement (TARa) of at least 1.0 over the
  pairs where both sides delivered an answer (the answers carry across classes, the bytes do
  not);
- **T5 same-class proximity**: at least 8 of the 12 prompts with billed tokens within a factor
  of 2 of round 37 (the billed-length class identity survives the exposure change);
- **N1 determinism**: within-run same-mode raw output agreement (P1 versus P3, TARr) of at
  least 0.90 overall and at least 0.50 in every cell;
- **N2 dispatch mode**: the serialized-to-paired-2 change moves nothing: P1 versus P2 TARr
  1.00 and zero token change on any prompt;
- **N3 parsed answer**: TARa 1.00 in every within-run stratum;
- **N4 delivery**: all 36 dispatches deliver their answer in the answer field and all 36 are
  correct;
- **N5 cost law**: the per-pass panel load slope (k = 8) and panel depth slope (E = 96) inside
  the 0.5x to 2.0x house band around the round-38 P1 panel reference (load 10.8946, depth
  24.875);
- **N6 noise guard, the measurement rule**: a slope difference counts as a change only beyond
  the 0.99 quantile of the same-class noise floor of its own stratum, the floor built by
  propagating that stratum's observed per-prompt length differences through the same slope
  estimator (4000 draws, seed 20261101); a stratum whose floor rests on a single observed pair
  is reported as not separable, never as a change.

## Results

Transport clean: endpoint healthy at session start (1.09 s at the 256-token budget, and the
health response already exposed the reasoning channel that motivates the round, 151
characters), 37 of the 40-call cap (1 health + 36 panel dispatches), `max_tokens` 2048,
`temperature` 0.0, zero retries, zero transport errors, probe wall 9 min 36 s, 29,778
completion tokens, 62,538 prompt tokens. Predictions: T1, T2, T3, T4, N1, N2, N3 pass; T5,
N4, N5 fail; under the N6 guard all four slope statements come out "not resolvable".

1. **T1 passes: the zero-trace status is a deployment property, not a class property.**
   All 36 dispatches (12 of 12 in every pass) expose non-empty reasoning text, exclusively via
   the `reasoning_content` field, on messages whose field names are exactly
   {`content`, `reasoning_content`, `role`}: 631 to 4,233 reasoning characters (median 1,848)
   against a content field of 0 to 3 characters (the bare "yes"/"no", or empty on the one
   truncated prompt). The two archived firings of the same class, probed with the identical
   inherited stack, exposed zero reasoning characters. Same class, opposite channel state:
   the channel is served by the deployment, not by the class.

2. **T4 passes: the cross-class byte comparison is now measurable, and it reads zero.**
   The round-38 addendum's unmeasurability condition (reasoning text surfaced and archived on
   both sides) is met on this panel: 12 of 12 joinable pairs carry reasoning text on both
   sides. Full-text byte identity against round 38 P1 is 0 of 12 (Wilson upper bound 0.242);
   8 of 12 prompts move by more than 10 percent in billed length (median relative deviation
   1.618, max 6.441), and this firing bills 622.75 tokens less on average than the flash-class
   firing. Over the 10 pairs where both sides delivered an answer (L2 arm X truncates on this
   side, L3 arm X on the flash side), parsed-answer agreement is 10 of 10. Trace-level class
   divergence is now a measured byte quantity, not a structural zero.

3. **Even the visible surface differs between same-class deployments.** The round-37
   deployment answered "\n\nyes" and "\n\nno"; this deployment answers bare "yes" and "no".
   The content-only hash of this firing's answer field takes three distinct values across the
   panel (yes, no, and the empty string of the truncated prompt) and matches 0 of 12 against
   round 37's two collapsed hashes, so even the visible answer string is deployment-specific,
   and the collapse to two hashes is a property of that deployment's output format, not of the
   class.

4. **N4 fails on a new budget boundary: the panel's (8, 128) arm X now truncates.** L2 arm X
   (digest `54d8b96f74e7`, k = 8, E = 128, 1,925 prompt tokens) truncated at 2048 in all
   three passes, byte-identical output in each (outcome `trace_only`, answer field empty,
   4,233 reasoning characters exposed, distractor-mention ratio 1.0 on the exposed trace).
   The same prompt completed on every archived firing of it: round 31 at 383 tokens, round 37
   at 746, round 38 P1 (flash class) at 1,700. Delivery 33 of 36, and all 33 delivered answers
   are correct. The budget-control framing of #71 extends to this class on a cell every
   archived firing of it delivered.

5. **T5 fails and the class-identity diagnostic sharpens: billed-length variation within the
   27B class is as large as the class difference.** Median relative deviation of billed
   tokens against the two same-class firings is 0.2696 against round 31 (max 4.347, 7 of 12
   within a factor of 2) and 0.8593 against round 37 (max 5.187, 6 of 12 within a factor of
   2); the two same-class firings differ from each other at a median 0.7118 (max 6.132).
   Against the flash class the medians are 1.618 (this firing against round 38 P1, max 6.441),
   1.483 (round 37 against round 38 P1) and 3.316 (round 31 against round 38 P1). The
   within-class and cross-class billed-length spread is the same order, so billed-length
   class identity in this program is deployment-scale at best, and the per-deployment floor
   (N6) is the only honest uncertainty for billed-length claims.

6. **N6: the round-38 load-axis class gap does not reproduce with a trace-exposing 27B
   firing.** The panel slopes of this firing are load -7.6545 tokens per fact and depth 15.625
   tokens per hop (2-items-per-cell basis). Against the flash-class reference (load 10.8946,
   depth 24.875) the deltas are -18.549 and -9.25, both inside the union floor q99 (load
   26.742, depth 232.504, the largest floor either class demonstrated on this panel): not
   resolvable on either axis. Round 38 had judged the load-axis gap resolvable (deltas -13.6
   and -16.6 tokens per fact against a union floor of 12.41), but that contrast was the
   trace-exposing flash class against the zero-trace 27B deployment. With the channel exposed
   on the 27B side, the billed-length class gap shrinks below the noise floor the program
   itself measured: the round-38 "class difference" on the load axis was dominated by the
   deployment's exposure setting, not by the model class.

7. **T2 passes: enumeration with the channel exposed is intermediate, and it is monotone in
   trace length.** The distractor-mention ratio is positive on 8 of 12 P1 dispatches (mean
   0.5039, median 0.5146), between this class's structural 0.0 on round 37 (no trace to
   mention in) and the flash class's mean 0.999 (11 of 12 at 1.0). The pattern is strictly
   ordered by trace length: the four shortest traces (631 to 745 characters) enumerate
   nothing, the next two (1,044 and 1,408 characters) mention the distractor once against
   dozens of tokens (0.0171 and 0.0292), and all six longest traces (2,288 to 4,233
   characters) enumerate fully (1.0).

8. **N1, N2, N3 pass: this deployment is byte-deterministic and mode-insensitive in a way the
   flash class was not.** Every prompt's completion is byte-identical across all three passes
   (pooled TARr 1.0 over 24 pairs, zero token change anywhere), including the truncation,
   which truncates identically each time. The serialized-to-paired-2 change moves nothing:
   TARr 1.00, zero token change on any prompt, in contrast to round 38, where batching grew
   one prompt by 18.2 percent. Parsed-answer agreement is 1.00 in every within-run stratum
   (11 of 11 both-delivered pairs per stratum) and in every comparison this round makes: of
   every pair that carries two answers, all agree.

9. **The cell table (#100's denominators), 2 items per cell, with the same-mode (P1 versus
   P3) byte agreement:**

   | Cell | accuracy per item | Wilson per item (n = 2) | Wilson per dispatch (n = 6) | TARr same-mode | delivered |
   |------|-------------------|-------------------------|-----------------------------|----------------|-----------|
   | L0   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 6/6       |
   | L1   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 6/6       |
   | L2   | 0.5 (1/2)         | [0.095, 0.905]          | [0.188, 0.812]              | 1.00           | 3/6       |
   | L3   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 6/6       |
   | D1   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 6/6       |
   | D2   | 1.0 (2/2)         | [0.342, 1.0]            | [0.610, 1.0]                | 1.00           | 6/6       |

   L2's 3 of 6 delivery is the truncation in finding 4; every cell's same-mode byte
   agreement is 1.00, including the truncated item, which is byte-identical across passes.

## What this means for the program

- **For #100 and the thesis line: the trace channel is a deployment variable, and the
  program's 27B-class trace claims need re-attribution.** Every trace-level quantity
  archived against the 27B class from rounds 31 and 37 (zero trace, structural 0.0
  enumeration, the two-hash transcript collapse) is now known to be a property of those
  deployments' serving, not of the class. The load-axis class gap measured in round 38 does
  not reproduce under the N6 guard once the 27B side exposes its channel (finding 6), so
  billed length, trace length and enumeration are deployment-scale quantities until the
  exposure setting is controlled across firings.
- **For #71 and the frontier: the budget-control framing extends to this class on a cell
  every archived firing of it delivered.** (8, 128) arm X truncates at 2048 in all three
  passes on this deployment (finding 4), so the load ceiling of this class cannot be quoted
  from any 2048-budget firing while this serving build is in the pool, and the
  pre-registered 4096-token budget (#12) is now the only place both the (8, 128) and the
  (8, 160) statements can be re-anchored.
- **For #94: the field census is the readout stack's first exposure-aware extension, and it
  decided the round.** The merge rule (`reasoning_content` if non-empty, else `reasoning`,
  else empty) and the per-record field names are archived on every dispatch, and the
  enumeration gradient (finding 7) is measurable only because the census names the field that
  carries the trace. The fallback-token provenance question is unchanged; the scoring rule
  held (the truncated item scores `trace_only` and counts as lost).
- **For #73: transport stayed clean under the contractual caps**, 37 of 40 calls, zero
  retries, zero transport errors, and the pre-grid health check doubled as the channel probe
  that motivates the round: the decision to run this question was made on the health
  response, before the panel was spent.
- **For #85: the producer chain held.** No endpoint value, hostname, IP, device name or
  model file path appears in any artifact of this round; the script reads
  `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID` and `NIGHTLY_API_KEY` from the environment and
  never writes them, and every file refers to the serving model by its public class name
  only.

## Limitations

- 2 items per cell: every per-cell number here is exploratory, and the two Wilson
  denominators disagree by construction. No archived verdict is re-placed. The panel load
  slope is additionally distorted by the one truncated item: the L2 cell mean (1,133.5)
  carries the 2048-truncated arm X, and the N5 load-axis failure (slope -7.6545 outside the
  band 5.4473 to 21.7892, while the depth slope 15.625 is inside its band 12.4375 to 49.75)
  is at least partly a truncation artifact on a 2-item basis.
- One endpoint, one session, and class identity is an inference from the pool slot and the
  served model id, not a fingerprint.
- The three passes share KV and scheduler state within one warm session; the
  serialized-versus-batched contrast is inside one session, not a cold-start comparison.
- Round 31's transcription carries no raw-text hash, so every raw pair involving it is
  non-joinable by construction, and round 31 enters the joins through billed tokens and
  parsed answers only.
- Cross-firing joins inherit whatever the deployment changed between firings (build, host,
  restart, exposure setting); that is exactly what the cross-firing floor carries and why it
  is never pooled with the within-run floor.
- The billing margin (billed tokens minus exposed characters at a 4-chars-per-token rate) is
  a heuristic context number, not a tokenization.

State: **Executed** (one endpoint, no independent second implementation, and the pre-registered
decision table does not cover this design; the selftest certifies the instrument's controls,
the digest-true replay of the pinned panel, the hash-pinned transcriptions and the
deterministic verification of round 37's collapsed hashes).

## Reproducing

Point `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID` and `NIGHTLY_API_KEY` at a 27B-class local
endpoint and run, in order (the session took about 10 minutes at roughly 50 tokens per
second):

    python3 panel_trace_channel_probe.py --selftest
    python3 panel_trace_channel_probe.py --gate --out gate.json
    python3 panel_trace_channel_probe.py --probe --out-dir .
    python3 panel_trace_channel_probe.py --analyze

`--probe` resumes from `raw.jsonl` under a matching gate hash and archives each record as it
finishes; `--analyze` rebuilds `summary.json` from the archived raw records alone, including
every noise floor (fixed bootstrap seed 20261101, 4000 draws). The panel slope basis (2 items
per cell) is deliberately not comparable to the published full-design slopes (6 per cell),
which the script carries as constants and `--selftest` recomputes from the same archives.
