-- GENERATED from src/artifactsmmo_cli/ai/tiers/skill_step_dispatch.py (sha256: f4aec9451fd9fde0de9d46a9ea58202b5383d4d6b31f7117af1a35c4d4484f15) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillStepDispatch

/-- Extracted from `combine_dispatch_pure` (line 93). -/
def combine_dispatch_pure (skill : String) (current_level : Int) (committed_skill : String) (committed_level : Int) (full_pick : String) (relaxed_pick : String) :
    (String × String) :=
  (if ((decide (committed_skill = skill)) && (decide (committed_level ≤ current_level)))
   then
    ("suppress", "")
   else
    let pick := (if (!(decide (full_pick = ""))) then full_pick else relaxed_pick)
    (if (!(decide (pick = "")))
     then
      ("grind", pick)
     else
      ("no_grind", "")))

end Extracted.SkillStepDispatch
