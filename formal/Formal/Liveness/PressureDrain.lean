import Formal.Liveness.BurstStep
import Formal.Liveness.PressureBurst
import Formal.Liveness.FightFairness
import Formal.Liveness.NoDeadlockV2

/-! # PressureDrain — Workstream A Phase-1 Brick 3d-c (transience drain): the
selected-blocker-is-a-reducer crux + the full high-pressure drain step + the
generalized reducer-drain toolkit.

`BurstStep.cycleStepF_drains_via_discardHigh` proved the drain for the SPECIFIC
case where `discardHigh` is the selected reducer. The bounded-burst counting needs
the drain for ANY selected reducer (at ≥95% `discardCritical` is selected; at
≥90% `depositFull`; at ≥85% `discardHigh`/`sellPressured` — all reducers). This
module supplies the means-agnostic version: whenever the cycle SELECTS any
`isPressureReducer` means, the bag drains to `0`, and the next selection state is
therefore LOW pressure.

These are the per-step facts the transience WF consumes: a drain resets pressure to
`0` (so the immediately-following state satisfies the `ReducedResidualF`
low-pressure conjunct), and — with Brick 2's `cycleStepF_inventoryUsed_le_add_bound`
(a fill is ≤ `DROP_BOUND`) — bound the pressure excursion between two drains.

The crux `selected_isPressureReducer` is now PROVED: under `Pressured ∧ DrainArmed ∧
the ten nonPressureBlockers quiet`, the selected blocker is necessarily a pressure
chore (Brick 3b shows a drain channel fires, so the ladder selects in the blocker
prefix; the ten non-pressure blockers are quiet, so the selected blocker is one of
the four pressure chores, all reducers). With the reducer-drain step this gives the
HIGH-pressure half of the local dichotomy in full means-agnostic generality:
`cycleStepF_drains_when_pressured_armed_tenQuiet` — high pressure + drain-armed +
ten quiet ⇒ the bag drains to `0`. This is what closes `ReducedResidualF`'s
low-pressure conjunct one step at a time; the remaining work is the bounded-burst
COUNTING that turns per-step drains into low-pressure-INFINITELY-OFTEN.

Additive only; axioms ⊆ {propext, Quot.sound, LIV-001}. Liveness namespace. -/

namespace Formal.Liveness.PressureDrain

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CycleStepF
open Formal.Liveness.Drainability
open Formal.Liveness.PressureBurst
open Formal.Liveness.FightFairness
open Formal.Liveness.NoDeadlockV2

/-- Selected-blocker-fires extractor (a local copy of the private
    `CycleStep.fires_of_productionLadder`): the means the ladder selects fires. -/
private theorem fires_of_selected {s : State} {k : MeansKind}
    (h : productionLadder s = some k) : fires k s = true := by
  unfold productionLadder at h
  rw [List.findSome?_eq_some_iff] at h
  obtain ⟨_pre, x, _suf, _hl, hbody, _hpre_none⟩ := h
  by_cases hfire : fires x s = true
  · simp [hfire] at hbody; rw [← hbody]; exact hfire
  · simp [hfire] at hbody

/-- **The crux: the selected blocker is a pressure reducer.** When the refreshed
    selection state is pressured (≥85%), drain-armed, and the ten `nonPressureBlockers`
    are quiet, the means the ladder SELECTS is one of the four pressure-gated chores —
    hence a reducer. Brick 3b shows `discardHigh`/`sellPressured` fires, so the ladder
    selects WITHIN the blocker prefix (not the objectiveStep suffix); the selected
    blocker fires, the ten non-pressure blockers do not, so it is one of the four
    pressure chores. -/
