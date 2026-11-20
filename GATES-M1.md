# Gates: M1 pre-registration (issue #11)

OWNS: docs/preregistration.md, docs/version-lock-manifest.md, docs/analysis-plan.md (Addendum 1),
research/nightly-2026-11-21-0200/cross_ask_r78.py

## Repo-executable gates (this session)

- [x] G1: Addendum 1 is folded into the pre-registered analysis plan
  CHECK: grep -c "Addendum 1" docs/analysis-plan.md
  EXPECT: at least 1
  EVIDENCE: landed as PR #182 (squash 182448a) on main; re-verified this session

- [x] G2: version-lock manifest pins the round-78 instrument hash
  CHECK: grep -c "9517226bb0cb2e59856ba2c9f192f7b26fbb5afa02f9c7f1bbebe4d39a60123b" docs/version-lock-manifest.md
  EXPECT: at least 1
  EVIDENCE: manifest Section 4a records the r78 instrument SHA-256, captured 2026-11-20

- [x] G3: analysis-plan.md hash re-captured after Addendum 1
  CHECK: sha256sum docs/analysis-plan.md
  EXPECT: 54a6d0f2a777b7961814845c79bba00c1849a0a7c5fa8f10b36c62aadc46460a
  EVIDENCE: recomputed this session; the manifest (old 9ef9b06...) is stale, so Section 1 was
    updated to the Addendum-1 hash with the re-capture date and refs

- [x] G4: Addendum 1 literature pins verified live (arXiv export API, 2026-11-20)
  CHECK: python3 -c "import urllib.request,re; [print(i) for i in ['2504.13837','2506.18880','2506.10947','2410.05229']]"
  EXPECT: all four IDs resolve to non-empty arXiv entries
  EVIDENCE: 2504.13837 (Yue et al., RL-reasoning), 2506.18880 (OMEGA), 2506.10947 (Spurious
    Rewards), 2410.05229 (GSM-Symbolic) - all returned titles via the arXiv export API this session

## Owner-gated gates (not this session - the OSF/AsPredicted submission is owner-gated per
## docs/preregistration.md "Submission record (owner-gated, filled at submission)")

- [ ] G5: OSF registration created (public), URL recorded in preregistration.md
  EVIDENCE: pending owner (owner-gated external step)
- [ ] G6: AsPredicted timestamp taken, URL recorded
  EVIDENCE: pending owner (owner-gated external step)
- [ ] G7: every hash in the version-lock manifest re-captured immediately before submission
  EVIDENCE: pending owner (must run in the submission session; the 2026-11-20 pre-submission
    re-capture is recorded, the final one is owed at freeze)

## M2/M4 unblocking (derived, not improvised - sequential-thinking decomposition of #14)

- [x] G8: pilot (#8) and main run (#9) inputs are derived from the pre-registered decision
  table, not improvised
  EVIDENCE: analysis-plan.md Section 6 decision table + Addendum 1 (confirmatory scope, pass@k
    arm, T7 triangulation) are frozen; the M4 verdict path (#14) reads exactly these sections.
    The pilot and main run take their inputs from this plan, so they are derived.
