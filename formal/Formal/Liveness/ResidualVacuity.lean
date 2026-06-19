import Formal.Liveness.EffectiveDrainTransience

/-! # ResidualVacuity — an HONEST self-audit: the level-50 capstone hypotheses are
UNSATISFIABLE, so the capstone is VACUOUSLY true.

This module exists to PROVE a flaw, not to hide it. Prompted by the question "are we
circling vacuous proofs because the model is wrong?", it checks whether the faithful
capstone `EffectiveDrainTransience.ai_reaches_level_fiftyF_of_effectiveDrain` actually
says anything.

The residuals (`TenQuietPairsBelowCapInfinitelyOften`, and the original
`BlockersQuietBelowCapInfinitelyOftenP`) carry a `(cycleStepFN k s).level < 50`
conjunct that must hold for INFINITELY MANY `k` (the `∀N ∃k≥N` shape). But `level` is
monotone non-decreasing along the trajectory (`cycleStepFN_level_ge`), so "level < 50
infinitely often" is equivalent to "level NEVER reaches 50". That directly contradicts
the capstone's conclusion `∃k, level ≥ 50`. Hence the hypothesis bundle is
unsatisfiable and `H → ∃k level ≥ 50` is vacuously true: it holds because `H` is never
true, not because the bot reaches 50.

`capstone_hypotheses_unsatisfiable` proves this by deriving `False` from the capstone's
own hypotheses. This is the formal-development "satisfiability witness" check turned on
its head: instead of exhibiting a witness, it proves NO witness exists. The same flaw
afflicts the predecessor `LevelFiftyReachableP` capstone (identical residual shape) —
the `level < 50` self-restriction the residual docstrings called "harmless" is in fact
exactly the vacuity: it makes the residual satisfiable ONLY when the goal FAILS.

THE FIX (not in this module — see docs/PLAN_faithfulness_modeling.md): the fairness
residual must NOT assert "blockers quiet ∧ level < 50" infinitely often. It must be a
LOCAL / conditional progress property — e.g. "from every below-50 reachable state, a
fight fires within finitely many steps while still below 50" — which is satisfiable for
trajectories that DO reach 50 (the post-50 tail is unconstrained) yet still drives the
level-advance engine's by-contradiction. Until that reformulation, the level-50
capstones are vacuous.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness ns. -/

namespace Formal.Liveness.ResidualVacuity

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepF
open Formal.Liveness.CycleStepFIteration
open Formal.Liveness.PressureTransience
open Formal.Liveness.EffectiveDrainTransience

/-- `level ≥ 50` PERSISTS: once the trajectory reaches the cap it never drops below it
    (monotonicity via `cycleStepFN_add` + `cycleStepFN_level_ge`). -/
theorem level_ge_fifty_persists (s : State) (K : Nat)
    (h : (cycleStepFN K s).level ≥ 50) {m : Nat} (hm : m ≥ K) :
    (cycleStepFN m s).level ≥ 50 := by
  obtain ⟨d, rfl⟩ := Nat.exists_eq_add_of_le hm
  rw [cycleStepFN_add K d s]
  have := cycleStepFN_level_ge (cycleStepFN K s) d
  omega

/-- **The residual precludes the goal.** `TenQuietPairsBelowCapInfinitelyOften` requires
    `level < 50` for arbitrarily large `k`; by monotonicity that forbids EVER reaching
    50. So the residual and the conclusion `∃k level ≥ 50` cannot both hold. -/
theorem tenQuietPairs_precludes_reaching_fifty (s : State)
    (htqp : TenQuietPairsBelowCapInfinitelyOften s) :
    ¬ ∃ k, (cycleStepFN k s).level ≥ 50 := by
  rintro ⟨K, hK⟩
  obtain ⟨k, hkK, hlt, _, _, _⟩ := htqp K
  have : (cycleStepFN k s).level ≥ 50 := level_ge_fifty_persists s K hK hkK
  omega

