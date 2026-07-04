import Formal.Liveness.CumulativeProgress
import Mathlib.Order.WellFounded
import Mathlib.Data.Prod.Lex

/-! # DMeasure — the cycleStepD-tailored lex measure (residual closure)

Brick D1 of `docs/PLAN_residual_closure.md`. Extends the committed `FMeasure`
design (13 slots, `docs/PLAN_l50_unconditional_descent.md`) with TWO slots so
the DEFER-FAITHFUL, ADVERSARIALLY-RE-ARMING cycle (`cycleStepD`) descends on
every below-50 cycle:

| # | slot | descended by | raised by (dominated via) |
|---|------|--------------|---------------------------|
| 1 | `levelDeficit`  | fight rollover | — |
| 2 | `xpDeficit`     | fight accumulate | rollover (1) |
| 3 | `phasePresent`  | completeTask, taskCancel, lowYieldCancel | acceptTask — unreachable below 50 (armed objectiveStep outside the gate; `pursueTaskFires` inside it contradicts `acceptTaskFires`) |
| 4 | `taskCycles`    | pursueTask/taskTrade (defer window; gate supplies `progress < total`) | acceptTask — unreachable (as slot 3) |
| 5-12 | the 8 chore flags (FMeasure order) | their blocker rows | `choreRearm` on FIGHT cycles only (slots 1/2) |
| 13 | `bankPressure` | reducers | fight loot (1/2), claim mint (12) |
| 14 | `hpDeficit`    | hpCritical / restForCombat | — |
| 15 | `objectiveStepFlag` | synthetic placeholder (stale-true Bool inside the defer window, `isFight = false`; `pressureDeltaD` gives it NO loot, and a placeholder cycle never arms — the gate held) | `perceptionRefreshD` arming — dominated because EVERY other row descends a slot ≤ 14 |

Honesty: same discipline as FMeasure (no quiescence claim; theorem is about the
model; offline perimeter in `docs/LEVEL_FIFTY_RESIDUALS.md`). The re-arm slots
5-12 now survive the WORST-CASE re-arming (every fight re-arms everything), so
the "flags never re-arm" objection is closed for the fight direction; the
chore-cycle cross-arm (claim→overstock) stays a disclosed offline item.

Additive only. Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.DMeasure

open Formal.Liveness.Measure
open Formal.Liveness.CumulativeProgress (b2n)

/-- The 15-slot lex measure for the defer-faithful cycle. -/
structure DMeasure where
  levelDeficit           : Nat
  xpDeficit              : Nat
  phasePresent           : Nat
  taskCycles             : Nat
  overstockFlag          : Nat
  selectBankDepositsFlag : Nat
  sellableFlag           : Nat
  recyclableFlag         : Nat
  craftReliefFlag        : Nat
  craftPotionsFlag       : Nat
  gearReviewFlag         : Nat
  pendingFlag            : Nat
  bankPressure           : Nat
  hpDeficit              : Nat
  objectiveStepFlag      : Nat
  deriving DecidableEq, Repr

/-- Extract the DMeasure from a `State`. Slots 1-3, 5-12, 14-15 mirror
    `FMeasure.fMeasure` exactly; slot 4 is the items-task remainder; slot 13
    books the synthetic placeholder's clear of a stale-armed objective Bool. -/
noncomputable def dMeasure (s : State) : DMeasure :=
  { levelDeficit           := 50 - s.level
    xpDeficit              := xpToNextLevel s.level - s.xp
    phasePresent           := b2n (decide (s.taskLifecyclePhase ≠ .none))
    taskCycles             := s.taskTotal - s.taskProgress
    overstockFlag          := b2n s.hasOverstockItems
    selectBankDepositsFlag := b2n s.selectBankDepositsNonempty
    sellableFlag           := b2n s.sellableInventoryNonempty
    recyclableFlag         := b2n s.recyclableSurplusNonempty
    craftReliefFlag        := b2n s.craftReliefFires
    craftPotionsFlag       := b2n s.craftPotionsFires
    gearReviewFlag         := b2n s.gearReviewFires
    pendingFlag            := b2n s.pendingItemsNonempty
    bankPressure           := s.inventoryUsed
    hpDeficit              := s.maxHp - s.hp
    objectiveStepFlag      := b2n s.objectiveStepFires }

/-- Right-associated 15-tuple of `Nat`. -/
abbrev LexFifteenD :=
  Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ
    Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat

/-- Embed a `DMeasure` into the right-associated lex 15-tuple. -/
def toLex15D (m : DMeasure) : LexFifteenD :=
  toLex (m.levelDeficit,
    toLex (m.xpDeficit,
      toLex (m.phasePresent,
        toLex (m.taskCycles,
          toLex (m.overstockFlag,
            toLex (m.selectBankDepositsFlag,
              toLex (m.sellableFlag,
                toLex (m.recyclableFlag,
                  toLex (m.craftReliefFlag,
                    toLex (m.craftPotionsFlag,
                      toLex (m.gearReviewFlag,
                        toLex (m.pendingFlag,
                          toLex (m.bankPressure,
                            toLex (m.hpDeficit, m.objectiveStepFlag))))))))))))))

/-- Strict lex order on `DMeasure` — DEFINED via the Mathlib lex embedding
    (equivalent to the hand-rolled 15-way disjunction; the slot helpers below
    provide the per-slot introduction forms the descent proofs use). -/
def dMeasureLt (m₁ m₂ : DMeasure) : Prop :=
  toLex15D m₁ < toLex15D m₂

