-- GENERATED from src/artifactsmmo_cli/ai/skill_xp_positive.py (sha256: 0651c7cdb1d26cfc7f8a9a984896b7d856f25892ddca1ceac198de2ed983cc2b) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillXpPositive

/-- Extracted module constant `GREY_SKILL_GAP` (line 42). -/
def GREY_SKILL_GAP : Int := 11

/-- Extracted from `skill_xp_positive` (line 50). -/
def skill_xp_positive (content_level : Int) (skill_level : Int) :
    Bool :=
  ((decide (content_level ≥ 1)) && (decide (skill_level < (content_level + GREY_SKILL_GAP))))

end Extracted.SkillXpPositive
