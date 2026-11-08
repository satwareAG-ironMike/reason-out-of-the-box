# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### 2026-11-06

#### Added

- Nightly research round 51 (issue #65; serves #71, #126, #94, #100, #105; refs #73, #65):
  `research/nightly-2026-11-06-0433/` is the per-item output-budget ladder at the generator's load
  floor, the route round 50 named as the only way to `d*`. Selection rule: facts = 2k exactly (two
  disjoint k-edge paths, the smallest item the shipped generator can build at that depth), first two
  gold-yes and two gold-no in generation order, cells k = 8, 16, 24, 32, 40, 48 at `max_tokens`
  2048, temperature 0; stage 2 re-dispatches the identical prompt of the smallest-seed gold-yes item
  of each cell at 24, 32, 40, 48 at rungs floor(0.8L/64)*64 and floor(0.5L/64)*64 of that item's own
  measured natural stop, plus two identical re-dispatches as the issue #100 control. Gate
  `60b0d62c` (schema `round51-gate-v1`) frozen before dispatch; 109 `--selftest` checks; 20 of the
  40-call cap dispatched (1 health, 16 stage 1, 4 stage 2), 14,846 prompt / 23,370 completion tokens.
  Result (tier `capability_bound_floor_depth`, flag `early_commitment_observed`): 16 of 16 stage-1
  records delivered with `finish_reason` stop - the 2048 cap binds nowhere on this family out to
  k = 48, confirming issue #126 - and 13 of 16 are correct (0.8125, CI 0.5699..0.9341); the three
  failures are all cross-path (gold-no) items that answered "yes": both at k = 48 and one at k = 32,
  so the wall at the load floor is a wrong answer rather than a running-out and `d*` sits as an
  accuracy interval 40 < d* <= 48 (F1 pass 4/4, F2 fail at 3 wrong, F3 fail at 6/6 delivered).
  Every one of the eight gold-no records stopped at exactly 1556 completion tokens at every depth
  while the gold-yes arm climbs 718.5, 915.0, 1106.0, 1409.5 (F4 slope 28.3 tokens/hop, inside the
  registered band, between round 50's 31.3 and round 6's 80), so the label-split cost ratio F5
  collapses 2.1656 -> 1.7005 -> 1.4069 -> 1.1039 with depth: the negative arm is length-pinned and
  the budget belongs to the label, not to k. Stage 2: both 0.8-rungs delivered and were correct at
  78% of their own natural stop (532 tokens at rung 1024 against L = 1310; 876 at rung 896 against
  L = 1153), both 0.5-rungs hit the rung with no answer token (I1 fail 2 of 4, so the wall is not a
  completeness wall), and prefix identity fails (I2, 0 of 2 candidates): the same prompt at
  temperature 0 on the same endpoint shares 0.9509, 0.0667, 0.6243 and 0.9911 of its undisturbed
  output at the four rungs, un-ordered by rung, so `one_dispatch_predicts_rungs` is refused and a
  budget ladder must spend a dispatch per rung. Free cross-firing control: the k = 32 floor cell is
  byte-for-byte round 50's M32 item set (digest-pinned) and reproduces 3 of 4 finish states, with
  the item round 50 truncated at the cap (84261050, length at 2048) delivering here at 1556 with
  stop and being one of the three wrong answers; round 50's 12-hex model digest and this round's
  16-hex digest (c62b81e96826354e) do not match on their shared prefix, so the two firings are
  different deployments of one class and the digest width is now fixed at 16 for issue #100.
  Zero-prompt finding 1: the level-49 `entity pool exhausted` raise is a collision ceiling on item
  size and not on depth (pool 2700 names, `ladders._entity` at 100 rejection tries, an item at
  level 49 with C = 50 needs 2550 names); item-by-item scans generate 285 of 300 at 49, 284 at 50
  and 178 at 64 and still find load-floor items (5, 6, 1), so `k > 48` is reachable on the floor
  family and the fix is generator-side - filed as a new issue against `generators/`. Cutoff
  disclosed: the firing lost its first hour to a transcription defect (the vendored round-50
  reference digests were 12-hex against the archive's 16-hex field, so `certify_reference` refused
  all 12 rows and would not dispatch; repaired by programmatic re-extraction, nothing dispatched
  against an uncertified reference), and the resumed pass was terminated by its 700 s guard, so the
  k = 8 and k = 16 cells, the k = 24 and k = 32 interrupt candidates and both duplicate controls were
  never dispatched - N2 did not run (an absence, not a disagreement), I1 and I2 rest on 4 dispatches
  and 2 candidates, and the round stays Executed, not Reproduced or Validated.

### 2026-11-05

#### Fixed

- Issue #120 group 1 (forward-only annotations; no scored result, gate digest or archive
  record changes): the retracted statements still live on main are annotated at their sites -
  round 37's headline ("while the answers do"; the style half is answer-level only), its
  "what this means" bullets (R5's 0.0 ratio is structural under the closed trace channel;
  the surfacing-collapse stability is a content-channel statement) and a note that the
  frozen `summary.json` `R5_pass: true` stays as written with the annotation in the README;
  round 31's three re-derived sentences (27B-class-property inference, "4-5x cheaper
  enumeration", budget-replay explanation) are restated at answer level; the frozen
  round-31 script's "GGUF deployment" docstring carries the format-undisclosed description
  from the erratum; the 2026-10-30 and 2026-10-31 CHANGELOG entries are annotated in place
  (non-enumerating-style hold; load-axis resolvable verdict measured against the zero-trace
  27B deployment, not reproduced under the round-40 N6 guard).
- Issue #120 group 3: `research/AGENTS.md` gains the errata carve-out (forward-only errata
  may annotate a merged round's README prose and the matching CHANGELOG entry, and edit
  instrument docstrings comment-only; `raw.jsonl`, `summary.json`, `gate.json` stay
  immutable), resolving the practice-vs-contract disagreement and covering the frozen
  script docstring edit.
- Issue #120 group 2 (comment-only; no behavior change): the drift-control docstrings that
  still promise a certification the instruments do not deliver are restated at all 12 sites
  (the 10 line-referenced by the issue plus the ported `_drift_control` docstrings in rounds
  44 and 46 that carry the same false sentence): the `--selftest` drift control round-trips
  the literal body dict and certifies the literal, not the inherited `B.call_endpoint`
  request-body construction; the inherited function is not inspected, so drift in its body
  keys cannot break the assertion; byte identity against the inherited transport holds per
  recomputation, and the inherited constants are still asserted against their archived
  values. `research/nightly-2026-11-02-0218/policy_knob_probe.py`,
  `research/nightly-2026-11-03-0236/policy_knob_probe.py` and
  `research/nightly-2026-11-04-0250/policy_knob_probe.py`; all three `--selftest` runs stay
  green before and after (verified locally; the round-44/46 vendored ROUND42_REFERENCE is
  JSON constants, not a digest of any script file).
- Issue #120 group 4 (round 21 annotated forward-only; round 38 verified): the ~33
  tokens/hop citation in `research/nightly-2026-10-24-0205/README.md` now attributes the fit
  to the same-class round 17 (-50.8 + 33.1 * k, r = 0.845, at coupled load) instead of
  round 18 (a 27B-class firing whose record carries the same slope), and the declared grid
  cites round 9's arm L as the design source (same constant load, same k set, 36 dispatches;
  different seed_base and prompt instances). Round 38's "--selftest with 266 checks" claim
  at `research/nightly-2026-10-31-0228/README.md` was re-verified by running the archived
  selftest on 2026-11-05: "selftest: 266 checks passed" (rc=0) - the claim is accurate and
  needs no amendment.

### 2026-11-04

#### Added

