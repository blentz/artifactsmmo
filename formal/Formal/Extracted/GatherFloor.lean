-- GENERATED from src/artifactsmmo_cli/ai/gather_floor.py (sha256: 33e71d56e7f51d602b5781631472e47a40ae5396fea33490b0f8ebf98efed23f) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.GatherFloor

/-- Extracted from `ceil_gathers` (line 17). -/
def ceil_gathers (units : Int) (max_yield : Int) :
    Int :=
  (Int.fdiv ((units + max_yield) - 1) max_yield)

end Extracted.GatherFloor
