-- GENERATED from src/artifactsmmo_cli/ai/tiers/skill_target_curve.py (sha256: f01b969bab01d6ce076cc68f14d9ca01b50c36a977b34e4025d7770b305fbba9) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillTargetCurve

/-- Extracted from `@dataclass SkillItem` (line 19). -/
structure SkillItem where
  craft_skill : String
  craft_level : Int
  item_level : Int
  gear_relevant : Bool

/-- Extracted from `skill_curve_target_pure` (line 29). -/
def skill_curve_target_pure (skill : String) (char_level : Int) (items : List SkillItem) (lookahead : Int) (max_skill_level : Int) :
    Int :=
  let best : Int := 0
  let best := List.foldl
    (fun best it =>
      let best := (if ((it.gear_relevant) && (decide ((it.craft_skill) = skill)) && (decide ((it.item_level) ≤ (char_level + lookahead))) && (decide ((it.craft_level) > best))) then (it.craft_level) else best)
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

end Extracted.SkillTargetCurve
