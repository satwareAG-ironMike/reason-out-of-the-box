# Round 78: cross-ask family, tokenization-matched notes arms (exploratory)

Moved to the exploratory lane by owner objective 2026-11-21; was prepared as
`research/nightly-2026-11-21-0200` (instrument pin in `docs/version-lock-manifest.md`
Section 4a).

## Question

Does the own-content readout survive when the four arms are token-matched on the endpoint's
measured `prompt_tokens`? Round 75 ran the issue #152 foreign-scaffold arm C and shipped
`own_content_selects` (arm X 3 of 3, arm C 0 of 3, arm F 0 of 3) with the context-length
claim downgraded to `context_length_unmatched`: the notes arms were matched on whitespace
tokens, not on the endpoint's tokenization. This round runs the same four-arm panel with
that fix.

## Arms

- arm X: turn-1 answer field PLUS the item's own turn-1 non-report channel under the fixed
  notes label (the own draft).
- arm C: turn-1 answer field PLUS a draft of a DIFFERENT item, whole and uncut, under the
  same label (a donor chosen for prompt-token parity).
- arm F: turn-1 answer field PLUS a tokenization-aware filler tuned by at most two
  registered probes to sit within the P1 band of arm X's measured `prompt_tokens`.
- arm B: turn-1 answer field only.

## Gate

Registered rows frozen in `gate.json` before any prompt (issue #137 shape). The instrument
emitted the gate blob `add64e29e143104cb2afd8c1d05d125949bdac4a13c5f17447f301907c1c4602`
at `--freeze`; `raw.jsonl` records carry the same blob.

## Run

- Endpoint: `qwen38-flash-next` (public name only, self-hosted, no metered key).
- `--selftest`: 151 of 151 checks green.
- 29 records dispatched, one at a time (issue #73, #141).
- `--rescore`: exits 0, `summary.json` sha256 `53c18c0c27ac` (identical before and after).
- Primary verdict: `X2_tail_shortcut` = `selection_beyond_tail`, arm X delivered the draft
  tail 0 of 3.
- P1 prompt-token parity held on the C64 cell (X pt=3357, C pt=3358, F pt=3348; band 400,
  all above arm B's 1301).

## Scoring

The frozen judge (`evaluation/frozen/`, issue #194) scores this round's raw records. The
round is exploratory (`qwen38-flash-next` is an `exploratory_only_model_class` build); no
confirmatory cell is produced. `score.json` will be written at the first frozen-judge PR
merge (owner act 1 on #197).

## Ledger

`explore/LEDGER.md` row r78: `OPEN, exploratory`. Distance moved: confirms the trigger
alignment; does not move the beyond-depth gap.
