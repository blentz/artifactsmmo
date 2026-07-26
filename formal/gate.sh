#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
# RUNTIME BUDGET: this script must stay under 15 minutes from a warm Lean build.
# Measured integrated run 2026-07-25 (docs/superpowers/specs/2026-07-25-local-gate-runtime-design.md):
#   kernel build + 8 Lean/audit cheap checks (cache/build/orphans/sorry/
#     axioms/manifest/proof-concept index/extraction/audit-drift/anchors) ~29s
#   differential (-n auto)                                               1:59   <- NEVER drop -n auto; single-process is 20-38 min
#   python suite (run_tests.sh)                                          1:36   <- needs COVERAGE_CORE=sysmon; ctrace core is ~6 min
#   PRIOR END-TO-END TOTAL (the three phases above, actually run together
#     2026-07-25): 4:03.6
# Added 2026-07-25 (final-review finding: gate.sh claimed to be "the whole
# local gate" while silently skipping ruff/mypy/openapi/census; timed
# standalone, not yet re-measured as one end-to-end run):
#   ruff + mypy + openapi conformance (strict)                          ~1s    <- 0.04s + 0.36s + 0.06s standalone
#   census --check x5 (inventory/recycle/craft/obtain-parity/req-parity) 2:39   <- 0:56 + 0:01 + 1:39 + 0:01 + 0:01 standalone
#   PROJECTED NEW TOTAL: ~6:43 (4:03.6 prior + ~2:40 added) -- still ~8 min
#   of headroom under the 15-minute ceiling.
# Full mutation execution is nightly (mutation-gate.yml) and must not return here.
# SCOPE (accuracy matters here -- this claims to be "the whole local gate"):
# this script now runs everything CI runs across formal-gate.yml, lint-gate.yml,
# type-gate.yml, and census-gate.yml, with exactly two deliberate exclusions:
#   1. Full mutation EXECUTION (formal/diff/mutate.py's sweep, not the
#      anchor-only check below) -- stays in the nightly mutation-gate.yml:
#      ~36 min, peaks ~22GB, was this script's own dominator before it was
#      moved out (see phase (d) below for detail).
#   2. formal/diff/test_game_data_fixture_diff.py -- needs a live network
#      call to the game API to diff against the pinned snapshot; excluded
#      from the differential phase below via --ignore, exactly as
#      formal-gate.yml excludes it. Not a local/CI divergence, just a test
#      that cannot run offline.
. "$HOME/.elan/env" 2>/dev/null || true
# Pull Mathlib's hosted prebuilt cache before compiling. Saves ~30 min
# of cold Lean+Mathlib compile per CI run. `|| true` because the command
# fails benignly when cache.lean isn't built yet (first invocation) —
# subsequent `lake build` still recompiles what's missing.
echo "== (pre) mathlib cache =="
( cd "$HERE" && lake exe cache get 2>&1 | tail -3 || echo "cache get skipped" )
echo "== (a) kernel build =="; ( cd "$HERE" && lake build )
echo "== (a') orphan modules =="; bash "$HERE/gate/check_no_orphan_modules.sh"
echo "== (a'') no sorry/admit =="; bash "$HERE/gate/check_no_sorry.sh"
echo "== (b) axiom lint =="; bash "$HERE/gate/check_axioms.sh"
echo "== (b') role manifest =="; ( cd "$HERE" && lake env lean Formal/Manifest.lean >/dev/null && echo "manifest OK" )
echo "== (b'') proof-concept index =="; bash "$HERE/gate/check_proof_concept_index.sh"
echo "== (b''') extraction drift =="; bash "$HERE/gate/check_extraction.sh"
echo "== (b'''a) audit list derived from manifest =="; bash "$HERE/gate/check_audit_generated.sh"
# Anchor resolution runs here, before the two slow phases, because it is the
# cheapest possible failure: seconds against ~580 anchors, no tests executed. A
# stale or ambiguous anchor used to surface only at the END of the hour-long
# mutation run, long after the commit that caused it.
echo "== (b'''') mutation anchors =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py --check-anchors )
# ruff/mypy/openapi conformance: three more sub-second CI gates
# (lint-gate.yml, type-gate.yml, formal-gate.yml's OpenAPI conformance step)
# that were missing from this script despite it claiming to be "the whole
# local gate". Same commands the workflows run, so a local pass means the
# CI job passes too.
echo "== (c) ruff =="; ( cd "$ROOT" && uv run ruff check src/ tests/ )
echo "== (c') mypy strict =="; ( cd "$ROOT" && uv run mypy src/ )
echo "== (c'') openapi conformance (strict) =="; ( cd "$ROOT" && uv run python formal/diff/openapi_conformance.py --strict )
# census-gate.yml's five --check scripts. Measured standalone 2026-07-25:
# inventory 56s, recycle 1s, craft 99s, obtain-parity 1s, requirement-parity
# 1s (~2:39 total) -- comfortably inside the gate's headroom, so they run
# here rather than being deferred like full mutation execution below. Placed
# before the differential phase per the same cheapest-real-failure-first
# principle: these are Python-only census scripts, no Lean oracle build
# needed, so they can fail before differential pays for `lake build oracle`.
echo "== (c''') census (--check x5) =="
( cd "$ROOT" \
  && uv run python scripts/gen_inventory_completeness.py --check \
  && uv run python scripts/gen_recycle_source_completeness.py --check \
  && uv run python scripts/gen_craft_completeness.py --check \
  && uv run python scripts/gen_obtain_parity.py --check \
  && uv run python scripts/gen_requirement_parity.py --check )
echo "== (d) differential =="; ( cd "$HERE" && lake build oracle ); ( cd "$ROOT" && uv run pytest formal/diff/ -q --no-cov -n auto --ignore=formal/diff/test_game_data_fixture_diff.py )
# Full mutation EXECUTION is deliberately not here. It runs nightly in
# mutation-gate.yml, where CI moved it: ~36 min, peaks ~22GB, and it was the
# dominator of this script. Anchor resolution (phase b'''' above) is the part
# worth paying per-commit — it is seconds, runs no tests, and catches the stale
# or ambiguous anchor on the commit that caused it rather than 14h later.
# To run the sweep by hand: `uv run python formal/diff/mutate.py`.
# The Python suite runs LAST: it is the second-slowest phase, and every check
# above fails in seconds. run_tests.sh owns its own two-lane split and the 100%
# coverage gate; it is invoked rather than inlined so local and CI run the same
# script (.github/workflows/pytest.yml calls exactly this).
echo "== (e) python suite =="; ( cd "$ROOT" && bash scripts/run_tests.sh )
echo "ALL GATE PARTS PASSED"
