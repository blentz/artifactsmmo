-- GENERATED from src/artifactsmmo_cli/ai/tiers/strategic_value.py (sha256: ea623dc3378d95ad7a932b7fc8aefcc397033cd4e918fa16e595b72c68a926ad) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.StrategicValue

/-- Extracted from `strategic_value_pure` (line 56). -/
def strategic_value_pure (combat_raw : Int) (wisdom : Int) (prospecting : Int) (inventory_space : Int) (haste : Int) (combat_weight : Int) (wisdom_weight : Int) (prospecting_weight : Int) (inventory_weight : Int) (haste_weight : Int) :
    Int :=
  (((((combat_raw * combat_weight) + (wisdom * wisdom_weight)) + (prospecting * prospecting_weight)) + (inventory_space * inventory_weight)) + (haste * haste_weight))

end Extracted.StrategicValue
