#!/usr/bin/env python3
"""Fail if any tracked file carries a git conflict marker line.

Pattern: a line whose first non-whitespace chars form one of
  <<<<<<<  =======  >>>>>>>
(each marker is 7+ characters of that symbol).

Usage:
  check_conflict_markers.py            # scan tracked .md and .yml/.yaml files
  check_conflict_markers.py --selftest
"""
import subprocess, re, sys

# 7+ consecutive <, =, or >
# 7+ consecutive <, =, or > at start of line (optional leading whitespace)
MARKER = re.compile(r"^\s*(?:<{7,}|={7,}|>{7,})")

def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True, text=True,
    ).stdout
    files = out.split("\0")
    return [f for f in files if f and f.endswith((".md", ".yml", ".yaml"))]

def scan(files):
    bad = []
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                if MARKER.match(line):
                    bad.append(f"{f}:{i}: {line.rstrip()}")
    return bad

# selftest uses basename only for stable comparison

def main():
    if "--selftest" in sys.argv:
        import tempfile, os
        d = tempfile.mkdtemp()
        p = os.path.join(d, "fix.md")
        with open(p, "w") as f:
            f.write("ok line\n<<<<<<< HEAD\n=======\n>>>>>>> theirs\n")
        got = scan([p])
        assert len(got) == 3, f"expected 3 marker lines, got {len(got)}: {got}"
        assert any("<<<<<<< HEAD" in g for g in got)
        assert any("=======" in g for g in got)
        assert any(">>>>>>> theirs" in g for g in got)
        print("selftest ok")
        return 0
    bad = scan(tracked_files())
    if bad:
        for b in bad:
            print(b)
        print(f"FAIL: {len(bad)} conflict-marker line(s) in tracked files")
        return 1
    print("ok: no conflict markers in tracked .md/.yml/.yaml files")
    return 0

if __name__ == "__main__":
    sys.exit(main())
