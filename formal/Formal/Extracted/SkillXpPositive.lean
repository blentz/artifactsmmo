-- GENERATED from src/artifactsmmo_cli/ai/skill_xp_positive.py (sha256: d0564ae7f87d6a64f4bf946dd8ed1bf7c096d489ac555d727a0d999a85730c65) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.SkillXpPositive

/-- Extracted module constant `GREY_SKILL_GAP` (line 88). -/
def GREY_SKILL_GAP : Int := 11

/-- Extracted from `skill_xp_positive` (line 96). -/
def skill_xp_positive (content_level : Int) (skill_level : Int) :
    Bool :=
  ((decide (content_level ≥ 1)) && (decide (skill_level < (content_level + GREY_SKILL_GAP))))

end Extracted.SkillXpPositive
