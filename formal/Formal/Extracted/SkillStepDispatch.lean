-- GENERATED from src/artifactsmmo_cli/ai/tiers/skill_step_dispatch.py (sha256: e7f0ea0cf05f4e9ff6bb15c74f174e60c68da6479235a5a018f9306dc2cada5a) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillStepDispatch

/-- Extracted from `combine_dispatch_pure` (line 96). -/
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
