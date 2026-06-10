#!/usr/bin/env bash
# Extraction-drift gate (mechanical extraction P1).
#
# The Lean models under formal/Formal/Extracted/ are GENERATED from the
# Python pure cores by scripts/extract_lean.py. This gate re-runs the
# extractor in --check mode: regeneration must be a byte-identical no-op.
# Any drift (Python core edited without regenerating, or a hand edit to a
# generated file) fails loudly with a diff. The bridge proofs in
# Formal/Extracted/Bridges.lean are then compiled by the kernel build,
# so a semantic change that survives regeneration breaks the bridges.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."   # repo root

uv run python scripts/extract_lean.py --check
