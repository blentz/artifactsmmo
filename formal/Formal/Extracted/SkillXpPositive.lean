-- GENERATED from src/artifactsmmo_cli/ai/skill_xp_positive.py (sha256: fbbed247a2ec0b2444dc5b2d32e8a8c0692fb2abf0d46945c97fad669288ac65) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillXpPositive

/-- Extracted module constant `GREY_SKILL_GAP` (line 89). -/
def GREY_SKILL_GAP : Int := 11

/-- Extracted from `skill_xp_positive` (line 103). -/
def skill_xp_positive (content_level : Int) (skill_level : Int) :
    Bool :=
  ((decide (content_level ≥ 1)) && (decide (skill_level < (content_level + GREY_SKILL_GAP))))

end Extracted.SkillXpPositive
