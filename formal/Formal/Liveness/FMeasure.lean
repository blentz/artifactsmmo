import Formal.Liveness.CumulativeProgress
import Formal.Liveness.CycleStepFIteration
import Mathlib.Order.WellFounded
import Mathlib.Data.Prod.Lex

/-! # FMeasure — the cycleStepF-tailored lex measure (unconditional-descent engine)

Phase U (see `docs/PLAN_l50_unconditional_descent.md`): the 16-slot lexicographic
measure under which EVERY below-50 `cycleStepF` cycle strictly descends — whatever
means the ladder selects. This is the measure that discharges the capstone's
`hquiet` (blockers-quiet) residual: instead of assuming every below-50 cycle
FIGHTS (`LevelingDescent.FightsBelowCap`), Brick 3/4 prove a per-means descent
covering every means selectable below the cap.

Slot design (most significant first) — each slot exists for a named blocker row,
and every means that RAISES a slot strictly descends an earlier one:

| # | slot | descended by | raised by (dominated via) |
|---|------|--------------|---------------------------|
| 1 | `levelDeficit`  | fight rollover | — (level monotone) |
| 2 | `xpDeficit`     | fight accumulate | rollover (slot 1) |
| 3 | `phasePresent`  | completeTask, taskCancel, lowYieldCancel (all set phase `.none`; their fires require phase ≠ `.none`) | acceptTask / taskTrade — unreachable below 50 (`objectiveStep` armed and earlier in `allInLadderOrder`). NOTE: `taskCompleteXpEstimate = 0` (server grants NO xp at turn-in, openapi-cited at `Measure.lean:440`), so completeTask CANNOT ride slots 1/2 — this slot is its descent. |
| 4 | `overstockFlag` | discardCritical, discardHigh | nothing in-model |
| 5 | `selectBankDepositsFlag` | depositFull | nothing in-model |
| 6 | `sellableFlag`  | sellPressured, sellRelief | nothing in-model |
| 7 | `recyclableFlag`| recycleRelief | nothing in-model |
| 8 | `craftReliefFlag` | craftRelief (`.craft` clears both craft flags) | nothing in-model |
| 9 | `craftPotionsFlag` | craftPotions | nothing in-model |
| 10 | `gearReviewFlag` | gearReview | nothing in-model |
| 11 | `pendingFlag`  | claimPending | nothing in-model |
| 12 | `bankPressure` (= raw `inventoryUsed`) | reducers (`→ 0`) | fight `+DROP_BOUND` (slots 1/2), claim `+1` (slot 11) |
| 13 | `hpDeficit`    | hpCritical / restForCombat (`hp := maxHp`, fires imply `hp < maxHp`) | nothing in-model |
| 14 | `geCancelFlag` | geCancel (fire-and-lose; clears only its own flag) | nothing in-model |
| 15 | `supplyDemandSlot` (2026-08-01) | supplyBank (`.gather` discharges one unit; fires require `supplyDemand ≥ SUPPLY_DEMAND_MIN > 0`) | nothing in-model |
| 16 | `currencyTurnInFlag` (2026-08-16) | currencyTurnIn (`.npcBuy` clears the flag; fire-and-lose, no threshold) | nothing in-model |

Deliberately NOT in the tuple: `objectiveStepFires`/`objectiveStepIsFight` (the ONLY
fields `perceptionRefresh` mutates — so the refresh is FMeasure-invariant by
construction) and the old measure's `taskCycles`/`skillXpDeficitProjected` (no
below-50-selectable means needs them, and `taskCycles` is RAISED by `acceptTask`,
which has no placeable fuel).

**Honesty note (why this is not the refused Settled false-story).** This measure
does NOT encode "chores never fire" or "chore flags never re-arm". It proves each
chore cycle itself makes strict progress — no quiescence or scheduling claim. The
theorem is about the MODEL (`cycleStepF`); its fidelity to production rests on the
named offline perimeter (opaque-flag differentials, defer-case characterization,
one-shot chore semantics — `docs/LEVEL_FIFTY_RESIDUALS.md`). Informal sketch of
why the shape is plausible for the real bot — fight-loot re-arms ride slot-1/2
descents; multi-step deposits drain `bankPressure` with flags equal — with one
DISCLOSED counter-instance: a claim-minted item can re-arm `overstockFlag`
(slot 4) on a cycle that descends only `pendingFlag` (slot 11), a local real-bot
measure increase the model does not exhibit. Chore-burst finiteness at such
points is covered only by the offline perimeter, not by this kernel proof.

