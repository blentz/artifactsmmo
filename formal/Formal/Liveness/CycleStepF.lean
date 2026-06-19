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

**This brick is the FOUNDATION** — the definition and the per-step bridges
(`cycleStepF` agrees with `cycleStepP` on every field except `inventoryUsed`, and its
pressure is bounded). `pressureDelta` makes `inventoryUsed` faithful (fights fill the
bag, reducers drain it).

The NON-VACUOUS faithful reach-50 built on this is
`Formal.Liveness.LevelingDescent.cycleStepF_reaches_fifty_of_fights`: a fight cycle
strictly DESCENDS the lex measure (via `levelDeficit`/`xpDeficit`, which `pressureDelta`
preserves — the loot fill at `bankPressure` is lex-dominated), fed to the
`MeasureDescent` well-founded engine. NOTE (2026-06-19): an earlier i.o.-fairness
transience tower built on this foundation (drain dichotomy / `BlockersQuiet` discharge)
was REMOVED as vacuous — its residual forced `level < 50` infinitely often,
contradicting monotone level + the reach-50 goal (`docs/REVIEW_levelfifty_vacuity.md`).

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
