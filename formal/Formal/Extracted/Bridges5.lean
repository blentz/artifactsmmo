import Formal.Scalarizer
import Formal.Extracted.ScalarCore

/-!
# Extracted ↔ hand-model bridge lemmas, part 5 (P3c: the exact-Fraction
learning core)

HAND-WRITTEN (size split of Bridges.lean..Bridges4.lean; same namespace).
The P3c wave refactored the float-typed Tier-3 learning core to EXACT
`Fraction` arithmetic (`scalar_yield_exact` in `scalar_core.py`),
mechanically extracted it to `Formal/Extracted/ScalarCore.lean`, and this
file proves it against the pre-existing hand model `Formal.Scalarizer`.
(The `cycles_for_progress` core, its extraction and its bridges were deleted
in the Phase 5-2c-iii cleanup once its only production caller — the
retired low-yield cancel — was gone.)

## THE FLOAT BOUNDARY (the trusted seam — read this)

The bridges below live ENTIRELY on the exact rational core: every proved
equality is between the extracted `Rat` definition and the hand `Rat` model.
The Python public wrapper `scalar_yield_pure` converts its inputs to
`Fraction` EXACTLY (a Python float IS a binary rational; `Fraction(float)` is
its exact expansion), runs the proved exact core, and rounds ONCE —
`float(total)` — at the very end. That single conversion is OUTSIDE
everything proved here. It is the trusted seam, and it is sampled, not
proved: the differential suite (`test_scalarizer_diff.py`) compares the exact
core to the Lean oracle EXACTLY (Fraction == Rat numerator/denominator, no
tolerance), and separately asserts the float wrapper equals
`float(exact result)` on every generated input — the wrapper's correctness
reduces to "Python's `float()` of a Fraction is the correctly-rounded
double", a property of CPython, not of this code.

## Bridge inventory

* `scalar_yield_bridge` — FULL: the extracted `scalar_yield_exact` equals
  the hand `scalarYield` for EVERY rational input, over the `encSkillTerm`
  weight-selection embedding (the hand model takes pre-selected
  `(weight, xp)` terms; the extracted core performs the membership
  selection itself — `List.contains`, order-independent over the
  frozenset image) and with the hand `goldUnit` instantiated at
  `1 / gold_per_xp` (Rat division IS multiplication by the reciprocal:
  `Rat.div_def`). `scalar_yield_mono_gold_extracted` transfers gold
  monotonicity to the extracted def.

* `coins_spent_bridge` — FULL (definitional): the extracted
  `coins_spent_from_delta` IS the hand `coinsSpent`;
  `coins_spent_inverts_extracted` transfers the no-sign-error inversion.

No sorry/admit, no new axioms; Lean core only.
-/

namespace Extracted.Bridges

/-! ### Scalarizer bridges. -/

/-- Weight-selection embedding: the hand model consumes pre-selected
`(weight, xp)` terms; the extracted core selects the weight by membership.
-/
def encSkillTerm (active : List String) (relW baseW : Rat)
    (kv : String × Rat) : Formal.Scalarizer.SkillTerm :=
  ((if List.contains active kv.1 then relW else baseW), kv.2)

/-- The extracted skill fold equals the hand `skillSum` over the encoded
terms, behind any running accumulator. -/
private theorem scalar_skill_fold (active : List String) (relW baseW : Rat) :
    ∀ (terms : List (String × Rat)) (acc : Rat),
      List.foldl
        (fun s kv => s + kv.2 * (if List.contains active kv.1 then relW else baseW))
        acc terms
        = acc + Formal.Scalarizer.skillSum
            (terms.map (encSkillTerm active relW baseW)) := by
  intro terms
  induction terms with
  | nil =>
    intro acc
    simp [Formal.Scalarizer.skillSum, Rat.add_zero]
  | cons kv rest ih =>
    intro acc
    simp only [List.map_cons, List.foldl_cons, encSkillTerm,
               Formal.Scalarizer.skillSum]
    rw [ih]
    have hcomm : kv.2 * (if List.contains active kv.1 then relW else baseW)
        = (if List.contains active kv.1 then relW else baseW) * kv.2 :=
      Rat.mul_comm _ _
    rw [hcomm, Rat.add_assoc]

/-- FULL BRIDGE: the extracted `scalar_yield_exact` equals the hand
`scalarYield` for EVERY rational input — level cast into `Rat`, skill terms
through the membership encoding, the hand `goldUnit` at `1 / gold_per_xp`.
-/
theorem scalar_yield_bridge (charXp : Rat) (level : Int)
    (skillXp : List (String × Rat)) (active : List String)
    (gold tasksCoins coinValue baseW relW goldPerXp charScale : Rat) :
    Extracted.ScalarCore.scalar_yield_exact charXp level skillXp active
        gold tasksCoins coinValue baseW relW goldPerXp charScale
      = Formal.Scalarizer.scalarYield charXp (level : Rat)
          (skillXp.map (encSkillTerm active relW baseW))
          gold tasksCoins coinValue charScale (1 / goldPerXp) := by
  simp only [Extracted.ScalarCore.scalar_yield_exact,
             Formal.Scalarizer.scalarYield]
  rw [scalar_skill_fold]
  have hlevel : mkRat (level + 1) 1 = (level : Rat) + 1 := by
    rw [Rat.mkRat_one, Rat.intCast_add, Rat.intCast_one]
  have hzero : mkRat 0 1 = (0 : Rat) := by decide
  have hgold : gold / goldPerXp = gold * (1 / goldPerXp) := by
    simp [Rat.div_def]
  have hcoin : tasksCoins * coinValue / goldPerXp
      = tasksCoins * coinValue * (1 / goldPerXp) := by
    simp [Rat.div_def]
  rw [hlevel, hzero, hgold, hcoin, Rat.zero_add]

/-- TRANSFER of gold monotonicity to the extracted def: with a non-negative
gold unit (production: `1/100`), more gold never lowers the extracted
scalar. -/
theorem scalar_yield_mono_gold_extracted (charXp : Rat) (level : Int)
    (skillXp : List (String × Rat)) (active : List String)
    (gold gold' tasksCoins coinValue baseW relW goldPerXp charScale : Rat)
    (hunit : 0 ≤ 1 / goldPerXp) (h : gold ≤ gold') :
    Extracted.ScalarCore.scalar_yield_exact charXp level skillXp active
        gold tasksCoins coinValue baseW relW goldPerXp charScale
      ≤ Extracted.ScalarCore.scalar_yield_exact charXp level skillXp active
          gold' tasksCoins coinValue baseW relW goldPerXp charScale := by
  rw [scalar_yield_bridge, scalar_yield_bridge]
  exact Formal.Scalarizer.scalarYield_mono_gold charXp (level : Rat)
    (skillXp.map (encSkillTerm active relW baseW))
    gold gold' tasksCoins coinValue charScale (1 / goldPerXp) hunit h

/-- FULL BRIDGE (definitional): the extracted `coins_spent_from_delta` IS
the hand `coinsSpent`. -/
theorem coins_spent_bridge (received delta : Int) :
    Extracted.ScalarCore.coins_spent_from_delta received delta
      = Formal.Scalarizer.coinsSpent received delta := rfl

/-- TRANSFER of the no-sign-error inversion to the extracted def. -/
theorem coins_spent_inverts_extracted (received delta : Int) :
    received - Extracted.ScalarCore.coins_spent_from_delta received delta
      = delta := by
  rw [coins_spent_bridge]
  exact Formal.Scalarizer.coinsSpent_inverts received delta

end Extracted.Bridges