Additive only. Liveness namespace — Mathlib allowed. Axioms of the defs:
`fMeasure` is `noncomputable` solely through `xpToNextLevel` (LIV-001). -/

set_option linter.dupNamespace false

namespace Formal.Liveness.FMeasure

open Formal.Liveness.Measure
open Formal.Liveness.CumulativeProgress (b2n)
open Formal.Liveness.CycleStepF
open Formal.Liveness.CycleStepFIteration

/-- The 16-slot lex measure for the faithful cycle. See module docstring for the
    slot-by-slot design table. -/
structure FMeasure where
  levelDeficit           : Nat
  xpDeficit              : Nat
  -- Slot 3 (2026-08-19). ACCEPT_TASK is promoted ABOVE `.objectiveStep`, and
  -- accepting RAISES `phasePresent` (none -> accepted) while touching no earlier
  -- slot — so unlike every other promoted rung it cannot descend at the bottom of
  -- the cascade the way `geCancelFlag` and `supplyDemandSlot` do. It descends
  -- HERE instead: a draw owed for the current course is discharged by taking it.
  -- The slot must precede `phasePresent` for that to dominate the phase rise.
  drawOwedFlag           : Nat
  phasePresent           : Nat
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
  -- geCancel is a fire-and-lose guard: `.geCancelOrder` clears ONLY
  -- `geCancelTargetsNonempty`, changing no other slot, so this flag can sit at the
  -- bottom of the cascade — a geCancel step decreases it with every higher slot
  -- equal, and no OTHER chore ever needs it (they all descend at a higher slot).
  geCancelFlag           : Nat
  -- Slot 15 (2026-08-01). SUPPLY_BANK was promoted ABOVE `.objectiveStep`, so a
  -- supply cycle is now selectable below the cap and must itself descend. Its
  -- `.gather` apply touches NO higher slot (it bumps `trackedSkillLevel`,
  -- `inventoryItems`, `skillXpDelta` — none of which are in this tuple) and
  -- discharges one unit of the outstanding request, so like `geCancelFlag` this
  -- flag sits at the bottom of the cascade. The strictness comes from
  -- `SUPPLY_DEMAND_MIN > 0`: the rung fires only at demand ≥ 10, so the
  -- saturating `- 1` is a genuine decrease. That is where the human ruling's
  -- threshold does real proof work — without it, a demand of 0 could fire the
  -- rung and the supply excursion would not terminate.
  supplyDemandSlot       : Nat
  -- Slot 16 (2026-08-16, fleet-currency-turn-in epic Task 6). CURRENCY_TURNIN
  -- sits directly below `supplyBank` in COLLECT_REWARD_ORDER — also ABOVE
  -- `.objectiveStep`, so it too is selectable below the cap and owes a
  -- descent. Its `.npcBuy` apply touches NO higher slot (it clears only
  -- `currencyTurnInActive`) and is fire-and-lose (unlike supplyBank, no
  -- threshold — the flag goes straight to false), so like `geCancelFlag` this
  -- flag sits at the bottom of the cascade, one below `supplyDemandSlot`
  -- since it is the newer of the two collect rungs.
  currencyTurnInFlag     : Nat
  deriving DecidableEq, Repr

/-- Extract the FMeasure from a `State`. Slot 3 is "a task is present"
    (`taskLifecyclePhase ≠ .none`) — the ONE quantity all three task-lifecycle
    blockers (`completeTask`, `taskCancel`, `lowYieldCancel`) strictly clear
    (their applies all set phase `.none`; their fires all require a non-`.none`
    phase). Slot 12 is RAW `inventoryUsed` (no threshold subtraction) — no chore
    descends via it, it only needs to be lex-dominated when raised. -/
