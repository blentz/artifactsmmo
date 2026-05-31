#!/usr/bin/env bash
# Axiom gate entry point (Phase 19a split). Runs:
#   1. Safety pass — non-Liveness modules, axioms ⊆ kernel three.
#   2. Liveness pass — Formal/Liveness/**, axioms ⊆ kernel ∪ Mathlib_standard.
#   3. Cross-namespace leak check — no safety module may `import Mathlib`.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORMAL="$(cd "$HERE/.." && pwd)"

echo "-- safety pass --"
bash "$HERE/check_axioms_safety.sh"

echo "-- liveness pass --"
bash "$HERE/check_axioms_liveness.sh"

echo "-- cross-namespace leak check --"
# Any Lean source outside Formal/Liveness/ that imports Mathlib is a leak —
# it would let Mathlib axioms enter the safety surface without going through
# the liveness gate.
LEAKS="$(grep -rl '^import Mathlib' "$FORMAL/Formal" | grep -v '/Liveness/' || true)"
if [ -n "$LEAKS" ]; then
  echo "GATE FAIL: safety modules import Mathlib:"
  echo "$LEAKS"
  exit 1
fi
echo "no cross-namespace leaks"
echo "axiom gate OK"
