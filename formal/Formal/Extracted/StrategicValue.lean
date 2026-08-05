-- GENERATED from src/artifactsmmo_cli/ai/tiers/strategic_value.py (sha256: e2b49b82b52b6568a577e8ca593a70410165f08db70732861f9afb51a7da518d) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.StrategicValue

/-- Extracted from `strategic_value_pure` (line 86). -/
def strategic_value_pure (combat_raw : Int) (wisdom : Int) (prospecting : Int) (inventory_space : Int) (haste : Int) (combat_weight : Int) (wisdom_weight : Int) (prospecting_weight : Int) (inventory_weight : Int) (haste_weight : Int) :
    Int :=
  (((((combat_raw * combat_weight) + (wisdom * wisdom_weight)) + (prospecting * prospecting_weight)) + (inventory_space * inventory_weight)) + (haste * haste_weight))

end Extracted.StrategicValue