noncomputable def fMeasure (s : State) : FMeasure :=
  { levelDeficit           := 50 - s.level
    xpDeficit              := xpToNextLevel s.level - s.xp
    drawOwedFlag           := b2n s.drawOwed
    phasePresent           := b2n (decide (s.taskLifecyclePhase ≠ .none))
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
    geCancelFlag           := b2n s.geCancelTargetsNonempty
    supplyDemandSlot       := s.supplyDemand
    currencyTurnInFlag     := b2n s.currencyTurnInActive }

/-! ## Strict lex order — hand-rolled 15-way disjunction (the
`CumulativeProgress.extMeasureLt` pattern). -/

/-- Equality of the first `n` slots, spelled out per prefix — the shared
    conjunction prefixes of `fMeasureLt`. -/
def fMeasureLt (m₁ m₂ : FMeasure) : Prop :=
  m₁.levelDeficit < m₂.levelDeficit
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit < m₂.xpDeficit)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag < m₂.drawOwedFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent < m₂.phasePresent)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag < m₂.overstockFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag < m₂.selectBankDepositsFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag < m₂.sellableFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag < m₂.recyclableFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag < m₂.craftReliefFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag = m₂.craftReliefFlag
     ∧ m₁.craftPotionsFlag < m₂.craftPotionsFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag = m₂.craftReliefFlag
     ∧ m₁.craftPotionsFlag = m₂.craftPotionsFlag
     ∧ m₁.gearReviewFlag < m₂.gearReviewFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag = m₂.craftReliefFlag
     ∧ m₁.craftPotionsFlag = m₂.craftPotionsFlag
     ∧ m₁.gearReviewFlag = m₂.gearReviewFlag
     ∧ m₁.pendingFlag < m₂.pendingFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag = m₂.craftReliefFlag
     ∧ m₁.craftPotionsFlag = m₂.craftPotionsFlag
     ∧ m₁.gearReviewFlag = m₂.gearReviewFlag
     ∧ m₁.pendingFlag = m₂.pendingFlag
     ∧ m₁.bankPressure < m₂.bankPressure)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag = m₂.craftReliefFlag
     ∧ m₁.craftPotionsFlag = m₂.craftPotionsFlag
     ∧ m₁.gearReviewFlag = m₂.gearReviewFlag
     ∧ m₁.pendingFlag = m₂.pendingFlag
     ∧ m₁.bankPressure = m₂.bankPressure
     ∧ m₁.hpDeficit < m₂.hpDeficit)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag = m₂.craftReliefFlag
     ∧ m₁.craftPotionsFlag = m₂.craftPotionsFlag
     ∧ m₁.gearReviewFlag = m₂.gearReviewFlag
     ∧ m₁.pendingFlag = m₂.pendingFlag
     ∧ m₁.bankPressure = m₂.bankPressure
     ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.geCancelFlag < m₂.geCancelFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag = m₂.craftReliefFlag
     ∧ m₁.craftPotionsFlag = m₂.craftPotionsFlag
     ∧ m₁.gearReviewFlag = m₂.gearReviewFlag
     ∧ m₁.pendingFlag = m₂.pendingFlag
     ∧ m₁.bankPressure = m₂.bankPressure
     ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.geCancelFlag = m₂.geCancelFlag
     ∧ m₁.supplyDemandSlot < m₂.supplyDemandSlot)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.drawOwedFlag = m₂.drawOwedFlag
     ∧ m₁.phasePresent = m₂.phasePresent
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.recyclableFlag = m₂.recyclableFlag
     ∧ m₁.craftReliefFlag = m₂.craftReliefFlag
     ∧ m₁.craftPotionsFlag = m₂.craftPotionsFlag
     ∧ m₁.gearReviewFlag = m₂.gearReviewFlag
     ∧ m₁.pendingFlag = m₂.pendingFlag
     ∧ m₁.bankPressure = m₂.bankPressure
     ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.geCancelFlag = m₂.geCancelFlag
     ∧ m₁.supplyDemandSlot = m₂.supplyDemandSlot
     ∧ m₁.currencyTurnInFlag < m₂.currencyTurnInFlag)

/-! ### Well-foundedness via embedding into Mathlib lex. -/

/-- Right-associated 17-tuple of `Nat`. Widened from sixteen on 2026-08-19 for
    `drawOwedFlag` — the third widening of this tuple, after slots 15 and 16. -/
