#!/usr/bin/env bash
# Pre-commit gate. Runs mypy strict + ruff bug-finder + pytest.
# Failure on ANY check blocks the commit.
#
# Install via scripts/install_hooks.sh.
#
# This script intentionally does NOT honor --no-verify in custom logic
# (git's native --no-verify still bypasses, but no project-level bypass
# flag exists per the discipline established 2026-06-04).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Skip when no Python files are staged or modified — workflow/markdown
# edits don't warrant a full type/lint/test pass.
if ! git diff --cached --name-only | grep -qE '\.py$|^pyproject\.toml$'; then
  echo "[pre-commit] no Python changes staged — skipping mypy/ruff/pytest"
  exit 0
fi

echo "[pre-commit] mypy strict..."
uv run mypy src/

echo "[pre-commit] ruff bug-finder rules on src/artifactsmmo_cli/ai/..."
uv run ruff check src/artifactsmmo_cli/ai/ \
  --select B007,SIM110,SIM115,RUF005,RUF059

echo "[pre-commit] pytest (no-cov, fast)..."
uv run pytest tests/test_ai/ --no-cov -q -x

echo "[pre-commit] all gates passed."
