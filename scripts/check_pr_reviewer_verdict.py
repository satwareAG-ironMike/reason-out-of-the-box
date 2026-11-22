#!/usr/bin/env python3
"""Check that a [pr-reviewer] verdict comment exists at the PR's current head SHA.

A passing verdict comment is an issue comment on the PR whose body contains
`[pr-reviewer] verdict at head `X` ... : MERGED` (backtick-wrapped SHA, any
prefix length >= 7 hex digits) where X is a prefix of the PR's current
headRefOid, and the outcome is the positive word MERGED (a NOT MERGED
verdict at the head does not pass the gate, issue #193).

The check FAILS when no such comment exists: a PR may only merge once a
MERGED verdict has been posted at the exact head that will land.

Usage:
  check_pr_reviewer_verdict.py PR_NUMBER HEAD_SHA
    PR_NUMBER  integer, the PR number
    HEAD_SHA   the PR's current headRefOid (full or abbreviated)

Requires GITHUB_TOKEN (or GH_TOKEN) and GITHUB_REPOSITORY (owner/name),
or the --owner/--repo flags. Exit 0 when a matching verdict exists, 1 when
not, 2 on API/argument errors.
"""
import json, os, re, sys, urllib.request

API = "https://api.github.com"

def main():
    args = [a for a in sys.argv[1:]]
    if "--selftest" in args:
        import tempfile
        # selftest: pattern matches a verdict at a prefix of the head,
        # and does not match a verdict at a different head
        verdict = "[pr-reviewer] verdict at head `541342e` (2026-11-19): MERGED as `3e10e81`."
        stale   = "[pr-reviewer] verdict at head `dfba376` (2026-11-15): NOT MERGED."
        head = "541342e355cc82e98d72b8571d02f28ebcc80068"
        assert has_verdict_at_head(verdict, head), "verdict at head must match"
        assert not has_verdict_at_head(stale, head), "verdict at stale head must not match"
        assert not has_verdict_at_head("plain comment", head), "non-verdict must not match"
        assert has_verdict_at_head("[pr-reviewer] verdict at head `541342e355` (full head): MERGED.", head)
        # issue #193: a NOT MERGED verdict at the current head must NOT pass
        # the merge gate; only a MERGED verdict at the head does.
        notmerged = "[pr-reviewer] verdict at head `541342e` (2026-11-21): NOT MERGED, one blocking item."
        assert not has_verdict_at_head(notmerged, head), "NOT MERGED verdict must not pass the gate"
        print("selftest ok")
        return 0
    if len(args) != 2:
        print("usage: check_pr_reviewer_verdict.py PR_NUMBER HEAD_SHA", file=sys.stderr)
        return 2
    pr_number, head_sha = args
    pr_number = int(pr_number)
    head = head_sha.lower().rstrip()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("FAIL: GITHUB_TOKEN (or GH_TOKEN) is not set", file=sys.stderr)
        return 2
    owner_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not owner_repo:
        print("FAIL: GITHUB_REPOSITORY (owner/name) is not set", file=sys.stderr)
        return 2
    url = f"{API}/repos/{owner_repo}/issues/{pr_number}/comments?per_page=100"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                              "Accept": "application/vnd.github+json",
                                              "User-Agent": "check_pr_reviewer_verdict"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            comments = json.load(resp)
    except Exception as e:
        print(f"FAIL: API error: {e}", file=sys.stderr)
        return 2
    for c in comments:
        if has_verdict_at_head(c.get("body", ""), head):
            print(f"ok: [pr-reviewer] verdict at head {head[:7]} exists (comment by {c.get('user', {}).get('login', '?')})")
            return 0
    print(f"FAIL: no [pr-reviewer] MERGED verdict at head {head[:7]}; post a three-lens MERGED verdict at the current head before merging")
    return 1

_VERDICT_RE = re.compile(
    r"\[pr-reviewer\] verdict at head `([0-9a-f]{7,40})`[^:]*: (MERGED|NOT MERGED)"
)

def has_verdict_at_head(body, head):
    for m in _VERDICT_RE.finditer(body):
        sha = m.group(1).lower()
        outcome = m.group(2)
        # the merge gate only accepts a positive verdict: NOT MERGED fails the gate (issue #193)
        if outcome != "MERGED":
            continue
        # verdict SHA must be a prefix of (or identical to) the current head
        if head.startswith(sha) or sha.startswith(head[:len(sha)]):
            return True
    return False

if __name__ == "__main__":
    sys.exit(main())
