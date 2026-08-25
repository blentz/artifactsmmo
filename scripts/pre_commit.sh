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

# formal/ added 2026-08-25: it was gate-EXECUTED but never LINTED, and the
# unused-binding rules below (B007/RUF059, plus F841) are exactly the class
# that matters in a differential harness — an unused `lean_*` binding means
# both sides were computed and only one compared. F841 is included here (it
# is not in the src/ai selection) because two of the fourteen findings in
# formal/ were F841, not RUF059.
echo "[pre-commit] ruff bug-finder rules on src/artifactsmmo_cli/ai/ and formal/..."
uv run ruff check src/artifactsmmo_cli/ai/ formal/ \
  --select B007,F841,SIM110,SIM115,RUF005,RUF059

echo "[pre-commit] pytest (no-cov, fast, excludes live-API integration tests)..."
uv run pytest tests/test_ai/ --no-cov -q -x -m "not integration"

echo "[pre-commit] all gates passed."
