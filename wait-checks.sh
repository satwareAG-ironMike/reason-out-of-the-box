#!/usr/bin/env bash
# wait-checks.sh <pr-number> [timeout-min] - exit 0 when all required checks SUCCESS
n="$1"; timeout="${2:-30}"
for i in $(seq 1 $((timeout * 4))); do
  out=$(gh pr checks "$n" 2>/dev/null)
  fail=$(echo "$out" | grep -ci "fail" || true)
  green=$(echo "$out" | grep -c "pass" || true)
  pending=$(echo "$out" | grep -ciE "queued|in progress|waiting" || true)
  if [ "$fail" -gt 0 ]; then echo "FAILED on PR $n"; echo "$out" | grep FAIL; exit 1; fi
  if [ "$green" -ge 4 ] && [ "$pending" -eq 0 ]; then echo "PR $n checks GREEN"; exit 0; fi
  sleep 15
done
echo "PR $n checks still pending after ${timeout} min"; exit 2
