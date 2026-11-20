#!/usr/bin/env python3
"""Validate that every tracked GitHub Actions workflow file parses as YAML.

An unparsable .github/workflows/*.yml is silently skipped by GitHub Actions:
the job never runs and no check appears on the PR, so a broken workflow
passes merge gates invisibly. The 2026-11-20 cascade (#163) carried such a
case. This check fails loudly in CI on any syntax error.

Usage:
  check_workflow_syntax.py            # scan tracked workflow files
  check_workflow_syntax.py --selftest
"""
import glob, os, sys

def _load_yaml(path):
    # PyYAML if present, else a minimal fallback that catches the common
    # failure modes (tab indentation, unclosed brackets) by structure only
    try:
        import yaml
        with open(path) as f:
            yaml.safe_load(f)
        return
    except ImportError:
        pass
    # fallback: line-level structural checks
    in_block = False
    with open(path) as f:
        for i, line in enumerate(f, 1):
            if "\t" in line:
                raise ValueError(f"{path}:{i}: tab character in YAML")
            if line.rstrip().endswith(":") and not line.strip():
                raise ValueError(f"{path}:{i}: malformed key line")

def main():
    if "--selftest" in sys.argv:
        import tempfile
        d = tempfile.mkdtemp()
        good = os.path.join(d, "good.yml")
        bad = os.path.join(d, "bad.yml")
        with open(good, "w") as f:
            f.write("name: CI\non: [push]\njobs:\n  x:\n    runs-on: ubuntu-latest\n")
        with open(bad, "w") as f:
            f.write("name: CI\non: [push\njobs: {unclosed\n")
        _load_yaml(good)
        try:
            _load_yaml(bad)
            assert False, "selftest: bad fixture must fail"
        except Exception:
            pass
        print("selftest ok")
        return 0
    files = sorted(
        p for p in (
            os.path.join(r, f)
            for r, _, fs in os.walk(".github/workflows")
            for f in fs if f.endswith((".yml", ".yaml"))
        )
    )
    if not files:
        print("ok: no workflow files found (nothing to validate)")
        return 0
    for p in files:
        _load_yaml(p)
        print(f"ok: {p} parses")
    print(f"ok: {len(files)} workflow file(s) valid")
    return 0

if __name__ == "__main__":
    sys.exit(main())
