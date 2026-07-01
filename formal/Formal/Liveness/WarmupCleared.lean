import Formal.Liveness.BlockerMonotone
import Formal.Liveness.BlockerSettled
import Mathlib.Tactic

/-! # WarmupCleared — the monotone core of `Settled` as one invariant (O5.2 warm-up)

The mechanical warm-up toward `Settled` drives ten conditions true; nine of them are
the `cycleStep`-MONOTONE ones (six opaque flags + `hp=maxHp` + `bankAccessible` +
`level≥bankRequiredLevel`), each individually shown "once true, stays true" in
`BlockerMonotone` (incr 7–9). This module bundles them into a single invariant
`MechCleared` and proves it `cycleStep`- and `cycleStepN`-preserved by composition, then
bridges to `Settled` with the two remaining facts: `phase = .none` and a committed
combat objective (the perception input).

So the warm-up factors cleanly:
  reach `MechCleared`  (bootstrap fights + inventory clearing — bounded, monotone)
  ∧ reach `phase = .none`  (task termination, stable once `MechCleared` ∧ perception)
  ∧ perception (`objectiveStepFires`/`objectiveStepIsFight`)
  ⇒ `Settled`.

NO new axioms (standard set + LIV-001 via the imports).
-/

namespace Formal.Liveness.WarmupCleared

open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.BlockerMonotone
open Formal.Liveness.BlockerSettled

/-- The monotone core of `Settled`: the ten `cycleStep`-monotone clearing
    conditions (excludes the non-monotone `phase` and the perception inputs). -/
structure MechCleared (s : State) : Prop where
  overstock      : s.hasOverstockItems = false
  deposits       : s.selectBankDepositsNonempty = false
  gear           : s.gearReviewFires = false
  potions        : s.craftPotionsFires = false
  pending        : s.pendingItemsNonempty = false
  sellable       : s.sellableInventoryNonempty = false
  craft          : s.craftReliefFires = false
  recycleNonempty : s.recyclableSurplusNonempty = false
  hpFull         : s.hp = s.maxHp
  bank           : s.bankAccessible = true
  leveled        : s.level ≥ s.bankRequiredLevel

/-- `MechCleared` is `cycleStep`-invariant — a direct composition of the nine
    per-condition monotonicity lemmas (incr 7–9). -/
theorem MechCleared_cycleStep (s : State) (h : MechCleared s) :
    MechCleared (cycleStep s) where
  overstock       := hasOverstockItems_false_cycleStep s h.overstock
  deposits        := selectBankDeposits_false_cycleStep s h.deposits
  gear            := gearReviewFires_false_cycleStep s h.gear
  potions         := craftPotionsFires_false_cycleStep s h.potions
  pending         := pendingItems_false_cycleStep s h.pending
  sellable        := sellable_false_cycleStep s h.sellable
  craft           := craftReliefFires_false_cycleStep s h.craft
  recycleNonempty := recyclableSurplusNonempty_false_cycleStep s h.recycleNonempty
  hpFull          := hp_eq_maxHp_cycleStep s h.hpFull
  bank            := bankAccessible_cycleStep s h.bank
  leveled         := by
    have h1 := cycleStep_level_ge s
    have h2 := bankRequiredLevel_cycleStep s
    have h3 := h.leveled
    rw [h2]; omega

theorem MechCleared_cycleStepN :
    ∀ (n : Nat) (s : State), MechCleared s → MechCleared (cycleStepN n s)
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact MechCleared_cycleStepN n (cycleStep s) (MechCleared_cycleStep s h)

/-- **Bridge to `Settled`.** The monotone core plus a parked task and a committed
    combat objective is exactly `Settled`. -/
theorem settled_of_mechCleared (s : State) (hm : MechCleared s)
    (hphase : s.taskLifecyclePhase = .none)
    (hof : s.objectiveStepFires = true) (hif : s.objectiveStepIsFight = true) :
    Settled s where
  overstock       := hm.overstock
  deposits        := hm.deposits
  gear            := hm.gear
  potions         := hm.potions
  pending         := hm.pending
  sellable        := hm.sellable
  craft           := hm.craft
  recycleNonempty := hm.recycleNonempty
  hpFull          := hm.hpFull
  bank            := hm.bank
  leveled         := hm.leveled
  phaseNone       := hphase
  objFires        := hof
  objFight        := hif

end Formal.Liveness.WarmupCleared
