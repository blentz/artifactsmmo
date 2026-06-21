-- GENERATED from src/artifactsmmo_cli/ai/tiers/strategic_value.py (sha256: b6a1bb858b619e9d71692851f4734f6b2d26082bbfae65bdc2ed0ed0026eab4b) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.StrategicValue

/-- Extracted from `strategic_value_pure` (line 56). -/
def strategic_value_pure (combat_raw : Int) (wisdom : Int) (prospecting : Int) (inventory_space : Int) (haste : Int) (combat_weight : Int) (wisdom_weight : Int) (prospecting_weight : Int) (inventory_weight : Int) (haste_weight : Int) :
    Int :=
  (((((combat_raw * combat_weight) + (wisdom * wisdom_weight)) + (prospecting * prospecting_weight)) + (inventory_space * inventory_weight)) + (haste * haste_weight))

end Extracted.StrategicValue
