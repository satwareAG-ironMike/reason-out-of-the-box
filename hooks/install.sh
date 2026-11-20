#!/usr/bin/env bash
# Install the house git hooks by pointing core.hooksPath at this directory.
# Idempotent; run from anywhere in the repo:
#   bash hooks/install.sh
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
git -C "$ROOT" config core.hooksPath hooks
echo "core.hooksPath=hooks  (pre-commit + pre-push active)"
echo "Requires: python3, betterleaks on PATH."
