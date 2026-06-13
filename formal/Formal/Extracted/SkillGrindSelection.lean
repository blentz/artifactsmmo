-- GENERATED from src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py (sha256: 31a0980267b7d80e4f790631de119331536b337ec49bf3ee137df4ca31bfc88d) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillGrindSelection

/-- Extracted from `@dataclass GrindCandidate` (line 22). -/
structure GrindCandidate where
  code : String
  craft_skill : String
  craft_level : Int
  mats_missing : Int
  obtainable : Bool

/-- Extracted from `_beats` (line 33). -/
def _beats (c : GrindCandidate) (best : Option GrindCandidate) :
    Bool :=
  (match best with
  | none =>
    true
  | some best_1 =>
    (if (!(decide ((c.mats_missing) = (best_1.mats_missing))))
     then
      (decide ((c.mats_missing) < (best_1.mats_missing)))
     else
      (if (!(decide ((c.craft_level) = (best_1.craft_level))))
       then
        (decide ((c.craft_level) > (best_1.craft_level)))
       else
        false)))

/-- Extracted from `skill_grind_selection_pure` (line 48). -/
def skill_grind_selection_pure (skill : String) (current_level : Int) (candidates : List GrindCandidate) :
    String :=
  let best : Option GrindCandidate := none
  let best := List.foldl
    (fun best c =>
      (if ((!(decide ((c.craft_skill) = skill))) || (decide ((c.craft_level) > current_level)) || (!(c.obtainable)))
       then
        best
       else
        let best := (if (_beats c best) then (some c) else best)
        best))
    best candidates
  (match best with
  | some best_1 => (best_1.code)
  | none => "")

end Extracted.SkillGrindSelection
