-- GENERATED from src/artifactsmmo_cli/ai/tiers/equip_value.py (sha256: 0254c3f2879366a388ea36fe2f3f4644b266b783eebe3b5636d8b390bc91e87e) — DO NOT EDIT
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

/-- Extracted from `equip_value_pure` (line 6). -/
def equip_value_pure (attack : Int) (resistance : Int) (hp_restore : Int) (hp_bonus : Int) (dmg : Int) (critical_strike : Int) (wisdom : Int) (prospecting : Int) (subtype : String) :
    Int :=
  let raw := (((((((attack + resistance) + hp_restore) + hp_bonus) + dmg) + critical_strike) + wisdom) + prospecting)
  let non_tool_bonus := (if (decide (subtype = "tool")) then 0 else 1)
  ((2 * raw) + non_tool_bonus)

/-- Extracted from `tool_value_pure` (line 25). -/
def tool_value_pure (skill_effects : List (String × Int)) (skill : String) :
    Int :=
  let effect := (_dictGetD skill_effects skill 0)
  (_intAbs effect)

end Extracted.EquipValue
