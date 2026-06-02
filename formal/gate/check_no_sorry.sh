#!/usr/bin/env bash
# No-sorry guard.
#
# Greps every Lean module for `sorry`, `admit`, `native_decide` and
# FAILS the gate if any are present in committed files.
#
# Existing axiom-check scripts cover axiom budget; this complements
# them by detecting outright stubs.

set -euo pipefail

cd "$(dirname "$0")/.."

# Search every .lean file under Formal/ for forbidden tactics/declarations.
# Use word boundaries to avoid matching `sorry_in_docstring` or similar
# false positives in comments. Comments using `-- ` or `/-- ... -/` ARE
# allowed to mention these terms (documentation), so we strip comment
# lines before grepping.

violations=()
while IFS= read -r f; do
  # Strip comments: drop lines starting with `--` (after optional ws),
  # and block comments `/- ... -/`. Use a simple AWK pass.
  body=$(awk '
    BEGIN { in_block = 0 }
    {
      line = $0
      # Strip block comments. A line may open/close on the same line.
      while (match(line, /\/-/)) {
        before = substr(line, 1, RSTART - 1)
        rest = substr(line, RSTART + 2)
        if (match(rest, /-\//)) {
          line = before substr(rest, RSTART + 2)
        } else {
          line = before
          in_block = 1
          break
        }
      }
      if (in_block) {
        if (match(line, /-\//)) {
          line = substr(line, RSTART + 2)
          in_block = 0
        } else {
          next
        }
      }
      # Strip line comments.
      sub(/--.*$/, "", line)
      print line
    }
  ' "$f")
  if echo "$body" | grep -qwE 'sorry|admit|native_decide'; then
    violations+=("$f")
  fi
done < <(find Formal -name "*.lean" -type f)

if [ ${#violations[@]} -gt 0 ]; then
  echo "NO-SORRY CHECK FAILED — these modules contain sorry/admit/native_decide:"
  for v in "${violations[@]}"; do
    echo "  $v"
    awk '
      BEGIN { in_block = 0 }
      {
        line = $0
        while (match(line, /\/-/)) {
          before = substr(line, 1, RSTART - 1)
          rest = substr(line, RSTART + 2)
          if (match(rest, /-\//)) {
            line = before substr(rest, RSTART + 2)
          } else {
            line = before
            in_block = 1
            break
          }
        }
        if (in_block) {
          if (match(line, /-\//)) {
            line = substr(line, RSTART + 2)
            in_block = 0
          } else { next }
        }
        sub(/--.*$/, "", line)
        if (line ~ /sorry|admit|native_decide/) {
          print "    line " NR ": " $0
        }
      }
    ' "$v"
  done
  exit 1
fi

echo "no-sorry check OK"
