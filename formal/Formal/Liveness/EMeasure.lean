import Formal.Liveness.CumulativeProgress
import Mathlib.Order.WellFounded
import Mathlib.Data.Prod.Lex

/-! # EMeasure — the geared-cycle lex measure (E-tower, C2b)

`docs/PLAN_c2_composed_liveness.md`. 20 slots. Gear slots:

* slot 1 `levelDeficit` — fight rollover; dominates the band-change gear
  re-arm (`gearGap := GEAR_CAP`, adequacy dropped).
* slot 2 `gearGap` — an open gap strictly decrements per gear cycle.
* slot 3 `inadequacyFlag` (`b2n !loadoutAdequate`) — pays for the
  gap-exhausted gear cycle that RESTORES adequacy (without it that cycle
  moves nothing the measure sees — a livelock the row analysis caught
  before proving). Raised only by the rollover re-arm (slot 1 pays).
* `gearReviewFlag` sits at slot 19, BELOW `hpDeficit`: the
  inadequate-arming refresh raises the latch on cycles that select
  rest/chores, so every other row descends above it; its own descent row is
  the STALE-latch clear (latch true in the pre-state with adequacy already
  true — the refresh only arms when inadequate).
* fight hp-loss raises only `hpDeficit` — dominated by slots 1/4.

Additive only. Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.EMeasure

open Formal.Liveness.Measure
open Formal.Liveness.CumulativeProgress (b2n)

/-- The 20-slot lex measure for the geared cycle. -/
structure EMeasure where
  levelDeficit           : Nat
  gearGap                : Nat
  inadequacyFlag         : Nat
  xpDeficit              : Nat
  phasePresent           : Nat
  taskCycles             : Nat
  pendingFlag            : Nat
  overstockDebt          : Nat
  overstockFlag          : Nat
  depositDebt            : Nat
  selectBankDepositsFlag : Nat
  sellDebt               : Nat
  sellableFlag           : Nat
  recyclableFlag         : Nat
  craftReliefFlag        : Nat
  craftPotionsFlag       : Nat
  bankPressure           : Nat
  hpDeficit              : Nat
  gearReviewFlag         : Nat
  objectiveStepFlag      : Nat
  deriving DecidableEq, Repr

/-- Extract the EMeasure from a `State` (slot order = field order). -/
noncomputable def eMeasure (s : State) : EMeasure :=
  { levelDeficit           := 50 - s.level
    gearGap                := s.gearGap
    inadequacyFlag         := b2n (!s.loadoutAdequate)
    xpDeficit              := xpToNextLevel s.level - s.xp
    phasePresent           := b2n (decide (s.taskLifecyclePhase ≠ .none))
    taskCycles             := s.taskTotal - s.taskProgress
    pendingFlag            := b2n s.pendingItemsNonempty
    overstockDebt          := s.overstockDebt
    overstockFlag          := b2n s.hasOverstockItems
    depositDebt            := s.depositDebt
    selectBankDepositsFlag := b2n s.selectBankDepositsNonempty
    sellDebt               := s.sellDebt
    sellableFlag           := b2n s.sellableInventoryNonempty
    recyclableFlag         := b2n s.recyclableSurplusNonempty
    craftReliefFlag        := b2n s.craftReliefFires
    craftPotionsFlag       := b2n s.craftPotionsFires
    bankPressure           := s.inventoryUsed
    hpDeficit              := s.maxHp - s.hp
    gearReviewFlag         := b2n s.gearReviewFires
    objectiveStepFlag      := b2n s.objectiveStepFires }

/-- Right-associated 20-tuple of `Nat`. -/
abbrev LexE :=
  Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ
    Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat

/-- Embed an `EMeasure` into the lex 20-tuple. -/
def toLexE (m : EMeasure) : LexE :=
  toLex (m.levelDeficit,
      toLex (m.gearGap,
      toLex (m.inadequacyFlag,
      toLex (m.xpDeficit,
      toLex (m.phasePresent,
      toLex (m.taskCycles,
      toLex (m.pendingFlag,
      toLex (m.overstockDebt,
      toLex (m.overstockFlag,
      toLex (m.depositDebt,
      toLex (m.selectBankDepositsFlag,
      toLex (m.sellDebt,
      toLex (m.sellableFlag,
      toLex (m.recyclableFlag,
      toLex (m.craftReliefFlag,
      toLex (m.craftPotionsFlag,
      toLex (m.bankPressure,
      toLex (m.hpDeficit,
      toLex (m.gearReviewFlag, m.objectiveStepFlag)))))))))))))))))))

/-- Strict lex order via the Mathlib embedding. -/
def eMeasureLt (m₁ m₂ : EMeasure) : Prop :=
  toLexE m₁ < toLexE m₂

/-- Well-foundedness by `InvImage`. -/
theorem eMeasureLt_wellFounded : WellFounded eMeasureLt := by
  have hwf : WellFounded (fun a b : LexE => a < b) :=
    (inferInstance : WellFoundedRelation LexE).wf
  exact InvImage.wf toLexE hwf

/-! ## Slot-decrease helpers. -/

private theorem lex_intro {m₁ m₂ : EMeasure}
    (h : toLexE m₁ < toLexE m₂) : eMeasureLt m₁ m₂ := h

theorem eLt_of_levelDeficit_dec {m₁ m₂ : EMeasure}
    (h : m₁.levelDeficit < m₂.levelDeficit) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inl h

theorem eLt_of_gearGap_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h : m₁.gearGap < m₂.gearGap) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inl h⟩

theorem eLt_of_inadequacy_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h : m₁.inadequacyFlag < m₂.inadequacyFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inl h⟩⟩

