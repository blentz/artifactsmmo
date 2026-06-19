import Formal.Liveness.InventoryDynamics

/-! # Drainability — Workstream A Phase-1 Brick 3b: the high-pressure engine

Brick 1 proved the LOW-pressure direction (`pressureGatedChores_quiet_of_low`:
below 85% all gated chores are silent). This brick proves the HIGH-pressure
direction: a pressured state with a drain channel ARMED fires a reducer — the step
that drains the bag so combat can resume. Together with Brick 2's
`pressureDelta_reducer_clears` (a reducer drains to 0) these three are the LOCAL
transience engine: fill → (pressured ∧ armed) fires a reducer → drains to 0 →
gated chores quiet → combat.

The honest core is `RuntimeInvariant`: the model CANNOT compute inventory
composition, and `applyActionKind` clears the opaque composition flags
(`hasOverstockItems`/`sellableInventoryNonempty`/…) and never re-arms them — so we
do NOT fabricate a perceive that always re-arms a drain (that would HIDE a real
full-of-useful-items livelock). Instead `RuntimeInvariant` CARRIES drainability as
an explicit, checkable assumption: whenever the bag is pressured, SOME drain
channel holds items. Where it fails is exactly where the bot livelocks
(`[[project_inventory_profiles]]`). `BlockersQuiet` for `cycleStepF` will be proven
MODULO this invariant — the precise, minimal residual the plan promised.

This brick: the `Pressured` / `DrainArmed` predicates, `RuntimeInvariant`, and the
local lemma `reducer_fires_of_pressured_drainArmed`. Brick 3c (claim/measure) and
3d (bounded-burst → BlockersQuiet) compose this with Bricks 1–2.

`DrainArmed` uses the two 85%-threshold reducers (`discardHigh`, `sellPressured`):
at the binding 85% pressure only these two are guaranteed past their threshold
(deposit needs 90%, critical 95%), so they are the channels a pressured state can
fire WITHOUT a stronger pressure assumption.

Additive only; axioms ⊆ {propext, Quot.sound}. Liveness namespace. -/

namespace Formal.Liveness.Drainability

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder

/-- The bag is at/above the binding 85% pressure threshold (`100·used ≥ 85·max`,
    in `DISCARD_HIGH` constants). At this level `discardHigh`/`sellPressured` are
    past their threshold; below it Brick 1 silences all four gated chores. -/
def Pressured (s : State) : Prop :=
  DISCARD_HIGH_DEN * s.inventoryUsed ≥ DISCARD_HIGH_NUM * s.inventoryMax

/-- A drain channel is armed: there is junk to discard (`hasOverstockItems`) or a
    sellable item (`sellableInventoryNonempty`) — the two reducers whose threshold
    is the binding 85%. This is the composition fact the model cannot compute; the
    `RuntimeInvariant` supplies it when pressured. -/
def DrainArmed (s : State) : Prop :=
  s.hasOverstockItems = true ∨ s.sellableInventoryNonempty = true

/-- **The drainability invariant** for a `cycleStepF` trajectory: post-unlock
    (`bankAccessible`) and, at every step where the bag is pressured, a drain
    channel is armed. This is the honest, checkable residual `BlockersQuiet` for
    `cycleStepF` reduces to — it pinpoints the livelock precondition (a pressured
    bag with NO drainable item) rather than hiding it behind a fabricated perceive.
    Stated abstractly over a step function `step` so Brick 3d can instantiate it at
    `cycleStepFN · s`. -/
def RuntimeInvariant (step : Nat → State → State) (s : State) : Prop :=
  ∀ k, (Pressured (step k s) ∧ (step k s).inventoryMax > 0) → DrainArmed (step k s)

/-! ## The local engine — a pressured, drain-armed state fires a reducer -/

/-- **Drainability engine.** A pressured state (`≥85%`) with a non-empty bag and a
    drain channel armed FIRES one of the two binding reducers (`discardHigh` or
    `sellPressured`). With Brick 2's `pressureDelta_reducer_clears` (the reducer
    drains to 0) and Brick 1 (drained ⇒ quiet), this is the local fill→drain→quiet
    cycle the bounded-burst argument iterates. -/
theorem reducer_fires_of_pressured_drainArmed {s : State}
    (hp : Pressured s) (hmax : s.inventoryMax > 0) (ha : DrainArmed s) :
    discardHighFires s = true ∨ sellPressuredFires s = true := by
  rcases ha with hover | hsell
  · -- junk present ⇒ discardHigh fires (overstock ∧ max>0 ∧ ≥85%).
    left
    simp only [discardHighFires, Bool.and_eq_true, decide_eq_true_eq]
    exact ⟨⟨hover, hmax⟩, hp⟩
  · -- sellable present ⇒ sellPressured fires (max>0 ∧ ≥85% ∧ sellable).
    right
    simp only [sellPressuredFires, Bool.and_eq_true, decide_eq_true_eq]
    refine ⟨⟨hmax, ?_⟩, hsell⟩
    -- SELL_PRESSURE threshold (85%) = DISCARD_HIGH threshold (85%): same constants.
    simpa only [SELL_PRESSURE_DEN, SELL_PRESSURE_NUM, DISCARD_HIGH_DEN, DISCARD_HIGH_NUM]
      using hp

end Formal.Liveness.Drainability