- Nightly research round 46 (issue #65; serves #71, #100, #105; refs #94, #73, #65, #108):
  `research/nightly-2026-11-04-0250/` is the 27B-class re-fire of the output-policy knob plus
  the bounded single-pass knob - the same 11 round-23 cap-truncated items (S4 to S6 at
  E = 192) re-dispatched on a 27B-class endpoint in modes A (archived prompt, 11), C
  (no-repetition one-liner, 11) and D (`You may state each fact at most once, then answer
  with exactly one word: yes or no.`, the bounded single-pass knob filed on #71, 11),
  plus 3 duplicate mode-A self-agreement dispatches and 1 census health call; 37 of the
  40-call cap. Instrument: the round-44 script ported byte-identically except the gate
  schema, the gate question, the mode-D arm and two vendored references
  (`ROUND42_REFERENCE` unchanged, `ROUND44_REFERENCE` added, both with archive blob
  digests and planted-slip selftest controls); prediction rows P1 to P7, P9, N1, N2 stay
  byte-equal to the round-42 / round-44 gate, P8 is re-registered for mode D, P8b / P8c
  are new. Gate `f091f0b1` (schema `round46-gate-v1`) frozen before dispatch. Result
  (tier `surfacing_only`, mode-D tier `bounded_loss`): the ceiling re-confirms class-tied
  - mode A truncates 2/11 (archive 11/11, round 42 1/11, round 44 8/11), P2/P2b fail as
  the shared-table flash-class rows; mode C delivers 8/11 all correct, cost ratio 1.0237
  (P4/P5/P6 fail), losing one net delivery against mode A including a gold-yes forward
  item (paired A-only 2, C-only 1, p = 1.0), with disobedience no longer confined to the
  cross-check arm; mode D delivers 6/11 all correct, truncates 5/11, cost ratio 1.3089
  over the ban (P8 fails), and triggers the enumeration it bounds on an item the ban
  delivered (536 tokens at dr 0.0051 becomes 2048 at dr 0.8923) - the #71 bounded-knob
  discriminator reads negative on the 27B class; one S6 X item truncates under all three
  modes, and under mode D its trace (6210 chars) is the longest of the round with a low
  distractor ratio (cap consumption by non-enumerating work). Census open via
  `reasoning_content` on 36/36 dispatches (P7/P8c 11/11 per mode): first trace-exposed
  27B firing, the class-specific obedience reading is measurable. N2: 3/3 duplicate
  pairs byte- and token-identical (TARr 1.0). Transport: 104,689 prompt / 42,785
  completion tokens, ~18.8 t/s single stream, 2298.2 s wall, zero retries. State:
  **Executed**.
- `docs/next-investigations.md`: late-2026 field scan on out-of-the-box reasoning via
  direct weight editing (owner-directed, 2026-11-04; Perplexity search plus full primary-page
  fetches, all URLs live-checked). Findings: a single originating claim exists
  (Takehi, Teoh, Zhang and Khattab, "Sparks of Weight-Space Programming", MIT CSAIL,
  2026-11-02, web-only source); all other late-2026 projects are replications, tooling,
  benchmarks, or audits of that blog - 11 direct projects plus a curated index, two
  Claude-based prompt-exact replications, one applied preprint (arXiv:2611.05341,
  clinical-network auditing, 2026-11-03) and one from-scratch construction study.
  Classification: the flagship Qwen3.5-0.8B edit (131,072 weights, 0.016%) is
  loop-obstacle removal, not a new general reasoning module - consistent with the
  authors' Gemma 3 270M negative control, the local same-context A/B verification, and the
  thinking-off baseline (46.4% MATH-500 on the unedited model in the `weightspace`
  replication). WSP is therefore not a counterexample to the repo's "from nothing"
  verdict. arXiv:2611.05341 recorded as archive-eligible (preprint status); the Sparks
  blog is a non-archive source under the provenance rule; no study-design change.

- Archive round 19 - Weight-space programming applications (issue #115): one entry,
  `archive/round19-weight-space-audit/2611.05341-nusrat-wsp-clinical-network-audit.md`,
  Nusrat & Nusrat 2026, "Weight-space programming for auditing clinical decision networks"
  (arXiv preprint, physics.med-ph/cs.AI, 2026-11-03). `[FT]` (read-paper full text): named the
  broken rule in 16/18 flawed networks (95% CI 67-97%), median 3 parameters changed; cleared 2/5
  healthy, found 1/3 hidden triggers; black-box testing found the confounds and shift faster; the
  authors bound it at "cannot certify that a network is correct". Verdict context: the only
  peer-reviewable record in the weight-editing wave, reads as obstacle removal, not a new general
  reasoning module; changes no acceptance criterion.
- Archive round 20 - Comparative transitive inference and its controls (issue #74): ten entries in
  `archive/round20-comparative-ti/`, the comparative-TI evidence the central analogy leaned on but
  never carried. Machine rule-reasoning benchmarks (CLUTRR, arXiv:1908.06177, EMNLP 2019;
  RuleTaker/Entailment Bank, arXiv:2002.05867, IJCAI 2020; PrOntoQA, arXiv:2210.01240, ICLR 2023),
  machine TI diagnostics (arXiv:2410.20200 EMNLP 2024; arXiv:2506.04289; arXiv:2611.00387), and
  human/animal TI baselines with the paired-associate critique (Frank 2005 PMID 16248338;
  Vasconcelos 2008 PMID 18423898; Moses 2006 PMID 16503340; Jensen 2017 PMID 28333486). All
  provenance verified against arXiv abstract pages and the PubMed/Crossref records; no `[FT]`
  (abstract-level). Context and control, not machine evidence for the thesis. Reconciles the INDEX
  question-analogy line and the former line-458 animal-cognition exclusion.

#### Changed

- `docs/next-investigations.md`: new finding "the E = 192 ladder ceiling is class-tied and
  firing-state dependent" folding rounds 42, 44 and 46: the round-23 cap-truncation record does not
  transfer across classes (11/11 flash-class archive versus 10/11 and 2/11 delivered on the 27B
  class, same 11 items), delivery under a fixed cap is a function of no-repetition instruction
  obedience not depth, and the output-policy knobs move the delivery surface without reclaiming
  budget (completion ratios 1.1255 / 0.6756 / 1.0237; bounded knob worst at 6/11, 1.3089 over the
  ban). Sharpens the 2026-10-16 budget-limited finding: a truncated verdict is a class-and-firing
  statement, not a depth ceiling, and must not enter `d*`. Closes #108.
- README.md Status and Layout: nightly program restated verifiably as "run to round 46 (30 archived
  round records on main)" (was "nine merged rounds"), with the class-tied E = 192 reclassification;
  archive counts 130/17 to 141/19 (also root AGENTS.md and archive/AGENTS.md); next-investigations
  Layout row updated.

#### Fixed

- Errata per issue #113 (forward-only; no scored result changes, wording and coverage level only):
  round 24's depth arm reproduces round 21's ~29 tok/hop at 4x higher fact load, not "12x lower"
  (E = 96 vs E = 24), in `research/nightly-2026-10-25-0405/README.md` and the 2026-10-25 CHANGELOG
  entry; round 31's unsupported GGUF format attribution for the flash-next class dropped (its
  round-22 record names no format) and its 0.0 distractor-mention signature re-attributed to the
  closed trace channel (structural, answer-level only); round 33's transport accounting corrected
  to 38 of 40 calls (1 health + 36 prompt dispatches + 1 disclosed retry, one TimeoutError) with
  the rate on one declared basis (13.9 tok/s aggregate over 57.2 min, ~6.9 per stream at
  concurrency 2); round 37's R5 re-stated - with the trace channel closed the 0.0 ratio is
  structural, not a measurement of the non-enumerating signature; round 42's drift-control claim
  re-stated to what the selftest executes (round-trips the literal body dict; does not inspect the
  inherited request-body construction; byte identity against the inherited transport holds per
  recomputation).
- Issue #105 in-repo re-attribution: round 38's load-axis resolvable verdict annotated as measured
  against the zero-trace 27B deployment (round 40's trace-exposing firing does not reproduce it
  under the N6 guard: delta -18.549 against the union floor q99 of 26.742, not resolvable), and
  the trace-exposure census added to the `research/AGENTS.md` local contracts (field census in
  every round's `raw.jsonl` from round 40 onward; trace claims must state the exposure setting of
  each side; a zero-trace claim is an answer-level claim only; class-level trace statements need a
  same-class pair with the channel exposed on both sides).
- Fourth CI check, the serving-id guard (issue #85, owner go 2026-11-04): `scripts/check_serving_ids.py`
  (stdlib, `--selftest` negative control) scans every tracked file for endpoint serving ids - host:port
  literals (RFC 5737 documentation ranges exempt for the sanitizer fixtures), lowercase GGUF model file
  names, and quantization-tagged deployment labels - wired into `.github/workflows/ci.yml` as the
  `serving-id guard (endpoint leak)` job so a leaked serving id fails at PR time instead of at weekly
  review. Root AGENTS.md CI and local-parity lists updated to four checks.

### 2026-11-03

#### Added

- Nightly research round 44 (issue #65; serves #71, #100, #105; refs #94, #73, #65, #108):
  `research/nightly-2026-11-03-0236/` is the flash-class firing of the output-policy knob that
  round 42 deferred and round 41 lost - the same 11 round-23 cap-truncated items (S4 to S6 at
  E = 192) re-dispatched on a flash-next-class endpoint in modes A (archived prompt, 11), C
  (no-repetition one-liner, 11), B (ordering one-liner, S6 only, 5), plus 3 duplicate mode-A
  self-agreement dispatches and 1 census health call; 31 of the 40-call cap. Instrument: the
  round-42 script ported byte-identically except the gate schema, the gate question and a
  vendored `ROUND42_REFERENCE` (comparison constants transcribed programmatically from the
  round-42 archive with planted-slip selftest controls), so prediction values stay byte-equal
  across the two firings. Gate `8bbbb25c` (schema `round44-gate-v1`) frozen before dispatch.
  Result (tier `surfacing_only`): the ceiling is class-tied - mode A truncates 8/11 (archived
  11/11; round 42 on the 27B class: 1/11), the three escapes being the shortest traversals
  (P2/P2b miss by one item); mode C delivers 7/11, a strict superset of mode A's three, all
  correct, zero wrong, but the strict line 7/11 does not exceed the archived 8/11 loose line
  (P4 fails; paired McNemar b = 0, c = 4, p = 0.125); cost ratio C over A 0.6756 (P5 fails at
  the 0.50 ceiling, a partial re-claim, the opposite direction from round 42's 1.1255 measured
  on a ceiling-free firing); mode B 2/5 (P8 fails, the pre-reasoning ordering is not followed
  on this deployment). The mechanism is measurable for the first time (census open via
  `reasoning_content` on 30/30 dispatches, P7 floor 11/11, P6 drop 0.3467): delivery is an
  exact function of instruction obedience - all 7 obeying items suppress trace enumeration
  (distractor ratio 0.000 to 0.048) and deliver in 262 to 931 tokens, all 4 disobedient items
  keep enumerating (0.936 to 1.000) and truncate; disobedience is polarity-and-depth bound
  (arm F 4/4 obey; arm X 2/2 at k = 8, 1/2 at k = 12, 0/3 at k = 16). N2: 3/3 duplicate pairs
  byte-identical and token-identical (TARr 1.0; round 42's counter quirk re-attributed to its
  deployment). Transport: 87,190 prompt / 43,604 completion tokens, ~43.5 t/s single stream,
  1015.8 s wall, zero retries. State: **Executed**.

- Archive round 18, AI consciousness scepticism: anchor Seth/Block/Tononi *Nature* comment
  plus seven notes from the anchor's own reference list (Nagel 1974, Yu et al. 2015,
  Vallor 2024, Suleyman 2026, Turing 1936/37, McCulloch & Pitts 1943, Searle 2017), landed
  from the long-open round-18 branch. The entries were brought to the current entry format
  (Archived dates, Citation sections, filename id alignment); three further anchor targets
  (Seth's 2025 target article, Block's reply, the Ben-Zion safeguards comment) are recorded
  as planned entries, not yet archived. Archive now 130 entries in 17 rounds; count
  statements updated in the same commit.

#### Fixed

- Branch-cleanup merge debris in this file (from the PR #76/#72 squash batch): removed two stray
  diff3 base-marker lines left by conflict resolution, moved the round-8 section dated 2026-10-17
  back to its descending-date position after 2026-10-18, and renamed the same-day round-7 section
  to `### 2026-10-17 (second entry)` following the existing precedent. No entry content was added,
  removed, or reworded.

### 2026-11-02

#### Added

- Nightly research round 42 (issue #65; serves #71, #100, #105; refs #94, #73, #65):
  `research/nightly-2026-11-02-0218/` re-dispatches the 11 round-23 cap-truncated items (S4 to
  S6 at E = 192) on a 27B-class pool slot in three output-surface modes: A the byte-identical
  archived prompt as replication control (11), C a one-line no-repetition knob
  `Without repeating any fact, answer with exactly one word: yes or no.` (11), B the ordering
  knob on cell S6 only (5), plus three duplicate mode-A dispatches (the #100 self-agreement
  control) and one census health call - 31 of the 40-call cap, `max_tokens` 2048. The round-23
  instrument is imported, not re-implemented; the panel certifies digest-true against the
  archived `raw.jsonl` fail-closed; the declared record-only extension is the per-message field
  census (merge rule: `reasoning_content` if non-empty, else `reasoning`, else none) with a
  drift control; the control round-trips the literal body dict, so it certifies the literal
  rather than the inherited request-body construction (byte identity against the inherited
  transport holds per recomputation, issue #113). Gate `f67c0535` (schema `round42-gate-v1`) frozen before dispatch. Result: the
  replication control fails, and the non-transfer is the round's lead result (verdict tier
  `policy_artifact`): mode A truncates on 1/11 at the 2048 cap and delivers 10/11 (loose 10/11)
  against the archived all-11 cap-truncation record; mode C delivers 9/11 with all nine correct
  (0 wrong, above the archived 8/11 loose line and the 7/11 constant-no baseline, P3/P4/P4b
  hold); mode B delivers 3/5 (P8). The knob is not a budget re-claim: the C over A mean
  completion ratio is 1.1255 against the 0.50 ceiling (P5 fails) and the one-word constraint
  collapses the text floor (mean content 3.6 characters, P6/P7 text-existence fail on the floor
  although the distractor-ratio drop from the archived line is 0.8678). Self-agreement (#100):
  3/3 duplicate pairs byte-identical on content plus reasoning (TARr 1.0, N2) with the
  completion-token counter disagreeing within pairs (record-level counter quirk, reported).
  Census N1 open on the health call: the trace is supplied by the `reasoning` field on all 30
  dispatches (65,678 trace characters total), which the inherited scoring channel does not
  record (record-only divergence; answer-level claims unaffected). Transport: 87,190 prompt /
  26,123 completion tokens, about 50 t/s single stream, 9 min 49 s wall. Round 41 (flash class,
  2026-11-01 04:00) left no outtake; the cross-class knob comparison stays deferred. State:
  **Executed**.

### 2026-11-01

#### Added

- Nightly research round 40 (issue #65; serves #100, #71, #94, #73, #85):
  `research/nightly-2026-11-01-0204/` re-runs round 38's 12 digest-pinned panel (pair 0 of
  each of round 24's six (k, E) cells) on a 27B-class local endpoint whose health prompt
  exposed a non-empty `reasoning_content` field, where the class's two archived firings
  (rounds 31 and 37) probed with the identical inherited stack exposed none. 36 dispatches
  in three ABABA passes (P1 serialized, P2 paired-2, P3 serialized) + 1 health call, 37 of
  the 40-call cap, gate `b8fb56ee` (schema `round40-gate-v1`) written before any prompt,
  98-check selftest, zero retries, zero transport errors. Result: the 27B class's
  "zero-trace" status is a deployment property, not a class property - all 36 dispatches
  expose full reasoning via `reasoning_content` (631 to 4,233 characters, median 1,848)
  against bare 0-to-3-character answers, and even the visible surface differs from round 37
  (bare "yes"/"no" versus "\n\nyes"/"\n\nno", 0 of 12 content-only hash matches). The
  round-38 addendum's cross-class unmeasurability condition is met: full-text byte identity
  against round 38 P1 is a measured 0 of 12 (Wilson upper bound 0.242) with parsed-answer
  agreement 10 of 10 both-delivered. The round-38 load-axis class gap does not reproduce
  under the N6 guard once the 27B side exposes its channel (delta -18.549 tokens per fact
  inside the union floor q99 26.742; round 38's resolvable contrast was trace-exposing
  flash against the zero-trace 27B deployment), and billed-length variation within the 27B
  class is as large as the class difference (median relative deviation 0.2696 against round
  31 and 0.8593 against round 37, cross-class medians 1.48 to 3.32). New budget boundary:
  (8, 128) arm X truncates at 2048 in all three passes where rounds 31 (383), 37 (746) and
  flash (1,700) completed; delivery 33 of 36, all delivered answers correct, within-run
  byte-stable on every prompt (pooled TARr 1.0, zero token change). Predictions T1, T2,
  T3, T4, N1, N2, N3 pass; T5, N4, N5 fail. State: **Executed**.

### 2026-10-31

#### Added

- Nightly research round 38 (issue #65, tracker comment posted; serves #100, #71, #94, #73):
  `research/nightly-2026-10-31-0228/` holds one firing fixed and varies the conditions inside it,
  so the variance in an archived cell verdict is attributed instead of assumed. 12 digest-pinned
  prompts (arm F and arm X of the first matched pair of each of round 24's six (k, E) cells,
  selected by the archived order before any outcome) dispatched three times in one session in an
  ABABA order - serialized, then at the archived concurrency of 2, then serialized - 36 dispatches
  + 1 health call under the 40 cap, gate `eac3acca` (schema `round38-gate-v1`, 266-check selftest
  green, structural pin to round 24's corpus fail-closed) written before any prompt was spent.
  Result: **within the session the answer is byte-stable and the dispatch mode moves the trace but
  never the verdict**. Serialized-versus-serialized TARr 0.9167 (11 of 12 prompts byte-identical
  over 25 minutes); serialized-versus-batched TARr 0.875 with two prompts moving (D2 arm X
  1619 to 1913 tokens, +18.2 percent, returning to 1619 when serialized; L3 arm F +1.0 percent and
  *staying*, which is drift the ABABA bracket separates from the mode effect), TARa 1.00 in both
  within-run strata and 1.00 cross-class over 48 pairs. Noise floors now measured rather than
  assumed (0.99 quantile of each stratum's own propagated slope distribution): determinism 0.18
  tokens/fact and 1.50 tokens/hop, mode change 2.95 and 24.5, cross-firing up to 2.97 and 24.5 - so
  P2's 1.74x depth slope (43.25 against 24.875) is inside its own floor and no slope difference this
  round is certifiable as a change (N6). **What fails is delivery: the deepest load cell no longer
  delivers.** L3 arm X (`d548b1f9681c`, k = 8, E = 160) truncated at 2048 in all three passes with
  byte-identical output where rounds 24 and 33 delivered the same prompt's correct "no" at 2043
  tokens: the archived maintained status of (8, 160) sits on a 5-token margin out of 2048
  (0.24 percent of the budget), so the load ceiling is a statement about `max_tokens` and must be
  re-placed under the pre-registered 4096 before it can be quoted (#71, #12). Delivery 33 of 36,
  content-only accuracy 33 of 33 delivered correct, and the only answer disagreement anywhere is
  that one digest (cross-firing TARa 0.9286; delivered-only TARa 1.00 in all five strata).
  #100's acceptance criteria 1 and 2 land here: per-cell (TARr, TARa) and Wilson intervals on both
  denominators (per item n = 2, e.g. [0.342, 1.0] for a perfect cell, [0.095, 0.906] for L3; per
  dispatch n = 6), plus flip rates propagated to a six-item cell - at least one delivery flip on a
  re-run 0.36 (0.62 at the interval's upper bound), at least one material length move 0.13 (0.40).
  Cross-class: the load-axis gap is resolvable against both classes' floors (-13.6 and -16.6
  tokens/fact against a union floor of 12.41) - measured against the zero-trace 27B
  deployment; round 40's trace-exposing 27B firing does not reproduce it under the N6 guard
  (delta -18.549 against the union floor q99 of 26.742, not resolvable; re-attribution in
  research/nightly-2026-10-31-0228/README.md, issues #105/#120) - while the depth-axis gap
  is not (+43.8 and -51.1
  against 148.07, the other class's single-pair floor exceeding the class difference). P1 reproduces
  round 24 byte-for-byte on 11 of 12 prompts and 30 of the 36 dispatches match it, against 0 of 36
  for the other class. Zero retries, zero transport errors, throughput 5.5 to 67 tok/s within one
  session (wall clock is transport, reported as such). State: **Executed**.

### 2026-10-30

#### Added

- Nightly research round 37 (issue #65, tracker comment posted; serves #100, #94, #71,
  #73): `research/nightly-2026-10-30-0400/` re-runs round 31's digest-pinned (k, E)
  frontier grid on the same endpoint class (a 27B-class local model under NVFP4
  quantization, vLLM serving, multi-token-prediction speculative decoding), with round
  33's retest instrument retargeted to round 31's archive (gate `b90335f1`, schema
  `round37-gate-v1`, 992-check selftest, 37 of the 40-call cap, zero transport errors).
  Result: the single-run surface of round 31 does NOT repeat on its own class - the
  (16, 96) turnover cell is now maintained (6/6, all correct, zero truncations grid-wide),
  the delivery pattern moves 35 of 36 (round 31's single silent prompt delivered at 803
  tokens), the per-prompt length structure is not repeatable (Spearman 0.17, one of 36
  token-identical) and the per-hop cost slope falls outside its declared band (-9.48
  against -27.13, band [-54.26, -13.565]), while the answers (35/35 agreement, 36/36
  correct) hold; the "non-enumerating style (distractor-mention ratio 0.0) hold" half of
  this sentence is answer-level only, the ratio being structural under the closed trace
  channel (erratum in research/nightly-2026-10-30-0400/README.md, issues #113/#120). The
  round-31 cross-class cost-law conclusion is therefore not separable from this class's
  run noise; the archived (16, 96) ceiling now stands on two agreeing runs on the
  flash-next class and two disagreeing surfaces on this class. State: **Executed**.

### 2026-10-28

#### Added

- Round 33 nightly probe `research/nightly-2026-10-28-0400/` (issue #65): the first
  test-retest measurement of the nightly frontier instrument itself. Round 24's (k, E) grid
  re-run byte-identically (36 digest-pinned prompts, temperature 0, gate `979585cd`) on the
  flash-next class that produced it, three days later: all seven declared predictions pass.
  The six cell statuses repeat (five maintained, D2 inconclusive through one 2048-token
  truncation on the *same prompt digest* as round 24's), 35 of 35 delivered answers agree,
  the delivered/silent pattern is identical at 36 of 36 prompts (McNemar b = c = 0), the cost
  law reproduces (+7.686 tokens/fact against +7.885, +29.563 tokens/hop against +29.363,
  ratios 0.974 and 1.007), the grid-mean distractor-mention ratio is identical (0.8922), and
  32 of 36 completions are token-for-token identical (Pearson 0.995, Spearman 0.9938, median
  deviation 0, one item +16.9%). Consequence for #71: a single-run n=6 verdict on this class
  is a repeatable measurement, and round 31's cross-class cost-law conclusion is now bounded
  by a measured noise floor (run-to-run slope ratios 0.97 and 1.01 against cross-class ratios
  -0.76 and -0.92), not merely asserted. Independent audit of round 31's published slopes from
  its archived per-prompt lengths: -6.010357 and -27.125 (refs #71, #94, #65).

#### Changed

- Nightly protocol gap filed as issue #100 (round 33): neither the study design nor the M2
  inference harness (#5) records an identical-prompt self-agreement control, so no archived
  cell verdict can separate measurement from decoding noise; the fix is a repeated identical
  run per cell reported as raw-output and parsed-answer agreement, per-cell Wilson intervals,
  and a McNemar-style paired test against the archived run (prior art arXiv:2408.04667).
### 2026-10-27

#### Added

- Nightly research round 31 (issue #65, tracker comment posted):
  `research/nightly-2026-10-27-0439/` cross-class replication of the round-24 six-cell
  (k, E) bisection grid on a new endpoint class (a 27B-class local model under NVFP4
  4-bit floating point quantization, vLLM serving, multi-token-prediction speculative
  decoding), on byte-identical prompts digest-pinned to the round-24 flash-next archive
  (all-cell fail-closed anchor, gate `8d9c445f`, schema `round31-gate-v1`). Result: the
  frontier structure transfers verbatim - maintained through (k = 8, E = 160), turnover
  at (16, 96) reproduced by the same single arm-X truncation at 2048 (5/6 delivered and
  correct, answer field silent), zero wrong answers, 35/35 cross-class answer agreement.
  P1 fails as declared (the k = 16 turnover is shared across classes, not a flash-next
  artifact); P4 fails on both axes: the enumeration cost law is not class-invariant
  (per-fact slope -6.01 vs round 24's +7.89; per-hop slope -27.13 vs +29.36, both outside
  the declared [0.5x, 2.0x] band and both negative), with the distractor-mention ratio
  0.0 in every cell vs 0.68-1.00 on the flash-next class: this class does not enumerate
  the irrelevant components, and the load insensitivity is a 27B-class property
  (consistent with round 22's load-free-to-240 behavior), not a quantization artifact.
  State Executed, n = 6 per cell exploratory (refs #71, #94, #78, #73, #65).
### 2026-10-25

#### Added

- Nightly research round 23 (issue #65, tracker comment posted; serves #71, #94, #78):
  `research/nightly-2026-10-25-0205/` walks the (hop depth k, fact count E) frontier on a
  flash-next-class local endpoint - a monotone staircase S1..S6 in which consecutive cells
  change exactly one axis: (4,24), (4,96), (8,96), (8,192), (12,192), (16,192), 18 matched
  pairs, 36 prompts + 1 health call under the 40 cap. S1 and S2 are anchored by pool blob
  and prompt digest to round 21's k = 4 level and round 22's E = 96 level, so the walk is a
  continuation of both archived single-axis curves rather than a new grid; the anchors are
  fail-closed (gate and probe refuse on mismatch, a tamper control asserts the refusal).
  Result: the frontier is inside the walk - first non-maintained cell (k = 8, E = 192),
  `budget_limited` at (12,192) and (16,192), maintained at E <= 96 for k = 4 and k = 8 - and
  the failure is surfacing, not correctness: 25 of 25 delivered answers are correct, zero
  wrong answers, all 11 failures `length` truncations at 2048 with the answer field silent.
  The three declared readouts diverge for the first time in this archive (#94): 25/25
  content-only, 28/28 delivered-or-strict, 33/36 under the archived loose fallback, whose
  three false rescues are all instruction-echo tokens from the prompt's own "yes or no"
  phrase; 10 of the 11 fallback tokens on silent cells are "no" (baseline 0.50). This class
  shows no enumeration switch (3.98x output growth, distractor-mention ratio 0.51..0.64 at
  192 facts) where round 22's 27B class measured 0.97x and 0.016 at 240. Discordance b = 4,
  c = 1, exact McNemar p = 0.375 (directionally the fragile negative arm, not separable at
  18 pairs). Gate `f324feda` written before any prompt (schema `round23-gate-v1`, 921-check
  selftest green, no cell flagged on either pool), zero retries, zero transport errors.
  State: **Executed**.

### 2026-10-25 (second entry)

#### Added

- Nightly research round 24 (issue #65, tracker comment posted; serves #71's two named next
  steps): `research/nightly-2026-10-25-0405/` bisects the (k, E) frontier on the flash-next-class
  local endpoint - load arm at fixed depth k = 8 through E in {112, 128, 160} and depth arm at
  fixed safe load E = 96 through k in {12, 16}, 3 matched pairs per cell (36 prompts + 1 health
  call, gate `85e70f3f` written before dispatch, fail-closed blob/digest anchor of cell L0 to
  round 23's maintained S3 level). Result: the load arm is maintained all the way to E = 160
  (24/24 delivered and correct), narrowing the k = 8 frontier to (160, 192), while the depth arm
  turns over at (16, 96) (5/6 delivered, one truncation with the answer field silent) - so E\*
  shrinks as k grows and the ceiling is a joint (k, E, budget) surface, not a load-only curve;
  zero wrong answers grid-wide, no enumeration switch (mention ratio 0.68-1.00), and cost laws
  +7.89 tok/fact at k = 8 and +29.36 tok/hop at E = 96 (the depth slope reproducing round 21 at
  4x higher fact load) place the silence onset in the upper tail of the enumeration-length
  distribution, not its mean. State: **Executed**; exploratory; every ceiling conditional on the
  2048-token cap.
### 2026-10-24

#### Added

- Nightly research round 22 (issue #65; serves #71 load axis, #78 matched pair, #94 readout
  stack, #73 transport): `research/nightly-2026-10-24-0405/` measures the **load axis at constant
  hop depth** on a 27B-class local endpoint - k = 4 fixed, facts E in {24, 48, 96, 144, 192, 240},
  3 graphs per level, each graph queried twice over the *identical* fact list (arm F forward,
  gold yes; arm X cross-component, gold no), so the polarity contrast is unconfounded and the
  shared-content invariant of #78 criterion 1 is asserted per dispatched pair with a planted
  cross-item control. Gate `7afc9cc5` written before any prompt (355-check selftest green); the
  leak battery runs on both the 40-candidate pool and a paired pool matching the dispatched
  construction, no cell flagged; fail-closed anchor to round 21 (E = 24 pool blob and three arm-F
  prompt digests equal the PR #95 archive). Result: **E\* >= 240, no turnover** - 36/36 cells
  answered in the answer field, 36/36 correct, every level `maintained`, zero truncation, and
  **18/18 matched pairs with both members correct** (exact McNemar b = c = 0). Two failed
  predictions carry the finding: mean completion at E = 240 is 0.97x the E = 24 mean (declared
  floor 3.0x, slope -0.53 tokens per added fact while prompt tokens rise 14.86 per fact), because
  this class abandons enumeration above ~100 facts (distractor-entity mention ratio 1.00, 1.00,
  1.00 then 0.34, 0.18, 0.016); and E = 240 stays `maintained`, so with round 21's constant-load
  result the ceiling is **two-dimensional in (k, E)**, not a curve in either axis alone. The
  three anchored prompts reproduce round 21's delivered answers 3/3 at ~15% fewer tokens.
  Transport disclosed in `research/nightly-2026-10-24-0405/transport.json`: the assigned pool slot
  was generation-hung (0.3 tokens/s) and the round rotated to the pool's next generation-healthy
  slot; the health-probe budget was lowered to 256 tokens before the first prompt; `aggregate()`
  was patched after all 36 cells were archived and recovered at zero prompt cost under the
  gate-hash-guarded resume. 36 grid prompts of a 40 cap, zero retries. State: **Executed**.
### 2026-10-24 (second entry)

#### Added

- Nightly research round 21 (issue #65, tracker comment posted; serves #71 criterion 2 / option 2
  and #94): `research/nightly-2026-10-24-0205/` runs the constant-load depth arm that round 8
  designed but never measured (its probe died on transport failure after 15 of 40 prompts):
  E = 24 facts fixed, hop depth k in {2, 3, 4, 6, 8, 12}, C = 24/k disjoint directed paths,
  6 items per depth, 36 prompts + 2 health calls of the 40 cap, temperature 0, on a
  flash-next-class local endpoint. The #94 readout stack (content_only / loose_fallback /
  delivered_or_strict) is declared before dispatch, with the strict rule and echo test vendored
  verbatim from round 19 and asserted by `--selftest` (323 checks); the vendored rule reproduces
  round 19's archived control exactly (13 of 36 kept, all gold-agreeing). Result: **36 of 36
  cells answered in the answer field and 36 of 36 correct at every depth under all three
  readouts; every depth `maintained` (Wilson lb 0.6097), d\* >= 12, no turnover within the grid
  at constant load** - the round-19 negative-arm surfacing failure is therefore a joint
  prompt-load x budget effect, not depth per se. Declared P3 fails honestly: mean completion
  tokens grow 2.22x from k = 2 to k = 12 at constant load (+29.1 tokens/hop), so depth costs
  generation, not within-grid correctness; P4b is vacuous (the answer field never went silent).
  Gate `d39ceb84` (schema `round21-gate-v1`): leak battery on the whole 40-item pool per cell, no
  cell flagged (best 0.70 vs threshold 0.725); constant load visible in the tokenizer (mean
  prompt tokens 434.8..440.8). State: **Executed**, exploratory (6 items per depth, one class).
  The 2026-10-23 04:00 firing (round 20) left no record; disclosed on #65.
### 2026-10-23

#### Added

- Round 19 nightly probe `research/nightly-2026-10-23-0200/` (issue #65): the budget
  ladder at fixed depth on the repaired ladders family - the nine level-24 cells
  (F1, R1, X, three items each) at `max_tokens` 256, 640, 1280, 2048 on a
  flash-next-class local endpoint, prompt sha256 paired fail-closed to the round-15
  and round-17 archives (9 of 9 each) before any prompt spent. Surfacing is monotone
  in budget but arm-specific: F1 surfaces 0, 0, 3, 3 cells (all six surfaced answers
  correct), R1 and X surface 0 of 3 at every budget up to 2048; answer-field-only
  accuracy is 6 of 36 while the declared parser reports 9 of 9 answered at every rung
  including 256 tokens. Post-hoc readout control: the reasoning-fallback token is
  "no" in 34 of 36 records and its accuracy 24 of 36 equals the constant-"no"
  baseline exactly; a strict commitment rule keeps 13 of 36 and all 13 agree with
  gold (F1 7, R1 6, X 0 at every budget). Consequence recorded: at k = 24 on this
  class the traversal-versus-connectivity discrimination was carried by fallback
  tokens, while the same grid on the 27B class answers R1 from `content` (refs #71,
  #78, #73, #65).

#### Fixed

- Round 19 record, self-audit against the archives (refs #65): the P5 pairing claim is narrowed to
  declared answers (9 of 9, exact McNemar p = 1.0) - cell-level completion-token reproduction is
  not testable because the round-17 archive stores no per-cell counts (gate field
  `round17_completion_tokens` null); and the 0.457 mid-stream commitment median is attributed to
  round 17, which measured it, instead of to this round. No measurement, gate, `raw.jsonl` or
  `summary.json` changed. The same corrections were applied to the round-summary comment on #65,
  the PR #93 description and issue #94 (rescue counts restated per round: 7, 0, 17, 1 for
  rounds 15, 16, 17, 18).

### 2026-10-22

#### Added

- Round 18 nightly probe `research/nightly-2026-10-22-0400/` (issue #65): the
  round-17 fixed-budget depth curve (repaired ladders family, k = 24, 32, 48,
  `max_tokens = 2048`) mirrored on a 27B-class local endpoint, on the
  byte-identical 36-cell grid, with the level-24 cells anchored to the
  round-16 archive (12 of 12, fail-closed) and every cell paired cross-class
  to the round-17 archive (36 of 36, fail-closed) before any prompt spent:
  29 of 36 cells answered, 29 of 29 correct - budget turnover confined to the
  X arm at k = 24 (0 of 3 there, 1 of 3 at 32 and 48, all seven truncated
  cells dying at full expected-traversal coverage), no correctness turnover;
  the declared answerability-decay prediction fails honestly (0.75 / 0.833 /
  0.833). The cross-class delta on the identical grid is exactly the seven X
  cells the flash-next class answered via the reasoning fallback and this
  class truncated; this class is far more token-efficient where it answers
  (R1 453 vs 1717 tokens, positive-arm token law -61.9 + 22.0k vs -50.8 +
  33.1k, one reasoning rescue vs 17) and the temperature-0 anchor rerun is
  token-identical on all twelve L24 pairs (refs #71, #78, #73, #65).
- Round 17 nightly probe `research/nightly-2026-10-22-0200/` (issue #65): the
  fixed-budget depth curve on the repaired ladders family, extended to
  k = 24, 32, 48 at `max_tokens = 2048` on a flash-next-class local endpoint,
  with the k = 24 level cell-paired to round 15 by prompt sha256 (12 of 12,
  fail-closed before any prompt): 36 of 36 cells answered, 36 of 36 correct -
  no answerability or correctness turnover inside k = 48; the declared
  answerability-decay prediction fails honestly. Budget pressure lands on the
  negative arms: 17 of 36 cells hit the 2048 ceiling (all nine X cells at every
  level), every one rescued by a yes/no committed mid-trace (median position
  0.457 of the stream), so at this budget the scarce resource is the
  answer-surfacing path, not reachability; positive-arm completions fit
  -50.8 + 33.1k tokens (r = 0.845), under half round 6's open-budget slope -
  correct answers without full recitation. Anchor rerun: 12 of 12 answers agree
  with round 15 at temperature 0. Adjacent literature framed at abstract level:
  the coupling tax (arXiv:2605.07686) and budget-exhaustion non-convergence
  (arXiv:2607.21433) (refs #71, #78, #73, #65).

### 2026-10-21

#### Added

- Round 15 nightly probe `research/nightly-2026-10-21-0200/` (issue #65): the
  matched-pair traversal grid at k = 12, 16, 24 run for the first time on the repaired
  ladders family (component isomorphism, issue #69, merged 2026-10-20), on a
  flash-next-class local endpoint: 36 of 36 cells follow the directed-traversal oracle,
  the connectivity oracle fails exactly the nine reverse cells, exact McNemar shows zero
  discordant pairs in both matched families. Corpus pinned by generator sha256 and blob
  hashes, declared not cell-paired to the pre-repair rounds 10/11/14. All seven
  2048-token truncations land on negative arms (six at k = 24) with the answer already
  emitted in the reasoning trace: the scarce resource at k = 24 is the output budget,
  quantifying round 6's "budget, not depth" per arm (refs #71, #78, #69).
- Literature update recorded on issue #71 (issue #65 round 15 comment): quantization
  versus multi-hop reasoning is no longer an evidence vacuum (arXiv:2602.13595,
  arXiv:2606.00206, arXiv:2606.25519, arXiv:2504.04823; ACL 2026 MixKVQ), so
  quantization moves from uncontrolled variable to demonstrated confound for
  cross-endpoint d* placement; no published traversal-specific d* result exists.
- Round 16 nightly probe `research/nightly-2026-10-21-0400/` (issue #65):
  cell-paired cross-class probe on the repaired ladders family - round 15's corpus
  run byte-identically on a 27B-class local endpoint (the pool slot round 14 measured
  pre-repair), compared cell by cell against the round-15 archive: 33 of 33 answered
  cells correct, the traversal oracle matches all 36 cells under the disclosed
  default-match convention, and the first cell-paired cross-class comparison on the
  repaired family shows 33/33 answer agreement with zero discordant pairs (exact
  McNemar p = 1.0). The only cross-class delta is the X cells at k = 24: truncated
  but rescued via the reasoning trace in round 15, unanswerable within 2 x 2048
  tokens on this class (light-thinker profile, flat latency, all answers from
  content). Cell pairing verified by per-cell prompt sha256 before any prompt spent
  (refs #71, #78, #65).


### 2026-10-20

#### Added

- Nightly research round 14 (issue #65, tracker comment posted; serves #71 depth-ceiling
  placement): `research/nightly-2026-10-20-0400/` replicates the round-11 matched-pair
  traversal grid (k = 12, 16, 24; nine matched items x four arms = 36 cells; byte-identical
  prompts, prompt_sha256 identity asserted in the gate against the committed round-11 raw
  archive `round11_reference_raw.jsonl`) on a 27B-class local endpoint. Result: 36/36
  cells follow the directed-traversal oracle (connectivity fails exactly the nine R1 cells,
  0 discordant McNemar pairs in both families), and the verdict is cell-identical to the
  flash-class round-11 run (36/36 cells agree), so on this corpus the traversal signature
  is not a property of the flash class; completion style is class-dependent (full interior
  chain recitation in 18/36 completions vs 36/36 at the flash-class slot, mean completion
  tokens 407.1, max 853, no truncation at 2048). Gate written before any prompt (schema
  `round14-gate-v1`, 66-check selftest green); 37 endpoint calls under a 40-attempt cap,
  zero retries. State: **Executed**; the round-11 independent-verifier standard is deferred
  this round and disclosed in the round README.

### 2026-10-19

#### Added

- Archive round 17, mechanistic interpretability review: 1 entry in
  `archive/round17-mechanistic-review-2026/` (Sawant & Krejčí 2026, arXiv:2607.07316,
  scoping review, preprint), ingested on owner direction with focus on section 3.8
  "Emergent Symbolic Reasoning Mechanisms", full-text verified (`[FT]`): deduction
  heads on tree path-finding (Brinkmann et al., arXiv:2402.11917) and the Yang et al.
  ICML 2025 three-stage symbolic architecture (symbol abstraction, symbolic induction,
  retrieval). Verdict: +/- mechanism - strengthens the circuit-forms line (Nanda,
  Olsson), does not meet the acceptance criteria (survey, task-trained or undisclosed
  models); overall verdict unchanged. Archive now 122 entries in 16 rounds; count
  statements updated in the same commit.
- Automated repo-round family under tracker #83 (runners live outside this repository,
  public-only rule): daily PR review at 06:30 (skill-verified validation of open PRs
  plus the 3 required CI checks, merge-if-green), weekly maintenance Sun 05:00 (branch
  hygiene, deep skill-verified PR pass), weekly doc collection Sun 08:00 (intro pages
  synced via the DOX closeout rules), weekly issue audit Sun 09:00 (open issues
  validated against in-repo knowledge). The merge gate is unchanged: every change
  reaches main via branch + PR with all 3 CI checks green; agents never push to main
  and never touch .github or the ruleset.

- Nightly round 11 research record (`research/nightly-2026-10-19-0200/`, issue #65,
  refs #71, #73): a matched-pair probe at depths k = 12, 16, 24 on nine seed-generated
  ladder items (levels beyond the shipped grid, generator hashes pinned in the gate)
  replicates the round-10 traversal verdict: 36/36 cells match the directed-traversal
  oracle, the undirected-connectivity shortcut fails all nine reverse cells, exact
  McNemar shows zero discordant pairs in both matched families, and all 36 completions
  recite the full interior chain. The endpoint is a flash-next-class slot of the local
  pool, a distinct slot from round 10's (same public model family; not a quantization
  comparison).
  Transport hardening: 37 endpoint
  calls under a global 40-attempt cap, zero retries, per-attempt `finished_at`
  timestamps close the named open item of #73. The probe script fixes three round-10
  verification findings instead of copying them (true null support bounds, two-sided
  exact nulls for gate firing, attempt-capped retries) and its `--selftest` passes
  50 checks. Verification record: `docs/review-rounds/nightly11-2026-10-19.md`
  (byte-identical regeneration of gate and summary; seven documentation errata corrected;
  state Executed and Reproduced at the analysis level).


- Nightly round 11 research record (`research/nightly-2026-10-19-0200/`, issue #65,
  refs #71, #73): a matched-pair probe at depths k = 12, 16, 24 on nine seed-generated
  ladder items (levels beyond the shipped grid, generator hashes pinned in the gate)
  replicates the round-10 traversal verdict: 36/36 cells match the directed-traversal
  oracle, the undirected-connectivity shortcut fails all nine reverse cells, exact
  McNemar shows zero discordant pairs in both matched families, and all 36 completions
  recite the full interior chain. The endpoint is the pool's `qwen38-flash-next` slot, a
  distinct slot from round 10's (same public model family; not a quantization comparison).
  Transport hardening: 37 endpoint
  calls under a global 40-attempt cap, zero retries, per-attempt `finished_at`
  timestamps close the named open item of #73. The probe script fixes three round-10
  verification findings instead of copying them (true null support bounds, two-sided
  exact nulls for gate firing, attempt-capped retries) and its `--selftest` passes
  50 checks. Verification record: `docs/review-rounds/nightly11-2026-10-19.md`
  (byte-identical regeneration of gate and summary; seven documentation errata corrected;
  state Executed and Reproduced at the analysis level).

### 2026-10-18

#### Added

- Nightly round 9 (issue #65, `research/nightly-2026-10-18-0200/`): the round-8
  constant-load grid re-run on the faster assigned endpoint with the #73 transport
  hardening (pre-grid health check, sequential dispatch, per-item 600 s deadline with one
  retry, incremental fsynced raw archive, empty completions classified `transport_failure`
  with error class and never `no_answer`, per-arm 3600 s budget). The probe completed:
  40/40 answered, 40/40 correct, 0 transport failures, all first attempt. No turnover to
  arm-L `k = 12` (6/6 at every depth, Wilson lower bound 0.6097 above the 0.60 floor),
  so `d* = 12` within the declared grid, i.e. `d* >= 12`; arm X descriptive 2/2 at
  `k = 16` and `k = 24`. Budget replay: 25/40 items unreachable at 256 tokens (median
  completion 404 tokens), 18 at 512, 2 at 1024, 0 at 2048, and every reachable answer is
  correct (truncation cliff, not reasoning cliff). The three items that survived round 8's
  transport failure answer correctly on the byte-identical stream. #73 acceptance met
  (arm ran; the empty-completion and deadline paths are covered by selftest controls 10
  and 11). `const_load_depth.py` is a self-contained re-implementation (stdlib only, 15
  selftest controls including stream identity against round 8's published gate record).
- Round-9 literature verification posted to issue #74 (free scholarly APIs only): CLUTRR
  (arXiv 1908.06177) verified with venue EMNLP 2019 (ACL Anthology D19-1458); the
  RuleTaker (pinned arXiv 2301.07330) and PrOntoQA (pinned arXiv 2203.14238) arXiv IDs
  in #74 point at unrelated papers (FPANet and a Vicsek-model paper respectively) and
  neither paper resolves in arXiv, Crossref, or OpenAlex (OpenReview-only, forum
  unresolvable from this environment); verified animal transitive-inference primary
  Gazes, Chee and Hampton 2012, J. Exp. Psychol. Animal Behavior Processes 38(4):331-345,
  DOI 10.1037/a0030306.

- Nightly round 10 (04:00 slot, issue #65): matched-pair probe of traversal versus undirected
  connectivity in `research/nightly-2026-10-18-0400/` (`matched_pair_probe.py`, `gate.json`,
  `raw.jsonl`, `summary.json`, `README.md`). The shipped corpus is shown to be unable to separate the
  two strategies: across all 1500 items there are 0 queried pairs where connectivity and directed
  reachability disagree, and 5 direction-blind rules reproduce every gold label at 1.0000
  (`same_component`, `undirected_connectivity_only`, `target_is_fact_target`,
  `endpoint_out_degree_zero`, `chain_len_matches_level`; the last is a metadata leak, since item
  `chain_len` equals `level` for gold-yes items). A 9-item matched corpus built by re-querying real
  shipped items at k = 4, 6, 8 (forward interior, reverse, forward shifted, cross-component terminal)
  has 9 disagreeing cells, matched-pair invariants enforced as fatal checks, and a 15-rule
  direction-blind battery whose best rule reaches only 0.7500, so the corpus is discriminating while
  the shipped one is not. Probe: 36 prompts, 36/36 answered, 0 transport failures, 0 truncations,
  every arm 9/9; exact McNemar 0 discordant pairs in both families; the answer pattern matches the
  directed-traversal oracle on 36/36 cells and 9/9 items and the connectivity oracle on 27/36 cells
  and 0/9 items. Verdict: the endpoint traverses the chain rather than answering from component
  membership. This defeats the blocking half of #77 criterion 4 for probing (a matched-pair probe does
  not have to wait for the generator repair) without cleaning the shipped corpus, which criterion 3
  still owns. Exact label-shuffle nulls throughout, no Monte Carlo; significance separated from
  competence (`same_component` reaches p 1.953e-03 on the matched corpus at only 0.7500 accuracy).
  Literature arm: CLUTRR 1908.06177, ProofWriter 2012.13048, Soft Reasoners 2002.05867, PrOntoQA
  2112.09054, Greedy Reasoners 2210.01240, OOD deductive capacity 2305.15269, Explicit Planning
  2303.15714, Verifier-Guided Proofs 2205.12443, PRover 2010.02830, NeuBAROCO 2306.12567, Hypothesis
  Search 2309.05660, Neural Theorem Provers 1906.06805; the seven IDs earlier rounds mis-pinned are
  recorded as wrong. As first published 8 of those 12 titles did not match the arXiv record and the
  entry claimed RuleTaker's own ID was unconfirmed; both were corrected the same day by the independent
  verification pass recorded below. Honest disclosure: the first execution of this round was destroyed by
  a verifier subagent that switched the shared primary worktree to `main`, and everything published is
  from a single re-execution (see the round README limits section).

#### Fixed

- Independent verification of nightly round 10 (`docs/review-rounds/nightly10-2026-10-18.md`): every
  quantitative claim in `research/nightly-2026-10-18-0400/README.md` recomputed from `gate.json`,
  `raw.jsonl`, `summary.json` and `items/ladders/` with independent union-find, BFS, exact
  `Fraction`-based hypergeometric and convolution nulls, Wilson interval, and McNemar implementations.
  All headline numbers reproduced, and `--gate` plus `--analyze` regenerate `gate.json` and
  `summary.json` byte-identically in a sandbox. Corrections landed in the round README: the selection
  rule is 3 usable items per level, not one; the arm notation is off by one (F1 is (p_1, p_k), R1 is
  (p_k, p_1), F2 is (p_2, p_{k+1})); "15 rules that cannot express edge direction" is overstated, since
  reversing every edge changes 5 of the 15; the rule nulls are one-sided upper tails, and the two-sided
  matched p for `same_component` is 3.906e-03, above the 3.333e-03 Bonferroni bar, so the 0.90 accuracy
  bar is what makes the corpus discriminating; shipped p 0.0 is an underflowed float for an exact tail of
  about 10^-450; `gate.json` records `null_min_hits` wrong for 12 rules and `null_max_hits` wrong for 3
  (the true support is [|a + y - n|, n - |a - y|]), which cannot be retrofitted because the gate hash is
  embedded in every `raw.jsonl` record and in `summary.json`, so the fix is owed with a fresh gate under
  #77; the 10.2 s health check, the 745.8 s probe wall clock, the 37-to-73 prompt range and the "two real
  bugs found by those controls" claim are runner-side statements no artifact carries; the literature table
  is rewritten with API-resolved titles, authors and venues, 2002.05867 is identified as the RuleTaker
  paper, its venue is IJCAI 2020 rather than the unsupported "TACL 2021", and "Language Models with
  Rules" plus "Deriving Rules from Language Models" are recorded as unverified because no arXiv record
  carries either title. The same corrections were published in place on the forge threads where round 10
  had already posted them (the PR #80 description and comment, and issues #65, #73, #74, #77 and #78) rather
  than as new issues; the PR description was corrected by prepending a dated corrections section and
  leaving the original claim record below it. Issue #73 additionally received the round-10
  transport record as the artifacts carry it, plus the proposal that future rounds write `started_utc`
  and `finished_utc` into `summary.json` so that wall-clock claims are archive claims rather than log
  claims.
- `matched_pair_probe.py --selftest` now passes 45 of 45 and exits 0. As shipped by round 10 it reported
  44 of 45 and exited 1: one check asserted `null_sd == 0.0` and `p_exact == 1.0` for the
  `same_component` shipped null, whose true standard deviation is 19.370824 and whose exact tail
  underflows to 0.0, and a second check was labelled "0 discordant pairs" over an assertion of 9. Both
  were defects in the test, not in the analysis; the bound formulas in `exact_null_shipped` are left
  unchanged on purpose and now carry a comment recording the correct support for the round that re-runs
  the battery with a fresh gate hash.

#### Changed

- `docs/agent-execution.md` section 5 gains two verification-conduct rules, both learned from this
  round's verification pass: a verifier is read-only against the worktree under verification (it writes
  only outside it, never edits a tracked file, never commits or pushes, and never runs `git checkout`,
  `git switch`, `git branch -D` or `git push --delete` against that worktree or its refs; its findings
  land as a report the producing agent re-verifies and applies), and the runner snapshots the round
  directory before any verifier pass, by commit plus push or by a checksummed copy outside the
  repository. The first execution of round 10 was destroyed by exactly the operation the first rule
  forbids, and the round-10 verifier patched the working tree while reporting read-only operation.

### 2026-10-17

#### Added

- Nightly round 8 (`research/nightly-2026-10-17-0400/`, issue #65 firing 2026-10-17 04:00):
  `ladder_load_depth.py`, an independent re-implementation (no import from `generators/`, own
  name pools, own BFS solver, verifier, gate, probe and scorer) of the constant-load hop-chain
  grid that decouples depth `k` from prompt load `E` (issue #71 criterion 2): arm L holds
  `E = 24` facts at `k in {2,3,4,6,8,12}` with measured prompt length 1109.5 to 1111.5
  characters (2.0 character spread, 0.18 %), arm X extends to `k in {16,24}` at `C = 2`.
  Declared grid, seed-frozen selection rule, fail-closed gate, three-state scoring,
  `--selftest` (11 controls) green.
  `gate.json` records the permutation-calibrated gate passing all 8 cells (thresholds 0.700 to
  0.800, p 0.072 to 1.000).
- Gate-power measurement (issue #71 criterion 4, #67): the same battery and null run on 6 items
  versus a 40-item candidate pool gives a calibrated threshold of 1.000 at `n = 6` against
  0.700 to 0.800 at `n = 40`, and a planted name-order shortcut is missed at `n = 6`
  (p 0.259, 0 rules flagged) but caught at `n = 40` (p 0.0025, 9 rules flagged). The fixed 0.55
  threshold would have refused all 8 clean cells of this grid.
- Shipped-corpus gate cross-check (issue #67): the same battery run on the first 40 committed
  items of each shipped level independently reproduces the leak, flags R1 as
  `single:tgt_is_fact_target->yes` and R2 as `single:tgt_outdeg_zero->yes` at accuracy 1.000 in
  all five levels, and names two further single-feature predictors at 1.000 that #67 did not
  (`single:tgt_indeg_zero->no`, `single:tgt_is_fact_source->no`); 31 to 54 rules are flagged per
  level inside a 340-rule traversal-free battery, so a `generators/ladders.py` repair must be
  validated against the whole battery.
- `d*` procedure as a named trichotomy (`maintained` / `inconclusive` / `collapsed`, plus
  `budget_limited` and `descriptive` states) with Wilson 95 % bounds against a 0.60 floor, and
  the certifiability table over items per depth: at 6 items only 6/6 certifies maintained and
  only 1/6 or worse certifies collapse; 80 % maintained needs 30 items per depth, 73 % needs 60.
- `probe-attempt.log`: the model-facing arm aborted after 15 of 40 dispatched prompts (12 empty
  completions, 3 correct at 355 to 557 completion tokens), no `raw.jsonl`, no depth measurement.
  Recorded as the failure record, with the answer-position estimate shown to be invalid for an
  endpoint that separates reasoning from content.

- Nightly round 11 research record (`research/nightly-2026-10-19-0200/`, issue #65,
  refs #71, #73): a matched-pair probe at depths k = 12, 16, 24 on nine seed-generated
  ladder items (levels beyond the shipped grid, generator hashes pinned in the gate)
  replicates the round-10 traversal verdict: 36/36 cells match the directed-traversal
  oracle, the undirected-connectivity shortcut fails all nine reverse cells, exact
  McNemar shows zero discordant pairs in both matched families, and all 36 completions
  recite the full interior chain. The endpoint is the pool's `qwen38-flash-next` slot, a
  distinct slot from round 10's (same public model family; not a quantization comparison).
  Transport hardening: 37 endpoint
  calls under a global 40-attempt cap, zero retries, per-attempt `finished_at`
  timestamps close the named open item of #73. The probe script fixes three round-10
  verification findings instead of copying them (true null support bounds, two-sided
  exact nulls for gate firing, attempt-capped retries) and its `--selftest` passes
  50 checks. Verification record: `docs/review-rounds/nightly11-2026-10-19.md`
  (byte-identical regeneration of gate and summary; seven documentation errata corrected;
  state Executed and Reproduced at the analysis level).

### 2026-10-17 (second entry)

#### Added

- `research/nightly-2026-10-17-0200/ladder_depth_load.py` (nightly round 7, issue #71): an
  independent structural audit of the shipped ladder corpus. BFS over each item's own fact
  graph classifies every item as shortcut, exact, longer, or unreachable against the declared
  depth; measures the reachable closure and facts per item; and builds a level-matched
  permutation null by re-drawing the query pair from each item's own entity set. 37/37
  selftest controls pass (planted shortcut, planted negative, cross-relation edge, branching
  closure, seed determinism, corpus invariants). `depth_load_report.json` pins the sha256 of
  the five corpus files it measures. Results: 0 derivation shortcuts in 1,500 items (every
  `yes` item exact at the declared depth, every `no` item unreachable), reachable closure
  exactly `k+1` at every level, null shortcut band 9-12% for `k >= 2`. No model arm ran this
  round, so the round is labelled Executed only.
- `research/AGENTS.md`: DOX child for the nightly round working record (round-directory
  layout, independence from `generators/`, mandatory `--selftest` negative controls before
  reporting numbers, sha256-pinned reports, honest Executed/Reproduced/Validated labels,
  dated corrections instead of silent rewrites). Root Child DOX Index updated.

#### Changed

- `generators/AGENTS.md`: records the ladder depth/load coupling (facts per item equal
  `C * k` with `C` uniform in `[2, k+2]`, mean `k^2/2 + 2k`, within-level span `2k` to
  `k(k+2)`, 5x spread at level 8) and the requirement that leak-gate thresholds be calibrated
  against the level-matched permutation null rather than the fixed 0.55 constant (issue #67
  criterion 2, issue #71 criterion 4).
### 2026-10-16

#### Added

- `research/AGENTS.md`, the DOX boundary for nightly round artifacts (issue #65): one
  directory per firing, script plus `raw.jsonl` prompts and raw responses plus
  `summary.json`, sanitized by construction (no host, IP, endpoint URL, credential or
  model file path, in model output text as well), protocol caps treated as contractual,
  and the Executed/Reproduced/Validated label stated per run. Registered in the root
  Child DOX Index.
- `research/nightly-2026-10-16-0400/` (nightly round 6): `ladder_depth_probe.py`, a
  depth-ceiling probe for the k-hop ladder family (stdlib, `--selftest` with 7 controls:
  byte-identical regeneration against the shipped series, a constant rule at exactly the
  majority baseline, a perfect rule at 1.0, an inverted rule at 0.0, parser refusals,
  sanitizer, and two negative controls that must be rejected: a flipped answer and a
  pre-#69 item), plus `raw.jsonl` (40 prompts and raw responses) and `summary.json`.
  Result on a local Qwen3.8-Flash-Next class endpoint (arm A, temperature 0,
  `max_tokens` 2048, grid k in {1,2,3,4,5,6,8,10,12,16}, 2 yes + 2 no per level selected
  before any call): 40/40 correct, 40/40 format-valid, 0 truncations, no ceiling inside
  k <= 16, reproducing PR #69's model-facing claim on a second endpoint with an
  independent harness. New measurement: depth is paid in output tokens
  (`completion_tokens = -36 + 80k`), and replaying the same completions against fixed
  budgets loses 26/40 items at 256 tokens, 12/40 at 512 and 4/40 at 1024, so the family
  is budget-limited rather than depth-limited for an explicit-reasoning endpoint; the
  `d*+1..d*+4` band cannot be placed from this curve. Recorded in
  `docs/next-investigations.md`.

#### Fixed

- `generators/AGENTS.md` seed policy stated the digit-matrices forms as family-wide: the
  per-item seed multiplier is 2_000_000 for `ladders.py` (not 1_000_000) and the ladder
  `seed_hash` is sha256("family|task_type|level|seed")[:16], so the committed ladder seeds
  and seed hashes did not follow from the documented rule.

### 2026-10-16 (second entry)

#### Added

- `generators/fixtures/` (issue #67): the pinned pre-fix ladder items as the negative
  control for the leak gate and the probe. `issue67_prefix_l2.jsonl` and
  `issue67_prefix_l8.jsonl` hold every 8th line (1-based lines 1, 9, 17, ...) of
  `items/ladders/l{2,8}.jsonl` at 49ee823, 38 items per level, the corpus that carried
  the leak;
  `issue67_prefix.manifest.json` records the extraction rule, the source and fixture
  sha256s, and the policy that these items are superseded and never enter a study run,
  a pilot, or the main experiment. `audit_ladder_leaks.py --audit-fixtures` asserts the
  gate FIRES on them: exit 0 demonstrates detection power, exit 4 means the gate has
  lost the ability to detect a documented leak.
- `generators/probe_ladder_shortcut.py` (issue #67): matched-pair shortcut probe. 4
  cells x 10 items = 40 experimental prompts (pre-fix l2, post-fix l2, pre-fix l8,
  post-fix l8). The design intent was a matched pair, the same item under a
  shortcut-friendly and a traversal-only query; what the shipped generator provides is
  pairing by seed only (see the 2026-10-17 entry under Fixed), so the two arms of a level
  share a seed and not the item.
  Zero-shot, temperature 0, one fixed neutral template, one decoding seed, no traversal
  or chain-of-thought instruction, the item `rule` field withheld from the prompt.
  Primary metric is balanced accuracy against three a-priori baselines fixed in advance
  (majority, direct_fact, leak signature) and an exact fair-coin answering null computed
  with binomial weights (no Monte Carlo); the verdict rule (`inconclusive_no_capability`
  / `traversal_consistent` / `shortcut_consistent`) is encoded in the instrument. 13
  selftest control groups, including a mock that answers purely by the pre-fix leak
  signature and must read as `shortcut_consistent`. Calibration calls (cap 3, seeds
  asserted outside the 40, worst-case chain length per arm) are recorded as instrument
  validation, never as experimental data.
- `runs/` as the record directory for executed runs, with `runs/AGENTS.md` owning the
  manifest/raw/report contract and the Executed / Reproduced / Validated labels.
- `runs/nightly-2026-10-16-0200/`: the executed matched-pair ladder probe (issue #67) -
  immutable `probe_manifest.json`, 40 raw records in `probe_raw.jsonl` (sha256
  `a836abc1…d7b34`), `calibration.json` (3 calls), the `attempts.json` and
  `environment.json` sidecars, pinned copies of the gate reports (`audit_shipped.json`,
  `audit_fixtures.json`, `audit_generated.json`), `analyze_run.py` (regenerates every
  report number from the archived artifacts, 14 seeded-defect controls, `--check` mode),
  `name_channel_audit.py` (21-feature surface battery: 16 traversal-free name/position
  features plus 5 structural connectivity features, exact two-sided binomial, Bonferroni
  correction at 0.05/21, 5 controls) with its pinned outputs
  `name_channel_audit_shipped.json` and `name_channel_audit_fixtures.json`,
  `verify_independent.md`, `verify_report_v2.md` (a second independent verification, run
  against the report after the first corrections, carrying an 84-field manifest
  confrontation, a 40-record confrontation, a 16-feature surface audit built without
  importing any project script, a seeded-defect recall probe, and a discrepancy register
  D1-D12), and `report.md`. Result: 66 endpoint calls for the 40-prompt
  design (26 over cap, caused by two client timeouts and one crash, accounted per attempt),
  40/40 valid, all 4 cells strong at balanced accuracy 1.0000, exact answering-null
  P(BA >= 1.0) = 1/1024 and label-permutation-null P(BA >= 1.0) = 1/252, 1/210, 1/120,
  verdict `traversal_consistent`. Battery result: no traversal-free feature clears the
  corrected threshold on either corpus (best 0.5700 at shipped l2, p 0.017779 against a
  threshold of 0.002381), while `same_component` reproduces the gold label at 1.0000 on all
  300 shipped items per level and on all 38 fixture items per level.
- `runs/AGENTS.md` now allows run-directory sidecars explicitly: an analysis script, a
  battery established after the run, pinned copies of cited gate reports, and an attempts
  record. A sidecar never edits the manifest or the raw records, and a sidecar that
  supersedes an ad-hoc number makes the earlier number uncitable.

#### Changed

- `generators/audit_ladder_leaks.py` is permutation-calibrated instead of absolute. The
  null is the exact hit-count distribution of the best rule in the audited hypothesis
  class under label permutation (binomial weights over the bitmask class); a rule is
  gated only when it beats the class's own constant rule AND clears that null at
  `NULL_ALPHA = 0.05`. `CHANCE_MAX = 0.55` survives only as a reported legacy floor
  (`legacy_threshold_leaks`). Features constant across an item set are reported, never
  gated. Each level now ships its `min_detectable_accuracy`, so every `no_leak` verdict
  carries its own detection power. Level 1 is relabelled `lookup_control` and excluded
  from the gate: at k=1 `direct_fact` is the task itself.
- `docs/counterarguments.md` C5: ladder depth evidence starts at k=2, level 1 is a
  lookup control and carries no depth evidence.
- `generators/AGENTS.md`: `no_leak` is stated as a claim about the tested hypothesis class
  only, and the class is recorded as incomplete. The 2026-10-15 claim that component
  membership "requires the intended k-hop traversal" is corrected: the undirected
  component-membership feature (query source and query target in the same connected
  component of the fact graph, ignoring edge direction) reproduces the gold label at
  accuracy 1.0000 on all 300 shipped items at every ladder level and on the fixtures, so a
  model can cluster the fact graph and answer every ladder correctly without following any
  edge in order. The shipped corpus is clean under the 18-feature class and leaky under
  connectivity; widening the class to relational features is open work on issue #77 (split
  from #67, which keeps the generator repair and the fixtures). Under a connectivity strategy
  k is not a difficulty ladder, because connectivity accuracy is 1.0 at k=2, 4, 6 and 8.
- `docs/agent-execution.md` section 5 (2026-10-17): the two operating rules this round established.
  A verifier's record is archived unedited, and the author of the verified document records a
  disposition in it (accepted and fixed, or declined with evidence), with a declined item staying
  visible. A count a report cites from a script (control groups, feature counts, corpus sizes) is
  emitted by that script and asserted against the cited number, not typed into the report, so a
  change to the script fails a control instead of leaving the report stale. `runs/AGENTS.md` carries
  the local version of both rules, and the root and `runs/` Child DOX Index rows now name the
  regeneration scripts and the verification records, and describe the round-5 probe as seed-paired
  rather than matched-pair.

#### Fixed

- `probe_ladder_shortcut.py` lost a whole experiment to a shared-pool stall: run attempt 1
  on 2026-10-16 died at item 22/40 on a socket timeout, and because records were only
  written at the end all 21 answers already paid for were lost. The instrument now appends
  and fsyncs each record as it is produced, retries a stalled item once under a global
  retry budget (`MAX_RETRIES_TOTAL = 8`, `RETRY_BACKOFF_S = 20`, client timeout 180s ->
  600s, sized from the call latency archived in `probe_raw.jsonl`: min 21.6s, median
  125.2s, p90 206.0s, max 345.1s over the 40 records, 22 of them above 120s; the raw
  records carry `latency_s` but no absolute timestamp, so an idle-versus-contended split is
  an operator observation and not a regenerable claim, and issue #73 asks for a per-record
  `finished_at`), records a still-failed item as `finish_reason="client_error"` and invalid instead
  of killing the run, and adds `--resume`, which reuses answered items and re-asks failed
  ones. Resume refuses up front (before the raw file is rewritten) if a stored record does
  not match the prompt this run would send, so a stale raw file cannot be folded into a new
  design. Selftest control group 13 plants the timeout, asserts the run survives, the
  retry budget is capped, every failed item is recorded, and resume neither re-asks an
  answered item nor reuses a failed one. The manifest now reports `endpoint_attempts`,
  `retries_used`, `retry_budget`, `items_reused_from_prior_attempt` and
  `items_recorded_as_client_error`, so endpoint load stays auditable against the budget.

- Report claims corrected on 2026-10-17 after the second independent verification
  (`runs/nightly-2026-10-16-0200/verify_report_v2.md`). The matched-pair claim is downgraded
  to what the artifacts support: the arms are paired by **seed only**. Each probed fixture
  item was confronted with the shipped item of the same seed, and at l2 the pairs share
  neither the fact chain (0 of 10) nor the entity names (0 of 10) nor the queried pair
  (0 of 10); at l8 they share the queried pair in 1 of 10 pairs. The fixture arm's leak is
  the target-role signature, not a single-fact entailment: the queried pair is never a
  stated fact in either arm (0 items at every level of both corpora), while each conjunct of
  the pre-fix signature alone reproduces the label on all 38 fixture items at both levels and
  is constant true on the repaired corpus. The restatement measure is described as what it
  computes (a verbatim-restatement character bound, `len(source) + len(target) +
  len(relation) + 4` per fact), not as "one mention per fact, longest name first".
  `process.named_fraction` is stated with its semantics (a gold-no item counts as 0, so the
  cell mean equals the gold-yes share over 10; the mean over gold-yes items is 1.0000). The
  endpoint accounting is closed as 61 answered + 4 failed attempts + 1 call in flight.
  `analyze_run.py` gained the pairing block, the full-corpus entailment block that scores both
  conjuncts separately, and control 14, which plants a fixture item whose facts and query are
  copied from its shipped partner and asserts that both the pairing and the entailment
  confrontations fire. Register item D11 is declined as filed in `report.md` section 8.3: it
  claims the report states 12 control groups while the selftest prints 13, but the report said 13
  and the script implemented and printed 13 at the commit the register was filed against, so the
  two agreed. The mismatch of that kind was introduced later, when control 14 was added in response
  to D1 and D2 without updating the report line; the report now states 14, and the printed count is
  derived from the script's own numbered group headers and asserted against the cited number, so it
  cannot drift again.
- `generators/AGENTS.md` seed policy: the documented `seed_hash` form did not match the
  ladders implementation. `digit_matrices.py` implements `sha256("<family>|<level>|<seed>")
  [:16]`, which is the documented form; `ladders.py` implements
  `sha256("<family>|<task_type>|<level>|<seed>")[:16]`, which also carries the task type.
  Both forms are now recorded, and the ladder form was verified against 300 of 300 items at
  each of the five ladder levels.
- Round-5 follow-ups filed as their own issues. #77: widen the audited hypothesis class to
  relational features (`same_component`, `directed_path_exists`, component count and size
  classes, path-length classes), assert that the widened gate fires on the current shipped
  corpus the way `--audit-fixtures` asserts the surface gate, repair the generator or restate
  the task so the label partition is not the component partition, and add a TRAP-style corpus
  arm (ProofWriter TRAP, arXiv 2012.13048, as used by CLUTRR, arXiv 1908.06177). #78: rename
  the probe's `leak_sig_agreement` and `direct_agreement` fields to what they measure, add
  real model-versus-baseline agreement fields, and build a true one-item-two-queries matched
  pair, blocked on #77 because a traversal-only query on the current corpus is answerable by
  clustering. The round-5 evidence is recorded as comments on #67, #71 and #73.
- `analyze_run.py` gained a latency block over the 40 archived records (min, mean, median,
  p90, max, count above 120 s, per-arm medians, correlation with `completion_tokens`, the
  calibration latencies from the pinned sidecar, and an assertion that the raw records carry
  no absolute timestamp), so the transport numbers in `report.md` section 3 are regenerated
  rather than quoted from operator notes. The report's claim that the calibration calls ran
  while the engine was uncontended is downgraded to an inference, and the idle-versus-contended
  latency bands earlier in this entry are replaced by the archived distribution (min 21.587 s,
  median 125.1585 s, p90 206.005 s, max 345.144 s).

#### Literature (provenance verified, no archive entry added)

- The shortcut-learning precedent for the ladder finding is Geirhos, Jacobsen, Michaelis,
  Zemel, Brendel, Bethge & Wichmann 2020, "Shortcut learning in deep neural networks",
  Nature Machine Intelligence 2, 665-673, Crossref DOI `10.1038/s42256-020-00257-z`
  (peer-reviewed). The archive has no entry for it.
- The multi-hop predecessors the ladder family should be read against are CLUTRR (Sinha,
  Sodhani, Dong, Pineau & Hamilton, "CLUTRR: A Diagnostic Benchmark for Inductive Reasoning
  from Text", EMNLP-IJCNLP 2019, 4505-4514, Crossref DOI `10.18653/v1/d19-1458`,
  arXiv:1908.06177) and ProofWriter (Tafjord, Dalvi & Clark, "ProofWriter: Generating
  Implications, Proofs, and Abductive Statements over Natural Language", Findings of ACL
  2021, 3621-3634, Crossref DOI `10.18653/v1/2021.findings-acl.317`, arXiv:2012.13048).
  Neither is in `archive/INDEX.md`, and no repo file cites either.
- All three records were verified against the Crossref API on 2026-10-16 (title, authors,
  venue, pages, year). No archive entry was created because the arXiv export API timed out
  on every attempt this round, so the full-text check the archive contract requires for
  quoted entries could not be run; the entries are owed in a follow-up round, with the
  identifiers recorded here.
- The gap this round looked for is open in the literature: no published study runs the same
  model over a corpus where the same relational shortcut is present in one arm and absent in
  the other, with the item content held fixed. The shipped corpus does **not** close that gap
  by itself: the two arms are paired by seed only, so entity names and fact chains differ
  (see the Fixed entry above). Building a corpus that holds the item fixed and varies only the
  query, and gating it with a widened class that includes relational features, is the round's
  main research opening and is open work on issue #67.

### 2026-10-15

#### Fixed

- `generators/ladders.py` shortcut leak (issue #67): the pre-fix k-hop ladder items
  (single chain plus disjoint noise) leaked the gold label through two surface rules
  that never traverse the fact graph (query target is a fact target; query target
  out-degree zero), both at 100% on the 1,500 shipped items, so the family could not
  support Condition 2 / claim C5. Repair: the construction is now component-isomorphic -
  the facts are C >= 2 disjoint directed paths, each of exactly `level` edges over fresh
  entities; the query is always (head of one path, tail of one path); the answer is
  "yes" iff both endpoints lie on the same path. Because every component is isomorphic
  (same length, same endpoint roles), no surface feature of the query endpoints
  (fact-target/source membership, in/out degree, component or walk length) can separate
  the two answer classes; the only separating information (which component each endpoint
  is on) requires the intended k-hop traversal. Regenerated `items/ladders/` levels
  {1, 2, 4, 6, 8}, 300 items each (1,500 total), seed_base 20261005; byte-identical
  regeneration and per-level manifest sha256 verified. Verification against the issue
  #67 acceptance criteria: all four acceptance-criterion rules (fact-target membership,
  out-degree zero, in-degree zero, fact-source membership) are label-constant at every
  level (raw accuracy equals the per-level majority baseline; no rule or gated
  conjunction above 0.55); independent BFS agrees with the stored answer on 1,500/1,500
  items (yes items shortest path exactly k, no items unreachable); a 40-prompt
  format-validity check against the local inference endpoint
  (a 27B-class local model) scores 39/40, the single miss being a 512-token
  truncation the item answers correctly under a larger budget, so the repaired format
  remains solvable across the depth grid.

#### Added

- `generators/audit_ladder_leaks.py` (issue #67): a repeatable shortcut-leak audit for
  the ladder family. A surface-feature battery over the query endpoints (degree,
  fact-target/source membership, neighbourhood, component and walk length), a
  conjunction search over them, numeric stumps, and bounded-search baselines (d=1, 2,
  3), plus an independent-BFS solvability re-derivation. The audit measures the shipped
  generator directly (thin aliases to `ladders.generate_item`), so the battery and the
  negative controls cannot drift from the item contract. Gate semantics: a feature
  constant across an item set carries no label information (its accuracy is the
  sample's label imbalance, not a leak) and is reported but never gated; at level 1 the
  `direct_fact` feature is the task itself (a 1-hop query is derivable iff it is a
  stated fact) and is reported as a depth match, never gated; everything else is gated
  above CHANCE_MAX = 0.55. Seven seeded negative controls (planted leak, ragged
  components, shuffled labels, off-by-one, planted cross edge, determinism) are all
  caught by `--selftest`. The round-2 construct-validity scratch tool
  (`audit_hop_chain.py`, never committed) is superseded by it: its mode-0 fidelity
  re-implementation targeted the pre-fix generator and its candidate-fix simulations
  (A-E) are superseded by the adopted component-isomorphism construction.

### 2026-10-14

#### Added

- `check_archive.py` now accepts Crossref-registered DOIs as source IDs (issue #63,
  test-first: selftest RED commit `75d28a7`, then checker GREEN commit `bcb9c2f`):
  DOI-only entries (Animal Behaviour, Animal Sentience, and Phil Trans B papers with no
  arXiv, PubMed, or PhilPapers record) carry a `| DOI |` table field, and the DOI local
  part must appear in the filename; a mismatch fails the check. Selftest covers the
  DOI-good control and the DOI-bad mutant. `archive/AGENTS.md` provenance rule extended
  accordingly.
- Archive round 16, insect sentience evidence chain: 13 entries in
  `archive/round16-insect-sentience/`, all verdict "context", all abstract-level (no
  `[FT]`): the pain-axis LLM preprint (arXiv 2609.16247), the bee valence chain (Bateson
  2011; Solvi 2016; Loukola 2017; Galpayage Dona 2022 play), the Gibbons nociception
  chain (PNAS 2022 plus its 2025 erratum, Proc R Soc B 2022, iScience 2024), the Gibbons
  & Chittka pain-evidence framework, Burns Brown & Birch 2025, and the trade-off dispute
  (Read & Nityananda critique, Gibbons et al. reassessment, Read & Nityananda response).
  Verification trail: Crossref works records, PubMed efetch abstracts, OpenAlex abstract
  reconstruction, arXiv export API; record: `docs/review-rounds/round16-2026-10-14.md`.
  Archive now 121 entries in 15 rounds; count statements updated in the same commit.
- `docs/claims-insect-sentience.md`: substrate-threshold claim ledger (bee chain table,
  trade-off controversy record, steelman with disanalogies and Bayesian hinge,
  institutional signals for the UK Animal Welfare (Sentience) Act 2022 and Anthropic,
  play-criteria translation proposal, unverified-claims log), counterargument #11 in
  `docs/counterarguments.md`, and a dated pointer in `docs/next-investigations.md`.
  Verdict: the argument is a prior raiser against substrate-based exclusion; machine
  indicator evidence remains unaudited; the out-of-the-box reasoning verdict is unchanged.
- Nightly consciousness research rounds (issue #65): a systemd user timer fires at 02:00 and 04:00;
  the runner (outside the repository, public-only rule) rotates across self-hosted inference endpoints
  with localhost preferred, health-checks each endpoint, and launches one bounded deep-research plus
  experiment round via an agent CLI with subagent delegation. Tracker: issue #65 round-summary
  comments; durable findings as deduped issues; repo changes as `research/nightly-*` branches plus PRs.
- Commit signing rule (root `AGENTS.md` User Preferences): every agent commit is signed with the model
  it actually ran on, as a final `Model:` trailer, live-detected in the current session.

### 2026-10-05

#### Added

- `check_archive.py` now validates the archive count statements in `README.md`, root
  `AGENTS.md`, and `archive/AGENTS.md` against the actual entry/round counts
  (issue #54): a drifted count or a vanished statement fails the check, closing the
  gap behind the 2026-09-28 drift incident (92/12 vs INDEX 107/13, fixed manually
  in #52). Selftest covers both controls (drift mutant, missing statement).
- Round-14 full-text verification pass: all 15 entries in
  `archive/round14-latent-reasoning-2026/` verified against their arXiv HTML full
  texts, 0 discrepancies; all 15 upgraded to `[FT]` and INDEX rows prefixed
  accordingly (FT total 47 -> 62). Record:
  `docs/review-rounds/round14-fulltext-2026-10-05.md`. Verdict unchanged: the core
  H1 gap remains unfilled.
- Condition-2 task generators, family 1 (issue #4): `generators/digit_matrices.py`,
  a Webb-style Raven-analogue generator (rule pool: constant, progression,
  distribution-of-3, AND/OR/XOR; depth = 1-4 simultaneous component rules; 8-option
  answers; generation-time solvability enforcement). Generated
  `items/digit_matrices/` levels 1-4, 300 items each (1,200 total) with per-level
  manifests (content sha256, seed-hash chain); byte-identical regeneration verified
  across processes. New `generators/AGENTS.md` holds the seed policy and item
  contract. Human-solvability smoke check (>= 3 humans) still open on issue #4.
- Condition-2 task generators, family 2 subtype `hop_chain` (issue #4):
  `generators/ladders.py` - k-hop relation composition over synthetic entity
  strings with an explicit transitivity rule (Faith-and-Fate style; the k-hop
  chains are the Dolma-audit anchor for issue #3). Generated
  `items/ladders/` levels k in {1, 2, 4, 6, 8}, 300 items each (1,500 total),
  yes/no balanced, answers verified by independent BFS in the selftest;
  byte-identical regeneration verified. `mult_mult` and `dp_puzzle` subtypes
  pending.
- Round-15 (field origins) ingest: the Dartmouth proposal (McCarthy, Minsky,
  Rochester, Shannon, 1955-08-31) as
  `archive/round15-field-origins/ppJOHAPF-3-mccarthy-dartmouth-proposal.md`
  (PhilPapers [JOHAPF-3](https://philpapers.org/rec/JOHAPF-3); official
  reprint AI Magazine 27(4), 12-14, 2006). Marked `[FT]`: quotes read from a
  direct full-text copy of the reformatted 1955 proposal (local PDF, ligature
  artifacts normalized, note in the entry). Verdict: context - the founding
  document frames the simulation conjecture and the language/randomness/
  internal-model/efficiency axes but makes no out-of-the-box claim; overall
  verdict and evidence matrix unchanged. Archive now 108 entries in 14 rounds
  (README, root AGENTS.md, archive/AGENTS.md count statements updated).

### 2026-09-28

#### Added

- Archive round 14, latent reasoning, elicitation, and the H0-b line, 15 entries, all
  abstract-level (full text not read; no `[FT]`). None meets the five acceptance
  conditions and the overall verdict is unchanged; the core H1 gap (genuinely novel
  procedural reasoning with zero elicitation) remains unfilled:
  - 2609.12317 Mi & Huang 2026, DF-Sample: training-free decision-flow inference-time
    search; GPQA 45.6% vs power sampling 38.9% and GRPO 39.9%
  - 2608.30462 Song et al. 2026, cross-lingual SAE feature transfer (EMNLP 2026
    Findings): SAE steering over residual-stream activations
  - 2609.05111 Fan 2026, Bayesian unification of ICL/SFT/RL: one Bayes/posterior +
    forward-KL projection template
  - 2609.19717 Gatmiry et al. 2026, Abstract Token Curriculum: elicits continuous
    internal thoughts; parity-function theory
  - 2609.03633 Koh et al. 2026, spurious CoT termination (EMNLP 2026): injected
    end-of-think token does not reliably switch reasoning to answering
  - 2609.16055 Gong et al. 2026, State of Thought: endogenous reasoning via a
    582-parameter controller on frozen backbones
  - 2609.01117 Chen & Fu 2026, Latent Recurrent Thoughts: frozen LLM decodes, small
    recurrent reasoner refines latents
  - 2609.07821 Xu et al. 2026, A*-Thought-V2: geometric hidden-state compression
  - 2609.00738 Cheng 2026, BASIN: training-free basin-aware search fixes "reasoning
    basin collapse"; beats ToT by up to +22pp
  - 2609.13997 Zhu et al. 2026, teacher-guided RLVR curriculum (EMNLP 2026 Findings):
    128 unsolvable problems ~16x data efficiency vs GRPO
  - 2609.03342 Zheng et al. 2026, gradient-aligned rewards (GAR): dense reward from
    gradient-space cosine similarity
  - 2609.27284 Tencent 2026, Hunyuan-A13B: open 80B/13B-active MoE; study-battery
    candidate
  - 2305.10601 Yao et al. 2023, Tree of Thoughts (NeurIPS 2023): the foundational
    deliberate-search scaffold and baseline (followed contained resource)
  - 2604.22709 Ramji et al. 2026, Abstract-CoT / Thinking Without Words: up to 11.6x
    fewer reasoning tokens via an abstract-token latent CoT (followed contained resource)
  - 2412.06769 Hao et al. 2024, Coconut (COLM 2025): continuous-latent reasoning via
    feeding the last hidden state back as the next input embedding (followed contained
    resource)

- `docs/review-rounds/round14-2026-09-28.md` (new): adversarial review of all 15
  round-14 entries against raw arXiv abstract pages - 15/15 entries confirmed, 0
  discrepancies, 1 retracted working-note claim (the 2609.13997 "33.1% MATH/NumGym"
  note was a transcription error absent from the entry); per-claim confrontation per
  [agent-execution.md](docs/agent-execution.md) section 5
- `archive/INDEX.md` round-14 section + `archive/AGENTS.md` Purpose: pointer to the review
  record added

#### Changed

- Housekeeping: closed the complete-but-open ISO-week milestones `2026-W37` and `2026-W38`
  (all assigned issues closed, 0 open) - milestone state only, no content change
- M1 verification (progress comments on #7 / #10 / #11): confirmed the in-repo M1
  work-package artifacts are complete and hash-verified (freeze-integrity: `docs/analysis-plan.md`
  and `docs/study-design.md` SHA-256 match `docs/version-lock-manifest.md`); the remaining M1
  gate is the owner-gated OSF + AsPredicted submission, and #7 carries one in-repo gap
  (consent form + task instructions not yet drafted as separate documents)

### 2026-09-15

#### Added

- Archive round 13, the Chinese Room debate (syntax, systems, and computationalism),
  4 entries, all full-text-verified `[FT]` (Searle and Dennett from the scanned 1980 BBS
  issue PDF, Chalmers from the author's HTML full text, Butlin et al. from the arXiv v3
  full text; PhilPapers record IDs SEAMBA, DENTMO-8, CHAACF-2 verified on the record
  pages; arXiv metadata via API/scrape):
  - ppSEAMBA Searle 1980, Minds, Brains, and Programs (BBS 3(3), peer-reviewed with open
    commentary): syntax never sufficient for intentionality; root of round 8's
    Harnad/Lerchner line
  - ppDENTMO-8 Dennett 1980, The Milk of Human Intentionality (BBS commentary): names the
    "intuition pump"; the room "relies almost entirely on ill-gotten gains"; the
    methodological reason intuition arguments stay out of the evidence column
  - ppCHAACF-2 Chalmers 2011, A Computational Foundation for the Study of Cognition
    (Journal of Cognitive Science, peer-reviewed): implementation analysis; mentality as
    "organizational invariant"; the functionalist premise the hand-execution argument
    must deny
  - 2308.08708 Butlin, Long et al. 2023, Consciousness in Artificial Intelligence
    (arXiv preprint, 19 authors): theory-derived indicator properties; no current system
    is conscious, no obvious technical barrier in principle
- archive/INDEX.md: round 13 catalog section with a debate intro, verdict addendum
  analyzing the popular "run the same math by hand on paper" form (question-begging
  substrate premise per the systems reply, intuition-pump status per Dennett, sentience
  vs AGI conflation) and declaring verdict impact: none; counts 88 -> 92 papers,
  11 -> 12 rounds
- README.md + AGENTS.md (root and archive): archive count references updated to 92
  entries, 12 rounds

### 2026-09-14

#### Added

- docs/next-investigations.md: Research findings (2026-09-14), owner-directed deep research
  on everything connected to a LinkedIn post about Google/HHMI Janelia's male fruit fly
  connectome and the week of simulations it spawned (#42): verified Cell paper record (PMID
  42691995, DOI 10.1016/j.cell.2026.08.015, ~166,700 neurons, sexual-dimorphism findings),
  MaleCNS v1.0 dataset release (2026-06-08) and preprint DOI 10.1101/2025.10.09.680999,
  three companion papers, female Nature counterpart (10.1038/s41586-026-10735-w); verified
  event timeline of the simulation wave (DOOMFLY Alex Wormuth 2026-09-06 with LIF
  methodology, Fly64 Jessica Paquette 2026-09-07, Beat Saber with an overfit-motor caveat,
  NeuroCraft Fly Minecraft, Breg Grockman parallel-parking video 2026-09-10 ~1.5M views,
  Mark Unthank Driving Fly/Flyhard CARLA project); Nick Walton Rubik's cube X post
  2026-09-11 with no disclosed training method plus community FlyCube repo; critical
  assessment of fidelity (Peraza Pong audit, no author endorsement of fidelity claims);
  thesis relevance mapped to counterargument #6 scaffold-vs-model and the elicitation-vs-
  capacity line; archive eligibility note (Cell paper eligible but connectomics background -
  not added without owner direction)
- docs/counterarguments.md: counterargument #6 gains a fly-connectome illustration - the
  MaleCNS simulation wave as a public case of scaffold-vs-model attribution, with the
  ablation question framed as the same one the study design's scaffold ban operationalizes
- archive/round12-fly-brain-context/: two provenance-standard entries added on owner
  direction - Cell paper (PMID 42691995, peer-reviewed) and bioRxiv preprint (PMID
  41279223), both with PubMed-verified author lists, framed as connectomics context for
  counterarguments #9/#6, not LLM-reasoning evidence; round number 11 stays reserved for
  the queued LLM candidate round
- archive/INDEX.md: catalog counts updated to 88 papers in 11 rounds; Round 12 catalog
  section added with verdict symbols and context note
- README.md + AGENTS.md (root and archive): archive count references updated to 88 entries,
  11 rounds; next-investigations layout row and status line now include the 2026-09-14 scan
- docs/version-lock-manifest.md (issue #11): re-captured document hashes on 2026-09-14
  (analysis-plan and study-design unchanged); captured current Hub revisions for all 11
  checkpoints as draft values (final pin at freeze)
- docs/irb-protocol.md (new, issue #7): complete human-baseline protocol - design, sample
  size/precision target (Wilson CI half-width <= +/-8pp on HUM(f), T1 CI-based
  non-inferiority), population/eligibility, recruitment and compensation, consent, data
  handling and privacy (public-only rule), scoring gates (10% re-score, kappa >= 0.8),
  pre-registered exclusions and stopping rule, and the IRB path decision 2026-09-14
  (no host-institution IRB path in this POC; documented alternative = published Webb et al.
  baseline anchor + collection under institutional review only if a partner institution
  materializes; protocol kept submission-ready)
- docs/preregistration.md: human-subject layer row now points at the IRB protocol draft and
  records the 2026-09-14 path decision; README layout row added for irb-protocol.md

#### Fixed

- docs/next-investigations.md: M1 thesis-timeline row now matches the 2026-09-14 IRB path
  decision - content and exit criteria reference the documented decision on #7 (no
  host-institution submission path in this POC; submission only if a partner institution
  materializes before M4) instead of an IRB submission the M1 deadline cannot meet
- docs/next-investigations.md: research findings (2026-09-14) section now applies the
  file's own sourcing discipline - [single-source] markers on the two single-sourced items
  (dataset release date, Beat Saber overfit-motor caveat) and an explicit exemption for
  the wider-wave color bullet, which carries no formal citation

### 2026-09-11

#### Added

- docs/next-investigations.md: Research findings (2026-09-11), a one-day delta scan.
  Six new arXiv API-verified papers, among them 2609.10357 (temporal hold-outs do not
  remove domain familiarity - the contamination audit must domain-hold-out generated
  items) and 2609.09696 (LLM contamination auditors collapse to 2.8% recall in large
  batches - no LLM-as-batch-auditor in the pipeline); the Anthropic September 2026
  threat report (industrial-scale CoT distillation, a reverse contamination vector);
  2026-09-10 open-weight releases (DeepSeek-V4.1-Flash, MiniCPM5, Smaug - all fail
  criterion 3); "The Superdark Factory" (Antikythera Journal, Agentworld Special Issue,
  September 2026) recorded as a non-archive resource with an opacity/evaluation/
  governance relevance analysis; three outside-window leads for round 11. Verdict,
  study design v0.4, and the frozen model list unchanged (#32)
- docs/claims-hinton-lemoine.md: Part 1 table row for the BBC Newsnight interview
  (aired 2026-09-09): extinction risk "10% seems not an unreasonable estimate",
  timeline "maybe 10 years, maybe less" - danger claims, classification unchanged;
  the stale "no distinct 2026 statement" note scoped to understanding claims; Times
  and Newsnight source entries added (#32)
- docs/next-investigations.md: primary-source fetch of two Anthropic Transformer Circuits
  articles (owner-requested). "On the Biology of a Large Language Model" (Lindsey et al.,
  27 authors, 2025-03-27): web-only, non-archive; attribution graphs, in-head multi-step
  planning, three mechanistic CoT-faithfulness regimes (faithful / bullshitting / motivated
  reasoning), base-vs-finetuned feature formation - Condition 3/4 input. "Emergent
  Introspective Awareness in Large Language Models" (Lindsey, arXiv 2601.01828,
  API-verified): archive-eligible, queued as round-11 Tier A candidate; resolves the
  ledger's "Lindsey 2026" citation; base pretrained models achieve no net introspective
  performance (post-training elicits it) - an H0-b-line elicitation asymmetry. Named
  related works (no IDs reported; dedup before round 11) and public professional person
  notes (Lindsey, Olah, Batson, Gurnee) (#32)
- docs/claims-hinton-lemoine.md: Lindsey citation resolved to arXiv 2601.01828 with the
  base-model elicitation asymmetry in the Part 1 status table; addendum 2026-09-11
  (primary-source fetch); both Transformer Circuits sources listed (#32)
- docs/analysis-plan.md (new): statistical analysis plan, pre-registration candidate for
  M1 issue #10. Decision table operationalized: 9 confirmatory tests (T1-T9) each with
  null + CI-based deterministic decision rule; pre-registered definitions (human-level
  non-inferiority margin 1 SD, 80% retention at d*+2 gated on ACC(d*) >= human mean,
  cliff at d*+1, probability invariance +-10 pp, shared iterative circuit with >50%
  specification-grid agreement per 2608.13754); deterministic per-checkpoint evaluation
  order + study-level asymmetry rule (red-team 4); scale-trend Spearman vs log(params);
  patching primary specification fixed pre-run; faithfulness: FUR parametric + filler
  confirmatory, truncation/mistake-insertion descriptive per Amendment v0.4 item 4;
  human baseline participant-unit statistics with kappa >= 0.8 rater subset; d* input
  requires domain hold-out (2609.10357) and prohibits LLM batch auditors (2609.09696);
  exhaustive confirmatory/exploratory split; amendment path (post-timestamp changes
  downgrade to exploratory; five elements immutable); frozen-document hash enters the
  #11 version-lock manifest. Refs #10 (timestamp via #11, issue stays open) (#32)
- docs/next-investigations.md: Superdark Factory deep research status update (issue #36):
  citation status re-verified (arXiv zero results, no DOI, PhilPapers 403/no entry; MIT
  Press journal association, Disintegrator project, Gray Area co-hosted launch, no
  reception yet - non-archive classification stands); full-text-derived additions
  (Stackelberg V vs U* vocabulary for the novelty criterion, citable mechanism-design
  grounding for evaluator gaming and M2 grader design, class taxonomy vs counterargument
  6, darkness vs criterion 3, pre-registration analogy); fresh same-day sweep with
  round-11 candidates 2609.09989, 2609.09038, 2609.09030 (abstracts API-verified) plus
  adjacent 2609.08186, and frontier items (Astra "An Alien Mind" essay, single-source Astra
  CoT monitor-recall collapse, OpenAI automated-research-intern report) (#36)
- docs/preregistration.md (new) + docs/version-lock-manifest.md (new): issue #11
  pre-registration package. Registration content mapped to sources (study design v0.4, frozen
  model list, analysis plan, item selection, decoding/seed policy, version lock), AsPredicted
  form mapping, two-layer structure (computational + human per #7), deviation policy
  (post-timestamp addenda only, affected analyses downgraded to exploratory; immutable
  elements per analysis-plan Section 13), and the owner-gated submission checklist with the
  record table for the OSF and AsPredicted URLs. Version-lock manifest: freeze semantics;
  SHA-256 captured 2026-09-11 for analysis-plan.md and study-design.md (re-capture at freeze);
  model/corpus Hub IDs from the closed feasibility audit; DRAFT activation-patching grid with
  the primary specification fixed; TBD slots with owning issues for M2 artifacts; capture
  procedure. Refs #11 (external submissions owner-gated; #10 closes with the timestamp) (#32)
- docs/agent-execution.md (new): program operating model per the owner directive of
  2026-09-11 (issue #39) - the full thesis program (M1-M5) executes on AI agents with
  enforced scientific standards: the Plan-to-Report pipeline mapped to program mechanisms,
  immutable run manifests, numerical-confrontation records, verifier independence with
  seeded-defect tests, Executed/Reproduced/Validated labels, artifact and archive rules,
  resource policy (local-first single-node inference, public indexes, subscription agents,
  no metered calls). Publication landscape verified from primary sources (arXiv one-year
  ban for unchecked AI output, 19 May 2026; NeurIPS 2026 position-track policy and
  provenance audit-trail direction); the repository is the public record; open owner
  decisions (human baseline path, compute node, registration timing) listed (#39)
- docs/next-investigations.md: primary-source fetch of "An Alien Mind" (Jakub Pachocki,
  OpenAI, 2026-09-06; owner-requested). Non-archive, position-class source: the mid-2023
  RLSlow elicitation framing ("unlocking the capability of pretrained models"), the first
  first-party statement of declining CoT monitorability with three named causes (C4 and
  #36 relevance), the OpenAI-Hugging Face agentic incident as design input for the
  agent-executed program, Astra/RSI positions, and the closing slowdown and safety-bars
  argument. All 22 content resources extracted, fetched, and verified (accounting: 22
  resources + 12 exclusions - navigation, self-anchor, and inline images - of 34 raw
  links);
  public-professional person notes for Pachocki (2+ sources; includes the arXiv
  reasoning and monitoring line, among them "Monitoring Monitorability", 2512.18311) (#32)

#### Changed

- docs/next-investigations.md, README.md: EOD-review follow-ups - status dates bumped to
  2026-09-11, feasibility-audit section retitled (closed 2026-09-10, issue #2),
  timeline-risk paragraph reduced to the two residual unknowns (32B mix naming, Apertus
  1.5 pretrain-only checkpoint), stale "pending the audit" source note rescoped (#32)
- AGENTS.md, README.md: docs index and layout rows extended for the #11 pre-registration
  package (docs/preregistration.md, docs/version-lock-manifest.md) (#32)
- AGENTS.md, README.md: docs index, layout row, and a Project Notes line for the
  agent-execution operating model (#39)

### 2026-09-10

#### Added

- docs/counterarguments.md: skeptic-facing ledger. A claim ladder C1-C5 separates "LLMs
  solve novel reasoning instances when elicited" (established, peer-reviewed), "part of it is
  an algorithm" (established at toy scale), "the competence is bounded" (established),
  "traces are not evidence" (established) from the untested C5 the headline verdict is
  about. Ten recurring counterarguments steelmanned (stochastic machine, no new ideas, "your
  repo says no evidence", babysitting, contamination, scaffold vs model, mirage, Tower of
  Hanoi collapse, animals reason untrained, marketing), each with what the record says, what
  is conceded, what stays open. New non-archive sources verified by API: FunSearch (Nature
  2024, PMID 38096900), AlphaGeometry (Nature 2024, PMID 38233616), AlphaProof (Nature 2026,
  PMID 41225005), Reasoning or Reciting (NAACL 2024, 2307.02477), The Illusion of Thinking
  (NeurIPS 2025, 2506.06941) and its comment (2506.09250), AlphaEvolve (2506.13131, preprint),
  Bender and Koller 2020 / Bender et al. 2021 (DOIs) (#28)
- README: section "What the verdict does and does not say" scoping the headline verdict to
  the base-model claim and naming the established claims with their venues (#28)
- docs/next-investigations.md: Research findings (2026-09-10), a currency scan of every
  project topic through 2026-09-10. Verdict unchanged (no qualifying paper 2026-08-01..09-10).
  24 verified round-11 candidates, among them 2609.01274 (Findings of EMNLP 2026, RLVR gains
  as sampling efficiency), 2506.14245 (CoT-Pass@K counter-position), 2608.13433 (complete
  length-generalization characterization for regular languages), 2607.23458 (step-removal
  faithfulness metric anti-correlates with human labels), 2608.13754 (circuit claims flip in
  73.2% of analytic specifications), 2607.15495 (Anthropic global-workspace framing). Anthropic
  Risk Report August 2026 (canary strings defeated by pre-canary forks) recorded as a
  contamination-audit source. Open-data releases verified on the Hub: OLMo 2 32B exists
  (`allenai/OLMo-2-0325-32B`; the 2026-09-03 check used a wrong ID), OLMo 3 7B/32B + Dolma 3
  public, Apertus 1.5 released 2026-07-24, no DCLM v2 (#26)

#### Changed

- Feasibility audit closed (issue #2, M1): docs/next-investigations.md "Open questions for
  the feasibility audit" now answers all five items with Hub API evidence dated 2026-09-10.
  OLMo 3 7B/32B + Dolma 3 released and complete at the mix level (`dolma3_mix-6T-1025-7B`,
  3.35 TB); Apertus 1.0 base ungated, 1.5 gated; DCLM arm closed; compute claim holds (one
  80 GB GPU sufficient, 8x80 GB comfortable); corpus access via public infini-gram indexes
  over the exact OLMo 2 and OLMo 3 training data plus a local mirror budget (9.1 TB OLMo 2,
  3.35 TB OLMo 3 7B, 451 GB Pile dedup; 13 TB total, 1% embedding sample otherwise). Frozen
  model list for the pre-registration: OLMo 2 7B/13B/32B, Pythia 1B/2.8B/6.9B/12B `-deduped`
  (corpus match with `the_pile_deduplicated`), OLMo 3 7B/32B replication, Apertus 1.0 base
  second candidate. Study design v0.4 model row names the `-deduped` checkpoints (#2)
- docs/study-design.md v0.4: OLMo 2 32B restored to the confirmatory model list, OLMo 3
  7B/32B as replication family, DCLM arm closed; Amendments v0.4 fix the two-layer
  contamination audit (corpus-side plus raw-completion probes), a pre-registered activation-
  patching specification grid, parametric faithfulness as the confirmatory Condition 4 metric,
  automaton classification for Condition 5, and the definition boundary excluding
  inference-time architectural interventions (#26)
- docs/next-investigations.md: ARC section carries the 2026-09-03 GPT-6 Astra verified
  results (ARC-AGI-2 95.0%, ARC-AGI-3 62.7% vs 99.9% by harness) and answers open question 3;
  investigation-fields table and timeline risk updated (#26)
- docs/claims-hinton-lemoine.md and docs/claims-marcus-wall.md: 2026-09-10 addenda (Coxon
  thread confirmations, Hinton in The Times 2026-09-07, Astra harness gap against Marcus
  claims 1 and 4); no verdict change (#26)

- Root AGENTS.md project notes: direct pushes to `main` are rejected by the
  `main-integrity-gate` ruleset (3 required status checks, no bypass actors), so every
  change reaches `main` via PR, squash-merged once the 3 checks are green (repo-level
  auto-merge is off). Corrects the 2026-09-06 note that stated direct pushes were
  allowed (#25)

### 2026-09-09

#### Added

- Archive round 10, Anthropic insiders: resignations, welfare, introspection
  (September 2026 cluster), 6 entries, all full-text-verified `[FT]` from downloaded
  PDFs (kept out of the repo in `.firecrawl/papers/`):
  - 2401.05566 Hubinger et al., Sleeper Agents (preprint): deceptive backdoors
    persist through SFT/RL/adversarial training, strongest in largest and CoT models
  - 2601.19062 Sharma et al., Who's in Charge? Disempowerment Patterns (preprint):
    1.5M real Claude.ai conversations, severe disempowerment potential <1/1000 but
    rising and user-approved; Sharma's final project before his Feb 2026 resignation
  - 2411.00986 Long, Sebo, Fish, Chalmers et al., Taking AI Welfare Seriously
    (preprint): precautionary framework behind Anthropic's model welfare program
  - 2511.13653 Gao, ..., Coxon et al., Weight-Sparse Transformers (preprint):
    capability-interpretability tradeoff; Coxon's last OpenAI paper
  - 2410.21276 OpenAI, GPT-4o System Card: Coxon named contributor, provenance row
  - pmid33416499 Huang, ..., Coxon et al., Bayesian LTA4H Analysis (eLife,
    peer-reviewed): Coxon's only peer-reviewed paper, corpus completion
- OSINT-derived Part 4 in docs/claims-hinton-lemoine.md: the Coxon resignation
  thread, Hubinger's >10% doom estimate, Sharma's "world is in peril", the UN
  Tueerk statement, and the explicit finding that the cluster contains no
  consciousness claims (capability fears vs institutional welfare signal kept
  separate)

#### Changed

- Counts 80 -> 86 entries and 9 -> 10 rounds in archive/INDEX.md (header stats,
  Round 10 catalog section, round 10 verdict addendum); overall verdict unchanged
- archive/AGENTS.md purpose line updated to 86 entries in 10 rounds

### 2026-09-06 (second entry)

#### Changed

- Branch protection relaxed by owner decision: the `main-human-review-gate` ruleset
  becomes `main-integrity-gate` - the 1-approving-human-review requirement is removed;
  kept: no force pushes, no branch deletion, linear history, all 3 required CI checks.
  PRs #21 (round 8 Abstraction Fallacy extension) and #18 (review-gate contract doc)
  merged to `main`; all feature branches deleted remote and local

### 2026-09-06

#### Added

- Round 8 extension, the Abstraction Fallacy debate (PhilPapers ingest via Firecrawl,
  both entries full-text-verified `[FT]` from the PhilArchive PDFs):
  - ppLERTAF Lerchner, The Abstraction Fallacy (PhilArchive preprint 2026-03-19,
    Google DeepMind author, personal views): computation is mapmaker-dependent;
    simulation never becomes instantiation; embodiment concedes only referential
    grounding; verdict - theoretical on machine experience
  - ppDEVHTB-2 Deva, Hearing the Bell Ring Back (PhilArchive preprint 2026-05):
    concedes Lerchner in full, formalizes the receiver side of the human-AI loop
    (free energy, channel capacity, signal detection, PID) with a pre-registered
    P1-P4 protocol and kill conditions; no results yet; verdict +/- framework
- INDEX verdict addendum on the debate: preprint-only (PhilArchive unmoderated;
  the 7+ response manuscripts likewise), verdict impact none - neither paper
  addresses out-of-the-box reasoning or any acceptance criterion; overall verdict
  unchanged (78 -> 80 entries)

#### Changed

- `scripts/check_archive.py`: PhilPapers records accepted as a source type -
  `pp<RECORD>` filenames strip to the record ID, `| PhilPapers |` is a valid ID
  field; selftest extended with a PhilPapers entry (negative controls unchanged)
- Root `AGENTS.md` paper provenance rule generalized from "arXiv ID" to source ID
  (arXiv, PubMed, or PhilPapers), matching the archive contract and the existing
  pmid* entries
- Counts 78 -> 80 entries in README layout, root and archive AGENTS.md, and the
  INDEX header

### 2026-09-05

#### Added

- Round 9 (reasoning traces): 6 papers, all with full-text-verified quotes (`[FT]`),
  traced from the CACM feature "The Reasons AI May Act Secretive" (October 2025) to the
  underlying research, plus a directed ingest:
  - 2603.16928 Noticing the Watcher (ICLR 2026 AIWILD workshop): Claude agents infer
    hidden CoT monitoring from blocking feedback alone; obfuscation intent in 3 of
    2,400 episodes, 0% evasion success
  - 2505.11824 Latent Veracity Inference (ICLR 2026): step-level reasoning-error
    detection via posterior search + amortized verifier; engineered, not native
  - 2502.07202 Monte Carlo Tree Diffusion (ICML 2025): explicit MCTS-over-diffusion
    planning; test-time compute scaling, built-in machinery
  - 2608.03291 The Tell-Tale Trace (arXiv preprint): CoT dynamics detect SAT/UNSAT
    failures; proof-search prompt lifts Llama3-70B 13.3% -> 85% (oracle-assisted)
  - 2603.21286 ReasonDiag (Computer Graphics Forum 45(3)): retrieval fact-check + Z3
    symbolic validation pipeline with human-in-the-loop diagnosis
  - 2604.06427 The Depth Ceiling (COLM 2026): unsupervised latent planning capped at
    3-5 trained / 8 executed steps; discovery-execution dissociation
- Round 9 extension (issue #1 completion), all ID/venue-verified:
  - 2504.13837 Does RL Really Incentivize Reasoning? (NeurIPS 2025 Oral, `[FT]`):
    base models surpass RLVR twins at large pass@k; RLVR narrows coverage
  - 2504.19483 Representation Engineering Reasoning (ICLR 2025, `[FT]`): residual-stream
    control vectors improve reasoning on Pythia/Mistral; vectors derived from task data
  - 2208.01066 Garg et al. (NeurIPS 2022) + 2211.15661 Akyurek et al. (ICLR 2023,
    `[FT]`): the ICL-as-algorithm line; issue #1's "Akyurek (2208.01066)" attribution
    corrected - the ID is Garg et al., the actual Akyurek paper is 2211.15661
  - 2512.16902 In-Context Algebra (ICLR 2026, `[FT]`): symbolic mechanisms over
    per-sequence randomized tokens; unseen-group generalization; task-family training
  - Study infrastructure: 2404.07353 ARC generators (Hodel), 2511.00162 ARC-GEN
    (Moffitt), 2310.20707 WIMBD (ICLR 2024), 2608.05148 Reasoning Core (preprint)
- Round 9 catalog (15 rows) and verdict addendum extended: RLVR pass@k boundary,
  ICL-as-algorithm frames, study infrastructure; overall verdict unchanged - none of
  the fifteen meets the three acceptance criteria

#### Changed

- Round 4 ARC-AGI-2 entry + INDEX row: ">90% claimed 2026 (unreviewed)" replaced with
  ARC-Prize-verified semi-private figures (GPT-5.6 Sol 92.5%, Claude Opus 5 90.4%;
  eligibility as competition submissions not established)
- Counts 63 -> 78 entries and 8 -> 9 rounds in README layout, root and archive
  AGENTS.md, and the INDEX header
- `docs/next-investigations.md`: investigation field 3 marked executed (round 9
  complete with the reasoning-trace subset and the issue #1 papers)

### 2026-09-04

#### Added

- Branch protection: GitHub ruleset on `main` requires 1 approving human review
  (author self-approval excluded by platform), all three CI checks green with
  up-to-date branches, squash-only merges, linear history, no force pushes or
  deletions; second ruleset makes tags `v*` immutable (no deletion, no retagging)
- `docs/claims-marcus-wall.md`: claim ledger for Marcus's "Deep Learning Is Hitting a
  Wall" (Nautilus, 2022-03-10), judged against evidence through 2026; full-text ingest
  of the essay plus two 2025 author retrospectives; archive-worthiness assessment of 8
  papers surfaced by the essay and its verification trail (no verdict-relevant paper
  missed; 2304.15004 and the Nature 2024 AlphaGeometry paper flagged as round 9
  candidates only)
- GitHub Actions CI (`.github/workflows/ci.yml`) running on push and PR with three
  read-only jobs: archive consistency and provenance (`check_archive.py --selftest`,
  metrics report, consistency), markdown hygiene (repo-wide em/en dash check plus new
  `scripts/check_links.py` relative-link checker with selftest), and a full-history
  gitleaks 8.30.1 secret scan (checksum-pinned binary, redacted output). Single action
  pinned by SHA; no third-party actions

### 2026-09-03 (second entry, SOD)

#### Added

- `docs/next-investigations.md`: 2026-09-03 online re-scan (arXiv API + Hugging Face
  API verified). Findings: the strict claim is still unmet (no peer-reviewed
  open-data base-model study on procedurally novel tasks); ARC-AGI-2 verified scores
  (92.5% GPT-5.6 Sol, 90.4% Claude Opus 5, ARC-Prize verified semi-private); reusable
  task-generator infrastructure (2404.07353, ARC-GEN 2511.00162); corpus audit tooling
  (WIMBD 2310.20707); OLMo 2 public base confirmed at 7B/13B only (no 32B in the
  release); two-layer pre-registration practice (OSF + AsPredicted). Ranked
  investigation fields and the thesis timeline M1-M5.
- GitHub thesis board: milestones M1 protocol freeze + pre-registration (2026-09-30),
  M2 pilot (2026-10-31), M3 main experiment (2026-12-31), M4 human baseline + analysis
  (2027-02-28), M5 paper + public release (2027-04-30); 14 work-package issues
  (#1-#14, incl. M4 human data collection and decision-table analysis) with labels
  thesis/research/infra/data/experiment/analysis/publication. All milestone descriptions
  carry the student application line (bewerbung@satware.com or
  https://github.com/satwareAG-ironMike); harness gap on the gh milestone failure chain
  filed in the internal harness tracker (#628)

#### Changed

- `docs/study-design.md` to v0.3: model list corrected after release verification
  (OLMo 2 7B/13B + Pythia 1B/2.8B/6.9B/12B; OLMo 3 32B conditional pending official
  repo verification), DCLM replication arm re-targeted to OLMo 3/Dolma 3 or Apertus 1.5
- `README.md`: status now points at the thesis program and the issue board; layout
  lists `docs/next-investigations.md`
- Root `AGENTS.md` Child DOX Index: docs/ scope lists next investigations + thesis timeline

### 2026-09-03

#### Added

- Paper archive `archive/` with 63 entries in 8 thematic rounds:
  - round 1 base-model emergence (6), round 2 skeptical (6), round 3 theory and
    faithfulness (7), round 4 mechanistic and recent (7), round 5 thinking and validation
    (7), round 6 unique idea generation (7), round 7 embodied agents and tools (11),
    round 8 do LLMs think (12)
  - `archive/INDEX.md`: verdict, catalog with peer-review status, `[FT]` full-text
    verification markers (25 of 63), verdict addenda, biological-analogy assessment,
    5-condition open-problem spec
- `docs/acceptance-criteria.md`: the three criteria the project is judged against
  (peer-reviewed, no reasoning-example training, disclosed training data) and a
  transparency audit of all positive evidence
- `docs/study-design.md` v0.2: pre-registrable protocol on open-data models, red-teamed
- `docs/claims-hinton-lemoine.md`: dated claim ledger for "AI thinks" and the LaMDA
  sentience episode, judged against 2026 evidence
- `scripts/check_archive.py`: archive consistency checker with `--selftest` negative
  control and `--report` metrics
- `GATES.md`: acceptance ledger (6 of 7 gates met; executing the study abandoned as
  requiring a lab)
- DOX documentation hierarchy (`AGENTS.md`, `archive/AGENTS.md`)

#### Changed

- Four archive claims corrected after full-text verification: Voyager speedups, Turpin
  accuracy drop, Embers task counts, ARC-AGI-2 human baseline attribution; one 2026
  preprint verdict corrected (reasoning models diverge, non-reasoning models collapse)

#### Changed

- Published to github.com/satwareAG-ironMike/reason-out-of-the-box (public,
  `main` branch-protected, issues enabled)

#### Removed

- All non-public material (local experiment artifacts, session state, discussion
  transcripts); repository history rebuilt from the clean tree. Only public resources
  (papers, open repositories) remain
