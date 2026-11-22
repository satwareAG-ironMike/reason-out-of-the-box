# Round 78: 2026-11-21 02:00 firing, pool slot 1/6, a flash-class local endpoint

Firing record for a round that dispatched nothing. No experiment ran, so no `raw.jsonl`,
no `summary.json` and no `measure.json` exist here, and the trace-exposure census (issue
#105) is absent for this endpoint this firing: any trace claim about this build class would
be unsupported by this directory.

## Directory naming

The runner log stamps this firing at 2026-11-21 02:00 with `round=78 slot=1/6`, while the
round identity handed to the agent carried 02:30. `research/nightly-2026-11-21-0200/`
already exists on `main` and holds the instrument that firing was staged to run (PR #184),
and a round directory is never reused, so this record opens `nightly-2026-11-21-0230` to
match its branch `research/nightly-2026-11-21-0230`. The 30 minute label drift between the
runner stamp and the agent identity is recorded here rather than resolved.

## Question (carried, unchanged)

Round 77 Next item 1 and issue #152: does the `own_content_selects` readout survive on the
flash build once arms X (own draft), C (whole foreign draft), B (answer field only) and F
(tokenization-aware filler) are matched on the endpoint's measured `prompt_tokens`? That is
the one missing cell of the {terminal, interior} x {flash, 27B} x {own, foreign} square,
since round 73 ran the flash interior ask under the whitespace-token match only.

## Method

The instrument for this cell was already merged: `research/nightly-2026-11-21-0200/cross_ask_r78.py`
with its frozen `research/nightly-2026-11-21-0200/gate.json` (rows V0-V3, C2, R2, X2, F1, P1,
H1, C1, S1, W2, M4, registered before any prompt). No new script was written and no gate was
frozen this firing. The firing was probed against that instrument instead of re-implementing
the panel.

## What the firing had (all verified in-firing)

1. `NIGHTLY_BASE_URL` was exported; `GET $NIGHTLY_BASE_URL/v1/models` returned no HTTP status
   at all (transport failure inside 25 s, curl code 000).
2. `NIGHTLY_MODEL_ID`, `NIGHTLY_MODEL_LABEL` and `NIGHTLY_PROVIDER_MODEL` were exported set
   but empty (length 0 each).
3. Because the script computes the build pin as sha256 of `NIGHTLY_MODEL_ID` truncated to 16
   hex, an empty id yields `e3b0c44298fc1c14`, the empty-string hash. The gate pins
   `26df9af5972ff312`, the 27B-class build of rounds 72, 75 and 77, so the freeze guard
   aborted the dispatch pass. Gate output, verbatim, captured at 04:22:

   ```text
   $ python3 cross_ask_r78.py --run
   refusing to dispatch: the serving build moved after the freeze
   exit=3
   ```

4. The staged gate also carries the *predecessor* firing's identity: `"firing":
   "2026-11-20 04:00"`, `"slot": "6/6"`, `"round": 78`. `research/nightly-2026-11-21-0400/
   gate.json` (PR #185, the 04:00 twin) carries the same pin and the same predecessor
   identity. A gate pinned to one build, staged a day ahead of a rotating firing, refuses by
   construction on five of six slots regardless of endpoint health.

## Verdict

No research result. The registered rows and the flash token-matched cell are untouched and
still owed. Nothing measured this firing licenses a claim about this build class, and the
refusal message this firing produced is not evidence about a model.

Two root causes, both instrument and runner side, filed after the round summary comment on
#65:

- an identity-empty slot: this family reads `NIGHTLY_MODEL_ID` both into the request body and
  into the digest pin, so a slot that exports no identity surfaces as a gate violation rather
  than as a transport error. Comment on issue #73 (the pre-grid health check contract), third
  instance after the 2026-11-19 02:00 and 2026-11-20 02:00 firings.
- a pre-staged gate pinning a build the rotation controls: issue #200.

## Budget and evidence labels

0 of the 40 prompt cap, 0 of the 12 scholarly API call cap, dispatch wall 0 s, 0 transport
retries. Evidence label **Executed** for the failure probe alone (one endpoint probe, one
gate refusal capture, exit 3, reproducible by running `--run` against an endpoint whose
`NIGHTLY_MODEL_ID` is empty). The research question is untested this firing. An arm that
could not run is not a result and nothing here is reported as one.
