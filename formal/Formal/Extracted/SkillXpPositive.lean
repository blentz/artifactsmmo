-- GENERATED from src/artifactsmmo_cli/ai/skill_xp_positive.py (sha256: 471b755f7de0647d1341b364703d7b342ae81a634b727d66406bdf9d510eeb64) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillXpPositive

/-- Extracted module constant `GREY_SKILL_GAP` (line 73). -/
def GREY_SKILL_GAP : Int := 11

/-- Extracted from `skill_xp_positive` (line 81). -/
def skill_xp_positive (content_level : Int) (skill_level : Int) :
    Bool :=
  ((decide (content_level ≥ 1)) && (decide (skill_level < (content_level + GREY_SKILL_GAP))))

end Extracted.SkillXpPositive
