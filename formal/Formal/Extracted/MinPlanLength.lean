-- GENERATED from src/artifactsmmo_cli/ai/min_plan_length.py (sha256: e31b16157264e2b3ebfe6eec3cd6882d75c518ce1f5c31cfba68e026dd80202a) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).
import Formal.Extracted.MinCrafts
import Formal.Extracted.MinGatherSteps

namespace Extracted.MinPlanLength

/-- Extracted from `min_plan_length` (line 39). -/
def min_plan_length (item : String) (qty : Int) (recipes : List (String × List (String × Int))) (owned : List (String × Int)) (max_gather_yield : Int) (equip : Bool) :
    Int :=
  let mints := (Extracted.MinGatherSteps.min_gather_steps item qty recipes owned)
  let crafts := (Extracted.MinCrafts.min_crafts item qty recipes owned)
  ((mints + crafts) + (if equip then 1 else 0))

end Extracted.MinPlanLength
