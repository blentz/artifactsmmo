-- GENERATED from src/artifactsmmo_cli/ai/tiers/progression_choice.py (sha256: d077ceff4257731d5d07a1580d69b08ef4c404a5a83c2a3a8e2a488300d654f6) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.ProgressionChoice

/-- Extracted from `@dataclass ProgressionCandidate` (line 43). -/
structure ProgressionCandidate where
  identity : String
  acquire_cost : Int
  reachable_level : Int
  cycles_to_fifty : Int
  failed : Bool

/-- Extracted module constant `TARGET_LEVEL` (line 31). -/
def TARGET_LEVEL : Int := 50

/-- Extracted module constant `_BAND_FINITE` (line 35). -/
def _BAND_FINITE : Int := 0

/-- Extracted module constant `_BAND_UNREACHABLE` (line 36). -/
def _BAND_UNREACHABLE : Int := 1

/-- Extracted module constant `_BAND_FAILED` (line 37). -/
def _BAND_FAILED : Int := 2

/-- Extracted from `candidate_band` (line 69). -/
def candidate_band (c : ProgressionCandidate) :
    Int :=
  (if (c.failed)
   then
    _BAND_FAILED
   else
    (if (decide ((c.reachable_level) < TARGET_LEVEL))
     then
      _BAND_UNREACHABLE
     else
      _BAND_FINITE))

/-- Extracted from `objective_j` (line 82). -/
def objective_j (c : ProgressionCandidate) :
    Int :=
  ((c.acquire_cost) + (c.cycles_to_fifty))

/-- Extracted from `sort_key` (line 91). -/
def sort_key (c : ProgressionCandidate) :
    (Int × Int × Int) :=
  let band := (candidate_band c)
  (if (decide (band = _BAND_FINITE))
   then
    (band, (objective_j c), 0)
   else
    (if (decide (band = _BAND_UNREACHABLE))
     then
      (band, (TARGET_LEVEL - (c.reachable_level)), (c.acquire_cost))
     else
      (band, 0, 0)))

end Extracted.ProgressionChoice
