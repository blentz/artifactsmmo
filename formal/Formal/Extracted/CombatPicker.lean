-- GENERATED from src/artifactsmmo_cli/ai/combat_picker.py (sha256: ad1fadb952d413a27bd5bbe8b1f8a540819daa42026476a3a95bbfd415679a05) — DO NOT EDIT
-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).

namespace Extracted.CombatPicker

/-- Extracted from `pick_winnable_monster_pure` (line 32). -/
def pick_winnable_monster_pure (char_level : Int) (monsters : List (String × Int)) (is_winnable : (String → Bool)) (xp_positive : (String → Bool)) :
    Option String :=
  let min_level := (max 1 (char_level - 1))
  let max_level := (char_level + 2)
  let best : Option (String × Int) := none
  let best := List.foldl
    (fun best _x =>
      let code := (_x.1)
      let level := (_x.2)
      (if (!((decide (min_level ≤ level)) && (decide (level ≤ max_level))))
       then
        best
       else
        (if (!(is_winnable code))
         then
          best
         else
          (match best with
          | none =>
              let best := (some (code, level))
              best
          | some best_1 =>
            (if (decide (level > (best_1.2)))
             then
              let best := (some (code, level))
              best
             else
              best)))))
    best monsters
  (match best with
  | some best_2 =>
    (some (best_2.1))
  | none =>
    let best := List.foldl
      (fun best _x =>
        let code := (_x.1)
        let level := (_x.2)
        (if ((decide (level > max_level)) || (!(xp_positive code)) || (!(is_winnable code)))
         then
          best
         else
          (match best with
          | none =>
              let best := (some (code, level))
              best
          | some best_3 =>
            (if (decide (level > (best_3.2)))
             then
              let best := (some (code, level))
              best
             else
              best))))
      best monsters
    (match best with
    | some best_4 => (some (best_4.1))
    | none => none))

end Extracted.CombatPicker
