#!/usr/bin/env python3
"""Fail if agent helper artifacts (log files, merge helpers) are tracked.

The 2026-11-20 cascade (issue #169) left agent-side helper files in two
squash commits on main: cascade.log, merge-one.sh, wait-checks.sh
(introduced by #154 / #163), and resolve_changelog.py (introduced by
#161, removed by #168). None are tracked today, but blanket additions
(`git add .`) can reintroduce them. This check fails on any tracked
file matching the block list.

Usage:
  check_no_agent_artifacts.py
  check_no_agent_artifacts.py --selftest
"""
import os, subprocess, sys, re

# patterns: (regex, description)
BLOCK = [
    (r"^cascade\.log$", "agent cascade log"),
    (r"^merge-one\.sh$", "agent merge helper script"),
    (r"^wait-checks\.sh$", "agent wait-checks helper script"),
    (r"^resolve_changelog\.py$", "agent changelog-resolution helper"),
    # .log files at repo root only (agent logs); research/ subdirectory .log files are run artifacts
    (r"\.log$", "root-level log file"),
]

def tracked_files():
    return subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True, text=True,
    ).stdout.split("\0")

def check(files):
    bad = []
    for f in files:
        f = f.strip()
        if not f:
            continue
        base = f.split("/")[-1]
        for pat, desc in BLOCK:
            # root-level .log: match only when file has no directory (path == basename)
            if desc == "root-level log file":
                if f == base and re.search(pat, base):
                    bad.append(f"{f} ({desc})")
                    break
            elif re.search(pat, base) or re.search(pat, f):
                bad.append(f"{f} ({desc})")
                break
    return bad

def main():
    if "--selftest" in sys.argv:
        good = ["CHANGELOG.md", "ci.yml", "check_archive.py", "research/nightly-2026-11-07-0400/README.md"]
        bad = ["cascade.log", "merge-one.sh", "wait-checks.sh", "resolve_changelog.py"]
        assert check(good) == [], f"good files should pass: {check(good)}"
        assert len(check(bad)) == 4, f"all 4 bad files should fail: {check(bad)}"
        print("selftest ok")
        return 0
    bad = check(tracked_files())
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        print(f"FAIL: {len(bad)} tracked agent artifact(s) found")
        return 1
    print("ok: no agent helper artifacts tracked")
    return 0

if __name__ == "__main__":
    sys.exit(main())
