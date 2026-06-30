-- @concept: combat-survivability @property: validity, safety
/-
Formal model of the pure win-rate-scaled potion-quantity core extracted from
`src/artifactsmmo_cli/ai/marginal_potion_qty.py` (`marginal_potion_qty_pure`).

The harder a winnable fight (observed win-rate just below the combat-veto
threshold), the more health potions the bot stacks into a free utility slot:
0 when the fight is not marginal (win-rate at/above threshold, or too few
samples, or the slot is taken / nothing held), 1 just below the threshold,
scaling up to a full stack (`maxStack`) at the full-stack win-rate. The equipped
count never exceeds what the bot holds (`heldHealQty`).

Win-rate is an integer permille so the decision is float-free; this Nat mirror is
locked to the Python bit-for-bit by `formal/diff/test_marginal_potion_qty_diff.py`
through the `marginal_potion_qty` oracle kind.

NOTE on `qty_le_max` (unconditional): the else branch is a plain `ceilDiv`, with
no floor or clamp. The branch guard gives `fullStackPermille < winPermille <
thresholdPermille`, so `thresholdPermille - winPermille < thresholdPermille -
fullStackPermille` (the denominator); hence the ceil of
`(threshold-win)·maxStack / (threshold-full)` is `≤ maxStack` already. A floor at
1 (the old `max 1 ...`) was the ONLY thing that ever produced a value `> maxStack`
— it returned 1 at `maxStack = 0` — so deleting it makes the bound `qty ≤ maxStack`
hold for all inputs with no hypothesis. Behavior is unchanged for `maxStack ≥ 1`
(always true in live data — production uses 100), where the ceil is already `≥ 1`;
at the degenerate `maxStack = 0` the ceil is 0 = maxStack.
-/

namespace Formal.MarginalPotionQty

/-- Integer ceil of `a / b` for `b > 0`: `(a + b - 1) / b`. -/
def ceilDiv (a b : Nat) : Nat := (a + b - 1) / b

def marginalPotionQty
    (samples winPermille minSamples thresholdPermille fullStackPermille
     maxStack : Nat) (slotFilled : Bool) (heldHealQty : Nat) : Nat :=
  if slotFilled || heldHealQty == 0 then 0
  else if samples < minSamples || thresholdPermille ≤ winPermille then 0
  else
    let desired :=
      if winPermille ≤ fullStackPermille then maxStack
      else ceilDiv ((thresholdPermille - winPermille) * maxStack)
                   (thresholdPermille - fullStackPermille)
    min desired heldHealQty

/-- Bounded above by the full stack, unconditionally: the else branch is a plain
    `ceilDiv` whose guard (`fp < w < tp`) forces `ceilDiv ≤ maxStack`, so no floor
    or clamp is needed and the bound holds even at `maxStack = 0`. -/
theorem qty_le_max (s w ms tp fp mx : Nat) (sf : Bool) (h : Nat) :
    marginalPotionQty s w ms tp fp mx sf h ≤ mx := by
  unfold marginalPotionQty
  split
  · exact Nat.zero_le _
  · split
    · exact Nat.zero_le _
    · rename_i hc2
      refine Nat.le_trans (Nat.min_le_left _ _) ?_
      split
      · exact Nat.le_refl _
      · rename_i hwf
        -- `hc2 : ¬(s < ms || tp ≤ w)` ⇒ `w < tp`; `hwf : ¬(w ≤ fp)` ⇒ `fp < w`.
        simp only [Bool.or_eq_true, decide_eq_true_eq, not_or] at hc2
        obtain ⟨_, htw⟩ := hc2
        have hb : 0 < tp - fp := by omega
        unfold ceilDiv
        -- ((tp - w) * mx + (tp - fp) - 1) / (tp - fp) ≤ mx
        rw [Nat.div_le_iff_le_mul_add_pred hb]
        -- (tp - w) * mx + (tp - fp) - 1 ≤ (tp - fp) * mx + ((tp - fp) - 1)
        have hmul : (tp - w) * mx ≤ (tp - fp) * mx :=
          Nat.mul_le_mul_right mx (by omega)
        omega

/-- Never more than held. -/
theorem qty_le_held (s w ms tp fp mx : Nat) (sf : Bool) (h : Nat) :
    marginalPotionQty s w ms tp fp mx sf h ≤ h := by
  unfold marginalPotionQty
  split
  · exact Nat.zero_le _
  · split
    · exact Nat.zero_le _
    · exact Nat.min_le_right _ _

/-- Zero at/above the threshold. -/
theorem qty_zero_above_threshold (s w ms tp fp mx : Nat) (sf : Bool) (h : Nat)
    (hge : tp ≤ w) : marginalPotionQty s w ms tp fp mx sf h = 0 := by
  unfold marginalPotionQty
  split
  · rfl
  · split
    · rfl
    · rename_i hc2
      exact absurd (by simp [hge]) hc2

end Formal.MarginalPotionQty
