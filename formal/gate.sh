#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
. "$HOME/.elan/env" 2>/dev/null || true
echo "== (a) kernel build =="; ( cd "$HERE" && lake build )
echo "== (b) axiom lint =="; bash "$HERE/gate/check_axioms.sh"
echo "== (b') role manifest =="; ( cd "$HERE" && lake env lean Formal/Manifest.lean >/dev/null && echo "manifest OK" )
echo "== (d) differential =="; ( cd "$HERE" && lake build oracle ); ( cd "$ROOT" && uv run pytest formal/diff/test_calculate_path_diff.py -q --no-cov )
echo "== (c) mutation =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py )
echo "ALL GATE PARTS PASSED"