theorem eLt_of_xpDeficit_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h : m₁.xpDeficit < m₂.xpDeficit) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inl h⟩⟩⟩

theorem eLt_of_phasePresent_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h : m₁.phasePresent < m₂.phasePresent) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inl h⟩⟩⟩⟩

theorem eLt_of_taskCycles_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h : m₁.taskCycles < m₂.taskCycles) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inl h⟩⟩⟩⟩⟩

theorem eLt_of_pending_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h : m₁.pendingFlag < m₂.pendingFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inl h⟩⟩⟩⟩⟩⟩

theorem eLt_of_overstockDebt_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h : m₁.overstockDebt < m₂.overstockDebt) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inl h⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_overstock_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h : m₁.overstockFlag < m₂.overstockFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_depositDebt_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h : m₁.depositDebt < m₂.depositDebt) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_selectBankDeposits_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h : m₁.selectBankDepositsFlag < m₂.selectBankDepositsFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_sellDebt_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h11 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h : m₁.sellDebt < m₂.sellDebt) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_sellable_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h11 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h12 : m₁.sellDebt = m₂.sellDebt)
    (h : m₁.sellableFlag < m₂.sellableFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_recyclable_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h11 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h12 : m₁.sellDebt = m₂.sellDebt)
    (h13 : m₁.sellableFlag = m₂.sellableFlag)
    (h : m₁.recyclableFlag < m₂.recyclableFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_craftRelief_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h11 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h12 : m₁.sellDebt = m₂.sellDebt)
    (h13 : m₁.sellableFlag = m₂.sellableFlag)
    (h14 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h : m₁.craftReliefFlag < m₂.craftReliefFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, Or.inr ⟨h14, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_craftPotions_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h11 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h12 : m₁.sellDebt = m₂.sellDebt)
    (h13 : m₁.sellableFlag = m₂.sellableFlag)
    (h14 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h15 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h : m₁.craftPotionsFlag < m₂.craftPotionsFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, Or.inr ⟨h14, Or.inr ⟨h15, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_hpDeficit_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h11 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h12 : m₁.sellDebt = m₂.sellDebt)
    (h13 : m₁.sellableFlag = m₂.sellableFlag)
    (h14 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h15 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h16 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h17 : m₁.bankPressure = m₂.bankPressure)
    (h : m₁.hpDeficit < m₂.hpDeficit) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, Or.inr ⟨h14, Or.inr ⟨h15, Or.inr ⟨h16, Or.inr ⟨h17, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_gearReview_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h11 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h12 : m₁.sellDebt = m₂.sellDebt)
    (h13 : m₁.sellableFlag = m₂.sellableFlag)
    (h14 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h15 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h16 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h17 : m₁.bankPressure = m₂.bankPressure)
    (h18 : m₁.hpDeficit = m₂.hpDeficit)
    (h : m₁.gearReviewFlag < m₂.gearReviewFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, Or.inr ⟨h14, Or.inr ⟨h15, Or.inr ⟨h16, Or.inr ⟨h17, Or.inr ⟨h18, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

theorem eLt_of_objectiveStepFlag_dec {m₁ m₂ : EMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.gearGap = m₂.gearGap)
    (h3 : m₁.inadequacyFlag = m₂.inadequacyFlag)
    (h4 : m₁.xpDeficit = m₂.xpDeficit)
    (h5 : m₁.phasePresent = m₂.phasePresent)
    (h6 : m₁.taskCycles = m₂.taskCycles)
    (h7 : m₁.pendingFlag = m₂.pendingFlag)
    (h8 : m₁.overstockDebt = m₂.overstockDebt)
    (h9 : m₁.overstockFlag = m₂.overstockFlag)
    (h10 : m₁.depositDebt = m₂.depositDebt)
    (h11 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h12 : m₁.sellDebt = m₂.sellDebt)
    (h13 : m₁.sellableFlag = m₂.sellableFlag)
    (h14 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h15 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h16 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h17 : m₁.bankPressure = m₂.bankPressure)
    (h18 : m₁.hpDeficit = m₂.hpDeficit)
    (h19 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h : m₁.objectiveStepFlag < m₂.objectiveStepFlag) : eMeasureLt m₁ m₂ := by
  apply lex_intro
  simp only [toLexE, Prod.Lex.lt_iff, ofLex_toLex]
  exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, Or.inr ⟨h14, Or.inr ⟨h15, Or.inr ⟨h16, Or.inr ⟨h17, Or.inr ⟨h18, Or.inr ⟨h19, h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

/-! ## The engine. -/

/-- No sequence is infinitely strictly-`eMeasureLt`-descending. -/
theorem eNo_infinite_descent (seq : Nat → EMeasure)
    (h : ∀ n, eMeasureLt (seq (n + 1)) (seq n)) : False := by
  have key : ∀ x : EMeasure, ∀ n, seq n ≠ x := by
    intro x
    induction x using eMeasureLt_wellFounded.induction with
    | _ x ih =>
      intro n hn
      exact ih (seq (n + 1)) (hn ▸ h n) (n + 1) rfl
  exact key (seq 0) 0 rfl

/-- **The geared level-50 engine.** -/
theorem exists_level_ge_of_edescent (traj : Nat → State)
    (hdesc : ∀ k, (traj k).level < 50 →
        eMeasureLt (eMeasure (traj (k + 1))) (eMeasure (traj k))) :
    ∃ k, (traj k).level ≥ 50 := by
  by_contra hcon
  push Not at hcon
  exact eNo_infinite_descent (fun k => eMeasure (traj k))
    (fun k => hdesc k (by have := hcon k; omega))

end Formal.Liveness.EMeasure
