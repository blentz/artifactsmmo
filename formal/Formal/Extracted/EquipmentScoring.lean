-- GENERATED from src/artifactsmmo_cli/ai/equipment/scoring.py (sha256: 899aff7204baf2c9ddbdf3ac7e8f413901cd1539868cf87a6d2201d8569eb81e) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.EquipmentScoring

/-- Python `dict.get(k, default)` over an insertion-ordered association list:
first matching value, else the default (value-polymorphic). -/
def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d

/-- Extracted from `weapon_score_raw_pure` (line 10). -/
def weapon_score_raw_pure (elements : List String) (attack : List (String × Int)) (critical_strike : Int) (monster_resistance : List (String × Int)) :
    Int :=
  let score := 0
  let score := List.foldl
    (fun score elem =>
      let score := (score + ((_dictGetD attack elem 0) * (max 0 (100 - (_dictGetD monster_resistance elem 0)))))
      score)
    score elements
  (score * (200 + critical_strike))

/-- Extracted from `weapon_score_pure` (line 40). -/
def weapon_score_pure (elements : List String) (attack : List (String × Int)) (subtype : String) (critical_strike : Int) (monster_resistance : List (String × Int)) :
    Int :=
  let non_tool_bonus := (if (decide (subtype = "tool")) then 0 else 1)
  ((2 * (weapon_score_raw_pure elements attack critical_strike monster_resistance)) + non_tool_bonus)

/-- Extracted from `gather_score_pure` (line 53). -/
def gather_score_pure (skill_effects : List (String × Int)) (skill : String) :
    Int :=
  (_dictGetD skill_effects skill 0)

/-- Extracted from `armor_score_pure` (line 63). -/
def armor_score_pure (elements : List String) (resistance : List (String × Int)) (monster_attack : List (String × Int)) (hp_bonus : Int) (wisdom : Int) (prospecting : Int) (inventory_space : Int) (haste : Int) (lifesteal : Int) :
    Int :=
  let score := 0
  let score := List.foldl
    (fun score elem =>
      let score := (score + ((_dictGetD monster_attack elem 0) * (_dictGetD resistance elem 0)))
      score)
    score elements
  ((((((score + hp_bonus) + wisdom) + prospecting) + inventory_space) + haste) + lifesteal)

end Extracted.EquipmentScoring
