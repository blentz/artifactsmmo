#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
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
# Anchor resolution runs here, before the two slow phases, because it is the
# cheapest possible failure: seconds against ~580 anchors, no tests executed. A
# stale or ambiguous anchor used to surface only at the END of the hour-long
# mutation run, long after the commit that caused it.
echo "== (b'''') mutation anchors =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py --check-anchors )
echo "== (d) differential =="; ( cd "$HERE" && lake build oracle ); ( cd "$ROOT" && uv run pytest formal/diff/ -q --no-cov -n auto --ignore=formal/diff/test_game_data_fixture_diff.py )
echo "== (c) mutation =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py )
echo "ALL GATE PARTS PASSED"
