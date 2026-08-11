-- @concept: combat, planner @property: safety
import Formal.XpPositive
/-! # XpValue — the exact combat-xp VALUE core (documented server formula)

Phase C0b (`docs/PLAN_c2_composed_liveness.md`). `unlock_boost` RANKS unlock
targets by `xp_per_kill` magnitude, so the value — not just its positivity
(C0a, `Formal.XpPositive`) — is in the decision path. Production was refactored
to EXACT integer arithmetic (mechanical-extraction discipline; the old float
path differed from the exact rational at 12/17400 grid points, all ±1 at
half-integer ties): the documented formula

    XP = round((ml/cl * 20 + hp * 0.04) * penalty * multiplier * wisdom_bonus)

is evaluated as one rational `num/den` with round-half-even (Python `round`):

    num = (2000*ml + 4*hp*cl) * penalty10 * mult10 * (1000 + wisdom)
    den = cl * 10000000
    penalty10 ∈ {10, 7, —}  (diff ≤ 4 / 5..9 / ≥10 returns 0)
    mult10    ∈ {10, 14, 20}  (normal / elite / boss — the type→mult10 map
                               stays a production data lookup; the mirror takes
                               mult10 as an input and the differential derives
                               it from the type string)

This mirror is bit-identical to `monster_catalog.xp_per_kill` — pinned by
`formal/diff/test_xp_value_diff.py` and the XP_VALUE mutation group.

Roles: `roundHalfUp` floor/ceil bounds; `xpPerKill_pos_iff_gate` — the value
is positive EXACTLY when C0a's proven `xpPositiveGate` holds (given a real
multiplier `mult10 ≥ 10`), tying the value core to the positivity core;
`xpPerKill_wisdom_mono` — more wisdom never lowers the value.

Core-only (no Mathlib). -/


namespace Formal.XpValue

open Formal.XpPositive

/-- Round-half-UP on the nonnegative rational `num/den`: a tie goes to the larger
    value. On `Nat` that is the same as half-away-from-zero, which is what the
    published award formula's `Round` is taken to mean.

    This was `roundHalfUp` — Python's built-in `round` — and that was a
    TOOLCHAIN artifact standing in for a game rule nobody had read. Half-to-even
    makes an award depend on the PARITY of the quotient, so two monsters whose
    exact awards differ by nothing but which side of a half they land on are
    ranked by an accident of representation. The same defect was found and removed
    from the measured-rate sample level in the same session. -/
def roundHalfUp (num den : Nat) : Nat :=
  let q := num / den
  let r := num % den
  if 2 * r < den then q else q + 1

/-- `roundHalfUp` never rounds below the floor. -/
theorem roundHalfUp_ge_floor (num den : Nat) :
    num / den ≤ roundHalfUp num den := by
  dsimp only [roundHalfUp]
  split <;> omega

/-- `roundHalfUp` never exceeds floor + 1. -/
theorem roundHalfUp_le_succ_floor (num den : Nat) :
    roundHalfUp num den ≤ num / den + 1 := by
  dsimp only [roundHalfUp]
  split <;> omega

/-- The exact xp value — bit-identical mirror of
    `monster_catalog.xp_per_kill` (post-C0b refactor). `mult10` is the
    ×10 monster-type multiplier (data lookup on the production side). -/
def xpPerKill (charLevel monsterLevel monsterHp mult10 wisdom : Nat) : Nat :=
  if monsterLevel = 0 ∨ charLevel = 0 then 0
  else if monsterLevel + 10 ≤ charLevel then 0
  else
    let penalty10 := if monsterLevel + 5 ≤ charLevel then 7 else 10
    let num := (2000 * monsterLevel + 4 * monsterHp * charLevel)
                 * penalty10 * mult10 * (1000 + wisdom)
    roundHalfUp num (charLevel * 10000000)

set_option maxRecDepth 4096 in
/-- **Value ↔ gate**: for any real multiplier (`mult10 ≥ 10`), the xp value is
    positive EXACTLY when the C0a positivity gate holds. The in-band lower
    bound is the KEY FACT from the C0a analysis, now kernel-proved for the
    value itself: `c ≤ m + 9 ⟹ num ≥ den` (worst case
    `2000·m·7·10·1000 ≥ c·10^7 ⟺ 14m ≥ c ⟸ c ≤ m + 9 ∧ 1 ≤ m`). -/
