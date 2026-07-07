-- GENERATED from src/artifactsmmo_cli/ai/tiers/next_tier_cap.py (sha256: 58508167b9f60b4ead8f1f225a1b1cebecfebdb2b42e397df06be47b06160621) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.NextTierCap

/-- Extracted from `@dataclass SkillItem` (line 22). -/
structure SkillItem where
  craft_skill : String
  craft_level : Int
  item_level : Int
  gear_relevant : Bool

/-- Extracted from `next_tier_cap_pure` (line 17). -/
def next_tier_cap_pure (skill : String) (char_level : Int) (items : List SkillItem) (max_skill_level : Int) :
    Int :=
  let floor : Int := (((Int.fdiv char_level 10) + 1) * 10)
  let best : Int := 0
  let best := List.foldl
    (fun best it =>
      let best := (if ((it.gear_relevant) && (decide ((it.craft_skill) = skill)) && (decide (floor ≤ (it.item_level))) && (decide ((it.item_level) ≤ (floor + 9))) && (decide ((it.craft_level) > best))) then (it.craft_level) else best)
      best)
    best items
  (if (decide (best ≤ 0))
   then
    0
   else
    (if (decide (best > max_skill_level))
     then
      max_skill_level
     else
      best))

/-- Extracted from `next_tier_dampened_pure` (line 43). -/
def next_tier_dampened_pure (current_skill : Int) (next_tier_cap : Int) :
    Bool :=
  ((decide (next_tier_cap > 0)) && (decide (current_skill ≥ next_tier_cap)))

end Extracted.NextTierCap
