-- GENERATED from src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py (sha256: 6e94039e3210256155aa5e76d10b5ab6582282238fc168c75ec9566088d7bd39) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillGrindSelection

/-- Extracted from `@dataclass GrindCandidate` (line 23). -/
structure GrindCandidate where
  code : String
  craft_skill : String
  craft_level : Int
  acquire_steps : Int
  obtainable : Bool
  wanted : Bool
  xp_positive : Bool

/-- Extracted from `_beats` (line 47). -/
def _beats (c : GrindCandidate) (best : Option GrindCandidate) :
    Bool :=
  (match best with
  | none =>
    true
  | some best_1 =>
    (if ((c.wanted) && (!(best_1.wanted)))
     then
      true
     else
      (if ((best_1.wanted) && (!(c.wanted)))
       then
        false
       else
        (if (!(decide ((c.acquire_steps) = (best_1.acquire_steps))))
         then
          (decide ((c.acquire_steps) < (best_1.acquire_steps)))
         else
          (if (!(decide ((c.craft_level) = (best_1.craft_level))))
           then
            (decide ((c.craft_level) > (best_1.craft_level)))
           else
            false)))))

/-- Extracted from `skill_grind_selection_pure` (line 95). -/
def skill_grind_selection_pure (skill : String) (current_level : Int) (candidates : List GrindCandidate) :
    String :=
  let best : Option GrindCandidate := none
  let best := List.foldl
    (fun best c =>
      (if ((!(decide ((c.craft_skill) = skill))) || (decide ((c.craft_level) > current_level)) || (!(c.obtainable)) || (!(c.xp_positive)))
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
