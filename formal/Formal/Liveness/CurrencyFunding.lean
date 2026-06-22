-- @concept: liveness, tasks @property: termination, sufficiency
/-
Termination/sufficiency model for `ReachCurrencyGoal` funding
(`src/artifactsmmo_cli/ai/goals/funding_core.py::funding_cycles_pure`).

A funding plan repeats accept→progress→complete cycles; each completed task mints
≥ `floor` (≥1) `tasks_coin` (C2 `CompleteTaskIncome.applyComplete_monotone`). This
proves:
  * SUFFICIENCY: `fundingCycles` cycles, each adding ≥ floor, REACH the target —
    so `ReachCurrencyGoal.max_depth` (∝ fundingCycles) admits a complete plan and
    the GOAP search terminates with a plan rather than the budget timeout that
    caused the original 641K-node burn.
  * DESCENT: while under target, one cycle strictly drops the remaining-coins
    measure `target - coins` — the well-founded termination argument.

Liveness namespace — mathlib permitted (Nat.div lemmas).
-/
import Mathlib.Data.Nat.Basic

namespace Formal.Liveness.CurrencyFunding

/-- Cycles to fund: 0 if already at target, else ceil((target-onHand)/floor). -/
def fundingCycles (onHand target floor : Nat) : Nat :=
  if target ≤ onHand then 0 else (target - onHand + floor - 1) / floor

/-- **SUFFICIENCY.** With `floor ≥ 1`, completing `fundingCycles` cycles — each
adding at least `floor` coins — reaches `target`. The depth bound is enough. -/
theorem fundingCycles_sufficient (onHand target floor : Nat) (h : 1 ≤ floor) :
    target ≤ onHand + fundingCycles onHand target floor * floor := by
  unfold fundingCycles
  split
  · omega
  · rename_i hgt
    have hmod := Nat.div_add_mod (target - onHand + floor - 1) floor
    have hr : (target - onHand + floor - 1) % floor < floor := Nat.mod_lt _ (by omega)
    rw [Nat.mul_comm]
    omega

/-- **DESCENT.** While under target, one cycle (adding ≥1) strictly reduces the
remaining-coins measure — the termination witness. -/
theorem funding_remaining_descends (coins target floor : Nat)
    (hlt : coins < target) (h : 1 ≤ floor) :
    target - (coins + floor) < target - coins := by omega

/-! ### Non-vacuity witnesses. -/
example : fundingCycles 0 8 2 = 4 := by decide
example : fundingCycles 0 9 2 = 5 := by decide
example : fundingCycles 8 8 2 = 0 := by decide
-- sufficiency is real, not vacuous: 0 + 4*2 = 8 ≥ 8.
example : (8 : Nat) ≤ 0 + fundingCycles 0 8 2 * 2 := by decide

end Formal.Liveness.CurrencyFunding
