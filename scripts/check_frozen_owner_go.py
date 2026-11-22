#!/usr/bin/env python3
"""Owner-go gate for the frozen instrument (issue #194).

evaluation/frozen/ is the judge. The owner alone merges anything there, so a pull
request that changes it must carry the `owner-go` label, and CI must refuse the
change without it. This script is that refusal.

Modes:
  --selftest              classification fixtures, no network
  --local [BASE]          report which frozen paths the current branch range touches
                          (advisory: preparing a frozen PR is allowed, merging it is not)
  --pr N                  ask the API for that PR's labels and changed files (CI mode)

CI mode reads the PR's changed files and its labels from the GitHub API
(GITHUB_TOKEN or GH_TOKEN, GITHUB_REPOSITORY). Exit 0 when the PR changes nothing
frozen, or changes frozen files and carries owner-go. Exit 1 when a frozen change
carries no owner-go. Exit 2 on argument or API failure: a gate that cannot see the
labels fails closed, it does not pass by default.

stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request

API = "https://api.github.com"
FROZEN_DIR = "evaluation/frozen/"
LABEL = "owner-go"


def frozen_paths(names: list[str]) -> list[str]:
    """The changed paths that belong to the instrument."""
    return sorted(n for n in names if n.startswith(FROZEN_DIR))


def has_owner_go(labels: list[str]) -> bool:
    return LABEL in [str(label).strip().lower() for label in labels]


def classify(names: list[str], labels: list[str]) -> tuple[int, str]:
    """(exit code, message) for one PR's changed files plus its labels."""
    touched = frozen_paths(names)
    if not touched:
        return 0, f"no change under {FROZEN_DIR}: owner-go not required"
    if has_owner_go(labels):
        return 0, (f"{len(touched)} frozen file(s) changed and the PR carries {LABEL}: "
                   "owner-only merge lane respected")
    listing = ", ".join(touched)
    return 1, (f"FAIL: {len(touched)} file(s) under {FROZEN_DIR} changed without the {LABEL} "
               f"label: {listing}. The frozen judge is merged by the owner alone; "
               f"the owner sets {LABEL} on the PR, no one else.")


def git_range(base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                         capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line.strip()]


def _get(url: str, token: str) -> object:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "Accept": "application/vnd.github+json",
                                               "User-Agent": "check_frozen_owner_go"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def pr_data(repo: str, pr_number: int) -> tuple[list[str], list[str]]:
    """(changed filenames, label names) for one pull request."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN (or GH_TOKEN) is not set")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY (owner/name) is not set")
    names: list[str] = []
    page = 1
    while True:
        files = _get(f"{API}/repos/{repo}/pulls/{pr_number}/files?per_page=100&page={page}", token)
        names.extend(str(f["filename"]) for f in files)
        if len(files) < 100:
            break
        page += 1
    pull = _get(f"{API}/repos/{repo}/pulls/{pr_number}", token)
    labels = [str(label.get("name", "")) for label in pull.get("labels", [])]
    return names, labels


def selftest() -> int:
    checks = 0

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(label)

    frozen = [f"{FROZEN_DIR}score.py", f"{FROZEN_DIR}rule.json"]
    other = ["README.md", "explore/2026-11-21-probe/README.md", "scripts/check_archive.py"]

    code, message = classify(other, [])
    ok(code == 0, f"a PR that does not touch the instrument must pass, got {code} {message}")

    code, message = classify(frozen, [])
    ok(code == 1, f"a frozen change without {LABEL} must fail, got {code} {message}")
    ok("owner-go" in message and "score.py" in message,
       f"the failure must name the label and the files, got {message}")

    code, message = classify(frozen, [LABEL])
    ok(code == 0, f"a frozen change carrying {LABEL} must pass, got {code} {message}")

    code, message = classify(frozen, ["research", "enhancement"])
    ok(code == 1, f"other labels are not {LABEL}, got {code} {message}")

    code, message = classify([*other, f"{FROZEN_DIR}MANIFEST.json"], [LABEL])
    ok(code == 0, f"a mixed PR carrying {LABEL} must pass, got {code} {message}")

    ok(frozen_paths(other) == [], "an ordinary PR must report no frozen change")
    ok(frozen_paths(["evaluation/frozen.md"]) == [],
       "a path that merely starts with evaluation/frozen and is not inside the directory "
       "is not a frozen change")
    ok(frozen_paths([f"{FROZEN_DIR}AGENTS.md"]) == [f"{FROZEN_DIR}AGENTS.md"],
       "the instrument's own DOX doc is part of the owner-only lane")
    ok(has_owner_go(["Owner-Go"]), "the label match is case-insensitive")
    print(f"selftest: {checks} of {checks} checks green")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--local", nargs="?", const="origin/main", metavar="BASE",
                        help="advisory local mode: report frozen paths changed since BASE")
    parser.add_argument("--pr", type=int, help="PR number (CI mode)")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.local:
        names = git_range(args.local)
        touched = frozen_paths(names)
        if not touched:
            print(f"no change under {FROZEN_DIR} since {args.local}")
            return 0
        print(f"advisory: {len(touched)} file(s) under {FROZEN_DIR} changed since {args.local}:")
        for name in touched:
            print(f"  - {name}")
        print(f"preparing this PR is allowed; only the owner merges it, and the PR must carry "
              f"the {LABEL} label set by the owner. The gate that enforces that is this script "
              f"run with --pr in CI (owner wires it).")
        return 0

    if args.pr:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        try:
            names, labels = pr_data(repo, args.pr)
        except (RuntimeError, KeyError, urllib.error.URLError, subprocess.CalledProcessError) as exc:
            print(f"FAIL: cannot read PR {args.pr}: {exc}", file=sys.stderr)
            return 2
        code, message = classify(names, labels)
        print(message)
        return code

    parser.error("one of --selftest, --local [BASE], --pr N is required")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
