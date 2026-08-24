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
#   1. DECLARATION — `theorem foo`, `def foo`, `abbrev foo`, ... in a .lean file,
#                    resolved by its FULLY-QUALIFIED name: the enclosing
#                    `namespace` chain plus the declared name. See NAMESPACES.
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
# NAMESPACES ARE PART OF THE NAME (2026-08-24). The DECLARATION arm used to
# take the LEAF (`${ident##*.}`) and grep the whole tree for it, so a citation
# with the WRONG namespace resolved as long as the leaf existed ANYWHERE.
# Two live citations disagreed about the namespace of `interleaveDue_reaches`
# and BOTH passed — which is precisely the failure mode this file exists to
# prevent, one level up: a reader who runs `#check` on the cited name gets
# "unknown identifier" and cannot tell a typo from a deleted proof. So the
# index below is built namespace-aware and the match is EXACT.
#
# A citation is a Lean identifier, so the arbiter is what Lean itself would
# accept — the `namespace` a declaration is written under, NOT the path of the
# file it lives in. Those two differ in this tree by design: the summation
# argument for `interleaveDue_reaches` needs mathlib, mathlib is quarantined to
# the liveness tier, so the theorem is written under `namespace
# Formal.ProgressionTree` inside `formal/Formal/Liveness/InterleaveNoStarvation
# .lean`. `Formal.ProgressionTree.interleaveDue_reaches` is the name that
# resolves; the path-derived `Formal.Liveness.InterleaveNoStarvation
# .interleaveDue_reaches` is not a name at all and now fails. Paths remain
# citable through shape 2, which is what shape 2 is for.
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

INDEX="$(mktemp)"
trap 'rm -f "$INDEX"' EXIT

# The fully-qualified name of every declaration in the tree, one per line.
# Built once (a per-citation `grep -r` over 227 files was the old cost too).
#
# The awk tracks `namespace`/`section`/`end` nesting per file and skips block
# comments, so prose inside a `/-- ... -/` that happens to begin "theorem foo"
# does not mint an index entry. Names carrying a prime (`foo'`) are skipped
# outright: CITATION_RE cannot express one, so indexing it under its unprimed
# spelling could only ever let a WRONG citation resolve.
build_index() {
  [ -d "$LEAN_ROOT" ] || return 0
  find "$LEAN_ROOT" -name "*.lean" -type f -print0 | xargs -0 -r awk '
    function qualified(   i, s) {
      s = ""
      for (i = 1; i <= depth; i++)
        if (kind[i] == "ns") s = (s == "" ? name[i] : s "." name[i])
      return s
    }
    FNR == 1 { depth = 0; cdepth = 0 }
    {
      line = $0
      sub(/--.*$/, "", line)
      was_open = (cdepth > 0)
      opens = gsub(/\/-/, "&", line)
      closes = gsub(/-\//, "&", line)
      cdepth += opens - closes
      if (cdepth < 0) cdepth = 0
      if (was_open) next
      sub(/^[ \t]+/, "", line)
      sub(/^@\[[^]]*\][ \t]*/, "", line)
      nf = split(line, f, /[ \t]+/)
      if (nf == 0) next
      if (f[1] == "namespace" && nf >= 2) {
        depth++; name[depth] = f[2]; kind[depth] = "ns"; next
      }
      if (f[1] == "section") { depth++; name[depth] = ""; kind[depth] = "sec"; next }
      if (f[1] == "end") { if (depth > 0) depth--; next }
      i = 1
      while (f[i] == "private" || f[i] == "protected" || f[i] == "noncomputable" \
             || f[i] == "partial" || f[i] == "scoped" || f[i] == "unsafe") i++
      if (f[i] !~ /^(def|theorem|lemma|abbrev|structure|inductive|instance|axiom|class)$/) next
      if (i + 1 > nf) next
      tok = f[i + 1]
      decl = ""
      for (k = 1; k <= length(tok); k++) {
        c = substr(tok, k, 1)
        if (c ~ /[A-Za-z0-9_.]/) decl = decl c; else break
      }
      if (decl == "") next
      if (substr(tok, length(decl) + 1, 1) == "\047") next
      prefix = qualified()
      print (prefix == "" ? decl : prefix "." decl)
    }
  ' | sort -u
}

build_index > "$INDEX"

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
        # 1. DECLARATION — exact fully-qualified name, namespace included.
        if grep -Fxq -- "$ident" "$INDEX"; then
          continue
        fi
        # 2. MODULE — Formal.A.B.C maps to formal/Formal/A/B/C.lean.
        local relpath="${ident#Formal.}"
        if [ -f "$LEAN_ROOT/${relpath//./\/}.lean" ]; then
          continue
        fi
        # Diagnostic: the leaf may exist under a DIFFERENT namespace, which is
        # the wrong-namespace defect rather than a missing proof.
        local leaf="${ident##*.}"
        local elsewhere
        # `|| true`: with `pipefail`, a no-match grep would abort the whole
        # check under `set -e` — silently, before a single violation printed.
        elsewhere="$( { grep -E "(^|\.)${leaf}\$" "$INDEX" || true; } | head -3 | tr '\n' ' ')"
        if [ -n "$elsewhere" ]; then
          violations+=("$pyfile:$lineno: $ident — wrong namespace; declared as: $elsewhere")
        else
          violations+=("$pyfile:$lineno: $ident — no such declaration or module")
        fi
      done < <(printf '%s\n' "$text" | grep -oE "$CITATION_RE" || true)
    done < <(grep -nE "$CITATION_RE" "$pyfile" || true)
  done < <(find "$dir" -name "*.py" -type f | sort)
}

scan_dir "src"
scan_dir "formal/diff"

if [ ${#violations[@]} -gt 0 ]; then
  echo "PROOF-CITATION CHECK FAILED — these name nothing in $LEAN_ROOT:"
  for v in "${violations[@]}"; do
    echo "  $v"
  done
  echo
  echo "Fix by naming what is actually proved — INCLUDING its namespace, which"
  echo "is the namespace the declaration is written under, not its file path —"
  echo "or, if the point is that it is NOT proved, tag the citation"
  echo "'NOT-PROVED:' so the retraction is explicit."
  exit 1
fi

echo "proof-citation check OK"
