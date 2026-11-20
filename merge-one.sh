#!/usr/bin/env bash
# merge-one.sh <branch> <pr-number> - re-resolve branch onto origin/main, push,
# wait for the 4 CI checks, squash-merge the PR.
set -e
b="$1"; pr="$2"
cd /tmp/opencode/reason-out-of-the-box/pr-rebase
git fetch -q origin
git reset -q --hard "origin/$b"
if ! git merge -q origin/main 2>/dev/null; then
  python3 resolve_changelog.py CHANGELOG.md
  git add CHANGELOG.md
  git commit -q -m "Merge origin/main: keep both [Unreleased] entries, newest first" \
    -m "Model: 27B-class local model (local self-hosted inference pool/qwen3.8-27b-nvfp4-mtp)"
  git push -q origin "HEAD:$b"
  echo "$b: re-resolved+pushed"
fi
bash wait-checks.sh "$pr"
cd /home/mw/internal/poc/reason-out-of-the-box
sleep 20
gh pr merge "$pr" --squash || { sleep 30; gh pr merge "$pr" --squash; }
echo "merged $b (PR #$pr)"
