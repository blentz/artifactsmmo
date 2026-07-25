#!/usr/bin/env bash
# Audit-list drift gate: Formal/Audit.lean must be exactly what
# scripts/gen_audit.py derives from Formal/Manifest.lean.
#
# The two files were hand-maintained and had drifted apart in BOTH directions —
# 216 declarations carried a Manifest traceability row while nothing scanned
# their axioms, and 112 were scanned with no row. Audit.lean is now generated,
# so the only way to widen the audited surface is to add a Manifest row, and
# this check fails if the generated file is stale.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."   # repo root
uv run python scripts/gen_audit.py --check
