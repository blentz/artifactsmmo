-- @concept: combat-survivability @property: validity, safety
/-
Formal model of the pure HP-need-scaled potion-provision core extracted from
`src/artifactsmmo_cli/ai/potion_provision_qty.py` (`potion_provision_qty_pure`).

Before a fight the bot equips enough heal potions to cover the monster's
learned/seeded HP-need: `ceil(hpNeed / potionRestore)`, clamped to what it holds
(`heldHealQty`) and to a full stack (`maxStack`). The provision is 0 when the
utility slot is already filled, nothing heal-worthy is held, or the potion
restores nothing (the last guard also avoids a divide-by-zero). This replaces the
win-rate heuristic `marginalPotionQty`.

The differential feeds non-negative inputs (`restore` down to 0), so the integer
`ceilDiv` matches Python's floor `//` bit-for-bit (both operands non-negative in
the live branch). This Int mirror is locked to the Python by
`formal/diff/test_potion_provision_qty_diff.py` through the
`potion_provision_qty` oracle kind.
-/

namespace Formal.PotionProvisionQty

/-- Integer ceil of `a / b` for `b > 0`: `(a + b - 1) / b`. Matches Python's
    `(a + b - 1) // b` whenever both operands are non-negative (the live branch,
    where `b = potionRestore ≥ 1` and `a = hpNeed ≥ 0`). -/
def ceilDiv (a b : Int) : Int := (a + b - 1) / b

def potionProvisionQty
    (hpNeed potionRestore heldHealQty : Int) (slotFilled : Bool) (maxStack : Int) : Int :=
  if slotFilled ∨ heldHealQty ≤ 0 ∨ potionRestore ≤ 0 then 0
  else min (min (ceilDiv hpNeed potionRestore) heldHealQty) maxStack

/-- Never more than a full stack (the outer `min maxStack`). Zero in the guarded
    branch, which needs `0 ≤ maxStack`. -/
theorem provision_le_max (hpNeed potionRestore heldHealQty maxStack : Int) (slotFilled : Bool)
    (hm : 0 ≤ maxStack) :
    potionProvisionQty hpNeed potionRestore heldHealQty slotFilled maxStack ≤ maxStack := by
  unfold potionProvisionQty
  split
  · exact hm
  · omega

/-- Never more than held (the inner `min heldHealQty`). Zero in the guarded
    branch, which needs `0 ≤ heldHealQty`. -/
theorem provision_le_held (hpNeed potionRestore heldHealQty maxStack : Int) (slotFilled : Bool)
    (hh : 0 ≤ heldHealQty) :
    potionProvisionQty hpNeed potionRestore heldHealQty slotFilled maxStack ≤ heldHealQty := by
  unfold potionProvisionQty
  split
  · exact hh
  · omega

/-- Non-negative: the guarded branch is 0; the else branch is a `min` of three
    non-negative terms (`ceilDiv ≥ 0` from `hpNeed ≥ 0` and `potionRestore ≥ 1`,
    `heldHealQty ≥ 1` from the guard, `maxStack ≥ 0` by hypothesis). -/
theorem provision_nonneg (hpNeed potionRestore heldHealQty maxStack : Int) (slotFilled : Bool)
    (hn : 0 ≤ hpNeed) (hm : 0 ≤ maxStack) :
    0 ≤ potionProvisionQty hpNeed potionRestore heldHealQty slotFilled maxStack := by
  unfold potionProvisionQty
  split
  · omega
  · rename_i hcond
    simp only [not_or] at hcond
    obtain ⟨_, _, hrestore⟩ := hcond
    have hceil : 0 ≤ ceilDiv hpNeed potionRestore := by
      unfold ceilDiv
      exact Int.ediv_nonneg (by omega) (by omega)
    omega

end Formal.PotionProvisionQty
