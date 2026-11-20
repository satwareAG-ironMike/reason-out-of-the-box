# Ready-to-submit checklist (issue #11, owner-facing)

One page. Status date 2026-11-20. Nothing here is submitted by an agent: OSF/AsPredicted,
the IRB path, and the freeze moment are owner decisions (`docs/agent-execution.md` section 10).

## What is ready now

- [x] Computational-layer registration text: [preregistration.md](preregistration.md) skeleton with
  the stable-facts table (design, units, exclusions, decision table all trace to
  [analysis-plan.md](analysis-plan.md) and [study-design.md](study-design.md)).
- [x] Frozen documents hash-verified: `analysis-plan.md` and `study-design.md` unchanged since the
  2026-09-14 capture (re-verified 2026-11-20, [version-lock-manifest.md](version-lock-manifest.md)).
- [x] Model list: all eleven Hub revisions re-fetched identical 2026-11-20; OLMo 3 IDs verified
  (issue #138, PR #141); OLMo 3 32B training mix stays unpinned until verified.
- [x] Human layer: two-track decision recorded 2026-09-14 (#7, `docs/irb-protocol.md`); Layer 2
  registers the documented alternative (published baselines, `docs/human-baseline.md`).
- [x] Deviation policy and immutable-element list in place (analysis-plan Section 13).

## What is NOT ready (blocks a full freeze today)

- [ ] Section 3 (prompts/decoding) and section 4 (generators/seeds/item sets) of the manifest are
  M2 values; they can only be hashed after the pilot lock (#3-#5). Freezing before that would
  register a program with no task material.
- [ ] Frozen snapshot of the model list to extract from `docs/next-investigations.md` at freeze
  (manifest section 1, by design).
- [ ] The exploratory addendum (nightly flash/27B program brought in scope as exploratory) should
  be decided and, if accepted, filed BEFORE the timestamp so the registered confirmatory/exploratory
  split matches the program as it actually runs.

## Owner decisions (the whole list)

| # | Decision | Where it lands |
|---|----------|----------------|
| 1 | OSF/AsPredicted go and the freeze date | submission record above |
| 2 | Exploratory addendum go/no-go | addendum PR (refs #65) |
| 3 | LICENSE choice | repo root (issue #107) |
| 4 | Analysis-plan amendment, if any, before freeze | analysis-plan Section 13 path |
| 5 | #138 item 4: rebuild shipped `summary.json` as a 1:1 projection or freeze the duplicate | PR #138 blocker comment |

## Steps at the freeze moment (order)

1. Re-run the capture procedure at the end of `version-lock-manifest.md` (docs hashes + Hub API);
   commit values to `main` via PR.
2. Freeze commit = current `main`; record its SHA in the manifest.
3. Create the OSF registration (public) + AsPredicted; record both URLs and the date in the
   submission record of `preregistration.md` (PR).
4. Then #10 closes on the timestamp and #11 closes on the URLs (acceptance criteria).
