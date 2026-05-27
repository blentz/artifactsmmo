#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."   # formal/
. "$HOME/.elan/env" 2>/dev/null || true
OUT="$(lake env lean Formal/Audit.lean 2>&1)"
echo "$OUT"
if echo "$OUT" | grep -Eiq 'sorryAx|sorry'; then echo "GATE FAIL: sorry detected"; exit 1; fi
# every 'depends on axioms: [...]' bracket must be a subset of the allowed three
if echo "$OUT" | grep -E 'depends on axioms' \
   | grep -Evq '\[(propext|Classical\.choice|Quot\.sound)(, (propext|Classical\.choice|Quot\.sound))*\]'; then
  echo "GATE FAIL: non-standard axiom present"; exit 1
fi
echo "axiom check OK"
