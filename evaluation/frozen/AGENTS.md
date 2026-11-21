# evaluation/frozen

## Purpose

The frozen judge for the claim in README.md: a BASE model (no instruction tuning, no RL, no
reasoning prompt) whose training corpus is public produces correct, unique solutions to
procedurally novel task instances beyond its measured trained depth. This directory is the
instrument. It decides; it does not explore. The open exploratory loop lives in `explore/`.

## Ownership

The owner alone merges anything here, and the freeze itself. After the merge the files here are
immutable except through `rule.json` `amendment_path` (a numbered addendum, owner-merged).
Agents prepare and score; agents never merge here, never amend a threshold, and never re-analysis
a run under different statistics.

## Local Contracts

- `rule.json` (`frozen-judge-rule-v1`, issue #194) is the single source of thresholds: effect (alpha 0.05,
  min gap 0.10, min n 300 confirmatory / 40 exploratory), trained depth (mastery 0.80, calibration
  n 40, calibration seed base 20260101, novel-band offsets 1-4), novelty (13-gram, clean-rate floor
  0.95 per cell, basis and measurability rules), baselines, delivery census, prompts, statistics,
  and the POSITIVE / NEGATIVE / OPEN gates with their machine-checkable numbers.
- `pins.json` (`frozen-judge-pins-v1`) is the only model set a verdict may use. Confirmatory:
  OLMo 2 and Pythia pins (hub revisions, `instruct/rl/reasoning_prompt` all false, each with its
  pinned smaller same-family partner). `olmo3-7b` is a secondary replication and never pools with
  OLMo 2. `apertus-8b` is confirmatory-eligible but corpus-capped. Any model outside this file,
  including every locally served Qwen-class build, is labelled `exploratory_only_model_class`.
- `verify.py` per-family verifiers, independent re-solvers, frozen prompt builders, the delivery
  census (`DELIVERY_STATES`), the trap gold-leak guard, and `--generate` for fresh-seed tasks.
- `novelty.py` novelty backends: `local_scan` (stdlib Aho-Corasick over `FROZEN_CORPUS_DIR`,
  capped by `FROZEN_CORPUS_MAX_BYTES`) plus inert `infinigram` and `olmotrace` HTTP adapters that
  only exist when `INFINIGRAM_BASE_URL` / `OLMOTRACE_BASE_URL` are set. A live corpus query is an
  owner-approved operation; CI never calls a live backend.
- `baselines.py` B1 corpus nearest-neighbour retrieval on the identical item surface, B2 random
  recombination off the audited public gold pool (`RECOMB_SEED_BASE` 20260202, pool provenance
  recorded per row), B3 the pinned smaller same-family checkpoint. `no_retrieval` is a delivered
  wrong arm, `not_evaluable` blocks the cell.
- `score.py` implements `rule.json` and nothing else: Wilson interval, exact two-sided McNemar,
  Holm-Bonferroni over the pooled confirmatory beyond-depth cell set. `--score` produces a
  checkpoint report (`checkpoint_status`, never a claim verdict); `--claim` is the only place
  POSITIVE / NEGITIVE / OPEN exists, and it recomputes every gate from the cell records it is
  given instead of trusting a cached gate field.
- `MANIFEST.json` records the sha256 of every file here, canonical single-line JSON.
  `scripts/check_frozen_integrity.py --check` is the gate; `--freeze` writes it and refuses to
  re-freeze silently over a disagreeing manifest.

## Work Guidance

- A cell answers `n` = dispatched count, never the answered count. A blocked baseline or an
  unmeasurable novelty is a blocker named in the report, never a win and never a negative.
- Novelty basis: a gold under 3 normalized tokens is judged on the item surface only
  (`basis=surface_only_short_gold`); the 13-gram path only runs on text with at least 13 tokens;
  the exact path is token-boundary to token-boundary.
- A configured-and-read corpus slice that matches nothing answers `clean`. An unconfigured backend
  answers `not_evaluable`, never `clean`.
- `d_hat` comes from the model's own calibration arm at the frozen calibration seed policy. The
  novel band is `level - d_hat` in {1, 2, 3, 4}. A calibration arm that delivered no answer at
  any level is a delivery failure, not a competence floor: trained depth is `not_evaluable`
  (`no_delivery_case`), the cells keep their `n`, they lose the beyond-depth reading, and no
  NEGATIVE branch can fire over them.
- A round that cannot run an arm says so in its ledger row and keeps the failure record. A timed
  out arm is never reported as a result.
- Nothing public here names a host, port, endpoint, model file path or serving build digest.
  Pins are hub names plus revisions.

## Verification

Local CI parity before any push in this subtree:

```
python3 evaluation/frozen/verify.py --selftest && python3 evaluation/frozen/verify.py
python3 evaluation/frozen/novelty.py --selftest && python3 evaluation/frozen/novelty.py
python3 evaluation/frozen/baselines.py --selftest && python3 evaluation/frozen/baselines.py
python3 evaluation/frozen/score.py --selftest
python3 scripts/check_frozen_integrity.py --selftest && python3 scripts/check_frozen_integrity.py --check
python3 scripts/check_frozen_owner_go.py --selftest && python3 scripts/check_frozen_owner_go.py --local
```

`check_frozen_owner_go.py --local` is advisory: preparing a change here is allowed. The enforcing
mode is `--pr N` in CI, which the owner wires (agents do not touch `.github`), and the label is
`owner-go`, set by the owner alone. `check_frozen_integrity.py --freeze` writes the manifest and
refuses to overwrite a manifest that already disagrees with the files unless `--confirm <reason>` is
given, in which case it prints the hash diff; a re-freeze is a recorded act, never a silent refresh.

Every selftest carries planted-slip negative controls: a changed frozen file, an unregistered
file, a gold left inside a prompt, an unconfigured corpus read as clean, a missing partner arm,
a cached gate field contradicting its cells, a fired branch below the evidence floor.

## Child DOX Index

No child directories.
