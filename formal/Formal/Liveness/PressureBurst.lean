import Formal.Liveness.InventoryPressure
import Formal.Liveness.Drainability
import Formal.Liveness.FightFairness

/-! # PressureBurst — Workstream A Phase-1 Brick 3c-prep: the FIGHT side of the
local dichotomy + the blocker partition that shrinks the residual.

`BurstStep.cycleStepF_drains_via_discardHigh` is the DRAIN side: a pressured,
overstock-armed selection state (with the seven higher slots quiet) selects
`discardHigh` and the bag drains to `0`. This module supplies the symmetric FIGHT
side: a LOW-pressure selection state whose ten NON-pressure blockers are quiet (and
whose combat objective is armed) selects `objectiveStep` — the cycle fights.

Together they are the **local dichotomy** the bounded-burst argument (Brick 3d)
iterates: under the ten non-pressure blockers quiet, every refreshed selection
state below the cap is EITHER a fight (low pressure, this module) OR a drain (high
pressure + a drain channel armed, `BurstStep` + `Drainability.RuntimeInvariant`).
Fights raise pressure by ≤ `DROP_BOUND` (Brick 2); a drain resets it to `0`; so
combat fires at a positive rate and the chore burst between two fights is bounded.

## The residual shrink (the honest win this brick names)

`FightFairness.objectiveStepBlockers` is the 14-means quiet obligation the
`cycleStepP` capstone carries as `BlockersQuietBelowCapInfinitelyOftenP`. Four of
those fourteen — `discardCritical`, `depositFull`, `discardHigh`, `sellPressured` —
are **inventory-pressure-gated** (their `*Fires` AND-gates a used/max threshold,
Brick 1). The faithfulness model proves THOSE FOUR transient from the bounded-burst
argument, so the residual the faithful `cycleStepF` capstone must carry shrinks to
the TEN `nonPressureBlockers` (+ the `RuntimeInvariant` drainability assumption).
`objectiveStepBlockers_quiet_of_low_pressure` is the partition fact that makes the
shrink mechanical: 14-quiet = (4 pressure-gated, silenced by low pressure) ∧
(10 non-pressure, the reduced residual).

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound}. Liveness ns. -/

namespace Formal.Liveness.PressureBurst

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.InventoryPressure
open Formal.Liveness.Drainability
open Formal.Liveness.FightFairness

/-- The ten `objectiveStepBlockers` that are NOT inventory-pressure-gated. The four
    excluded — `discardCritical`, `depositFull`, `discardHigh`, `sellPressured` —
    are the chores the bounded-burst argument proves transient; what remains is the
    reduced residual the faithful `cycleStepF` capstone carries. -/
def nonPressureBlockers : List MeansKind :=
  [.hpCritical, .restForCombat, .bankUnlock, .reachUnlockLevel,
   .craftRelief, .gearReview, .claimPending, .completeTask,
   .lowYieldCancel, .taskCancel]

/-- **The 14 → 4 + 10 partition.** When inventory pressure is below the binding
    85% threshold (`100·used < 85·max`, so Brick 1 silences all four pressure-gated
    chores) AND the ten `nonPressureBlockers` are quiet, EVERY one of the fourteen
    `objectiveStepBlockers` is quiet. This is the mechanical heart of the residual
    shrink: it lets a "ten quiet" hypothesis discharge the full "fourteen quiet"
    obligation the selection lemma needs. -/
theorem objectiveStepBlockers_quiet_of_low_pressure (s : State)
    (hlow : 100 * s.inventoryUsed < 85 * s.inventoryMax)
    (hnp : ∀ b ∈ nonPressureBlockers, fires b s = false) :
    ∀ b ∈ objectiveStepBlockers, fires b s = false := by
  obtain ⟨hdc, hdh, hdf, hsp⟩ := pressureGatedChores_quiet_of_low hlow
  intro b hb
  simp only [objectiveStepBlockers, List.mem_cons, List.not_mem_nil, or_false] at hb
  rcases hb with h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst h; exact hnp .hpCritical (by decide)
  · subst h; exact hnp .restForCombat (by decide)
  · subst h; exact hnp .bankUnlock (by decide)
  · subst h; exact hnp .reachUnlockLevel (by decide)
  · subst h; show discardCriticalFires s = false; exact hdc
  · subst h; exact hnp .craftRelief (by decide)
  · subst h; show depositFullFires s = false; exact hdf
  · subst h; show discardHighFires s = false; exact hdh
  · subst h; exact hnp .gearReview (by decide)
  · subst h; exact hnp .claimPending (by decide)
  · subst h; exact hnp .completeTask (by decide)
  · subst h; show sellPressuredFires s = false; exact hsp
  · subst h; exact hnp .lowYieldCancel (by decide)
  · subst h; exact hnp .taskCancel (by decide)

/-- **FIGHT side of the local dichotomy.** When the refreshed selection state has
    LOW inventory pressure (below 85%), its combat objective armed
    (`fires .objectiveStep`), and the ten `nonPressureBlockers` quiet, the ladder
    SELECTS `objectiveStep` — the cycle fights. Composes the 14→4+10 partition with
    `FightFairness.productionLadder_eq_objectiveStep_of_unblocked`. This is the
    fight-step the bounded-burst argument lands on between drains; it feeds directly
    into `LevelFiftyReachableP.cycleStepPN_succ_eq_fight_refreshed`. -/
theorem productionLadder_eq_objectiveStep_of_low_pressure (s : State)
    (hlow : 100 * s.inventoryUsed < 85 * s.inventoryMax)
    (hobj : fires .objectiveStep s = true)
    (hnp : ∀ b ∈ nonPressureBlockers, fires b s = false) :
    productionLadder s = some .objectiveStep :=
  productionLadder_eq_objectiveStep_of_unblocked s hobj
    (objectiveStepBlockers_quiet_of_low_pressure s hlow hnp)

end Formal.Liveness.PressureBurst