/-- **The capstone's hypotheses are UNSATISFIABLE.** Feeding the faithful capstone its
    own hypotheses yields `∃k level ≥ 50`, which the residual forbids — `False`. So
    `ai_reaches_level_fiftyF_of_effectiveDrain` is vacuously true: it proves nothing
    about the real bot. The honest fix is a local/conditional fairness residual (see the
    module docstring). -/
theorem capstone_hypotheses_unsatisfiable (s : State)
    (hnowait : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) ≠ some .wait)
    (hex : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .taskExchange →
                (perceptionRefresh (cycleStepFN k s)).taskExchangeMinCoins > 0)
    (hbe : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .bankExpand →
                (perceptionRefresh (cycleStepFN k s)).nextExpansionCost > 0)
    (hed : EffectiveDrainArmed s)
    (htqp : TenQuietPairsBelowCapInfinitelyOften s) :
    False :=
  tenQuietPairs_precludes_reaching_fifty s htqp
    (ai_reaches_level_fiftyF_of_effectiveDrain s hnowait hex hbe hed htqp)

/-! ## The SAME flaw afflicts the predecessor `cycleStepP` capstone

The faithful `cycleStepF` work merely inherited the residual shape from
`LevelFiftyReachableP`. `BlockersQuietBelowCapInfinitelyOftenP` carries the identical
`(cycleStepPN k s).level < 50` infinitely-often conjunct, and `cycleStepPN` is monotone
too (`cycleStepPN_level_ge`). So `ai_reaches_level_fiftyP_of_blockers_quiet` is
vacuous by the same argument — the level-50 perimeter has been vacuous since the
`cycleStepP` capstone, not a regression introduced here. -/

open Formal.Liveness.CycleStepP
open Formal.Liveness.FightFairnessP
open Formal.Liveness.LevelFiftyReachableP

/-- `level ≥ 50` persists along the `cycleStepP` trajectory. -/
theorem level_ge_fifty_persistsP (s : State) (K : Nat)
    (h : (cycleStepPN K s).level ≥ 50) {m : Nat} (hm : m ≥ K) :
    (cycleStepPN m s).level ≥ 50 := by
  obtain ⟨d, rfl⟩ := Nat.exists_eq_add_of_le hm
  rw [cycleStepPN_add K d s]
  have := cycleStepPN_level_ge (cycleStepPN K s) d
  omega

/-- `BlockersQuietBelowCapInfinitelyOftenP` forbids ever reaching 50 (monotonicity). -/
theorem blockersQuietP_precludes_reaching_fifty (s : State)
    (hq : BlockersQuietBelowCapInfinitelyOftenP s) :
    ¬ ∃ k, (cycleStepPN k s).level ≥ 50 := by
  rintro ⟨K, hK⟩
  obtain ⟨k, hkK, hlt, _⟩ := hq K
  have : (cycleStepPN k s).level ≥ 50 := level_ge_fifty_persistsP s K hK hkK
  omega

/-- **The predecessor capstone's hypotheses are UNSATISFIABLE too.**
    `ai_reaches_level_fiftyP_of_blockers_quiet` is vacuous by the identical argument —
    the level-50 perimeter has rested on an unsatisfiable residual since `cycleStepP`. -/
theorem levelFiftyP_hypotheses_unsatisfiable (s : State)
    (hnowait : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) ≠ some .wait)
    (hex : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) = some .taskExchange →
                (perceptionRefresh (cycleStepPN k s)).taskExchangeMinCoins > 0)
    (hbe : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) = some .bankExpand →
                (perceptionRefresh (cycleStepPN k s)).nextExpansionCost > 0)
    (hq : BlockersQuietBelowCapInfinitelyOftenP s) :
    False :=
  blockersQuietP_precludes_reaching_fifty s hq
    (ai_reaches_level_fiftyP_of_blockers_quiet s hnowait hex hbe hq)

end Formal.Liveness.ResidualVacuity
