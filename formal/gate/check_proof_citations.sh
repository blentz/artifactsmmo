#!/usr/bin/env bash
# Proof-citation guard.
#
# Every `Formal.<Ns>.<name>` named in production Python must resolve to
# something that actually exists in formal/. FAILS the gate otherwise.
#
# WHY THIS EXISTS. The gather-batching branch (2026-08-13) found FIFTEEN
# places where a comment claimed more than the code or the kernel supported.
# The most expensive was `Formal.PlanModel.min_plan_length_le_plan`, cited as
# "(proved: ...)" in FOUR live locations — a theorem that had never been
# written at all. It named the predicate that admits or rejects every gear
# goal before A* runs, so the admission gate rested on nothing, and the gate
# was green throughout. The reviewer who found it observed that a grep for
# such citations, checked against formal/, would have caught it mechanically.
#
# Every instance of that class named an identifier, which is what makes this
# check possible. Unnamed prose ("provably sound") is deliberately NOT matched:
# `proved|proven|provably` hits 199 lines in src/ and "provenance" contains
# "proven", so a broad rule would be almost all noise and would rot into an
# allowlist. Naming a theorem is the load-bearing act; this checks the names.
#
# THREE SHAPES RESOLVE, and all three are legitimate:
#
#   1. DECLARATION — `theorem foo`, `def foo`, `abbrev foo`, ... in a .lean file.
#   2. MODULE      — `Formal.Liveness.CycleStep` is a FILE
#                    (formal/Formal/Liveness/CycleStep.lean), not a theorem.
#   3. RETRACTION  — text whose PURPOSE is to say a theorem does not exist,
#                    tagged `NOT-PROVED:` immediately before the identifier.
#                    This repo wrote three such retractions on purpose; a gate
#                    that failed them would push authors back toward silence,
#                    which is the disease rather than the cure. The tag is
#                    required so a retraction is greppable and deliberate
#                    rather than inferred from prose.
#
# SCOPE: src/ (production) and formal/diff/ (the oracle harnesses, which exist
# precisely to bind Python to Lean). NOT tests/ — a stale citation there
# misleads but does not misrepresent shipped behaviour. NOT docs/ — historical
# design records are an audit trail and are deliberately left as written.

set -euo pipefail

# Scan root: argument for tests, repo root by default.
BASE="${1:-$(cd "$(dirname "$0")/../.." && pwd -P)}"
cd "$BASE"

LEAN_ROOT="formal/Formal"

violations=()

# A citation is `Formal.` followed by two or more dot-separated segments, so a
# bare namespace mention (`Formal.PlanModel`) is not treated as a claim.
CITATION_RE='Formal\.[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+'

scan_dir() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  while IFS= read -r pyfile; do
    while IFS= read -r hit; do
      local lineno="${hit%%:*}"
      local text="${hit#*:}"
      # Every citation on the line, so one line naming two is fully checked.
      while IFS= read -r ident; do
        [ -n "$ident" ] || continue
        # 3. RETRACTION — `NOT-PROVED:` anywhere before this identifier on the
        # line. Checked first: a retraction names a thing that must NOT resolve.
        local before="${text%%"$ident"*}"
        case "$before" in
          *NOT-PROVED:*) continue ;;
        esac
        local leaf="${ident##*.}"
        # 1. DECLARATION.
        if grep -rqE \
          "^[[:space:]]*(private[[:space:]]+)?(protected[[:space:]]+)?(noncomputable[[:space:]]+)?(partial[[:space:]]+)?(def|theorem|lemma|abbrev|structure|inductive|instance|axiom|class)[[:space:]]+$leaf\b" \
          "$LEAN_ROOT" 2>/dev/null; then
          continue
        fi
        # 2. MODULE — Formal.A.B.C maps to formal/Formal/A/B/C.lean.
        local relpath="${ident#Formal.}"
        if [ -f "$LEAN_ROOT/${relpath//./\/}.lean" ]; then
          continue
        fi
        violations+=("$pyfile:$lineno: $ident")
      done < <(printf '%s\n' "$text" | grep -oE "$CITATION_RE" || true)
    done < <(grep -nE "$CITATION_RE" "$pyfile" || true)
  done < <(find "$dir" -name "*.py" -type f | sort)
}

scan_dir "src"
scan_dir "formal/diff"

if [ ${#violations[@]} -gt 0 ]; then
  echo "PROOF-CITATION CHECK FAILED — these name nothing in $LEAN_ROOT:"
  for v in "${violations[@]}"; do
    echo "  $v — no such declaration or module"
  done
  echo
  echo "Fix by naming what is actually proved, or — if the point is that it is"
  echo "NOT proved — tag the citation 'NOT-PROVED:' so the retraction is explicit."
  exit 1
fi

echo "proof-citation check OK"
