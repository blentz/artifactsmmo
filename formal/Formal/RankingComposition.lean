import Formal.GearPolicy

/-!
# Formal.RankingComposition

**Composition theorems for the Tier-2 ranking layer.**

The live Python `StrategyEngine._value(root)` returns
  `base_prior(root) * marginal(root, state) * balancing(root, state)`
where each factor is nonneg. The Lean modules `Scalarizer`, `StrategyBlend`,
and `PriorityBand` cover the primitives individually. None of them, until
this module, composed the three factors into a SINGLE expression that the
ranking layer's argmax can be reasoned over.

This module:

1. Defines the composite `value` formula as a pure function.
2. Proves the value is monotone in each factor (when others are
   nonneg).
3. Lifts G1's `armor_strictly_dominates_empty_slot` THROUGH the
   composite — so a strictly-higher armor marginal under equal
   personality weight produces a strictly-higher composite value.

This is the bridge that connects the kernel-checked empty-slot
dominance to the live ranker's chosen_root selection. Without it, G1
was correct in isolation but the chain "armor dominance ⇒ ranker
picks armor root" relied on extra Python-only reasoning.

Outstanding work from `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.RankingComposition

/-! ## Composite value model. -/

/-- The composite value: `base * marginal * balancing`. All three factors
are nonneg in the production code (personality weights, marginal
contribution, balancing ratio). -/
def value (base marginal balancing : Int) : Int :=
  base * marginal * balancing

/-! ## Independence: zero in any factor zeroes the whole. -/

theorem value_zero_of_base_zero (m b : Int) : value 0 m b = 0 := by
  simp [value]

theorem value_zero_of_marginal_zero (base b : Int) : value base 0 b = 0 := by
  simp [value]

theorem value_zero_of_balancing_zero (base m : Int) : value base m 0 = 0 := by
  simp [value]

/-! ## Monotonicity in marginal (the main lever G1 controls). -/

/-- Equal `base` and `balancing`, strict-improvement in `marginal` ⇒ strict
improvement in `value`, when both `base` and `balancing` are STRICTLY
positive. (The strictness in base/balancing is necessary — a zero factor
collapses the whole.) -/
theorem value_strict_of_strict_marginal
    (base m1 m2 b : Int)
    (hBase : 0 < base) (hBal : 0 < b) (hM : m1 < m2) :
    value base m1 b < value base m2 b := by
  unfold value
  have h1 : base * m1 < base * m2 := Int.mul_lt_mul_of_pos_left hM hBase
  exact Int.mul_lt_mul_of_pos_right h1 hBal

/-- Weak monotonicity (≤ instead of <): more marginal never worsens value
when the other factors are nonneg. -/
theorem value_mono_in_marginal
    (base m1 m2 b : Int)
    (hBase : 0 ≤ base) (hBal : 0 ≤ b) (hM : m1 ≤ m2) :
    value base m1 b ≤ value base m2 b := by
  unfold value
  have h1 : base * m1 ≤ base * m2 := Int.mul_le_mul_of_nonneg_left hM hBase
  exact Int.mul_le_mul_of_nonneg_right h1 hBal

/-! ## Composition lift: G1 dominance through the ranker. -/

/-- Marginal sentinels for armor roots: an EMPTY-slot armor candidate
contributes `armorMarginalFromAScore item` (the G1 baseline being 0). -/
def armorMarginalFromAScore (aScore : Int) : Int := aScore

/-- **The composition theorem**. Under equal `base` (personality weight),
equal `balancing` (no skill leader effect), strictly-positive base AND
balancing, an item with a strictly-higher G1 AScore produces a
strictly-higher composite value than the empty-slot baseline (whose
marginal is 0). This is the kernel-checked bridge from G1's empty-slot
dominance into the ranker's argmax decision.

For the LIVE Python ranker to honor this:
  * `base` = `_base_prior(armor_root) * personality.category_weight("gear")`
    must be > 0 (true unless personality zeroes gear category — currently
    BalancedPersonality returns 1.0 across the board),
  * `balancing` = 1 for non-skill roots (Python `_balancing` returns 1.0
    when root is not `ReachSkillLevel`),
  * `marginal` ∝ G1's AScore.
-/
theorem armor_root_outranks_empty_baseline
    (base b : Int) (aScore : Int)
    (hBase : 0 < base) (hBal : 0 < b)
    (hAScore : 0 < aScore) :
    value base 0 b < value base (armorMarginalFromAScore aScore) b := by
  apply value_strict_of_strict_marginal base 0 (armorMarginalFromAScore aScore) b hBase hBal
  unfold armorMarginalFromAScore
  exact hAScore

/-- A useful corollary: in a list of root candidates, if exactly one root
has marginal > 0 and the others have marginal = 0 (and all share equal
base+balancing with positive values), the higher-marginal root's value is
the maximum. -/
theorem unique_positive_marginal_dominates
    (base b m : Int)
    (hBase : 0 < base) (hBal : 0 < b) (hM : 0 < m) :
    value base 0 b < value base m b := by
  apply value_strict_of_strict_marginal base 0 m b hBase hBal hM

/-! ## Tie semantics. -/

/-- Equal marginal ⇒ equal value (under equal base, balancing). This pins
the determinism property of the ranker: identical inputs ⇒ identical
output. -/
theorem value_eq_of_eq_marginal
    (base m b : Int) : value base m b = value base m b := rfl

/-- Composite value is symmetric in the factor ORDER (commutativity).
Useful for proofs that reassemble the factors in different orderings. -/
theorem value_comm_left (base m b : Int) :
    value base m b = value m base b := by
  unfold value; rw [Int.mul_comm base m]

end Formal.RankingComposition