abbrev LexSixteen :=
  Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ
    Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat

/-- Embed an `FMeasure` into the right-associated lex 16-tuple. -/
def toLex13 (m : FMeasure) : LexSixteen :=
  toLex (m.levelDeficit,
    toLex (m.xpDeficit,
      toLex (m.drawOwedFlag,
      toLex (m.phasePresent,
        toLex (m.overstockFlag,
          toLex (m.selectBankDepositsFlag,
            toLex (m.sellableFlag,
              toLex (m.recyclableFlag,
                toLex (m.craftReliefFlag,
                  toLex (m.craftPotionsFlag,
                    toLex (m.gearReviewFlag,
                      toLex (m.pendingFlag,
                        toLex (m.bankPressure,
                          toLex (m.hpDeficit,
                            toLex (m.geCancelFlag,
                              toLex (m.supplyDemandSlot, m.currencyTurnInFlag))))))))))))))))

/-- `fMeasureLt` implies the embedded `<` on `LexFifteen`. -/
theorem toLex13_lt_of_fMeasureLt
    {m₁ m₂ : FMeasure} (h : fMeasureLt m₁ m₂) :
    toLex13 m₁ < toLex13 m₂ := by
  simp only [toLex13, Prod.Lex.lt_iff, ofLex_toLex]
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · exact Or.inl h
  · obtain ⟨h1, h⟩ := h
    exact Or.inr ⟨h1, Or.inl h⟩
  · obtain ⟨h1, h2, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inl h⟩⟩
  · obtain ⟨h1, h2, hd, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inl h⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inl h⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4, Or.inl h⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inl h⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inl h⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10, h11, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12,
                Or.inr ⟨h13, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12,
                Or.inr ⟨h13, Or.inr ⟨h14, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14, h15, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨hd, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12,
                Or.inr ⟨h13, Or.inr ⟨h14, Or.inr ⟨h15, h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

/-- Well-foundedness of `fMeasureLt`, by `InvImage` reduction to Mathlib's
    standard well-founded order on `LexSixteen`. -/
theorem fMeasureLt_wellFounded : WellFounded fMeasureLt := by
  have hwf : WellFounded (fun a b : LexSixteen => a < b) :=
    (inferInstance : WellFoundedRelation LexSixteen).wf
  exact Subrelation.wf
    (h₁ := fun {a b} h => toLex13_lt_of_fMeasureLt h)
    (InvImage.wf toLex13 hwf)

/-! ## Slot-decrease helpers — one per descended slot (no helper for slot 12,
`bankPressure`: no means descends via it; it is only ever a dominated riser). -/

/-- Slot 1 (`levelDeficit`) decrease dominates. -/
theorem fLt_of_levelDeficit_dec {m₁ m₂ : FMeasure}
    (h : m₁.levelDeficit < m₂.levelDeficit) : fMeasureLt m₁ m₂ := Or.inl h

/-- Slot 2 (`xpDeficit`) decrease with slot 1 equal. -/
theorem fLt_of_xpDeficit_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h : m₁.xpDeficit < m₂.xpDeficit) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inl ⟨h1, h⟩)

/-- Slot 3 (`drawOwedFlag`) decrease with slots 1-2 equal. Taking the owed draw
    discharges it, which is why `.acceptTask` descends despite RAISING
    `phasePresent` one slot below. -/
theorem fLt_of_drawOwed_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h : m₁.drawOwedFlag < m₂.drawOwedFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inl ⟨h1, h2, h⟩))

/-- Slot 4 (`phasePresent`) decrease with slots 1-2 equal. -/
theorem fLt_of_phasePresent_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h : m₁.phasePresent < m₂.phasePresent) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, hd, h⟩)))

/-- Slot 4 (`overstockFlag`) decrease with slots 1-3 equal. -/
theorem fLt_of_overstock_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h : m₁.overstockFlag < m₂.overstockFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, hd, h3, h⟩))))

/-- Slot 5 (`selectBankDepositsFlag`) decrease with slots 1-4 equal. -/
theorem fLt_of_selectBankDeposits_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h : m₁.selectBankDepositsFlag < m₂.selectBankDepositsFlag) :
    fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h⟩)))))

