-- GENERATED from src/artifactsmmo_cli/ai/min_plan_length.py (sha256: cc9b74faf1fac83003529247f3797aa0d25be09130f64e154520d2d64d73abb2) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).
import Formal.Extracted.MinCrafts
import Formal.Extracted.MinGatherSteps

namespace Extracted.MinPlanLength

/-- Extracted from `min_plan_length` (line 40). -/
def min_plan_length (item : String) (qty : Int) (recipes : List (String × List (String × Int))) (owned : List (String × Int)) (max_gather_yield : Int) (equip : Bool) :
    Int :=
  let mints := (Extracted.MinGatherSteps.min_gather_steps item qty recipes owned)
  let crafts := (Extracted.MinCrafts.min_crafts item qty recipes owned)
  ((mints + crafts) + (if equip then 1 else 0))

end Extracted.MinPlanLength
