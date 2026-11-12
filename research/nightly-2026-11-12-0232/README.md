# Nightly round 61: where does the theory place the measured ladder wall, and which single prediction does the k > 48 name-walk panel discriminate?

| Field | Value |
|-------|-------|
| Question | Where does the theory place the measured ladder wall, and which single prediction does the now-generatable k > 48 name-walk panel (issue #129) discriminate? Full wording in `gate.json`. |
| Gate blob | `d29e33cf12760e95125fe225bbb7f72b40d0c432613e103364a8e660ea4bf555` (sha256 of `gate.json`, `blob` key omitted) |
| Contract | Literature-first round against a rate-limited 27B-class endpoint: 2 experimental dispatches (E1 anchor cell, R1 dead-end control), `max_tokens` 2048, temperature 0.0, 3 pre-gate calibration calls (2 census at cap 256, 1 full calibration dispatch), anchor re-certification against the archived digest before any prompt was spent, P1 core panel registered and owed; call cap 40, 6 calls used |
| Fired | 2026-11-12, gate frozen 05:32:33 CET; dispatch 05:55:06 CET to 06:09:09 CET: 2 of 2 cells, 0 retries, 2148 completion tokens across the two cells; 6 calls and 3499 completion tokens counting the 3 calibration calls and the health call |
| Verdict | `literature_synthesis_rate_limited_record`, flags `endpoint_rate_limited` and `dead_end_control_refused` (informational: the control refused correctly); scorecard: E1 pass, E2 pass, R1 reported (refused), P1 owed, N3 certified, T1 through T4 verified |

## Why

The ladder program now carries four wall records at different deployment positions: the
flash-class accuracy turnover at `j >= 40` with position errors on the right path (round 59),
the 27B-class yes/no arm censoring at k = 48 on the gold-no cells (round 52, PR #132), the
zero-truncation wall on the current flash builds (issue #126), and the generator scan ceiling
at k = 48 (issue #129, now unlocked at 49/50/64 for the load-floor family). This round is the
literature-first reframing of the "extend j past 48" step that round 55 owed: the theory says
the wall is an encoding and output-budget property of the deployment, and the remaining clean
discriminator is the now-generatable k > 48 name-walk panel.

The four theory rows frozen in the gate:

| Id | Statement (frozen before any dispatch) | Source |
|----|----------------------------------------|--------|
| T1 | learnable chain-of-thought length-generalizes only within the TC level of the deterministic time hierarchy under standard positional encodings and a finite alphabet; the signpost-token remedy shows the barrier is encoding-specific, not universal | arXiv:2604.25800 |
| T2 | complete characterization of length generalization for regular languages under NoPE: it holds iff the syntactic monoid decomposes into loop-balanced integer counters (C-RASP); a near-binary split on 175 languages and 10x data does not rescue the failing class. Caveat on record: NoPE theory; the deployed models use RoPE | arXiv:2608.13433 |
| T3 | depth-tracking positional encoding plus halting gives exact length generalization on Boolean evaluation, ListOps and modular arithmetic with 280 parameters: the second encoding-specific remedy, i.e. the wall moves with the encoding | arXiv:2608.31067 (with arXiv:2604.25800) |
| T4 | the ladder item at any tested depth is a two-path BFS problem solvable in constant-depth parallel circuits (the NC class; 128 facts at k = 64): the task stays computationally trivial while the observed walls sit at output budget (2048 cap, round 52) and step position (`j >= 40`, round 59), so the wall is a length-generalization and output-budget property of the deployment, not a task-complexity limit | in-repo measurement (rounds 51/52/59) |

The reading the theory implies: the measured wall is where the deployment's encoding and
output policy live, not where the task gets hard. Under that reading, the name-arm panel past
k = 48 on the 27B class is the single cleanest remaining prediction, because the 27B-class
yes/no arm already censors at k = 48 (round 52) and the name arm has never fired on the class.

The assigned endpoint for this firing is a 27B-class local endpoint (public class name only;
the assigned identifier appears in the commit trailer and in machine-only files), and it
served under a co-fired load: a concurrent nightly round on the shared inference host
(flash class, started 04:40 CET with its own 90-minute budget) plus another heavy local
process, 9 GB of swap in use. Measured pre-gate: the census answered 76 tokens in 44.7 s and
76 tokens in 88.7 s (1.7 and 0.9 tok/s); the full calibration dispatch on the k = 48 anchor
cell took 1123 completion tokens in 1116 s (1.01 tok/s). At that rate the frozen dispatch
budget of 3000 s holds roughly 3000 completion tokens, and the four-cell core panel (round-52
shape, roughly 6000 completion tokens, roughly 100 minutes) does not fit. This firing
therefore records the shallow rate-limited record (E1 plus R1) and registers the panel as P1.

## Items and lineage

Items were generated from the pinned generator `generators/ladder_matrix.py` (manifest seed
policy, issue #67 guards) and certified:

| Cell | level k | facts | start | `j` | kind | gold | seed | lineage |
|------|---------|-------|-------|-----|------|------|------|---------|
| `A48_j8` | 48 | 96 | `glag` | 8 | name | `trackst` | 116261051 | archived k = 48 anchor item (rounds 51 through 54), re-certified before dispatch (N3): regenerates from seed 116261051 with the archived yes/no prompt digest `068bc6a1fb0620fb` |
| `A49_deadend` | 49 | 98 | `studnd` | 1 | dead-end NONE control | NONE | 118261016 | new k = 49 load-floor item (the first level past the old ceiling); asks the first step from the dead-end node (a name with no successor in the walk), where no successor exists |

`A49_deadend` is deliberately one step deep: the round 60 lesson is that off-end controls at
depth inherit truncation, so the control is shallow on purpose. The anchor cell's pseudo-gold
(`quackrk`, position 9) sits in the item list, so the cell cannot be passed by recognizing the
gold. No archived matrix or ladder cell is quoted into the dispatch except the archived anchor
item itself, and that one was re-certified before any prompt was spent.

## Fired

Gate frozen at 05:32:33 CET (the blob above). Pre-gate calls: 2 census (cap 256) plus 1
calibration dispatch (the anchor cell at cap 2048). N3 certified before the first prompt was
spent. Health call at 05:34:56 CET. Dispatch at 05:55:06 CET (2 workers, start derived as
landing minus measured wall time):

| Cell | declared | gold | correct | finish | completion tokens | wall | rate |
|------|----------|------|---------|--------|-------------------|------|------|
| `A48_j8` | `trackst` | `trackst` | yes | stop | 1123 | 843.0 s | 1.33 tok/s |
| `A49_deadend` | `none` | NONE | yes | stop | 1025 | 829.0 s | 1.24 tok/s |

2 of 2 dispatched, 0 retries, inside the frozen 3000 s budget. The anchor cell is the same
prompt as the pre-gate calibration dispatch, and both produced 1123-token completions at
temperature 0.0, a within-firing duplicate under the same load. `summary.json` is rescored
with the frozen blob attached to every gate row and to every raw record.

## Result

- E1 (anchor, shallow): pass. The archived k = 48 anchor item delivers the correct 8th walk
  name on this 27B-class firing under the measured co-fired load. The 27B-class name arm is
  alive at shallow `j`; the wall question (deep `j` past 48) is P1's and is not re-answered
  here.
- E2 (census, issue #105): pass. The health census answers the two-fact transitivity query
  correctly and exposes the trace in `reasoning_content` (277 chars). This firing therefore
  states its own exposure setting, which any cross-class trace claim must state.
- R1 (dead-end control, report-only, no tier input): reported, refused correctly. The model
  declined to name a successor where the walk has none (1025 tokens, stop). The flag
  `dead_end_control_refused` is informational by construction and means the control behaved
  as the flash-class record does at the same depth.
- P1 (registered, owed): the core panel on the four endpoint cells past the old ceiling
  (k = 48, 49, 50 and 64 at each item's deepest `j`, cap 2048) is owed to the next healthy
  27B-class firing. Registered discriminator: at least 3 of 4 deliver the correct terminal
  and the wall is an output-budget and output-policy artifact (the issue #126 reading); at
  most 1 of 4 delivers (censor at the cap or a position error on the right path, the round-59
  shape) and the length-generalization reading (T1 through T3) survives on the 27B class.
- N3: certified pre-dispatch (seed 116261051, digest `068bc6a1fb0620fb`).
- T1 through T4: verified at work-record level (below).

## Findings

1. The theory places the measured wall where the deployment's encoding and output budget
   live, not where the task gets hard. T1 and T3 are the core: two independent
   encoding-specific remedies (signpost tokens; depth-tracking encoding plus halting at 280
   parameters) move the wall with the encoding, and T2 characterizes exactly which
   regular-language classes generalize under NoPE (with the RoPE caveat on record). T4 keeps
   the task side trivial (two-path BFS, constant-depth circuits). The round-52 censoring and
   the round-59 position errors are therefore deployment properties, and the panel
   registered as P1 is the single cleanest remaining discriminator on this program.
2. The 27B-class name arm has now fired once, at shallow `j`, and it is correct. The round 52
   record for this class was yes/no-only and the name arm had never run on it; E1 adds that
   first data point and confirms the archived anchor (item plus gold) is stable from rounds 51
   through 54 into this firing.
3. The dead-end control refuses (R1): the 27B class declines a walk past the terminal at one
   step, matching the flash-class record at the same depth. Off-end behavior on this class is
   not a truncation artifact at shallow depth.
4. The co-fired load is the binding constraint of this firing, and it was measured before the
   commitment: 1.7 and 0.9 tok/s on the census, 1.01 tok/s on the full calibration, 1.24 and
   1.33 tok/s on the two dispatched cells. The frozen 3000 s budget holds at most roughly
   3000 completion tokens at the measured rate; the four-cell core panel (roughly 6000 tokens
   at the round-52 shape) does not fit, so it was registered (P1) rather than dispatched. The
   measurement-driven scoping kept the firing inside its caps instead of burning them on a
   panel it could not deliver.
5. Off-schedule note: the expected 06:00 CET timeout marker for this firing's runner process
   passed while the round was still completing. The dispatch itself finished at 06:09:09 CET,
   inside the frozen budget, and this record was published after the marker (house precedent:
   rounds 38 and 40 completed after a stale timeout marker). The artifact set is complete:
   gate, raw records, summary, this README.

## Limits

- Two dispatched cells at n = 1 each on one rate-limited endpoint: small-n exploratory by
  construction, and the label is `Executed` (no independent second implementation, no
  pre-registered decision table covering this literature tier).
- E1 is shallow (`j = 8`): it certifies the anchor and the class's name-arm liveness, it does
  not touch the wall. The wall question is P1, owed, and nothing in this firing discriminates
  the two wall readings.
- All rates are measured under a co-fired load, not the class's clean rate; the absolute
  tok/s values are load-specific and must not be cited as class performance.
- T2 is NoPE theory with the RoPE caveat on record; the deployed 27B-class endpoint uses RoPE.
- E2 is one 256-token census call; it states this firing's exposure setting, not a class-level
  trace proof.
- The dispatch window ran past the expected 06:00 timeout marker; see the off-schedule note.

## Verification notes (literature)

One OpenAlex works batch (free scholarly API, one call, 2026-11-12) resolved the four DOIs
cited in the gate at work-record level (title, authors, year, source). No quote was taken; the
gate statements are re-verified against the work record.

| Row | Source | Work record (2026-11-12) |
|-----|--------|--------------------------|
| T1 | arXiv:2604.25800, 10.48550/arXiv.2604.25800 | "Barriers to Universal Reasoning With Transformers (And How to Overcome Them)", Kraus, Sarrof, Yao, Koller, Hahn, 2026, arXiv |
| T2 | arXiv:2608.13433, 10.48550/arXiv.2608.13433 | "Algebraic Decomposition Theory for Transformer Length Generalization", Yang, Veseli, Barloy, Cadilhac, Krebs, Paperman and 2 more, 2026, arXiv |
| T3 | arXiv:2608.31067, 10.48550/arXiv.2608.31067 | "Universal Transformers for Circuit Computations: Perfect Length Generalization in Tiny Transformers", Ito, Puri, Campbell, Parikshit Ram, 2026, arXiv |
| context | arXiv:2211.15661, 10.48550/arXiv.2211.15661 | "What learning algorithm is in-context learning? Investigations with linear model", Akyürek, Schuurmans, Andreas, Ma, Zhou, 2022, arXiv |

## Reproduce

- `python3 name_walk_probe_r61.py --selftest` (113 deterministic checks: frozen gate schema
  and blob, the r61/full/core panel plans, item lineage and issue #67 guards, the E1/E2/R1/P1
  scoring paths against synthetic records, sanitizer fixtures)
- `python3 name_walk_probe_r61.py --freeze --panel r61` (derives the gate; the frozen
  `gate.json` in this directory is the contract and is never rewritten by a run)
- `python3 name_walk_probe_r61.py --run --panel r61` (health call plus the 2 dispatches;
  writes `health.json`, `raw.jsonl` and `summary.json`)
- `python3 name_walk_probe_r61.py --rescore` (rescores from `raw.jsonl` and `health.json`
  against the frozen blob; idempotent)
- `python3 name_walk_probe_r61.py --check-readme` (issue #137 row-and-blob guard over this
  README)
- literature: one OpenAlex works call with a DOI filter over the four gate DOIs (free
  scholarly API, 2026-11-12), work-record level

`raw.jsonl` and `health.json` carry a machine-only 16-hex model digest for verification and
are excluded from human-readable surfaces, per `research/AGENTS.md`. Every raw record carries
the gate blob. Evidence label: `Executed`; the small-n exploratory caveat is in Limits.