/-- Slot 6 (`sellableFlag`) decrease with slots 1-5 equal. -/
theorem fLt_of_sellable_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h : m₁.sellableFlag < m₂.sellableFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h⟩))))))

/-- Slot 7 (`recyclableFlag`) decrease with slots 1-6 equal. -/
theorem fLt_of_recyclable_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h : m₁.recyclableFlag < m₂.recyclableFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h6, h⟩)))))))

/-- Slot 8 (`craftReliefFlag`) decrease with slots 1-7 equal. -/
theorem fLt_of_craftRelief_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h7 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h : m₁.craftReliefFlag < m₂.craftReliefFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h6, h7, h⟩))))))))

/-- Slot 9 (`craftPotionsFlag`) decrease with slots 1-8 equal. -/
theorem fLt_of_craftPotions_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h7 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h8 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h : m₁.craftPotionsFlag < m₂.craftPotionsFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h⟩)))))))))

/-- Slot 10 (`gearReviewFlag`) decrease with slots 1-9 equal. -/
theorem fLt_of_gearReview_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h7 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h8 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h9 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h : m₁.gearReviewFlag < m₂.gearReviewFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h⟩))))))))))

/-- Slot 11 (`pendingFlag`) decrease with slots 1-10 equal (slot 12 free — the
    claim mint's `+1` pressure is exactly what this dominates). -/
theorem fLt_of_pending_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h7 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h8 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h9 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h10 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h : m₁.pendingFlag < m₂.pendingFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10, h⟩)))))))))))

/-- Slot 13 (`hpDeficit`) decrease with slots 1-12 equal. -/
theorem fLt_of_hpDeficit_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h7 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h8 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h9 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h10 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h11 : m₁.pendingFlag = m₂.pendingFlag)
    (h12 : m₁.bankPressure = m₂.bankPressure)
    (h : m₁.hpDeficit < m₂.hpDeficit) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10, h11,
      h12, h⟩)))))))))))))

/-- Slot 14 (`geCancelFlag`) decrease with slots 1-13 equal — the fire-and-lose
    GE_CANCEL guard. `.geCancelOrder` clears only `geCancelTargetsNonempty`, so every
    higher slot is unchanged and this bottom slot strictly drops. -/
theorem fLt_of_geCancel_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h7 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h8 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h9 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h10 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h11 : m₁.pendingFlag = m₂.pendingFlag)
    (h12 : m₁.bankPressure = m₂.bankPressure)
    (h13 : m₁.hpDeficit = m₂.hpDeficit)
    (h : m₁.geCancelFlag < m₂.geCancelFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10,
      h11, h12, h13, h⟩))))))))))))))

/-- Slot 15 (`supplyDemandSlot`) decrease with slots 1-14 equal (2026-08-01).
    The SUPPLY_BANK rung's `.gather` apply touches no other slot, so — exactly
    like `geCancel` one rung above it — the whole cascade above is equal and the
    bottom slot carries the descent. -/
theorem fLt_of_supplyDemand_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h7 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h8 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h9 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h10 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h11 : m₁.pendingFlag = m₂.pendingFlag)
    (h12 : m₁.bankPressure = m₂.bankPressure)
    (h13 : m₁.hpDeficit = m₂.hpDeficit)
    (h14 : m₁.geCancelFlag = m₂.geCancelFlag)
    (h : m₁.supplyDemandSlot < m₂.supplyDemandSlot) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10,
      h11, h12, h13, h14, h⟩)))))))))))))))

/-- Slot 16 (`currencyTurnInFlag`) decrease with slots 1-15 equal
    (2026-08-16). The CURRENCY_TURNIN rung's `.npcBuy` apply touches no other
    slot, so — exactly like `supplyDemandSlot` one rung above it — the whole
    cascade above is equal and the bottom slot carries the descent. Unlike
    `supplyDemandSlot`, no threshold is needed: `.npcBuy` clears
    `currencyTurnInActive` unconditionally, so the fire-and-lose Bool flip
    `true → false` is itself the strict decrease. -/
