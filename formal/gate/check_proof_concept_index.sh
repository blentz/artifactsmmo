#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."   # repo root
uv run python scripts/gen_proof_concept_index.py --check
