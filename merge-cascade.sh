#!/usr/bin/env bash
cd /tmp/opencode/reason-out-of-the-box/pr-rebase
for pair in \
  "research/nightly-2026-11-09-0301 136" \
  "research/nightly-2026-11-11-0440 138" \
  "research/nightly-2026-11-11-0318 140" \
  "research/nightly-2026-11-12-0232 142" \
  "research/nightly-2026-11-13-0348 143" \
  "research/nightly-2026-11-13-0441 144" \
  "research/nightly-2026-11-16-0412 151" \
  "research/nightly-2026-11-17-0401 153" \
  "research/nightly-2026-11-18-0423 154" \
  "research/nightly-2026-11-19-0401 155" \
  "research/nightly-2026-11-16-0219 157" \
  "research/nightly-2026-11-09-0417 158" \
  "research/nightly-2026-11-10-0401 159" \
  "research/nightly-2026-11-10-0223 160" \
  "research/errata-round51 161" \
  "fix/gates-redact-and-guard 163" \
  "fix/two-track-sync-147 164"; do
  set -- $pair
  if ! bash merge-one.sh "$1" "$2"; then
    echo "ABORTED at $1 (PR #$2)"
    exit 1
  fi
done
echo "ALL 17 MERGED"
