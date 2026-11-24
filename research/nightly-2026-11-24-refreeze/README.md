# Panel re-freeze 2026-11-24 (issue #126, owner go: execute in W48)

## Question

#126 recorded that the 2048 truncation wall collapsed to zero on both classes
(round 49: 0/11 truncated, 33/36 dispatches landed at exactly 1,556 tokens), so the
archived panel's cap-bound selection premise no longer holds on the current builds.
The goal directs the re-freeze: re-verify the premise on the build actually serving,
and re-derive the cap-bound panel from the result.

## Method

- Instrument: `research/nightly-2026-11-05-0400/policy_knob_probe.py --probe`
  (the round-49 battery, byte-identical construction: 11 archived E = 192 panel
  items x modes A/C/D + 3 duplicate A self-agreement dispatches + 1 census health
  call = 36 dispatches, `max_tokens` 2048, temperature 0.0, one sample per item).
- Endpoint: a live flash-class build (the class the round-49 archive came from;
  #126's root cause is that the wall is a property of the serving build, not of
  model class or task).
- Artifacts: `raw.jsonl` (one record per dispatch: prompt, raw response, score),
  `gate.json` (the battery's decision table over this firing), `probe.log` (dispatch
  log), `summary.json` (the re-derivation tally: this is the decision artifact).

## Result (from `summary.json`)

- Mode A truncates **8/11** at 2048 (round 49 read 0/11); C 7/11, D 8/11.
- The #126 "premise void" finding is **false on the current build**: the wall is
  back. The cap still binds wherever the work is put - the same consequence
  `docs/next-investigations.md` (2026-11-12 research findings) already derived for
  the cap-bound panel.
- **Re-derived cap-bound panel (5 items, the dispatches that actually hit 2048 on
  the serving build):** S4-X (k = 8), S5-F (k = 12), S5-X (k = 12), S6-F (k = 16),
  S6-X (k = 16). The panel re-anchors to these under the 2048 cap with a
  current-build baseline; the archived 11-item panel is retired, not amended.

## How to reproduce

`python3 research/nightly-2026-11-05-0400/policy_knob_probe.py --probe` against a
flash-class endpoint (env: `NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`, `NIGHTLY_API_KEY`;
no endpoint value is written to any artifact). 36 dispatches + 1 health call.

## Evidence label

`Executed` (exploratory, n = 36 dispatches, one endpoint). The re-derivation is a
measurement, not a confirmatory verdict; it decides which panel the exploratory
rounds use, not a thesis claim.
