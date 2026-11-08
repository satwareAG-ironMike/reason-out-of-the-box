# Round 49 (2026-11-05 04:00): the flash-class A/C/D knob battery the #71 discriminator was owed - the round-44 ceiling does not repeat (0/11 truncated against 8/11), 33 of 36 dispatches stop at exactly 1,556 tokens below the 2048 cap, and the one knob readout that transfers across classes is the bounded permission's cost (+11%)

## Question

Is the round-44 flash-class knob readout a property of the class, or a property of the
firing? Round 44 (`research/nightly-2026-11-03-0236/`, a flash-next-class endpoint) read
a class-tied wall: mode A truncated 8/11 at mean 1,636.9 completion tokens, the ban
delivered 7/11 at cost ratio 0.6756 over mode A, and the distractor-ratio drop A minus C
was 0.3467. On the 27B class the bounded single-pass knob flipped tier between its two
firings (`bounded_loss` round 46, `bounded_gain` round 48), so the discriminator that
separates a class effect from a firing-state effect is a flash-class A/C/D firing, which
is the arm issue #71 was still owed and which rounds 41, 45 and 47 could not run. This
slot is a flash-class slot, so the arm ran.

## Instrument

`policy_knob_probe.py` is a byte-identical port of the round-48 instrument (branch
`research/nightly-2026-11-05-0229`, PR #125, not yet on `main`), changed only at: the
gate schema (`round49-gate-v1`), the class rows and their bands, the gate question, and
the identity reference retarget (round 44 as the same-class join target, round 46 kept as
the mode-D cross-class constant source, both pinned fail-closed by blob digest and
record-count plus join-key audit before any prompt is spent). The panel, the prompts, the
rendering, the sanitization and the scoring come in by import from the merged round-23
instrument (`../nightly-2026-10-25-0205/frontier_walk_probe.py`), so this directory must
stay where it is for the imports and the reference paths to resolve.

Dispatch: mode A (the archived prompt, 11 records), mode C (the ban, "Without repeating
any fact, answer with exactly one word: yes or no.", 11), mode D (the bounded permission,
"You may state each fact at most once, then answer with exactly one word: yes or no.",
11 - the first mode-D dispatches ever on this class), 3 duplicate mode-A dispatches as the
self-agreement control (#100), and 1 census health call: 37 of the 40-call cap,
`max_tokens` 2048, `temperature` 0.0, concurrency 2, one attempt per record, zero retries.
Mode B (the 5-cell ordering knob) was dropped to stay inside the cap; in the round-44 gate
the P8 family named mode B, not mode D, so no archived mode D number exists for this
class and F3 was anchored to the ban's archived delivery on this class instead.

Panel (inherited, digest-certified): the 11 round-23 records that hit the 2048 cap with
the answer field silent - 2 at S4 (k = 8), 4 at S5 (k = 12), 5 at S6 (k = 16), all at
E = 192; 4 gold-yes / 7 gold-no. Baselines: constant-"no" 7/11, constant-"yes" 4/11,
archived loose-fallback line 8/11.

## Gate

`gate.json`, blob `9109bf712db53aa4833c812b26f2499ec79be1b8aa9630204f40d0bbdf1fb186`,
frozen before dispatch and pinned in the instrument as `ROUND49_GATE_BLOB_SHA256` so a
drifted re-run reads as a gate change instead of a re-fire. The five re-fire rows were
fixed from the two archived firings only, never from this round's data:

| Row | Registered band | Basis | Result |
|-----|-----------------|-------|--------|
| F1 | mode A truncates >= 7/11 | round 44 read 8/11 on this class | fails at 0/11 |
| F2 | cost ratio C/A inside [0.50, 0.90] | round 44 read 0.6756; disjoint from the 27B band [0.90, 1.25] | fails at 0.9578 |
| F3 | mode D delivers <= 7/11 | the ban delivered exactly 7/11 on this class | fails at 11/11 |
| F4 | cost ratio D/C >= 1.10 (cap-censoring note registered) | 1.3089 round 46, 1.1224 round 48 | holds at 1.1092 |
| F5 | distractor-ratio drop A minus D >= 0.15 behind the P8c text floor | the ban's archived drop on this class is 0.3467 | fails at -0.0808 |
| F6 | byte-identical dispatch records against round 44 over the joinable keys (readout, not a tier row) | 25 keys: 11 A + 11 C + 3 A2, verified against the archive before the gate was frozen | 0/25 byte, 5/25 content |

Repeat tier: `repeated` = every row that ran holds, `partial` = at least 3 of the rows
that ran, `divergent` = fewer than 3. The shared rows P1-P9, N1 and N2 are byte-equal to
the round-46/48 gates, so the firings 42, 44, 46, 48 and 49 score one table; the round-48
27B rows R1-R5 are not part of this gate. F5 is the registered refusal path: it evaluates
to `refused` and leaves the denominator when no trace text is recorded (it ran here).

## How to reproduce

```
python3 research/nightly-2026-11-05-0400/policy_knob_probe.py --selftest
python3 research/nightly-2026-11-05-0400/policy_knob_probe.py --gate --out /tmp/gate.json
NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... \
python3 research/nightly-2026-11-05-0400/policy_knob_probe.py \
  --probe --out-dir research/nightly-2026-11-05-0400
python3 research/nightly-2026-11-05-0400/policy_knob_probe.py --analyze \
  --out-dir research/nightly-2026-11-05-0400
```

`--selftest` is green before dispatch (3,496 checks: the inherited battery plus the F-row
tier controls, the F5 refusal and operand-wiring controls, the F6 identity-join controls,
the vendored round-44 and round-46 reference consistency with planted-slip controls, and a
planted duplicate-record control over both reference archives). `--probe` refuses unless
the panel certifies digest-true (that is the P1 row, enforced pre-dispatch rather than
scored), both archived reference blobs certify their embedded digests with clean
(mode, seed, arm) join keys, and the endpoint passes the census health call. Endpoint
values are read from the `NIGHTLY_*` environment and never written to an artifact; stored
model text passes the inherited sanitizer.

## Results

Evidence label `Executed` (exploratory, n = 11 panel items, one endpoint, one firing, 36
dispatched records, zero retries, zero transport errors). Tier `surfacing_only`, mode-D
tier `bounded_loss`, repeat tier `divergent` (1 of 5 rows met).

Modes (all `max_tokens` 2048, `temperature` 0.0):

| Mode | Delivered | Truncated | Wrong deliveries | Correct | Mean completion tokens | Distractor ratio | Trace chars nonzero |
|------|-----------|-----------|------------------|---------|------------------------|------------------|---------------------|
| A (archived) | 11/11 | 0/11 | 8 | 3/11 | 1,464.6 | 0.8585 | 11/11 |
| C (the ban) | 11/11 | 0/11 | 7 | 4/11 | 1,402.8 | 0.7674 | 11/11 |
| D (the permission) | 11/11 | 0/11 | 5 | 6/11 | 1,556.0 | 0.9393 | 11/11 |

- The wall is gone. Mode A truncated nothing on the class where it truncated 8/11 in
  round 44. The truncation ledger on the same 11 items under the same cap is 8/11
  (round 44, flash-class), 2/11 (round 46, 27B-class), 1/11 (round 48, 27B-class), 0/11
  (this firing, flash-class): a monotone collapse on both classes, so the ceiling this
  family has been measuring is a property of the serving build.
- The output is length-degenerate. 33 of 36 dispatch records finished `stop` at exactly
  1,556 completion tokens (trace text 1,363 to 3,455 chars), 492 tokens below the cap;
  the only exceptions are mode A 551, mode C 495 and mode C 932. No record anywhere
  finished `length`. The instruction knobs now move output length only through those
  three records: C/A 0.9578 (round 44: 0.6756), D/C 1.1092, D/A 1.0624.
- F4 is the transferable readout: the bounded permission costs about 11% more than the
  ban on both classes (1.1224 on the 27B class in round 48, 1.1092 here).
- Mode D is not a delivery loser on this class: it delivered the most (11/11) and scored
  the best (6/11). `bounded_loss` came from the tier rule's own condition (any wrong
  delivery in mode D), while the ban delivered 7 wrong answers in the same firing.
- No mode beat a baseline: 3/11, 4/11 and 6/11 against constant-"no" 7/11 and the
  archived loose line 8/11. `beats_archived_loose_line` false, mode D false. Paired
  accuracy A vs C: 0 / 1, exact McNemar p = 1.0; C vs D: 1 / 3, p = 0.625 at n = 11.
  Delivery pairs are 0 / 0 in both comparisons (nothing to pair: everything delivered).
- The anti-repetition instruction has lost most of its effect on this class: A minus C
  0.0911 against the 0.15 floor (P6 fails on a flash-class firing for the first time;
  round 44 read 0.3467, the archived panel mean is 0.8678), and the permission moved
  repetition the wrong way (A minus D -0.0808, C minus D -0.1719).
- Census: N1 holds, the channel is open through `reasoning_content` on the health call
  and on 36/36 records (the round-44 state; round 48's 27B firing read the flipped
  `reasoning` state), so the text-derived claims were accepted rather than refused. Mode
  C trace chars 1,363 / 3,378 / 3,434 (min / median / max), mode D 3,375 / 3,394 / 3,455;
  mode C one-word answer rate 1.0, mean visible content 3.0 chars, mode D 2.6.
- Identity (F6): 25 joinable (mode, seed) keys against the archived round-44 firing,
  0/25 byte-identical, 5/25 content-identical. Same exposure state, different serving
  build: this is a new firing, not a restatement.
- Self-agreement (#100): 2/3 duplicate pairs byte-identical (TARr 0.6667, the >= 2 floor
  holds), 3/3 token-identical. All three pairs sit at exactly 1,556 tokens; the S6 pair
  diverges in trace text at identical length and identical token count.
- Transport: 104,689 prompt / 53,326 completion tokens, 36 dispatches in 1,095 s wall
  across 2 streams (48.7 completion tokens/s aggregate; per-dispatch wall 13.5 to 99.2 s).

## What it changes

- Issue #126 opened from this round: the cap-bound selection premise is stale. The panel
  is selected because those items truncated at 2048 on the round-23 build; on the current
  builds they do not truncate at all, so F1-F3 are untestable as registered and the
  battery needs either a re-registered lower cap or a panel re-derived from a fresh
  frontier walk on the build that is actually serving.
- The #71 arm ran and is reported there: the ceiling-conditioned form of the bounded-knob
  discriminator cannot be decided on a build where the ceiling is absent, and the mode-D
  tier rule needs to compare D against the C of the same firing before the next knob round
  (here the label read `bounded_loss` while mode D was the best mode on the board).
- The #100 ledger gained a fourth row and a new shape (token-identical but byte-different),
  the mirror of round 48's byte- and token-different case; a token-count control alone
  would have read this firing as fully self-agreeing.
- The #94 baseline-equal-accuracy pattern now holds at k = 8, 12 and 16 on E = 192, not
  only at k = 24.

## Disclosure

- `Executed` label: exploratory, n = 11 panel items, one endpoint, one firing. The verdict
  is a surface readout for this firing. The collapse statement is the four-firing ledger
  of archived public records in this repository; the fixed-length signature (33/36 at
  exactly 1,556 tokens) is a single-firing observation and is not treated as a build
  property until one more flash-class firing reproduces it.
- Cross-firing comparisons are band statements at n = 2 or 3 firings per class, never
  class laws. Per-item joins are within-firing only (mode A vs C vs D on the same items).
- F3 had no archived flash-class mode-D number to be anchored to, because mode D was never
  dispatched on this class before this round; it was anchored to the ban's 7/11 delivery
  on this class, and that anchor is now known to be invalid on the current build (see
  #126) rather than hidden.
- F4 was registered with the cap-censoring note (a cap-saturated class compresses both
  means toward 2048); with no cap saturation in this firing the note no longer applies,
  which strengthens the F4 reading rather than weakening it.
- Mode B's 5 cells were dropped to keep the round inside the 40-call cap, so this firing
  does not test the ordering knob.
- Literature located through free scholarly metadata APIs only (9 calls; OpenAlex
  anonymous search returned a transient rate limit on 4 attempts, and 2 arXiv attempts sent
  over plain http against export.arxiv.org returned empty bodies): arXiv:2511.04108
  (Srivastava, Bidhan, Yan, Dey, 2025-11-06, preprint), arXiv:2512.19585 (Iacobacci,
  Qian, AL-Tam, AL-Qurishi, 2025-12-22, 4 pages, preprint), arXiv:2508.19277 (Li, Huang,
  Mu, Huang, 2025-08-23, preprint). They are cited here as context for the reading, not
  as archive entries: `archive/INDEX.md` was not touched, so no provenance record is
  implied for them by this directory.
- Endpoint values are read from the environment and are not written to any artifact; the
  serving build is identified only in the commit trailer, per the public-only rule. The
  runner dispatch log stays outside the repository.
