-- GENERATED from src/artifactsmmo_cli/ai/learning/scalar_core.py (sha256: d675f50b15f08654687a909686e4625c0d8e0c11fe4f027696961e1767cdb5ad) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.ScalarCore

/-- Extracted from `scalar_yield_exact` (line 41). -/
def scalar_yield_exact (char_xp : Rat) (level : Int) (skill_xp : List (String × Rat)) (active_skills : List String) (gold : Rat) (tasks_coins : Rat) (coin_value : Rat) (baseline_w : Rat) (relevant_w : Rat) (gold_per_xp : Rat) (char_scalar : Rat) :
    Rat :=
  let char_xp_component := ((char_xp * char_scalar) * (mkRat (level + 1) 1))
  let skill_xp_component := (mkRat 0 1)
  let skill_xp_component := List.foldl
    (fun skill_xp_component _x =>
      let skill_name := (_x.1)
      let delta := (_x.2)
      let skill_xp_component := (skill_xp_component + (delta * (if (List.contains active_skills skill_name) then relevant_w else baseline_w)))
      skill_xp_component)
    skill_xp_component skill_xp
  let gold_component := (gold / gold_per_xp)
  let coin_component := ((tasks_coins * coin_value) / gold_per_xp)
  (((char_xp_component + skill_xp_component) + gold_component) + coin_component)

/-- Extracted from `coins_spent_from_delta` (line 113). -/
def coins_spent_from_delta (received : Int) (delta_inv_used : Int) :
    Int :=
  (received - delta_inv_used)

end Extracted.ScalarCore
