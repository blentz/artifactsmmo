-- GENERATED from src/artifactsmmo_cli/ai/equipment/scoring.py (sha256: 3efd93da67febb407dae49837ff1775967ac57dbda914e7792d488398da95669) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.EquipmentScoring

/-- Python `dict.get(k, default)` over an insertion-ordered association list:
first matching value, else the default (value-polymorphic). -/
def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=
  match m with
  | [] => d
  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d

/-- Extracted from `weapon_score_raw_pure` (line 10). -/
def weapon_score_raw_pure (elements : List String) (attack : List (String × Int)) (monster_resistance : List (String × Int)) :
    Int :=
  let score := 0
  let score := List.foldl
    (fun score elem =>
      let score := (score + ((_dictGetD attack elem 0) * (max 0 (100 - (_dictGetD monster_resistance elem 0)))))
      score)
    score elements
  score

/-- Extracted from `weapon_score_pure` (line 28). -/
def weapon_score_pure (elements : List String) (attack : List (String × Int)) (subtype : String) (monster_resistance : List (String × Int)) :
    Int :=
  let non_tool_bonus := (if (decide (subtype = "tool")) then 0 else 1)
  ((2 * (weapon_score_raw_pure elements attack monster_resistance)) + non_tool_bonus)

/-- Extracted from `gather_score_pure` (line 39). -/
def gather_score_pure (skill_effects : List (String × Int)) (skill : String) :
    Int :=
  (_dictGetD skill_effects skill 0)

/-- Extracted from `armor_score_pure` (line 49). -/
def armor_score_pure (elements : List String) (resistance : List (String × Int)) (monster_attack : List (String × Int)) :
    Int :=
  let score := 0
  let score := List.foldl
    (fun score elem =>
      let score := (score + ((_dictGetD monster_attack elem 0) * (_dictGetD resistance elem 0)))
      score)
    score elements
  score

end Extracted.EquipmentScoring