theorem xpPerKill_pos_iff_gate (c m hp mult10 w : Nat)
    (hc : 1 ≤ c) (hmult : 10 ≤ mult10) :
    (0 < xpPerKill c m hp mult10 w ↔ xpPositiveGate c m = true) := by
  unfold xpPerKill
  rw [gate_iff]
  split
  · -- degenerate levels: value 0, gate false
    omega
  · split
    · -- out of band: value 0, gate false
      omega
    · -- in band: floor ≥ 1 hence roundHalfUp ≥ 1; gate true
      rename_i hdeg hband
      dsimp only
      constructor
      · intro _
        omega
      · intro _
        have hden : 0 < c * 10000000 := by omega
        -- num ≥ den, by an explicit product chain:
        --   2000·m·7·10·1000 ≤ (2000m + 4hp·c)·p10·mult10·(1000+w)
        -- and c·10^7 ≤ 140000000·m (linear, from c ≤ 14m ⟸ c ≤ m+9 ∧ 1 ≤ m).
        have hp10 : 7 ≤ (if m + 5 ≤ c then 7 else 10) := by split <;> omega
        have key : 2000 * m * 7 * 10 * 1000 ≤
            (2000 * m + 4 * hp * c) * (if m + 5 ≤ c then 7 else 10)
              * mult10 * (1000 + w) :=
          Nat.mul_le_mul
            (Nat.mul_le_mul
              (Nat.mul_le_mul (Nat.le_add_right _ _) hp10) hmult)
            (Nat.le_add_right 1000 w)
        have hlin : c * 10000000 ≤ 2000 * m * 7 * 10 * 1000 := by omega
        have hnum : c * 10000000 ≤
            (2000 * m + 4 * hp * c) * (if m + 5 ≤ c then 7 else 10)
              * mult10 * (1000 + w) := Nat.le_trans hlin key
        have hfloor : 1 ≤ ((2000 * m + 4 * hp * c) * (if m + 5 ≤ c then 7 else 10)
              * mult10 * (1000 + w)) / (c * 10000000) :=
          (Nat.le_div_iff_mul_le hden).mpr (by omega)
        exact Nat.lt_of_lt_of_le hfloor
          (roundHalfUp_ge_floor
            ((2000 * m + 4 * hp * c) * (if m + 5 ≤ c then 7 else 10)
              * mult10 * (1000 + w)) (c * 10000000))

/-- More wisdom never lowers the value (`roundHalfUp` is monotone in the
    numerator; the tie rule can only round UP from the shared floor). -/
theorem xpPerKill_wisdom_mono (c m hp mult10 w w' : Nat) (h : w ≤ w') :
    xpPerKill c m hp mult10 w ≤ xpPerKill c m hp mult10 w' := by
  unfold xpPerKill
  split
  · omega
  · split
    · omega
    · have hmono : ∀ n n' d : Nat, n ≤ n' →
          roundHalfUp n d ≤ roundHalfUp n' d := by
        intro n n' d hn
        have hq : n / d ≤ n' / d := Nat.div_le_div_right hn
        rcases Nat.lt_or_ge (n / d) (n' / d) with hlt | hge
        · -- floors strictly ordered: bound both sides through the floor.
          have h1 := roundHalfUp_le_succ_floor n d
          have h2 := roundHalfUp_ge_floor n' d
          omega
        · -- equal floors: the remainders are ordered the same way, and half-up has
          -- ONE branch point, so the only bad case would be n rounding up while n'
          -- rounds down -- which needs the larger remainder to be the smaller one.
          have hqe : n / d = n' / d := Nat.le_antisymm hq hge
          have hr : n % d ≤ n' % d := by
            have e1 := Nat.div_add_mod n d
            have e2 := Nat.div_add_mod n' d
            -- align the two nonlinear d·(·/d) products into ONE atom
            rw [← hqe] at e2
            omega
          dsimp only [roundHalfUp]
          split
          · split <;> omega
          · split <;> omega
      apply hmono
      have : 1000 + w ≤ 1000 + w' := by omega
      exact Nat.mul_le_mul_left _ this

end Formal.XpValue
