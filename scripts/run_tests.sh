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

# Coverage measurement core. Python 3.12+ implements coverage via sys.monitoring
# instead of a C trace function, which is ~4.5x cheaper on lane 2: the census
# fixture fans 152 planner searches over a ProcessPoolExecutor and tracing all of
# them dominated the lane (5:34 -> 1:14; whole suite ~6:00 -> 1:38.8). sysmon does
# not support BRANCH coverage, which is why this is safe here: pyproject.toml sets
# `branch = false`. Overridable so a bisect can pin the old core:
# `COVERAGE_CORE=ctrace bash scripts/run_tests.sh`.
export COVERAGE_CORE="${COVERAGE_CORE:-sysmon}"

SCENARIOS=tests/test_ai/scenarios
CENSUS=tests/test_audit/test_inventory_census.py

rm -f .coverage .coverage.*

echo "== Lane 1: parallel bulk (-n auto, excludes scenarios + census) =="
uv run pytest -n auto -p no:cacheprovider tests/ \
  --ignore="$SCENARIOS" --ignore="$CENSUS" \
  --cov-fail-under=0 -q

# No planner-budget override for lane 2 any more. The arbiter's cheap/full
# two-pass and its ARTIFACTSMMO_CHEAP_BUDGET_SECONDS escape hatch are deleted:
# there is ONE budget (planner._SEARCH_BUDGET_SECONDS = 15s), pinned by a unit
# test, and no env can move it. That is 50% MORE wall clock than the 10s the
# scenarios actually ran under in lane 1 before, so the searches this override
# was protecting (e.g. l12_bag_pursuit's ReachCurrency) have more room than
# they did, not less — but a scenario that starts timing out on slow hardware
# is now a real signal to fix the search, not an env var to raise.
echo "== Lane 2: serial census + scenarios (append coverage, enforce 100%) =="
uv run pytest -p no:cacheprovider "$CENSUS" "$SCENARIOS" \
  --cov-append -q
