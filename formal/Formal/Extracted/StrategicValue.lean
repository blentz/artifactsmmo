-- GENERATED from src/artifactsmmo_cli/ai/tiers/strategic_value.py (sha256: 39abb21ff591af276123d9c14fc26ff3a22311eebb075e52cf79bd0f0867fa44) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.StrategicValue

/-- Extracted from `strategic_value_pure` (line 66). -/
def strategic_value_pure (combat_raw : Int) (wisdom : Int) (prospecting : Int) (inventory_space : Int) (haste : Int) (combat_weight : Int) (wisdom_weight : Int) (prospecting_weight : Int) (inventory_weight : Int) (haste_weight : Int) :
    Int :=
  (((((combat_raw * combat_weight) + (wisdom * wisdom_weight)) + (prospecting * prospecting_weight)) + (inventory_space * inventory_weight)) + (haste * haste_weight))

end Extracted.StrategicValue
