import Formal.Liveness.ProductionLadder
import Mathlib.Tactic

/-! # InventoryPressure — Workstream A Phase-1 Brick 1: the gate-direction lemmas

Phase 0 of `docs/PLAN_faithfulness_modeling.md` established that the four
pressure-gated chores — `discardCritical`, `discardHigh`, `depositFull`,
`sellPressured` — fire ONLY when inventory pressure `inventoryUsed / inventoryMax`
meets their threshold. The threshold conjunct is ALREADY inside each `*Fires`
predicate (`ProductionLadder`), so the **gate direction** (fire ⇒ pressure ≥
threshold) is provable directly from the definitions — NO state extension needed.

These are the foundation of the faithful `BlockersQuiet` transience argument: the
contrapositive (`pressureGatedChores_quiet_of_low`) says that below the binding
85% threshold all four are quiet, so combat-pressure reduction (a deposit/discard
that drops `inventoryUsed`) provably drives them silent — the step the eventual
settled-reachability proof needs. The opaque chores (`craftRelief`, `gearReview`,
`claimPending`) and the two latches are handled in later bricks; this brick is the
threshold-gated four, which need nothing but their existing definitions.

Additive only; uses NO axioms beyond `ProductionLadder`'s import chain
({propext, Quot.sound}). Liveness namespace — Mathlib allowed. -/

namespace Formal.Liveness.InventoryPressure

open Formal.Liveness.Measure
open Formal.Liveness.ProductionLadder

/-! ## Gate direction — firing implies the pressure threshold is met -/

/-- `depositFull` fires ⇒ pressure ≥ 90% (`100·used ≥ 90·max`). -/
theorem depositFullFires_imp_threshold {s : State} (h : depositFullFires s = true) :
    DEPOSIT_FULL_DEN * s.inventoryUsed ≥ DEPOSIT_FULL_NUM * s.inventoryMax := by
  simp only [depositFullFires, Bool.and_eq_true, decide_eq_true_eq] at h
  exact h.1.2

/-- `discardCritical` fires ⇒ pressure ≥ 95%. -/
theorem discardCriticalFires_imp_threshold {s : State}
    (h : discardCriticalFires s = true) :
    DISCARD_CRITICAL_DEN * s.inventoryUsed ≥ DISCARD_CRITICAL_NUM * s.inventoryMax := by
  simp only [discardCriticalFires, Bool.and_eq_true, decide_eq_true_eq] at h
  exact h.2

/-- `discardHigh` fires ⇒ pressure ≥ 85%. -/
theorem discardHighFires_imp_threshold {s : State} (h : discardHighFires s = true) :
    DISCARD_HIGH_DEN * s.inventoryUsed ≥ DISCARD_HIGH_NUM * s.inventoryMax := by
  simp only [discardHighFires, Bool.and_eq_true, decide_eq_true_eq] at h
  exact h.2

/-- `sellPressured` fires ⇒ pressure ≥ 85%. -/
theorem sellPressuredFires_imp_threshold {s : State} (h : sellPressuredFires s = true) :
    SELL_PRESSURE_DEN * s.inventoryUsed ≥ SELL_PRESSURE_NUM * s.inventoryMax := by
  simp only [sellPressuredFires, Bool.and_eq_true, decide_eq_true_eq] at h
  exact h.1.2

/-! ## The transience foundation — low pressure silences all four gated chores

85% is the BINDING threshold: deposit needs 90%, critical 95%, high & sell 85%.
So `used/max < 85%` (`100·used < 85·max`) is below every one of them, and all four
are quiet. This is the step a settled-reachability proof invokes after a
pressure-reducing chore drops `inventoryUsed` below the band. -/

/-- Below the binding 85% pressure threshold, every pressure-gated chore is quiet.
    (`100·used < 85·max` ⇒ none of discardCritical/discardHigh/depositFull/
    sellPressured fires.) Proven by contradiction with each gate-direction lemma,
    discharging the constant arithmetic with `omega`. -/
theorem pressureGatedChores_quiet_of_low {s : State}
    (h : 100 * s.inventoryUsed < 85 * s.inventoryMax) :
    discardCriticalFires s = false ∧ discardHighFires s = false
      ∧ depositFullFires s = false ∧ sellPressuredFires s = false := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · by_contra hc
    have := discardCriticalFires_imp_threshold (by simpa using hc)
    simp only [DISCARD_CRITICAL_DEN, DISCARD_CRITICAL_NUM] at this
    omega
  · by_contra hc
    have := discardHighFires_imp_threshold (by simpa using hc)
    simp only [DISCARD_HIGH_DEN, DISCARD_HIGH_NUM] at this
    omega
  · by_contra hc
    have := depositFullFires_imp_threshold (by simpa using hc)
    simp only [DEPOSIT_FULL_DEN, DEPOSIT_FULL_NUM] at this
    omega
  · by_contra hc
    have := sellPressuredFires_imp_threshold (by simpa using hc)
    simp only [SELL_PRESSURE_DEN, SELL_PRESSURE_NUM] at this
    omega

end Formal.Liveness.InventoryPressure
