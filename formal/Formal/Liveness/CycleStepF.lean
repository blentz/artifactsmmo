import Formal.Liveness.InventoryDynamics
import Formal.Liveness.CycleStepP

/-! # CycleStepF — Workstream A Phase-1 Brick 3a: the faithful cycle (foundation)

`cycleStepF` is the perception-refreshed cycle with the faithful inventory-pressure
dynamics layered on: it applies `cycleStepP` (refresh-then-step) and then adjusts
`inventoryUsed` by `pressureDelta` for the means the cycle just selected
(`productionLadder (perceptionRefresh s)` — exactly the means `cycleStepP` acted
on). This is the cycle whose `BlockersQuiet` is a faithful THEOREM rather than the
refused false-story (the real bot re-arms chores via inventory filling, which
`cycleStepF` models and earlier cycles did not).

**This brick is the FOUNDATION only** — the definition and the per-step bridges
(`cycleStepF` agrees with `cycleStepP` on every field except `inventoryUsed`, and
its pressure is bounded). It does NOT yet prove the transience. The remaining
Brick-3 work, with the design forks sharpened 2026-06-19, is:

* **3b — conservative perceive re-arming.** `pressureDelta` makes `inventoryUsed`
  faithful, but the OPAQUE composition flags (`hasOverstockItems`,
  `selectBankDepositsNonempty`, `sellableInventoryNonempty`) are still cleared-and-
  never-re-armed by `applyActionKind`, so chores would not faithfully re-fire as
  the bag fills. A conservative `inventoryPerceive` must re-arm them from pressure
  (pressure present ⇒ assume a chore is available) — an OVER-approximation that is
  the conservative direction for "combat still fires i.o." (more chores fire ⇒
  harder to prove ⇒ holds a fortiori). BUT over-arming can HIDE a real
  full-of-useful-items livelock, so the arming must be gated by a drainability
  `RuntimeInvariant` (when pressured, a deposit is available: `bankAccessible ∧
  selectBankDepositsNonempty`) — surfacing the livelock as a precondition, not
  hiding it.
* **3c — the claim/measure surgery.** Lex measure component 5
  `bankPressure = max(0, used − 80%·max)`: fight raises it but reduces levelDeficit/
  xpDeficit (lex 1–2, above) ⇒ descent OK; a reducer lowers it ⇒ OK; but CLAIM
  raises it with no level/xp progress ⇒ measure INCREASES. Add a `pendingCount`
  component ABOVE `bankPressure` (claim depletes its own finite fuel ⇒ descends it).
* **3d — bounded-burst transience** ⇒ `BlockersQuietBelowCapInfinitelyOftenP`
  for `cycleStepF` ⇒ reach-50, discharging the residual FAITHFULLY. The local
  dichotomy it iterates is now COMPLETE: `BurstStep.cycleStepF_drains_via_discardHigh`
  (drain side) + `PressureBurst.productionLadder_eq_objectiveStep_of_low_pressure`
  (fight side). The residual the faithful capstone carries SHRINKS from the 14
  `objectiveStepBlockers` to the 10 `PressureBurst.nonPressureBlockers` (+ the
  `Drainability.RuntimeInvariant`): the 4 pressure-gated chores are proven transient.

Additive only; axioms ⊆ {propext, Quot.sound, …measure-chain}. Liveness namespace. -/

namespace Formal.Liveness.CycleStepF

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepP
open Formal.Liveness.InventoryDynamics

/-- The faithful cycle: refresh-then-step (`cycleStepP`), then adjust inventory
    pressure by the means the cycle selected (identity when the ladder selects
    nothing). -/
noncomputable def cycleStepF (s : State) : State :=
  match productionLadder (perceptionRefresh s) with
  | some k => pressureDelta k (cycleStepP s)
  | none   => cycleStepP s

/-- `n`-fold faithful cycle. -/
noncomputable def cycleStepFN : Nat → State → State
  | 0,     s => s
  | n + 1, s => cycleStepFN n (cycleStepF s)

@[simp] theorem cycleStepFN_zero (s : State) : cycleStepFN 0 s = s := rfl

theorem cycleStepFN_succ (n : Nat) (s : State) :
    cycleStepFN (n + 1) s = cycleStepFN n (cycleStepF s) := rfl

/-! ## Per-step bridges — `cycleStepF` agrees with `cycleStepP` on every field
except `inventoryUsed`. (`pressureDelta` touches only `inventoryUsed`.) These are
the atoms Brick 3b/3d apply at each `cycleStepFN k s`; note `cycleStepF` and
`cycleStepP` DIVERGE over multiple steps — pressure feeds back into selection — so
these are per-step, not `…N`-composable, bridges. -/

theorem cycleStepF_level (s : State) : (cycleStepF s).level = (cycleStepP s).level := by
  unfold cycleStepF; cases productionLadder (perceptionRefresh s) with
  | none => rfl
  | some k => exact pressureDelta_level k _

theorem cycleStepF_xp (s : State) : (cycleStepF s).xp = (cycleStepP s).xp := by
  unfold cycleStepF; cases productionLadder (perceptionRefresh s) with
  | none => rfl
  | some k => exact pressureDelta_xp k _

theorem cycleStepF_hp (s : State) : (cycleStepF s).hp = (cycleStepP s).hp := by
  unfold cycleStepF; cases productionLadder (perceptionRefresh s) with
  | none => rfl
  | some k => exact pressureDelta_hp k _

theorem cycleStepF_maxHp (s : State) : (cycleStepF s).maxHp = (cycleStepP s).maxHp := by
  unfold cycleStepF; cases productionLadder (perceptionRefresh s) with
  | none => rfl
  | some k => exact pressureDelta_maxHp k _

theorem cycleStepF_inventoryMax (s : State) :
    (cycleStepF s).inventoryMax = (cycleStepP s).inventoryMax := by
  unfold cycleStepF; cases productionLadder (perceptionRefresh s) with
  | none => rfl
  | some k => exact pressureDelta_inventoryMax k _

theorem cycleStepF_bankRequiredLevel (s : State) :
    (cycleStepF s).bankRequiredLevel = (cycleStepP s).bankRequiredLevel := by
  unfold cycleStepF; cases productionLadder (perceptionRefresh s) with
  | none => rfl
  | some k => exact pressureDelta_bankRequiredLevel k _

/-- One faithful cycle raises pressure by at most `DROP_BOUND` over the
    refresh-then-step value — the bounded riser that caps the chore burst. -/
theorem cycleStepF_inventoryUsed_le_add_bound (s : State) :
    (cycleStepF s).inventoryUsed ≤ (cycleStepP s).inventoryUsed + DROP_BOUND := by
  unfold cycleStepF; cases productionLadder (perceptionRefresh s) with
  | none => exact Nat.le_add_right _ _
  | some k => exact pressureDelta_inventoryUsed_le_add_bound k _

end Formal.Liveness.CycleStepF
