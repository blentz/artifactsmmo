#!/usr/bin/env bash
# Two-lane parallel test runner.
#
# The suite has two kinds of tests that must NOT run under pytest-xdist's
# process fan-out:
#   * tests/test_audit/test_inventory_census.py already fans its 152 planner
#     searches out over a ProcessPoolExecutor (all cores). Running it under
#     xdist would nest process pools and oversubscribe the machine.
#   * tests/test_ai/scenarios drive the GOAP planner against a 10s WALL-CLOCK
#     budget; busy xdist workers squeeze that budget and cause spurious
#     timeouts.
#
# So lane 1 parallelizes the fast bulk with `-n auto`, and lane 2 runs the two
# CPU-saturating / wall-clock-sensitive suites serially. Coverage from lane 1 is
# combined with lane 2 (--cov-append), and lane 2 enforces the 100% gate over
# the union.
set -euo pipefail

cd "$(dirname "$0")/.."

# Match CI's colour env exactly: neither variable set. A dev shell that exports
# FORCE_COLOR makes Rich colourize CliRunner output and breaks command tests that
# assert plain-text substrings; setting NO_COLOR instead breaks the Textual TUI
# tests. Clearing both is the only combination that keeps every suite green.
unset FORCE_COLOR NO_COLOR

SCENARIOS=tests/test_ai/scenarios
CENSUS=tests/test_audit/test_inventory_census.py

rm -f .coverage .coverage.*

echo "== Lane 1: parallel bulk (-n auto, excludes scenarios + census) =="
uv run pytest -n auto -p no:cacheprovider tests/ \
  --ignore="$SCENARIOS" --ignore="$CENSUS" \
  --cov-fail-under=0 -q

echo "== Lane 2: serial census + scenarios (append coverage, enforce 100%) =="
uv run pytest -p no:cacheprovider "$CENSUS" "$SCENARIOS" \
  --cov-append -q
