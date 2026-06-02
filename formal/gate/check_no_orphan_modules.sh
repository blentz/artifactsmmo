#!/usr/bin/env bash
# Orphan-module check.
#
# Every Lean module under Formal/ must be imported by Formal.lean
# (the project root file). Modules that aren't imported don't get
# compiled by `lake build` against the root target — so a subagent
# could silently ship a sorry-laden module that "compiles in isolation"
# but never hits the gate.
#
# This script detects orphan modules and FAILS the gate if any exist.
#
# Phase: perimeter-hardening (post-Phase 24-fix). The orphan-module
# pattern caused Phase 23a, 23b, and 23d-6 subagents to ship broken
# Lean while claiming "build clean".

set -euo pipefail

cd "$(dirname "$0")/.."

ROOT="Formal.lean"
SRC_DIR="Formal"

if [ ! -f "$ROOT" ]; then
  echo "ERROR: $ROOT not found"
  exit 1
fi

# Collect all Lean modules under Formal/, excluding LivenessAudit (an
# audit-only module that imports content modules; not itself meant to
# be imported BY Formal.lean — it's a separate audit entry).
declare -a all_modules
while IFS= read -r f; do
  # Convert path Formal/Liveness/Foo.lean → Formal.Liveness.Foo
  rel="${f#./}"  # drop ./
  mod="${rel%.lean}"
  mod="${mod//\//.}"
  # Skip the audit-only module + the root itself
  case "$mod" in
    # Audit/Manifest modules import content modules to print axioms;
    # they're entry points run directly by gate scripts, not imported by Formal.lean.
    Formal.LivenessAudit) continue ;;
    Formal.Audit) continue ;;
    Formal.Manifest) continue ;;
    Formal) continue ;;
  esac
  all_modules+=("$mod")
done < <(find "$SRC_DIR" -name "*.lean" -type f)

# Collect all imports from Formal.lean.
declare -a imported
while IFS= read -r line; do
  # `import Formal.Foo` → `Formal.Foo`
  imp=$(echo "$line" | sed -n 's/^import \([A-Za-z0-9._]*\).*/\1/p')
  if [ -n "$imp" ]; then
    imported+=("$imp")
  fi
done < "$ROOT"

# Find orphans: modules in all_modules but not in imported.
orphans=()
for m in "${all_modules[@]}"; do
  found=0
  for i in "${imported[@]}"; do
    if [ "$m" = "$i" ]; then
      found=1
      break
    fi
  done
  if [ $found -eq 0 ]; then
    orphans+=("$m")
  fi
done

if [ ${#orphans[@]} -gt 0 ]; then
  echo "ORPHAN MODULE CHECK FAILED — these modules are not imported by Formal.lean:"
  for o in "${orphans[@]}"; do
    echo "  $o"
  done
  echo ""
  echo "Modules not imported by Formal.lean don't get gated. Subagents have"
  echo "shipped broken Lean by exploiting this (Phase 23a, 23b, 23d-6)."
  echo "Add the missing 'import ...' line to Formal.lean."
  exit 1
fi

echo "orphan module check OK (${#all_modules[@]} modules, all imported)"
