> **VOID FIRING - INSTRUMENT ONLY.** No gate, no records, no result. This
> directory preserves `wall_shape_probe.py` from the 2026-11-10 02:23 firing
> (the round-57 slot, issue #150). The instrument fails its own selftest;
> nothing was dispatched or scored. Keep-or-delete decision: issue #150 ask 2.
> Label: **void, not Executed.**

# Firing 2026-11-10 02:23 (void): instrument only, no gate, no records

This directory preserves an instrument, not a round record. The 2026-11-10 02:23 firing of the #65
family left exactly one file here, `wall_shape_probe.py`, and produced no `gate.json`, no
`raw.jsonl`, no `summary.json`, no `health.json` and no `README.md`. It is the round-57 slot in the
audit filed as issue #150.

The instrument does not pass its own selftest:

```
python3 research/nightly-2026-11-10-0223/wall_shape_probe.py --selftest
AssertionError: selftest failed: the registered discriminator set moved:
['L32A_j32', 'L48_j16', 'L48_j24', 'L48_j8', 'L64_j16', 'L64_j24', 'L64_j8']
```

So the firing never reached its gate freeze: the registered cell set in the script does not match the
archived set the script itself asserts against. Nothing was dispatched, nothing was scored, and this
round has no result to report. Issue #150's inventory said "the probe script only, no gate, no
records", and the selftest above is the reason that firing is void rather than merely unarchived.

## Why this is in the repository at all

The file was the only copy, in a working directory that the nightly runner reuses. Landing it here is
a preservation move with a decision attached, not a claim about a result: the owner can keep it as
the ancestor of the round-58 instrument (which shipped green at `research/nightly-2026-11-10-0401/`
two hours later) or delete it. Issue #150 ask 2 frames exactly this keep-or-delete call for the
script-only firing.

## One change to the file, disclosed

The sanitizer selftest fixture planted a private-range IPv4 address with a port and a model file name
under a home path. The serving-id guard (`scripts/check_serving_ids.py`) scans tracked files and reads
both as leaks, so the fixture now plants an RFC 5737 documentation-range address and a path under
`/root/`, with the matching assertion, plus a comment naming the rule. Both classes are still stripped
by the sanitizer patterns, the change is inside `selftest()` only, and the selftest failure above is
unrelated to it and predates the change.

Label: **void**. Not `Executed`: no dispatch ran. Nothing here contributes to any depth or wall claim,
and no confirmatory run may cite this directory.

Refs #150 (the audit), #65 (the round tracker), #149 (the leak classes this landing demonstrates).
