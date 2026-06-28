-- GENERATED from src/artifactsmmo_cli/ai/tiers/equip_value.py (sha256: e7c6d81682a2263f618ba967cc68c56dd57afbda0305d422fdb01b0dfc8af897) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.EquipValue

/-- `abs` on `Int` (Python `abs`): non-negative magnitude. -/
def _intAbs (i : Int) : Int := Int.ofNat i.natAbs

/-- Python `dict.get(k, default)` over an insertion-ordered association list:
first matching value, else the default (value-polymorphic). -/
def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d

/-- Extracted from `tool_value_pure` (line 8). -/
def tool_value_pure (skill_effects : List (String × Int)) (skill : String) :
    Int :=
  let effect := (_dictGetD skill_effects skill 0)
  (_intAbs effect)

end Extracted.EquipValue
