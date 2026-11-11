# Round 60 (2026-11-11 04:40): the ban on written intermediate names is inert on the answer channel (4.31 against 4.69 visible characters), converts one truncated `j = 32` cell into a byte-reproducible correct name, and leaves the per-hop bill at 36.64 tokens

Firing: 2026-11-11 04:40 (issue #65 timer, pool slot 2/6). Class: a flash-next-class local model
(the serving id is disclosed only in the commit `Model:` trailer; artifact digest
`4075b5949b2b0487`, the same digest round 55 recorded). No metered or hosted provider was used; no
search API other than OpenAlex record lookups was used. Status label: **Executed** (see Limits).

## Question

Registered before dispatch (schema `round60-gate-v1`, frozen in `gate.json`, stamped on every
record), blob:

`8aeb5ec66178de93f745228da063c37f4087ad44264bd7fb1ced97af11990344`

> On one load-floor ladder item, with the fact block fixed and only the step count `j` and the
> output permission moved, does banning the written traversal (a) collapse terminal-name accuracy,
> (b) preserve it at a token cost that still grows with depth, or (c) preserve it at flat cost?

Registered tiers, in order: `controls_invalid`, `ban_not_followed`, `no_ceiling_both_modes`,
`internalized_flat_cost`, `cost_migrated_to_hidden_channel`, `externalized_chain_required`,
`unresolved`. Cost line a-priori at 10 completion tokens per hop, one fifth of round 6's
80-tokens-per-hop law (issue #71).

## Why

Every depth number in this program comes from a free-writing instruction. Round 6 priced that
writing at about 80 tokens per hop; round 50 found accuracy never turns over while delivery does,
and could not separate missing computation from missing surfacing; round 55 delivered correct names
to `j = 32` and lost `j = 48` to non-delivery. Issue #71 asks for a named procedure that says which
resource is scarce, so this round withdraws the permission to write the chain.

## Arms, items and dispatch

Minimal pair, asserted byte-wise in the selftest: the ban prompt is the free prompt (round 55's
template, byte-identical) plus the 81-character clause `Do not write out any intermediate entity
name; answer with the single name only.` No equal-length neutral filler on the free arm.

Items: pinned load-floor items (`facts = 2k`, seed base 20261005), seeds 36261005 (L8), 52261033
(L16), 84261011 (L32A), 116261051 (L48). The `k = 48` fact block is certified fail-closed against
the archived yes/no prompt digest `068bc6a1fb0620fb` that rounds 51, 53 and 54 dispatched.

36 cells, 18 per arm: 24 name cells, 10 NONE-gold controls (eight `j = k+1` off-end, two path-tail
dead-end, one per arm), two byte-identical re-dispatch pairs (issue #100). Dispatch order was
re-ordered once before the freeze so the validity gates and the primary contrast ran first; the
re-freeze is the blob above. One health probe ran before the plan and is not experimental data.

| Measure | Result |
|---|---|
| Dispatched | 36 of 36, `not_dispatched` empty, 0 retries, 0 transport errors, wall 633.0 s |
| Registered tier | `controls_invalid` (flags `none_control_unresolved`, `trace_provenance_refused`) |
| NONE controls | 7 of 10 declared NONE, 0 named an entity, 3 non-deliveries at exactly 2,048 tokens |
| Name cells | 21 of 21 delivered names correct, 0 wrong, 3 undelivered (all at the cap) |
| Visible answer length | mean 4.31 chars free against 4.69 ban over the 26 in-band cells |
| Cost slope on L48 | +30.49 tokens/hop free, +36.64 ban (both inflated by cap-censored cells) |
| Self-agreement | 2 of 2 pairs byte-identical on name and tokens |
| Trace provenance | gap 0.00 on 3 undelivered records (gold 3/3, pseudo-gold 3/3), refused |
| Census (issue #105) | `reasoning_content` 36 of 36, `content` present 36 of 36 |

Matched deep pairs (delivered-correct): free 1 of 3, ban 2 of 3.

| `j` | free arm | ban arm |
|---|---|---|
| 8 (L48) | correct `trackst`, 1,096 tok | correct `trackst`, 263 tok |
| 16 (L48) | correct `flixm`, 883 tok | correct `flixm`, 1,221 tok |
| 32 (L48, 96 facts) | no delivery, truncated at 2,048 | correct `whesh`, 1,080 tok |
| 48 (L48) | no delivery, truncated at 2,048 | no delivery, truncated at 2,048 |
| 32 (L32A, 64 facts) | correct `sterk`, 951 tok | correct `sterk`, 1,102 tok |

## Findings

1. **The visible channel is already answer-only in both arms.** 4.31 against 4.69 characters: the
   model emits the bare name either way and the traversal runs in the `reasoning_content` field the
   serving stack exposes separately. The knob is bolted to a channel that spends nothing, so the
   registered tier order reports `controls_invalid` first and the inertness second; the distinction
   is only visible because the census was taken.
2. **One deep cell flips, and it flips repeatably within the firing.** At `j = 32` on the 96-fact
   item the free arm truncated at 2,048 with an empty answer and the ban arm delivered the correct
   name `whesh` at 1,080 tokens; the byte-identical re-dispatch returned the same name at the same
   1,080 tokens and the same 2,860 trace characters. Cross-firing and cross-class reproduction are
   owed.
3. **Withdrawing permission to write does not withdraw the per-hop bill.** The ban arm's cost grows
   at +36.64 tokens per hop against +30.49 free on the same item, and at `j = 8` and `j = 16` the
   ban arm is sometimes dearer. Both slopes include cells censored at the cap; stated, not corrected.
4. **Termination is cheap, traversal is not.** The path-tail dead-end control on the 96-fact item
   refused correctly at 1,002 tokens free and 130 ban, while the `j = 49` off-end controls on that
   item burned the whole budget in both arms and produced no answer. That is what invalidated the
   controls gate, and it is a controls-design gap, not a model error.
5. **The trace readout refuses itself for a stated reason.** Among the three undelivered name-gold
   records the gold terminal appears in 3 of 3 traces and the matched pseudo-gold in 3 of 3, so the
   provenance gap is 0.00: the trace restates the fact list, which contains both names. Round 50's
   0.5652 calibration was the same defect from the other side.
6. **Consequence for `d*`.** No ceiling on this family can be priced in visible-output tokens on
   this build; the boundary between `j = 32` and `j = 48` is a serving budget plus a shift in how
   that budget splits between channels. Issue #71's procedure has to name the channel it prices.

## Reproduce

```
python3 research/nightly-2026-11-11-0440/internalized_traversal_probe.py --selftest
python3 research/nightly-2026-11-11-0440/internalized_traversal_probe.py --dry-run
python3 research/nightly-2026-11-11-0440/internalized_traversal_probe.py --freeze-gate <dir>
python3 research/nightly-2026-11-11-0440/internalized_traversal_probe.py --run <dir> [--resume]
python3 research/nightly-2026-11-11-0440/internalized_traversal_probe.py --rescore <dir>
```

Endpoint read from `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`, `NIGHTLY_API_KEY`; never written. Model
referred to by digest only. Caps: 36 of the 40-prompt budget, `max_tokens` 2,048, temperature 0.

## Limits

`Executed`: single firing, one class, and the registered decision table refuses the firing on its
controls gate, so no row here is `Validated` and none is `Reproduced`. Small n per cell: the
`j = 32` difference is one item and one matched pair. The 81-character ban clause is itself a
treatment and the free arm carries no equal-length neutral filler, so a length confound is not
excluded. Cost slopes include cap-censored cells. The literature set behind this question is
verified at OpenAlex work-record level only (the arXiv export API returned 429 throughout the
window and no abstract was retrieved), so nothing from it is quoted here.

## Literature (record-level, OpenAlex; no abstract retrieved, nothing quoted)

Coconut, `arXiv:2412.06769` (Hao et al., 2024, preprint), trained continuous latent reasoning;
Chain of Draft, `arXiv:2502.18600` (Xu et al., 2025, preprint), shortening the written chain
without an accuracy cost; `arXiv:2505.05410` (Chen et al., 2025, preprint) and Turpin et al. 2023 on
unfaithful visible traces. Methodological import: score compliance and correctness separately and
never infer channel migration from the visible text.