theorem fLt_of_currencyTurnIn_dec {m₁ m₂ : FMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (hd : m₁.drawOwedFlag = m₂.drawOwedFlag)
    (h3 : m₁.phasePresent = m₂.phasePresent)
    (h4 : m₁.overstockFlag = m₂.overstockFlag)
    (h5 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h6 : m₁.sellableFlag = m₂.sellableFlag)
    (h7 : m₁.recyclableFlag = m₂.recyclableFlag)
    (h8 : m₁.craftReliefFlag = m₂.craftReliefFlag)
    (h9 : m₁.craftPotionsFlag = m₂.craftPotionsFlag)
    (h10 : m₁.gearReviewFlag = m₂.gearReviewFlag)
    (h11 : m₁.pendingFlag = m₂.pendingFlag)
    (h12 : m₁.bankPressure = m₂.bankPressure)
    (h13 : m₁.hpDeficit = m₂.hpDeficit)
    (h14 : m₁.geCancelFlag = m₂.geCancelFlag)
    (h15 : m₁.supplyDemandSlot = m₂.supplyDemandSlot)
    (h : m₁.currencyTurnInFlag < m₂.currencyTurnInFlag) : fMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
      ⟨h1, h2, hd, h3, h4, h5, h6, h7, h8, h9, h10,
       h11, h12, h13, h14, h15, h⟩)))))))))))))))

/-! ## The engine — reach 50 from per-cycle FMeasure descent (the
`MeasureDescent.exists_level_ge_of_descent` shape over the richer tuple). -/

/-- No sequence is infinitely strictly-`fMeasureLt`-descending. -/
theorem fNo_infinite_descent (seq : Nat → FMeasure)
    (h : ∀ n, fMeasureLt (seq (n + 1)) (seq n)) : False := by
  have key : ∀ x : FMeasure, ∀ n, seq n ≠ x := by
    intro x
    induction x using fMeasureLt_wellFounded.induction with
    | _ x ih =>
      intro n hn
      exact ih (seq (n + 1)) (hn ▸ h n) (n + 1) rfl
  exact key (seq 0) 0 rfl

/-- **The unconditional-descent level-50 engine.** If the FMeasure strictly
    decreases on every step of `traj` where `level < 50`, the trajectory reaches
    `level ≥ 50`. -/
theorem exists_level_ge_of_fdescent (traj : Nat → State)
    (hdesc : ∀ k, (traj k).level < 50 →
        fMeasureLt (fMeasure (traj (k + 1))) (fMeasure (traj k))) :
    ∃ k, (traj k).level ≥ 50 := by
  by_contra hcon
  push Not at hcon
  exact fNo_infinite_descent (fun k => fMeasure (traj k))
    (fun k => hdesc k (by have := hcon k; omega))

/-- Level-50 reachability for `cycleStepF` from per-cycle FMeasure descent —
    the engine instantiated at the faithful trajectory. Brick 4 discharges the
    hypothesis by ladder case analysis (`docs/PLAN_l50_unconditional_descent.md`). -/
theorem cycleStepF_reaches_fifty_of_fdescent (s : State)
    (hdesc : ∀ k, (cycleStepFN k s).level < 50 →
        fMeasureLt (fMeasure (cycleStepFN (k + 1) s)) (fMeasure (cycleStepFN k s))) :
    ∃ k, (cycleStepFN k s).level ≥ 50 :=
  exists_level_ge_of_fdescent (fun k => cycleStepFN k s) hdesc

/-- Non-vacuity of the descent hypothesis (the `MeasureDescent` audit pattern):
    it is jointly satisfiable WITH the goal — at a `≥ 50` state the hypothesis
    holds vacuously and the goal at `k = 0`. The SUBSTANTIVE discharge (every
    below-50 state descends) is Brick 4's theorem, which has no hypothesis at
    all — so the capstone built on this engine cannot be vacuous. -/
theorem fdescent_hyp_satisfiable_with_goal (s : State) (h : s.level ≥ 50) :
    (∀ k, (cycleStepFN k s).level < 50 →
        fMeasureLt (fMeasure (cycleStepFN (k + 1) s)) (fMeasure (cycleStepFN k s)))
    ∧ (∃ k, (cycleStepFN k s).level ≥ 50) := by
  refine ⟨fun k hk => absurd hk (by have := cycleStepFN_level_ge s k; omega), 0, ?_⟩
  rw [cycleStepFN_zero]; exact h

end Formal.Liveness.FMeasure
