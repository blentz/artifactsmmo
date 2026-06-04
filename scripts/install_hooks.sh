#!/usr/bin/env bash
# Install the project's pre-commit hook into .git/hooks/pre-commit.
# Runs scripts/pre_commit.sh on every git commit.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

HOOK=".git/hooks/pre-commit"
TARGET="../../scripts/pre_commit.sh"

if [ -e "$HOOK" ] && [ ! -L "$HOOK" ]; then
  echo "[install_hooks] $HOOK exists and is NOT a symlink; refusing to overwrite."
  echo "[install_hooks] Move or delete it first, then re-run."
  exit 1
fi

ln -sf "$TARGET" "$HOOK"
echo "[install_hooks] installed pre-commit → scripts/pre_commit.sh"
