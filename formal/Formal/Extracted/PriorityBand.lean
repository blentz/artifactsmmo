-- GENERATED from src/artifactsmmo_cli/ai/priority_band.py (sha256: 69efe5c0d4bdccc5e55ffe755ca1caf5aa26261598522ad808fe35592bf9e309) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.PriorityBand

/-- Extracted from `clamp_into_band` (line 18). -/
def clamp_into_band (floor : Rat) (ceiling : Rat) (bonus : Rat) :
    Rat :=
  (min ceiling (max floor (floor + bonus)))

end Extracted.PriorityBand