theorem selected_isPressureReducer (r : State)
    (hp : Pressured r) (hmax : r.inventoryMax > 0) (ha : DrainArmed r)
    (hquiet : ∀ b ∈ nonPressureBlockers, fires b r = false)
    {m : MeansKind} (hsel : productionLadder r = some m) :
    isPressureReducer m = true := by
  have hmfire : fires m r = true := fires_of_selected hsel
  have hbf : discardHighFires r = true ∨ sellPressuredFires r = true :=
    reducer_fires_of_pressured_drainArmed hp hmax ha
  have hblockfires : ∃ b ∈ objectiveStepBlockers, fires b r = true := by
    rcases hbf with h | h
    · exact ⟨.discardHigh, by decide, h⟩
    · exact ⟨.sellPressured, by decide, h⟩
  have hpre_ne : (objectiveStepBlockers.findSome?
      (fun k => if fires k r then some k else none)) ≠ none := by
    obtain ⟨b, hbmem, hbf'⟩ := hblockfires
    intro hnone
    rw [List.findSome?_eq_none_iff] at hnone
    have := hnone b hbmem
    simp [hbf'] at this
  obtain ⟨b₀, hb₀⟩ := Option.ne_none_iff_exists'.mp hpre_ne
  have hsplit : productionLadder r = some b₀ := by
    unfold productionLadder
    rw [ladder_split_objectiveStep, List.findSome?_append, hb₀, Option.some_or]
  have hmb : m = b₀ := by rw [hsel] at hsplit; exact Option.some.inj hsplit
  have hb₀mem : b₀ ∈ objectiveStepBlockers := by
    rw [List.findSome?_eq_some_iff] at hb₀
    obtain ⟨pre, x, suf, hl, hbody, _⟩ := hb₀
    by_cases hfx : fires x r = true
    · simp [hfx] at hbody; rw [← hbody, hl]; simp
    · simp [hfx] at hbody
  subst hmb
  simp only [objectiveStepBlockers, List.mem_cons, List.not_mem_nil, or_false] at hb₀mem
  rcases hb₀mem with h|h|h|h|h|h|h|h|h|h|h|h|h|h <;> subst h
  · exact absurd hmfire (by rw [hquiet .hpCritical (by decide)]; decide)
  · exact absurd hmfire (by rw [hquiet .restForCombat (by decide)]; decide)
  · exact absurd hmfire (by rw [hquiet .bankUnlock (by decide)]; decide)
  · exact absurd hmfire (by rw [hquiet .reachUnlockLevel (by decide)]; decide)
  · rfl
  · exact absurd hmfire (by rw [hquiet .craftRelief (by decide)]; decide)
  · rfl
  · rfl
  · exact absurd hmfire (by rw [hquiet .gearReview (by decide)]; decide)
  · exact absurd hmfire (by rw [hquiet .claimPending (by decide)]; decide)
  · exact absurd hmfire (by rw [hquiet .completeTask (by decide)]; decide)
  · rfl
  · exact absurd hmfire (by rw [hquiet .lowYieldCancel (by decide)]; decide)
  · exact absurd hmfire (by rw [hquiet .taskCancel (by decide)]; decide)

/-- **Generalized reducer-drain step.** When the faithful cycle SELECTS any
    pressure-reducing means on the refreshed selection state, `cycleStepF` drains the
    bag to `0`. Generalizes `BurstStep.cycleStepF_drains_via_discardHigh` from the
    `discardHigh`-specific selection to ANY reducer (`pressureDelta` of every reducer
    clears `inventoryUsed`). -/
theorem cycleStepF_inventoryUsed_zero_of_reducer (s : State) {k : MeansKind}
    (hsel : productionLadder (perceptionRefresh s) = some k)
    (hred : isPressureReducer k = true) :
    (cycleStepF s).inventoryUsed = 0 := by
  unfold cycleStepF
  rw [hsel]
  exact pressureDelta_reducer_clears hred _

/-- **Low pressure after a drain.** A drained bag (`inventoryUsed = 0`) with positive
    capacity is strictly below the binding 85% threshold — i.e. the state satisfies
    `ReducedResidualF`'s low-pressure conjunct. Combined with the reducer-drain step,
    the state immediately AFTER any reducer selection is low pressure. -/
theorem low_pressure_of_drained {s : State}
    (hzero : s.inventoryUsed = 0) (hmax : s.inventoryMax > 0) :
    100 * s.inventoryUsed < 85 * s.inventoryMax := by
  rw [hzero]; omega

/-- **Low pressure after a reducer selection.** Composition: when the cycle selects a
    reducer, the resulting state has low pressure (positive capacity assumed — the
    capacity is preserved by `pressureDelta`/`cycleStepF`). The clean per-step fact
    the transience argument iterates between fills. -/
theorem cycleStepF_low_pressure_of_reducer (s : State) {k : MeansKind}
    (hsel : productionLadder (perceptionRefresh s) = some k)
    (hred : isPressureReducer k = true)
    (hmax : (cycleStepF s).inventoryMax > 0) :
    100 * (cycleStepF s).inventoryUsed < 85 * (cycleStepF s).inventoryMax :=
  low_pressure_of_drained (cycleStepF_inventoryUsed_zero_of_reducer s hsel hred) hmax

/-! ## The high-pressure half of the local dichotomy, in full -/

/-- **High-pressure drain step.** When the refreshed selection state is pressured
    (≥85%), drain-armed, with positive capacity and the ten `nonPressureBlockers`
    quiet, the faithful cycle drains the bag to `0`. The means-agnostic completion of
    `BurstStep.cycleStepF_drains_via_discardHigh`: the selected blocker is a reducer
    (the crux `selected_isPressureReducer`), and the reducer-drain step empties the
    bag. Together with the fight-side dichotomy
    (`PressureBurst.productionLadder_eq_objectiveStep_of_low_pressure`) this closes
    the local dichotomy — under the ten non-pressure blockers quiet, every refreshed
    selection state below the cap is a fight (low pressure) or a drain (high pressure
    + armed). -/
theorem cycleStepF_drains_when_pressured_armed_tenQuiet (s : State)
    (hp : Pressured (perceptionRefresh s)) (hmax : (perceptionRefresh s).inventoryMax > 0)
    (ha : DrainArmed (perceptionRefresh s))
    (hquiet : ∀ b ∈ nonPressureBlockers, fires b (perceptionRefresh s) = false) :
    (cycleStepF s).inventoryUsed = 0 := by
  obtain ⟨m, hm⟩ := exists_firing_means (perceptionRefresh s)
  exact cycleStepF_inventoryUsed_zero_of_reducer s hm
    (selected_isPressureReducer (perceptionRefresh s) hp hmax ha hquiet hm)

end Formal.Liveness.PressureDrain