/-- Well-foundedness of `dMeasureLt` by `InvImage`. -/
theorem dMeasureLt_wellFounded : WellFounded dMeasureLt := by
  have hwf : WellFounded (fun a b : LexFifteenD => a < b) :=
    (inferInstance : WellFoundedRelation LexFifteenD).wf
  exact InvImage.wf toLex15D hwf

/-! ## Slot-decrease helpers. Each unfolds the embedding once; the equality
arguments pin every earlier slot. -/

private theorem lex_intro {m₁ m₂ : DMeasure}
    (h : toLex15D m₁ < toLex15D m₂) : dMeasureLt m₁ m₂ := h

theorem dLt_of_levelDeficit_dec {m₁ m₂ : DMeasure}
    (h : m₁.levelDeficit < m₂.levelDeficit) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inl h

theorem dLt_of_xpDeficit_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h : m₁.xpDeficit < m₂.xpDeficit) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inl h⟩

theorem dLt_of_phasePresent_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h : m₁.phasePresent < m₂.phasePresent) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inl h⟩⟩

theorem dLt_of_taskCycles_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h : m₁.taskCycles < m₂.taskCycles) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inl h⟩⟩⟩

theorem dLt_of_overstock_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h : m₁.overstockFlag < m₂.overstockFlag) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inl h⟩⟩⟩⟩

theorem dLt_of_selectBankDeposits_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h : m₁.selectBankDepositsFlag < m₂.selectBankDepositsFlag) :
    dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inl h⟩⟩⟩⟩⟩

theorem dLt_of_sellable_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h6 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h : m₁.sellableFlag < m₂.sellableFlag) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5,
    Or.inr ⟨h6, Or.inl h⟩⟩⟩⟩⟩⟩

theorem dLt_of_recyclable_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h6 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h7 : m₁.sellableFlag = m₂.sellableFlag)
    (h : m₁.recyclableFlag < m₂.recyclableFlag) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5,
    Or.inr ⟨h6, Or.inr ⟨h7, Or.inl h⟩⟩⟩⟩⟩⟩⟩

theorem dLt_of_craftRelief_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h6 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h7 : m₁.sellableFlag = m₂.sellableFlag)
    (h8 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h : m₁.craftReliefFlag < m₂.craftReliefFlag) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5,
    Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩

theorem dLt_of_craftPotions_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h6 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h7 : m₁.sellableFlag = m₂.sellableFlag)
    (h8 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h9 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h : m₁.craftPotionsFlag < m₂.craftPotionsFlag) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5,
    Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem dLt_of_gearReview_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h6 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h7 : m₁.sellableFlag = m₂.sellableFlag)
    (h8 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h9 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h10 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h : m₁.gearReviewFlag < m₂.gearReviewFlag) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5,
    Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10,
      Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem dLt_of_pending_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h6 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h7 : m₁.sellableFlag = m₂.sellableFlag)
    (h8 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h9 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h10 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h11 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h : m₁.pendingFlag < m₂.pendingFlag) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5,
    Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10,
      Or.inr ⟨h11, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem dLt_of_objectiveStepFlag_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h6 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h7 : m₁.sellableFlag = m₂.sellableFlag)
    (h8 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h9 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h10 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h11 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h12 : m₁.pendingFlag = m₂.pendingFlag)
    (h13 : m₁.bankPressure = m₂.bankPressure)
    (h14 : m₁.hpDeficit = m₂.hpDeficit)
    (h : m₁.objectiveStepFlag < m₂.objectiveStepFlag) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5,
    Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10,
      Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, Or.inr ⟨h14, h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem dLt_of_hpDeficit_dec {m₁ m₂ : DMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.taskCycles = m₂.taskCycles)
    (h5 : m₁.overstockFlag = m₂.overstockFlag)
    (h6 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h7 : m₁.sellableFlag = m₂.sellableFlag)
    (h8 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h9 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h10 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h11 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h12 : m₁.pendingFlag = m₂.pendingFlag)
    (h13 : m₁.bankPressure = m₂.bankPressure)
    (h : m₁.hpDeficit < m₂.hpDeficit) : dMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLex15D, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5,
    Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10,
      Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

/-! ## The engine — reach 50 from per-cycle DMeasure descent. -/

/-- No sequence is infinitely strictly-`dMeasureLt`-descending. -/
theorem dNo_infinite_descent (seq : Nat → DMeasure)
    (h : ∀ n, dMeasureLt (seq (n + 1)) (seq n)) : False := by
  have key : ∀ x : DMeasure, ∀ n, seq n ≠ x := by
    intro x
    induction x using dMeasureLt_wellFounded.induction with
    | _ x ih =>
      intro n hn
      exact ih (seq (n + 1)) (hn ▸ h n) (n + 1) rfl
  exact key (seq 0) 0 rfl

/-- **The defer-faithful level-50 engine.** If the DMeasure strictly decreases
    on every step of `traj` where `level < 50`, the trajectory reaches
    `level ≥ 50`. -/
theorem exists_level_ge_of_ddescent (traj : Nat → State)
    (hdesc : ∀ k, (traj k).level < 50 →
        dMeasureLt (dMeasure (traj (k + 1))) (dMeasure (traj k))) :
    ∃ k, (traj k).level ≥ 50 := by
  by_contra hcon
  push Not at hcon
  exact dNo_infinite_descent (fun k => dMeasure (traj k))
    (fun k => hdesc k (by have := hcon k; omega))

end Formal.Liveness.DMeasure
