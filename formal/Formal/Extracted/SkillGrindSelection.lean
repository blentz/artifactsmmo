-- GENERATED from src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py (sha256: f507b11eb8595c32a4311ae9d1dcbc04dc0a90d14b537e29406200d06bb2d916) — DO NOT EDIT
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

/-- Extracted from `_beats` (line 49). -/
def _beats (c : GrindCandidate) (best : Option GrindCandidate) :
    Bool :=
  (match best with
  | none =>
    true
  | some best_1 =>
    let c_steps := (if (c.wanted) then 0 else (c.acquire_steps))
    let best_steps := (if (best_1.wanted) then 0 else (best_1.acquire_steps))
    let c_rate := ((c.craft_level) * best_steps)
    let best_rate := ((best_1.craft_level) * c_steps)
    (if (!(decide (c_rate = best_rate)))
     then
      (decide (c_rate > best_rate))
     else
      (if ((c.wanted) && (!(best_1.wanted)))
       then
        true
       else
        (if ((best_1.wanted) && (!(c.wanted)))
         then
          false
         else
          (if (!(decide ((c.craft_level) = (best_1.craft_level))))
           then
            (decide ((c.craft_level) > (best_1.craft_level)))
           else
            (if (!(decide ((c.acquire_steps) = (best_1.acquire_steps))))
             then
              (decide ((c.acquire_steps) < (best_1.acquire_steps)))
             else
              false))))))

/-- Extracted from `skill_grind_selection_pure` (line 145). -/
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
