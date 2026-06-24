-- GENERATED from src/artifactsmmo_cli/ai/tiers/skill_step_dispatch.py (sha256: 358de682e93541183130f26d1156471cf504e73f017856ee44a76c9901c3cacd) — DO NOT EDIT
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
