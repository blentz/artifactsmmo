-- GENERATED from src/artifactsmmo_cli/ai/skill_xp_positive.py (sha256: 21c2648df24e65ed09441a9187df9c4c91e1b09e6347cd300c600d17affb56ef) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillXpPositive

/-- Extracted module constant `GREY_SKILL_GAP` (line 49). -/
def GREY_SKILL_GAP : Int := 11

/-- Extracted from `skill_xp_positive` (line 57). -/
def skill_xp_positive (content_level : Int) (skill_level : Int) :
    Bool :=
  ((decide (content_level ≥ 1)) && (decide (skill_level < (content_level + GREY_SKILL_GAP))))

end Extracted.SkillXpPositive
