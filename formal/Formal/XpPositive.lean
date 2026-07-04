-- @concept: combat, planner @property: safety
/-! # XpPositive — the combat-xp positivity gate (server level_penalty band)

Phase C0a (`docs/PLAN_c2_composed_liveness.md`). The server pays combat xp per

    XP = round((monster_level/player_level * 20 + monster_hp * 0.04)
               * level_penalty * monster_multiplier * wisdom_bonus)
    level_penalty: 1.0 (diff ≤ 4), 0.7 (5 ≤ diff ≤ 9), 0.0 (diff ≥ 10)
    where diff = char_level - monster_level

(documented: https://docs.artifactsmmo.com/concepts/stats_and_fights/#xp-formula;
production mirror `monster_catalog.xp_per_kill`, doc-cited; live corroboration
399/399 fights — `formal/diff/xp_formula_replay.py`).

KEY FACT making the DECISION gate float-free: inside the band the formula's
minimum value is ≈1.4 (worst case player 10 / monster 1 / penalty 0.7), which
rounds to ≥ 1 under ANY rounding mode; outside the band the penalty factor is
0. Hence production's targeting gate `xp_per_kill(code, level) > 0`
(player.py:1574 → combat_picker) is EXACTLY the integer predicate proved here —
no float, no rounding-mode dependence. The differential
(`formal/diff/test_xp_positive_diff.py`) pins the real float path's `> 0`
verdict to this gate over random catalogs; the mutation group anchors the
penalty thresholds in `monster_catalog.py`.

Roles: characterization (`gate_iff` / `gate_false_iff` — the penalty-zero band
is the gate's exact complement), picker-window compatibility (`gate_of_window`
— the preferred window [L-1, L+2] structurally rides penalty 1.0), and
antitonicity in char level (`gate_antitone` — leveling up never turns a
zero-xp target positive).

Core-only (no Mathlib). -/

namespace Formal.XpPositive

/-- The combat-xp positivity gate: a real monster (level ≥ 1) pays xp iff the
    character is fewer than 10 levels above it (`level_penalty > 0`). -/
def xpPositiveGate (charLevel monsterLevel : Nat) : Bool :=
  decide (1 ≤ monsterLevel) && decide (charLevel < monsterLevel + 10)

/-- Characterization: the gate is the integer band, exactly. -/
theorem gate_iff (c m : Nat) :
    xpPositiveGate c m = true ↔ 1 ≤ m ∧ c < m + 10 := by
  simp [xpPositiveGate]

/-- The `level_penalty = 0` band ("10+ levels above") is EXACTLY the gate's
    complement for real monsters. -/
theorem gate_false_iff (c m : Nat) (hm : 1 ≤ m) :
    xpPositiveGate c m = false ↔ m + 10 ≤ c := by
  rw [← Bool.not_eq_true, gate_iff]
  omega

/-- Preferred picker-window targets (`monsterLevel ≥ charLevel - 1`, i.e.
    `charLevel ≤ monsterLevel + 1`) are always xp-positive — the window
    structurally rides `level_penalty = 1.0`. -/
theorem gate_of_window (c m : Nat) (hm : 1 ≤ m) (hw : c ≤ m + 1) :
    xpPositiveGate c m = true := by
  rw [gate_iff]
  omega

/-- Antitone in character level: leveling UP never turns a zero-xp target
    positive (once out of band, always out of band). -/
theorem gate_antitone (c c' m : Nat) (h : c ≤ c') :
    xpPositiveGate c' m = true → xpPositiveGate c m = true := by
  simp only [gate_iff]
  omega

end Formal.XpPositive
