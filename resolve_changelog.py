#!/usr/bin/env python3
"""Resolve the CHANGELOG.md merge conflict in a PR branch: keep origin/main's
[Unreleased] entries first, then the branch's own entry, then the common tail."""
import sys

path = sys.argv[1]
lines = open(path, encoding="utf-8").read().split("\n")
out, i = [], 0
while i < len(lines):
    l = lines[i]
    if l.startswith("<<<<<<<"):
        head, main = [], []
        i += 1
        while lines[i] not in ("|||||||", "======="):
            head.append(lines[i]); i += 1
        if lines[i] == "|||||||":
            i += 1
            while not lines[i].startswith("======="):
                i += 1
        i += 1
        while not lines[i].startswith(">>>>>>>"):
            main.append(lines[i]); i += 1
        i += 1
        out += main + head
    else:
        out.append(l); i += 1
open(path, "w", encoding="utf-8").write("\n".join(out))
assert not any(l.startswith(("<<<<<<<", ">>>>>>>")) for l in out)
print("resolved")
