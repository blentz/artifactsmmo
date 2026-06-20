-- GENERATED from src/artifactsmmo_cli/ai/min_plan_length.py (sha256: 1012ad0cdf68c3736a776bbc60324f87c2f2785c1f3b43d6bab9c4922f080ae4) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).
import Formal.Extracted.GatherFloor
import Formal.Extracted.MinCrafts
import Formal.Extracted.MinGathers

namespace Extracted.MinPlanLength

/-- Extracted from `min_plan_length` (line 14). -/
def min_plan_length (item : String) (qty : Int) (recipes : List (String × List (String × Int))) (owned : List (String × Int)) (max_gather_yield : Int) (equip : Bool) :
    Int :=
  let mints := (Extracted.GatherFloor.ceil_gathers (Extracted.MinGathers.min_gathers item qty recipes owned) max_gather_yield)
  let crafts := (Extracted.MinCrafts.min_crafts item qty recipes owned)
  ((mints + crafts) + (if equip then 1 else 0))

end Extracted.MinPlanLength
