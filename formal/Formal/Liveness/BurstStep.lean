import Formal.Liveness.Drainability
import Formal.Liveness.CycleStepF
import Formal.Liveness.BlockerSelection

/-! # BurstStep — Workstream A Phase-1 Brick 3d-prep: the one-step drain

Composes the LOCAL engine (Bricks 1–2–3b) into a single `cycleStepF` step fact:
from a pressured, overstock-armed selection state whose seven higher-priority guard
slots are quiet, the faithful cycle SELECTS `discardHigh` and the resulting state
has `inventoryUsed = 0` — the bag is drained in one step. This is the drain step
the bounded-burst argument (Brick 3d) iterates: each fill (a fight, +≤DROP_BOUND)
is undone by one drain, so the chore burst between two combats is bounded.

The seven "higher slot quiet" hypotheses are taken as PREMISES here — discharging
them along the `cycleStepF` trajectory (hp rested, bank unlocked, not over-
pressured into discardCritical/depositFull, craftRelief/gearReview quiet) is Brick
3d's trajectory-assembly job, kept separate so this composition stays a clean,
reusable atom. The symmetric `sellPressured` channel (slots 0–10 quiet) is the
analogous lemma; `discardHigh` is the shortest-premise channel.

Additive; axioms ⊆ {propext, Quot.sound, LIV-001 via cycleStepF}. Liveness ns. -/

namespace Formal.Liveness.BurstStep

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepP
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CycleStepF
open Formal.Liveness.Drainability
open Formal.Liveness.BlockerSelection

/-- **One-step drain via the overstock channel.** When the refreshed selection
    state is pressured (`≥85%`), has junk to discard (`hasOverstockItems`), a
    non-empty bag, and the seven higher guard slots are quiet, the cycle selects
    `discardHigh` and `cycleStepF` drives `inventoryUsed` to `0`. Combines Brick
    3b's "pressured ⇒ a reducer fires" with the `discardHigh` selection lemma and
    Brick 2's `pressureDelta_reducer_clears`. -/
theorem cycleStepF_drains_via_discardHigh (s : State)
    (h0 : fires .hpCritical (perceptionRefresh s) = false)
    (h1 : fires .restForCombat (perceptionRefresh s) = false)
    (h2 : fires .bankUnlock (perceptionRefresh s) = false)
    (h3 : fires .reachUnlockLevel (perceptionRefresh s) = false)
    (h4 : fires .discardCritical (perceptionRefresh s) = false)
    (h5 : fires .craftRelief (perceptionRefresh s) = false)
    (h6 : fires .depositFull (perceptionRefresh s) = false)
    (hover : (perceptionRefresh s).hasOverstockItems = true)
    (hpre : Pressured (perceptionRefresh s))
    (hmax : (perceptionRefresh s).inventoryMax > 0) :
    (cycleStepF s).inventoryUsed = 0 := by
  -- discardHigh fires on the selection state (overstock ∧ max>0 ∧ ≥85%).
  have hfire : fires .discardHigh (perceptionRefresh s) = true := by
    show discardHighFires (perceptionRefresh s) = true
    simp only [discardHighFires, Bool.and_eq_true, decide_eq_true_eq]
    exact ⟨⟨hover, hmax⟩, hpre⟩
  -- with the seven higher slots quiet, the ladder SELECTS discardHigh.
  have hsel : productionLadder (perceptionRefresh s) = some .discardHigh :=
    productionLadder_eq_discardHigh (perceptionRefresh s) h0 h1 h2 h3 h4 h5 h6 hfire
  -- so cycleStepF applies the reducer's pressureDelta, draining to 0.
  unfold cycleStepF
  rw [hsel]
  exact pressureDelta_reducer_clears (by rfl) (cycleStepP s)

end Formal.Liveness.BurstStep
