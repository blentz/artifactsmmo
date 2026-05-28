#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."   # formal/
. "$HOME/.elan/env" 2>/dev/null || true
OUT_RAW="$(lake env lean Formal/Audit.lean 2>&1)"
echo "$OUT_RAW"
# Lean wraps long `#print axioms` output across lines; fold continuation
# lines (those starting with whitespace) into the previous line so the
# bracket `[ propext, Classical.choice, Quot.sound ]` becomes a single
# token for the regex below.
OUT="$(printf '%s\n' "$OUT_RAW" | python3 -c 'import sys, re; print(re.sub(r"\n\s+", " ", sys.stdin.read()))')"
if echo "$OUT" | grep -Eiq 'sorryAx|sorry'; then echo "GATE FAIL: sorry detected"; exit 1; fi
# every 'depends on axioms: [...]' bracket must be a subset of the allowed three
if echo "$OUT" | grep -E 'depends on axioms' \
   | grep -Evq '\[(propext|Classical\.choice|Quot\.sound)(, (propext|Classical\.choice|Quot\.sound))*\]'; then
  echo "GATE FAIL: non-standard axiom present"; exit 1
fi
echo "axiom check OK"
