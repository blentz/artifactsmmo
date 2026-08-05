-- GENERATED from src/artifactsmmo_cli/ai/equipment/scoring.py (sha256: ca89d8a2001251f45e1b119646efe29957ae461869f3116a25ce72db753e64ab) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.EquipmentScoring

/-- Python `dict.get(k, default)` over an insertion-ordered association list:
first matching value, else the default (value-polymorphic). -/
def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d

/-- Extracted module constant `RULER_SCALE` (line 13). -/
def RULER_SCALE : Int := 2

/-- Extracted from `weapon_score_raw_pure` (line 50). -/
def weapon_score_raw_pure (elements : List String) (attack : List (String × Int)) (critical_strike : Int) (monster_resistance : List (String × Int)) :
    Int :=
  let score := 0
  let score := List.foldl
    (fun score elem =>
      let score := (score + ((_dictGetD attack elem 0) * (max 0 (100 - (_dictGetD monster_resistance elem 0)))))
      score)
    score elements
  (score * (200 + critical_strike))

/-- Extracted from `gear_score_efficiency_pure` (line 90). -/
def gear_score_efficiency_pure (wisdom : Int) (prospecting : Int) (inventory_space : Int) (haste : Int) :
    Int :=
  ((RULER_SCALE * 200) * (((wisdom + prospecting) + inventory_space) + haste))

/-- Extracted from `weapon_score_combat_pure` (line 124). -/
def weapon_score_combat_pure (elements : List String) (attack : List (String × Int)) (subtype : String) (critical_strike : Int) (monster_resistance : List (String × Int)) :
    Int :=
  let non_tool_bonus := (if (decide (subtype = "tool")) then 0 else 1)
  ((RULER_SCALE * (weapon_score_raw_pure elements attack critical_strike monster_resistance)) + non_tool_bonus)

/-- Extracted from `weapon_score_pure` (line 149). -/
def weapon_score_pure (elements : List String) (attack : List (String × Int)) (subtype : String) (critical_strike : Int) (monster_resistance : List (String × Int)) (wisdom : Int) (prospecting : Int) (inventory_space : Int) (haste : Int) :
    Int :=
  ((weapon_score_combat_pure elements attack subtype critical_strike monster_resistance) + (gear_score_efficiency_pure wisdom prospecting inventory_space haste))

/-- Extracted from `gather_score_pure` (line 171). -/
def gather_score_pure (skill_effects : List (String × Int)) (skill : String) :
    Int :=
  (_dictGetD skill_effects skill 0)

/-- Extracted from `armor_score_combat_pure` (line 181). -/
def armor_score_combat_pure (elements : List String) (resistance : List (String × Int)) (monster_attack : List (String × Int)) (monster_resistance : List (String × Int)) (player_attack : List (String × Int)) (dmg : Int) (dmg_elements : List (String × Int)) (critical_strike : Int) (hp_restore : Int) (hp_bonus : Int) (lifesteal : Int) (combat_buff : Int) :
    Int :=
  let defense := 0
  let defense := List.foldl
    (fun defense elem =>
      let defense := (defense + ((_dictGetD monster_attack elem 0) * (_dictGetD resistance elem 0)))
      defense)
    defense elements
  let offense := 0
  let offense := List.foldl
    (fun offense elem =>
      let offense := (offense + (((_dictGetD player_attack elem 0) * (max 0 (100 - (_dictGetD monster_resistance elem 0)))) * ((2 * (dmg + (_dictGetD dmg_elements elem 0))) + critical_strike)))
      offense)
    offense elements
  let flat_combat := (((hp_restore + hp_bonus) + lifesteal) + combat_buff)
  (RULER_SCALE * (((200 * defense) + offense) + (200 * flat_combat)))

/-- Extracted from `armor_score_pure` (line 232). -/
def armor_score_pure (elements : List String) (resistance : List (String × Int)) (monster_attack : List (String × Int)) (monster_resistance : List (String × Int)) (player_attack : List (String × Int)) (dmg : Int) (dmg_elements : List (String × Int)) (critical_strike : Int) (hp_restore : Int) (hp_bonus : Int) (wisdom : Int) (prospecting : Int) (inventory_space : Int) (haste : Int) (lifesteal : Int) (combat_buff : Int) :
    Int :=
  ((armor_score_combat_pure elements resistance monster_attack monster_resistance player_attack dmg dmg_elements critical_strike hp_restore hp_bonus lifesteal combat_buff) + (gear_score_efficiency_pure wisdom prospecting inventory_space haste))

end Extracted.EquipmentScoring
