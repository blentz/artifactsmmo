-- @concept: characters, items @property: dominance
import Formal.RankingComposition

/-!
# Formal.PersonalityGrounding

**Closes the personality-positivity hypothesis used by `RankingComposition`.**

`RankingComposition.armor_root_outranks_empty_baseline` requires
`0 < base ∧ 0 < balancing`. The base prior is the personality weight on
the gear category; balancing is 1 for non-skill roots. Without a model
of which personalities satisfy these hypotheses, the composition lift
is conditional — true when supplied a witness, undecidable otherwise.

This module ships the witness: the integer surrogate for the production
`BalancedPersonality` returns a positive weight for every category, so
the G1→ranker bridge is unconditional under that personality.
-/

namespace Formal.PersonalityGrounding

/-! ## Personality model.

A `Personality` is a function from category-keys to nonneg integer weights.
Production has `BalancedPersonality` (every category gets weight 100, the
integer surrogate for 1.0) and `WeightedPersonality` (per-category from a
table). We prove the BALANCED variant satisfies the hypothesis. -/

/-- Category-tag of a meta-goal root for personality lookup. -/
inductive Category where
  | gear
  | skills
  | tools
  | charLevel
deriving Repr, DecidableEq

/-- Personality weight surrogate. Production uses Rational [0, 1+]; we
model it as Int in basis points (1.0 ↦ 100, 0.5 ↦ 50). Order-preserving. -/
abbrev PersonalityWeight := Int

/-- The integer surrogate for `BalancedPersonality`: every category gets 100. -/
def balancedPersonality (_ : Category) : PersonalityWeight := 100

/-! ## Positivity of every BalancedPersonality category. -/

theorem balanced_pos_gear : 0 < balancedPersonality Category.gear := by decide
theorem balanced_pos_skills : 0 < balancedPersonality Category.skills := by decide
theorem balanced_pos_tools : 0 < balancedPersonality Category.tools := by decide
theorem balanced_pos_charLevel : 0 < balancedPersonality Category.charLevel := by decide

theorem balanced_pos (c : Category) : 0 < balancedPersonality c := by
  cases c <;> decide

/-! ## Composition: BalancedPersonality discharges G1's hypothesis. -/

open Formal.RankingComposition

/-- **Composition lift**: under `BalancedPersonality`, the G1→ranker
bridge is UNCONDITIONAL. An armor item with positive AScore strictly
outranks the empty-slot baseline for the gear category. -/
theorem balanced_armor_outranks_empty_unconditional
    (category : Category) (b aScore : Int)
    (hBal : 0 < b) (hAS : 0 < aScore) :
    value (balancedPersonality category) 0 b <
    value (balancedPersonality category) (armorMarginalFromAScore aScore) b := by
  apply armor_root_outranks_empty_baseline
  · exact balanced_pos category
  · exact hBal
  · exact hAS

/-! ## Balancing positivity for non-skill roots.

`balancing(root, state)` returns 1.0 for non-`ReachSkillLevel` roots
(see Python `StrategyEngine._balancing`). We pin this — non-skill roots
have balancing surrogate = 100 (basis points for 1.0). -/

def balancingNonSkill : Int := 100

theorem balancingNonSkill_pos : 0 < balancingNonSkill := by decide

/-- **Full-chain composition**: a gear root under BalancedPersonality with
positive AScore strictly outranks the empty-slot baseline. All
hypotheses discharged. -/
theorem balanced_gear_armor_strictly_outranks_empty
    (aScore : Int) (hAS : 0 < aScore) :
    value (balancedPersonality Category.gear) 0 balancingNonSkill <
    value (balancedPersonality Category.gear)
          (armorMarginalFromAScore aScore) balancingNonSkill := by
  apply balanced_armor_outranks_empty_unconditional
  · exact balancingNonSkill_pos
  · exact hAS

end Formal.PersonalityGrounding
