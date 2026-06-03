/-
  Formal.Liveness.CumulativeProgress

  Phase 23a/b — Tier 4 cumulative progress.

  ## Phase 23a — weaker form (kept intact)

  `cumulative_state_change_under_no_wait`: under three load-bearing
  hypotheses (`level < 50`, "no wait ever fires", and the `.taskExchange`
  non-degeneracy lifted pointwise) some iterate of `cycleStep` produces
  a state different from the starting one.

  ## Phase 23b — strong form (level strictly advances)

  `cumulative_progress_under_no_wait_restricted`: under FIVE load-bearing
  hypotheses surfaced in the signature, some iterate of `cycleStep`
  produces a state whose level is strictly greater than the starting
  level. The proof goes through well-founded induction on an EXTENDED
  lex measure (see `ExtMeasure` below).

  The strong form CANNOT be proved unconditionally for all 17 non-wait
  MeansKinds: the task lifecycle (acceptTask → pursueTask → completeTask
  → taskCancel) creates fundamental measure-monotonicity obstructions —
  acceptTask CREATES task state (slot 4 taskCycles goes 0→1), pursueTask
  ADVANCES task progress without level change, completeTask CLEARS task
  state but flips a `noTaskFlag` upward. No single lex tuple over the
  current `State` can dominate all of these unilaterally.

  Phase 23b's honest workaround: restrict the trajectory to a subset of
  12 means whose firing strictly decreases the extended measure (or
  advances the level). The restriction is surfaced as a sixth
  load-bearing hypothesis. Phase 23c (out of scope) will lift the
  restriction by augmenting the state with a "task lifecycle counter"
  that absorbs the lifecycle transitions.

  The 12 in-scope means (`progressMeans`) are:
    .hpCritical, .bankUnlock, .reachUnlockLevel,
    .discardCritical, .depositFull, .discardHigh,
    .claimPending, .sellPressured, .objectiveStep,
    .taskExchange, .sellIdle, .bankExpand.

  The 5 out-of-scope means (deferred to 23c, surfaced as restriction):
    .completeTask, .lowYieldCancel, .taskCancel, .pursueTask, .acceptTask.
  (Plus `.wait` which the existing `hnowait` hypothesis already excludes.)

  ## Extended measure (Phase 23b)

  The Phase-19c 6-tuple is augmented with 8 slots — total 14 slots,
  ordered lex (most significant first):

      1. levelDeficit               (existing)
      2. xpDeficit                  (existing)
      3. taskCycles                 (existing)
      4. skillXpDeficitProjected    (existing)
      5. bankPressure               (existing)
      6. hpDeficit                  (existing)
      7. bankInaccessibleFlag       (NEW — bankUnlock witness)
      8. overstockFlag              (NEW — discardCritical/discardHigh)
      9. selectBankDepositsFlag     (NEW — depositFull when bankPressure already 0)
     10. sellableFlag               (NEW — sellPressured/sellIdle)
     11. pendingItemsFlag           (NEW — claimPending)
     12. objectiveStepFlag          (NEW — objectiveStep)
     13. taskCoinsTotal             (NEW — taskExchange, gated by hex)
     14. gold                       (NEW — bankExpand, gated by nextExpansionCost > 0)

  Slots 1-6 match the existing Phase-19 measure verbatim. Adding slots
  7-14 BELOW slot 6 preserves all Phase-19 progress lemmas
  (`fight_decreases_measure`, etc.) — they decrease slot 1, 2, 4, 5, or
  6 and remain valid in any lex extension to the right.

  ## Integrity

  - No `sorry`/`admit`/`native_decide`.
  - No new `axiom` keyword.
  - All `noncomputable` markers descend from LIV-001 `xpToNextLevel`.
  - Axioms ⊆ {propext, Classical.choice, Quot.sound, xpToNextLevel,
              plus Mathlib's standard axioms via WellFounded imports}.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.CycleStep
import Formal.Liveness.ProductionLadder
import Formal.Liveness.Measure
import Formal.Liveness.NoDeadlockV2
import Formal.Liveness.LIV003Decomposition
import Mathlib.Order.WellFounded
import Mathlib.Data.Prod.Lex

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.CumulativeProgress

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.NoDeadlockV2
open Formal.Liveness.LIV003Decomposition

/-! ## cycleStepN — iterated cycle transition -/

/-- Iterate `cycleStep` n times. Tail-recursive shape so unfolding at
    `n+1` exposes the next state directly. -/
noncomputable def cycleStepN : Nat → State → State
  | 0,     s => s
  | n+1,   s => cycleStepN n (cycleStep s)

@[simp] theorem cycleStepN_zero (s : State) : cycleStepN 0 s = s := rfl

theorem cycleStepN_succ (n : Nat) (s : State) :
    cycleStepN (n+1) s = cycleStepN n (cycleStep s) := rfl

/-- Composition law for `cycleStepN`. Moved here (Item 1g-C) from
    `LevelFiftyReachable` to let `XpMonotonicity`/`LifecycleBound7`
    consume it without pulling in the rest of LevelFifty. -/
theorem cycleStepN_add (m n : Nat) (s : State) :
    cycleStepN (m + n) s = cycleStepN n (cycleStepN m s) := by
  induction m generalizing s with
  | zero =>
    show cycleStepN (0 + n) s = cycleStepN n (cycleStepN 0 s)
    rw [cycleStepN_zero, Nat.zero_add]
  | succ j ih =>
    show cycleStepN ((j + 1) + n) s = cycleStepN n (cycleStepN (j + 1) s)
    rw [show (j + 1) + n = (j + n) + 1 from by omega]
    rw [cycleStepN_succ (j + n) s]
    rw [cycleStepN_succ j s]
    exact ih (cycleStep s)

/-! ## Weaker headline — Phase 23a, kept intact -/

/-- WEAKER Tier-4 headline shipped in Phase 23a.

    Under three load-bearing hypotheses, some iterate of `cycleStep`
    produces a state different from the starting one. See the original
    23a docstring for the full discussion. -/
theorem cumulative_state_change_under_no_wait
    (s : State)
    (_hlvl : s.level < 50)
    (hnowait : ∀ k, productionLadder (cycleStepN k s) ≠ some .wait)
    (hex : ∀ k, productionLadder (cycleStepN k s) = some .taskExchange →
                (cycleStepN k s).taskExchangeMinCoins > 0) :
    ∃ k, cycleStepN k s ≠ s := by
  have h22a := cycleStep_progress_or_waits s (hex 0)
  have hwait0 : productionLadder s ≠ some .wait := by
    have := hnowait 0
    simpa [cycleStepN] using this
  have hne : cycleStep s ≠ s := by
    cases h22a with
    | inl h => exact h
    | inr h => exact absurd h hwait0
  refine ⟨1, ?_⟩
  show cycleStepN 1 s ≠ s
  have hrw : cycleStepN 1 s = cycleStep s := by
    rw [cycleStepN_succ]; rfl
  rw [hrw]
  exact hne

/-! ## Phase 23b extension — restricted progress-means set -/

/-- The 12-element subset of `MeansKind` for which Phase 23b proves
    strict measure decrease (or level advance). The 5 deferred kinds
    (`acceptTask`, `pursueTask`, `completeTask`, `taskCancel`,
    `lowYieldCancel`) are task-lifecycle transitions that require Phase
    23c's task-lifecycle counter. -/
def progressMeans : List MeansKind :=
  [.hpCritical, .bankUnlock, .reachUnlockLevel,
   .discardCritical, .depositFull, .discardHigh,
   .claimPending, .sellPressured, .objectiveStep,
   .taskExchange, .sellIdle, .bankExpand]

/-! ## Extended lex measure (Phase 23b)

The Phase-19c 6-tuple measure is augmented with 8 new Nat slots placed
LEX-BELOW the existing 6. Slot encodings: 1 = "still has work", 0 =
"work cleared" for the flag slots. -/

/-- Bool-to-Nat helper. `1` for `true`, `0` for `false`. -/
@[inline] def b2n (b : Bool) : Nat := if b then 1 else 0

@[simp] theorem b2n_true  : b2n true  = 1 := rfl
@[simp] theorem b2n_false : b2n false = 0 := rfl

/-- Extended 14-tuple lex measure. Slots 1-6 mirror `Measure` exactly. -/
structure ExtMeasure where
  -- 1-6: Phase-19c base.
  levelDeficit            : Nat
  xpDeficit               : Nat
  taskCycles              : Nat
  skillXpDeficitProjected : Nat
  bankPressure            : Nat
  hpDeficit               : Nat
  -- 7-14: Phase 23b additions.
  bankInaccessibleFlag    : Nat
  overstockFlag           : Nat
  selectBankDepositsFlag  : Nat
  sellableFlag            : Nat
  pendingItemsFlag        : Nat
  objectiveStepFlag       : Nat
  taskCoinsTotal          : Nat
  gold                    : Nat
  deriving DecidableEq, Repr

/-- Extract the extended measure from a `State`. -/
noncomputable def extMeasure (s : State) : ExtMeasure :=
  { levelDeficit            := 50 - s.level
    xpDeficit               := xpToNextLevel s.level - s.xp
    taskCycles              := s.taskTotal - s.taskProgress
    skillXpDeficitProjected := s.targetSkillXp - s.projectedSkillXpDelta
    bankPressure            := s.inventoryUsed - bankPressureThreshold s.inventoryMax
    hpDeficit               := s.maxHp - s.hp
    bankInaccessibleFlag    := b2n (!s.bankAccessible)
    overstockFlag           := b2n s.hasOverstockItems
    selectBankDepositsFlag  := b2n s.selectBankDepositsNonempty
    sellableFlag            := b2n s.sellableInventoryNonempty
    pendingItemsFlag        := b2n s.pendingItemsNonempty
    objectiveStepFlag       := b2n s.objectiveStepFires
    taskCoinsTotal          := s.taskCoinsTotal
    gold                    := s.gold }

/-! ## Strict lex order on `ExtMeasure`

Hand-rolled 14-way disjunction: at the first index where the tuples
differ, the smaller component wins. -/

/-- Strict lex order on `ExtMeasure`. -/
def extMeasureLt (m₁ m₂ : ExtMeasure) : Prop :=
  -- Slot 1 strictly less.
  m₁.levelDeficit < m₂.levelDeficit
  -- OR (equal in slot 1 AND slot 2 strictly less).
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit < m₂.xpDeficit)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles < m₂.taskCycles)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected < m₂.skillXpDeficitProjected)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure < m₂.bankPressure)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit < m₂.hpDeficit)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.bankInaccessibleFlag < m₂.bankInaccessibleFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag
     ∧ m₁.overstockFlag < m₂.overstockFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag < m₂.selectBankDepositsFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag < m₂.sellableFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.pendingItemsFlag < m₂.pendingItemsFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.pendingItemsFlag = m₂.pendingItemsFlag
     ∧ m₁.objectiveStepFlag < m₂.objectiveStepFlag)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.pendingItemsFlag = m₂.pendingItemsFlag
     ∧ m₁.objectiveStepFlag = m₂.objectiveStepFlag
     ∧ m₁.taskCoinsTotal < m₂.taskCoinsTotal)
  ∨ (m₁.levelDeficit = m₂.levelDeficit ∧ m₁.xpDeficit = m₂.xpDeficit
     ∧ m₁.taskCycles = m₂.taskCycles
     ∧ m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected
     ∧ m₁.bankPressure = m₂.bankPressure ∧ m₁.hpDeficit = m₂.hpDeficit
     ∧ m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag
     ∧ m₁.overstockFlag = m₂.overstockFlag
     ∧ m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag
     ∧ m₁.sellableFlag = m₂.sellableFlag
     ∧ m₁.pendingItemsFlag = m₂.pendingItemsFlag
     ∧ m₁.objectiveStepFlag = m₂.objectiveStepFlag
     ∧ m₁.taskCoinsTotal = m₂.taskCoinsTotal
     ∧ m₁.gold < m₂.gold)

/-! ### Well-foundedness of `extMeasureLt` via embedding into Mathlib lex. -/

/-- Right-associated 14-tuple of `Nat` for the embedding. -/
abbrev LexFourteen :=
  Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat ×ₗ
    Nat ×ₗ Nat ×ₗ Nat ×ₗ Nat

/-- Embed an `ExtMeasure` into the right-associated lex 14-tuple. -/
def toLex14 (m : ExtMeasure) : LexFourteen :=
  toLex (m.levelDeficit,
    toLex (m.xpDeficit,
      toLex (m.taskCycles,
        toLex (m.skillXpDeficitProjected,
          toLex (m.bankPressure,
            toLex (m.hpDeficit,
              toLex (m.bankInaccessibleFlag,
                toLex (m.overstockFlag,
                  toLex (m.selectBankDepositsFlag,
                    toLex (m.sellableFlag,
                      toLex (m.pendingItemsFlag,
                        toLex (m.objectiveStepFlag,
                          toLex (m.taskCoinsTotal, m.gold)))))))))))))

/-- `extMeasureLt` implies the embedded `<` on `LexFourteen`. -/
theorem toLex14_lt_of_extMeasureLt
    {m₁ m₂ : ExtMeasure} (h : extMeasureLt m₁ m₂) :
    toLex14 m₁ < toLex14 m₂ := by
  simp only [toLex14, Prod.Lex.lt_iff, ofLex_toLex]
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · exact Or.inl h
  · obtain ⟨h1, h⟩ := h
    exact Or.inr ⟨h1, Or.inl h⟩
  · obtain ⟨h1, h2, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inl h⟩⟩
  · obtain ⟨h1, h2, h3, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inl h⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4, Or.inl h⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inl h⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h6, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inl h⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h6, h7, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inl h⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inl h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩
  · obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h⟩ := h
    exact Or.inr ⟨h1, Or.inr ⟨h2, Or.inr ⟨h3, Or.inr ⟨h4,
            Or.inr ⟨h5, Or.inr ⟨h6, Or.inr ⟨h7, Or.inr ⟨h8,
              Or.inr ⟨h9, Or.inr ⟨h10, Or.inr ⟨h11, Or.inr ⟨h12, Or.inr ⟨h13, h⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩⟩

/-- Well-foundedness of `extMeasureLt`, by `InvImage` reduction to
    Mathlib's standard well-founded order on `LexFourteen`. -/
theorem extMeasureLt_wellFounded : WellFounded extMeasureLt := by
  have hwf : WellFounded (fun a b : LexFourteen => a < b) :=
    (inferInstance : WellFoundedRelation LexFourteen).wf
  exact Subrelation.wf
    (h₁ := fun {a b} h => toLex14_lt_of_extMeasureLt h)
    (InvImage.wf toLex14 hwf)

/-! ## Slot-decrease helpers — one per slot 1..14 -/

/-- Slot 1 (levelDeficit) decrease dominates. -/
theorem extLt_of_level_dec {m₁ m₂ : ExtMeasure}
    (h : m₁.levelDeficit < m₂.levelDeficit) : extMeasureLt m₁ m₂ := Or.inl h

/-- Slot 2 (xpDeficit) decrease with slot 1 equal. -/
theorem extLt_of_xp_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h : m₁.xpDeficit < m₂.xpDeficit) : extMeasureLt m₁ m₂ :=
  Or.inr (Or.inl ⟨h1, h⟩)

/-- Slot 6 (hpDeficit) decrease with slots 1-5 equal. -/
theorem extLt_of_hp_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h : m₁.hpDeficit < m₂.hpDeficit) : extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨h1, h2, h3, h4, h5, h⟩)))))

/-- Slot 7 (bankInaccessibleFlag) decrease with slots 1-6 equal. -/
theorem extLt_of_bankInacc_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h6 : m₁.hpDeficit = m₂.hpDeficit)
    (h : m₁.bankInaccessibleFlag < m₂.bankInaccessibleFlag) :
    extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
    ⟨h1, h2, h3, h4, h5, h6, h⟩))))))

/-- Slot 8 (overstockFlag) decrease with slots 1-7 equal. -/
theorem extLt_of_overstock_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h6 : m₁.hpDeficit = m₂.hpDeficit)
    (h7 : m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag)
    (h : m₁.overstockFlag < m₂.overstockFlag) :
    extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
    ⟨h1, h2, h3, h4, h5, h6, h7, h⟩)))))))

/-- Slot 9 (selectBankDepositsFlag) decrease with slots 1-8 equal. -/
theorem extLt_of_selectBank_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h6 : m₁.hpDeficit = m₂.hpDeficit)
    (h7 : m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag)
    (h8 : m₁.overstockFlag = m₂.overstockFlag)
    (h : m₁.selectBankDepositsFlag < m₂.selectBankDepositsFlag) :
    extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
    ⟨h1, h2, h3, h4, h5, h6, h7, h8, h⟩))))))))

/-- Slot 10 (sellableFlag) decrease with slots 1-9 equal. -/
theorem extLt_of_sellable_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h6 : m₁.hpDeficit = m₂.hpDeficit)
    (h7 : m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag)
    (h8 : m₁.overstockFlag = m₂.overstockFlag)
    (h9 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h : m₁.sellableFlag < m₂.sellableFlag) :
    extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
    ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h⟩)))))))))

/-- Slot 11 (pendingItemsFlag) decrease with slots 1-10 equal. -/
theorem extLt_of_pending_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h6 : m₁.hpDeficit = m₂.hpDeficit)
    (h7 : m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag)
    (h8 : m₁.overstockFlag = m₂.overstockFlag)
    (h9 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h10 : m₁.sellableFlag = m₂.sellableFlag)
    (h : m₁.pendingItemsFlag < m₂.pendingItemsFlag) :
    extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
    ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h⟩))))))))))

/-- Slot 12 (objectiveStepFlag) decrease with slots 1-11 equal. -/
theorem extLt_of_objStep_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h6 : m₁.hpDeficit = m₂.hpDeficit)
    (h7 : m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag)
    (h8 : m₁.overstockFlag = m₂.overstockFlag)
    (h9 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h10 : m₁.sellableFlag = m₂.sellableFlag)
    (h11 : m₁.pendingItemsFlag = m₂.pendingItemsFlag)
    (h : m₁.objectiveStepFlag < m₂.objectiveStepFlag) :
    extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
    ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h⟩)))))))))))

/-- Slot 13 (taskCoinsTotal) decrease with slots 1-12 equal. -/
theorem extLt_of_taskCoins_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h6 : m₁.hpDeficit = m₂.hpDeficit)
    (h7 : m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag)
    (h8 : m₁.overstockFlag = m₂.overstockFlag)
    (h9 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h10 : m₁.sellableFlag = m₂.sellableFlag)
    (h11 : m₁.pendingItemsFlag = m₂.pendingItemsFlag)
    (h12 : m₁.objectiveStepFlag = m₂.objectiveStepFlag)
    (h : m₁.taskCoinsTotal < m₂.taskCoinsTotal) :
    extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inl
    ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h⟩))))))))))))

/-- Slot 14 (gold) decrease with slots 1-13 equal. -/
theorem extLt_of_gold_dec {m₁ m₂ : ExtMeasure}
    (h1 : m₁.levelDeficit = m₂.levelDeficit)
    (h2 : m₁.xpDeficit = m₂.xpDeficit)
    (h3 : m₁.taskCycles = m₂.taskCycles)
    (h4 : m₁.skillXpDeficitProjected = m₂.skillXpDeficitProjected)
    (h5 : m₁.bankPressure = m₂.bankPressure)
    (h6 : m₁.hpDeficit = m₂.hpDeficit)
    (h7 : m₁.bankInaccessibleFlag = m₂.bankInaccessibleFlag)
    (h8 : m₁.overstockFlag = m₂.overstockFlag)
    (h9 : m₁.selectBankDepositsFlag = m₂.selectBankDepositsFlag)
    (h10 : m₁.sellableFlag = m₂.sellableFlag)
    (h11 : m₁.pendingItemsFlag = m₂.pendingItemsFlag)
    (h12 : m₁.objectiveStepFlag = m₂.objectiveStepFlag)
    (h13 : m₁.taskCoinsTotal = m₂.taskCoinsTotal)
    (h : m₁.gold < m₂.gold) :
    extMeasureLt m₁ m₂ :=
  Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr (Or.inr
    ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h⟩))))))))))))

/-! ## cycleStep level-monotonicity

A small lemma used by the well-founded induction: `cycleStep` never
DECREASES the level. Plan.lean's `applyActionKind .fight` either
preserves or increments level; all other branches preserve it. -/

theorem cycleStep_level_ge (s : State) : (cycleStep s).level ≥ s.level := by
  unfold cycleStep
  cases productionLadder s with
  | none => exact le_refl _
  | some k =>
    cases k with
    | wait =>
      show (applyActionKind .wait s).level ≥ s.level
      simp [applyActionKind]
    | hpCritical =>
      show (applyActionKind .rest s).level ≥ s.level
      simp [applyActionKind]
    | bankUnlock =>
      show (applyActionKind .fight s).level ≥ s.level
      simp only [applyActionKind]
      split <;> omega
    | reachUnlockLevel =>
      show (applyActionKind .fight s).level ≥ s.level
      simp only [applyActionKind]
      split <;> omega
    | discardCritical =>
      show (applyActionKind .deleteItem s).level ≥ s.level
      simp [applyActionKind]
    | depositFull =>
      show (applyActionKind .depositAll s).level ≥ s.level
      simp [applyActionKind]
    | discardHigh =>
      show (applyActionKind .deleteItem s).level ≥ s.level
      simp [applyActionKind]
    | claimPending =>
      show (applyActionKind .claimPendingItem s).level ≥ s.level
      simp [applyActionKind]
    | completeTask =>
      -- Item 1f: completeTask now has level rollover. New level is
      -- either s.level (no rollover) or s.level + 1 (rollover). Either
      -- way, ≥ s.level.
      show (applyActionKind .completeTask s).level ≥ s.level
      show ((if (decide (s.xp + Formal.Liveness.Measure.taskCompleteXpEstimate
                          ≥ xpToNextLevel s.level)
                  && decide (s.level < 50))
              then s.level + 1
              else s.level) ≥ s.level)
      split <;> omega
    | sellPressured =>
      show (applyActionKind .npcSell s).level ≥ s.level
      simp [applyActionKind]
    | lowYieldCancel =>
      show (applyActionKind .taskCancel s).level ≥ s.level
      simp [applyActionKind]
    | taskCancel =>
      show (applyActionKind .taskCancel s).level ≥ s.level
      simp [applyActionKind]
    | objectiveStep =>
      show (applyActionKind .objectiveStep s).level ≥ s.level
      simp [applyActionKind]
    | pursueTask =>
      show (applyActionKind .taskTrade s).level ≥ s.level
      simp [applyActionKind]
    | acceptTask =>
      show (applyActionKind .acceptTask s).level ≥ s.level
      simp [applyActionKind]
    | taskExchange =>
      show (applyActionKind .taskExchange s).level ≥ s.level
      simp [applyActionKind]
    | sellIdle =>
      show (applyActionKind .npcSell s).level ≥ s.level
      simp [applyActionKind]
    | bankExpand =>
      show (applyActionKind .buyBankExpansion s).level ≥ s.level
      simp [applyActionKind]

/-! ## Per-MeansKind cycle-step decrease lemmas -/

/-- Reused from `CycleStep.fires_of_productionLadder`: extract the firing
    Bool from the ladder result. -/
private theorem fires_of_ladder {s : State} {k : MeansKind}
    (h : productionLadder s = some k) : fires k s = true := by
  unfold productionLadder at h
  rw [List.findSome?_eq_some_iff] at h
  obtain ⟨_pre, x, _suf, _hl, hbody, _hpre_none⟩ := h
  by_cases hfire : fires x s = true
  · simp [hfire] at hbody
    rw [← hbody]; exact hfire
  · simp [hfire] at hbody

/-- Master case-split: for every `k ∈ progressMeans`, `cycleStep`
    produces a state whose level strictly advances OR whose extended
    measure strictly decreases.

    Phase 23b's core sub-lemma. -/
theorem progressMeans_decreases_extMeasure_or_advances_level
    (s : State) (k : MeansKind)
    (hk : productionLadder s = some k)
    (hmem : k ∈ progressMeans)
    (hex : k = .taskExchange → s.taskExchangeMinCoins > 0)
    (hbe : k = .bankExpand → s.nextExpansionCost > 0)
    (hperc : k = .bankUnlock ∨ k = .reachUnlockLevel →
              s.xp < xpToNextLevel s.level ∧ s.level < 50) :
    (cycleStep s).level > s.level
    ∨ ((cycleStep s).level = s.level
        ∧ extMeasureLt (extMeasure (cycleStep s)) (extMeasure s)) := by
  have hfires : fires k s = true := fires_of_ladder hk
  cases k with
  | wait =>
    -- Not in progressMeans.
    exfalso; revert hmem; unfold progressMeans; decide
  | hpCritical =>
    -- Rest. hpDeficit strictly decreases; slots 1-5 unchanged.
    right
    have hcs : cycleStep s = applyActionKind .rest s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    -- hpCriticalFires forces hp < maxHp/4 ≤ maxHp.
    simp only [fires, hpCriticalFires, CRITICAL_HP_DEN, CRITICAL_HP_NUM,
               Bool.and_eq_true, decide_eq_true_eq] at hfires
    refine ⟨?_, ?_⟩
    · show (applyActionKind .rest s).level = s.level
      rfl
    refine extLt_of_hp_dec ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show s.maxHp - s.maxHp < s.maxHp - s.hp
      omega
  | bankUnlock =>
    -- Fight. Either level advances (rollover) OR xpDeficit decreases.
    have hcs : cycleStep s = applyActionKind .fight s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    have ⟨hxpInv, _hlvlInv⟩ := hperc (Or.inl rfl)
    by_cases hwill : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                       && decide (s.level < 50)) = true
    · -- Rollover branch: level advances.
      left
      have hlvl : (applyActionKind .fight s).level = s.level + 1 := by
        simp only [applyActionKind]; simp [hwill]
      rw [hlvl]; omega
    · -- No rollover: xpDeficit decreases. Plus level unchanged.
      right
      have hwillf : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) = false := by
        cases hbv : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) with
        | true  => exact absurd hbv hwill
        | false => rfl
      have hxp : (applyActionKind .fight s).xp = s.xp + 10 := by
        simp only [applyActionKind]; simp [hwillf]
      have hlvl_eq : (applyActionKind .fight s).level = s.level := by
        simp only [applyActionKind]; simp [hwillf]
      refine ⟨hlvl_eq, ?_⟩
      refine extLt_of_xp_dec ?_ ?_
      · show 50 - (applyActionKind .fight s).level = 50 - s.level
        rw [hlvl_eq]
      · show xpToNextLevel (applyActionKind .fight s).level
              - (applyActionKind .fight s).xp
              < xpToNextLevel s.level - s.xp
        rw [hlvl_eq, hxp]
        omega
  | reachUnlockLevel =>
    -- Identical to bankUnlock case.
    have hcs : cycleStep s = applyActionKind .fight s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    have ⟨hxpInv, _hlvlInv⟩ := hperc (Or.inr rfl)
    by_cases hwill : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                       && decide (s.level < 50)) = true
    · left
      have hlvl : (applyActionKind .fight s).level = s.level + 1 := by
        simp only [applyActionKind]; simp [hwill]
      rw [hlvl]; omega
    · right
      have hwillf : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) = false := by
        cases hbv : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) with
        | true  => exact absurd hbv hwill
        | false => rfl
      have hxp : (applyActionKind .fight s).xp = s.xp + 10 := by
        simp only [applyActionKind]; simp [hwillf]
      have hlvl_eq : (applyActionKind .fight s).level = s.level := by
        simp only [applyActionKind]; simp [hwillf]
      refine ⟨hlvl_eq, ?_⟩
      refine extLt_of_xp_dec ?_ ?_
      · show 50 - (applyActionKind .fight s).level = 50 - s.level
        rw [hlvl_eq]
      · show xpToNextLevel (applyActionKind .fight s).level
              - (applyActionKind .fight s).xp
              < xpToNextLevel s.level - s.xp
        rw [hlvl_eq, hxp]
        omega
  | discardCritical =>
    right
    have hcs : cycleStep s = applyActionKind .deleteItem s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, discardCriticalFires, Bool.and_eq_true,
               decide_eq_true_eq] at hfires
    have hpre : s.hasOverstockItems = true := hfires.1.1
    refine ⟨rfl, ?_⟩
    refine extLt_of_overstock_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show b2n (({s with hasOverstockItems := false} : State).hasOverstockItems)
            < b2n s.hasOverstockItems
      show b2n false < b2n s.hasOverstockItems
      rw [hpre]; decide
  | depositFull =>
    right
    have hcs : cycleStep s = applyActionKind .depositAll s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, depositFullFires, Bool.and_eq_true] at hfires
    have hpre : s.selectBankDepositsNonempty = true := hfires.2
    refine ⟨rfl, ?_⟩
    refine extLt_of_selectBank_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show b2n (({s with selectBankDepositsNonempty := false} : State).selectBankDepositsNonempty)
            < b2n s.selectBankDepositsNonempty
      show b2n false < b2n s.selectBankDepositsNonempty
      rw [hpre]; decide
  | discardHigh =>
    right
    have hcs : cycleStep s = applyActionKind .deleteItem s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, discardHighFires, Bool.and_eq_true,
               decide_eq_true_eq] at hfires
    have hpre : s.hasOverstockItems = true := hfires.1.1
    refine ⟨rfl, ?_⟩
    refine extLt_of_overstock_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show b2n (({s with hasOverstockItems := false} : State).hasOverstockItems)
            < b2n s.hasOverstockItems
      show b2n false < b2n s.hasOverstockItems
      rw [hpre]; decide
  | claimPending =>
    right
    have hcs : cycleStep s = applyActionKind .claimPendingItem s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, claimPendingFires] at hfires
    refine ⟨rfl, ?_⟩
    refine extLt_of_pending_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show b2n (({s with pendingItemsNonempty := false} : State).pendingItemsNonempty)
            < b2n s.pendingItemsNonempty
      show b2n false < b2n s.pendingItemsNonempty
      rw [hfires]; decide
  | sellPressured =>
    right
    have hcs : cycleStep s = applyActionKind .npcSell s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, sellPressuredFires, Bool.and_eq_true] at hfires
    have hpre : s.sellableInventoryNonempty = true := hfires.2
    refine ⟨rfl, ?_⟩
    refine extLt_of_sellable_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show b2n (({s with sellableInventoryNonempty := false} : State).sellableInventoryNonempty)
            < b2n s.sellableInventoryNonempty
      show b2n false < b2n s.sellableInventoryNonempty
      rw [hpre]; decide
  | objectiveStep =>
    right
    have hcs : cycleStep s = applyActionKind .objectiveStep s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, ProductionLadder.objectiveStepFires] at hfires
    refine ⟨rfl, ?_⟩
    refine extLt_of_objStep_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show b2n (({s with objectiveStepFires := false} : State).objectiveStepFires)
            < b2n s.objectiveStepFires
      show b2n false < b2n s.objectiveStepFires
      rw [hfires]; decide
  | taskExchange =>
    right
    have hcs : cycleStep s = applyActionKind .taskExchange s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    have hmin : s.taskExchangeMinCoins > 0 := hex rfl
    simp only [fires, taskExchangeFires, decide_eq_true_eq] at hfires
    refine ⟨rfl, ?_⟩
    refine extLt_of_taskCoins_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show ({s with taskCoinsTotal := s.taskCoinsTotal - s.taskExchangeMinCoins}
              : State).taskCoinsTotal < s.taskCoinsTotal
      show s.taskCoinsTotal - s.taskExchangeMinCoins < s.taskCoinsTotal
      omega
  | sellIdle =>
    right
    have hcs : cycleStep s = applyActionKind .npcSell s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, sellIdleFires, Bool.and_eq_true] at hfires
    have hpre : s.sellableInventoryNonempty = true := hfires.2
    refine ⟨rfl, ?_⟩
    refine extLt_of_sellable_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show b2n (({s with sellableInventoryNonempty := false} : State).sellableInventoryNonempty)
            < b2n s.sellableInventoryNonempty
      show b2n false < b2n s.sellableInventoryNonempty
      rw [hpre]; decide
  | bankExpand =>
    right
    have hcs : cycleStep s = applyActionKind .buyBankExpansion s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    have hcost : s.nextExpansionCost > 0 := hbe rfl
    simp only [fires, bankExpandFires, Bool.and_eq_true, decide_eq_true_eq] at hfires
    have hgold_ge : s.gold ≥ s.nextExpansionCost := hfires.2
    refine ⟨rfl, ?_⟩
    refine extLt_of_gold_dec ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_ ?_
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · unfold extMeasure applyActionKind; rfl
    · show ({s with bankCapacity := s.bankCapacity + bankExpansionSlots,
                    gold := s.gold - s.nextExpansionCost} : State).gold < s.gold
      show s.gold - s.nextExpansionCost < s.gold
      omega
  -- Out-of-scope kinds: ruled out by hmem.
  | completeTask    => exfalso; revert hmem; unfold progressMeans; decide
  | lowYieldCancel  => exfalso; revert hmem; unfold progressMeans; decide
  | taskCancel      => exfalso; revert hmem; unfold progressMeans; decide
  | pursueTask      => exfalso; revert hmem; unfold progressMeans; decide
  | acceptTask      => exfalso; revert hmem; unfold progressMeans; decide

/-! ## Headline — strong form (restricted trajectory)

Phase 23b's headline. Under SIX load-bearing hypotheses (the original
three from 23a plus three trajectory restrictions), some iterate of
`cycleStep` reaches a state with strictly greater level. -/

/-- Strong form of cumulative progress (Phase 23b).

    Load-bearing hypotheses (HONEST disclosure):

    1. `hlvl` — starting level below cap.

    2. `hnowait` — `.wait` never fires along the trajectory (carried
       from 23a).

    3. `hex` — `.taskExchange` non-degeneracy: when the ladder selects
       `.taskExchange`, `taskExchangeMinCoins > 0` (carried from 23a).

    4. `hbe` — `.bankExpand` non-degeneracy: when the ladder selects
       `.bankExpand`, `nextExpansionCost > 0`. NEW in 23b: required
       so that `gold` strictly decreases on `buyBankExpansion`.

    5. `hrestricted` — the trajectory's firing means are all in
       `progressMeans` (the 12-element subset). EXCLUDES the five
       task-lifecycle means (`acceptTask`, `pursueTask`, `completeTask`,
       `taskCancel`, `lowYieldCancel`) whose treatment is deferred to
       Phase 23c. The exclusion is HONEST scope reduction, not a hidden
       sorry — the deferred kinds appear in the theorem signature.

    6. `hperc` — perception invariant on the Fight-firing means: when
       the ladder selects `.bankUnlock` or `.reachUnlockLevel`,
       `s.xp < xpToNextLevel s.level` and `s.level < 50`. This is the
       same perception invariant Phase 19's `fight_decreases_measure`
       carries; here it is lifted pointwise along the trajectory.

    Conclusion: ∃ k, (cycleStepN k s).level > s.level. -/
theorem cumulative_progress_under_no_wait_restricted
    (s : State)
    (hlvl : s.level < 50)
    (hnowait : ∀ k, productionLadder (cycleStepN k s) ≠ some .wait)
    (hex : ∀ k, productionLadder (cycleStepN k s) = some .taskExchange →
                (cycleStepN k s).taskExchangeMinCoins > 0)
    (hbe : ∀ k, productionLadder (cycleStepN k s) = some .bankExpand →
                (cycleStepN k s).nextExpansionCost > 0)
    (hrestricted : ∀ k k', productionLadder (cycleStepN k s) = some k' →
                            k' ∈ progressMeans)
    (hperc : ∀ k k', productionLadder (cycleStepN k s) = some k' →
                      (k' = .bankUnlock ∨ k' = .reachUnlockLevel) →
                      (cycleStepN k s).xp < xpToNextLevel (cycleStepN k s).level
                      ∧ (cycleStepN k s).level < 50) :
    ∃ k, (cycleStepN k s).level > s.level := by
  -- Well-founded induction on State via the InvImage relation on extMeasure.
  -- Define R s' s := extMeasureLt (extMeasure s') (extMeasure s); this is
  -- well-founded by InvImage.wf. WellFounded.induction on R gives the
  -- state-level induction we want.
  let R : State → State → Prop := fun s₁ s₂ => extMeasureLt (extMeasure s₁) (extMeasure s₂)
  have hRwf : WellFounded R := InvImage.wf extMeasure extMeasureLt_wellFounded
  -- The motive: trajectory hypotheses ⇒ level advances somewhere.
  -- We thread all the trajectory hypotheses through the induction.
  suffices hgen :
      ∀ s' : State,
        s'.level < 50 →
        (∀ k, productionLadder (cycleStepN k s') ≠ some .wait) →
        (∀ k, productionLadder (cycleStepN k s') = some .taskExchange →
              (cycleStepN k s').taskExchangeMinCoins > 0) →
        (∀ k, productionLadder (cycleStepN k s') = some .bankExpand →
              (cycleStepN k s').nextExpansionCost > 0) →
        (∀ k k', productionLadder (cycleStepN k s') = some k' →
                  k' ∈ progressMeans) →
        (∀ k k', productionLadder (cycleStepN k s') = some k' →
                  (k' = .bankUnlock ∨ k' = .reachUnlockLevel) →
                  (cycleStepN k s').xp < xpToNextLevel (cycleStepN k s').level
                  ∧ (cycleStepN k s').level < 50) →
        ∃ k, (cycleStepN k s').level > s'.level by
    exact hgen s hlvl hnowait hex hbe hrestricted hperc
  intro s'
  -- Use WellFounded.induction explicitly with the trajectory hypotheses in the motive.
  apply hRwf.induction (C := fun s' =>
    s'.level < 50 →
    (∀ k, productionLadder (cycleStepN k s') ≠ some .wait) →
    (∀ k, productionLadder (cycleStepN k s') = some .taskExchange →
          (cycleStepN k s').taskExchangeMinCoins > 0) →
    (∀ k, productionLadder (cycleStepN k s') = some .bankExpand →
          (cycleStepN k s').nextExpansionCost > 0) →
    (∀ k k', productionLadder (cycleStepN k s') = some k' → k' ∈ progressMeans) →
    (∀ k k', productionLadder (cycleStepN k s') = some k' →
              (k' = .bankUnlock ∨ k' = .reachUnlockLevel) →
              (cycleStepN k s').xp < xpToNextLevel (cycleStepN k s').level
              ∧ (cycleStepN k s').level < 50) →
    ∃ k, (cycleStepN k s').level > s'.level)
  intro s' ih hlvl' hnowait' hex' hbe' hrestricted' hperc'
  --
  -- Pull out the ladder selection at index 0.
  obtain ⟨k0, hk0⟩ := exists_firing_means s'
  -- Lift hk0 through cycleStepN 0 (which is rfl-equal to s').
  have hk0' : productionLadder (cycleStepN 0 s') = some k0 := hk0
  have hk0_mem : k0 ∈ progressMeans := hrestricted' 0 k0 hk0'
  have hk0_ne_wait : k0 ≠ .wait := by
    intro habs
    have := hnowait' 0
    rw [habs] at hk0'
    exact this hk0'
  -- Discharge hex/hbe/hperc at index 0 for the per-cycle lemma.
  have hex0 : k0 = .taskExchange → s'.taskExchangeMinCoins > 0 := by
    intro hk_eq
    have hkex : productionLadder (cycleStepN 0 s') = some .taskExchange := by
      rw [← hk_eq]; exact hk0'
    have := hex' 0 hkex
    simpa [cycleStepN] using this
  have hbe0 : k0 = .bankExpand → s'.nextExpansionCost > 0 := by
    intro hk_eq
    have hkbe : productionLadder (cycleStepN 0 s') = some .bankExpand := by
      rw [← hk_eq]; exact hk0'
    have := hbe' 0 hkbe
    simpa [cycleStepN] using this
  have hperc0 : k0 = .bankUnlock ∨ k0 = .reachUnlockLevel →
                  s'.xp < xpToNextLevel s'.level ∧ s'.level < 50 := by
    intro hor
    have := hperc' 0 k0 hk0' hor
    simpa [cycleStepN] using this
  -- Apply the per-cycle progress lemma.
  have hcycle := progressMeans_decreases_extMeasure_or_advances_level
                  s' k0 hk0 hk0_mem hex0 hbe0 hperc0
  cases hcycle with
  | inl hadv =>
    -- Level advances after one cycle. Witness k = 1.
    refine ⟨1, ?_⟩
    have : cycleStepN 1 s' = cycleStep s' := by
      rw [cycleStepN_succ]; rfl
    rw [this]
    exact hadv
  | inr hdec =>
    -- Measure decreases AND level is preserved. Apply IH to cycleStep s'.
    obtain ⟨hlvl_eq, hdec'⟩ := hdec
    have hR : R (cycleStep s') s' := hdec'
    -- Re-derive trajectory hypotheses for cycleStep s' (by re-indexing).
    have hlvl_succ : (cycleStep s').level < 50 := by
      rw [hlvl_eq]; exact hlvl'
    have hnowait_succ : ∀ k, productionLadder (cycleStepN k (cycleStep s')) ≠ some .wait := by
      intro k
      have := hnowait' (k + 1)
      rwa [cycleStepN_succ] at this
    have hex_succ : ∀ k, productionLadder (cycleStepN k (cycleStep s')) = some .taskExchange →
                          (cycleStepN k (cycleStep s')).taskExchangeMinCoins > 0 := by
      intro k hk
      have := hex' (k + 1)
      rw [cycleStepN_succ] at this
      exact this hk
    have hbe_succ : ∀ k, productionLadder (cycleStepN k (cycleStep s')) = some .bankExpand →
                          (cycleStepN k (cycleStep s')).nextExpansionCost > 0 := by
      intro k hk
      have := hbe' (k + 1)
      rw [cycleStepN_succ] at this
      exact this hk
    have hrestricted_succ : ∀ k k', productionLadder (cycleStepN k (cycleStep s')) = some k' →
                                     k' ∈ progressMeans := by
      intro k k' hk
      have := hrestricted' (k + 1) k'
      rw [cycleStepN_succ] at this
      exact this hk
    have hperc_succ : ∀ k k', productionLadder (cycleStepN k (cycleStep s')) = some k' →
                                (k' = .bankUnlock ∨ k' = .reachUnlockLevel) →
                                (cycleStepN k (cycleStep s')).xp
                                  < xpToNextLevel (cycleStepN k (cycleStep s')).level
                                ∧ (cycleStepN k (cycleStep s')).level < 50 := by
      intro k k' hk hor
      have := hperc' (k + 1) k'
      rw [cycleStepN_succ] at this
      exact this hk hor
    obtain ⟨j, hj⟩ := ih (cycleStep s') hR hlvl_succ hnowait_succ hex_succ
                        hbe_succ hrestricted_succ hperc_succ
    -- hj : (cycleStepN j (cycleStep s')).level > (cycleStep s').level
    -- We want : (cycleStepN (j+1) s').level > s'.level
    refine ⟨j + 1, ?_⟩
    rw [cycleStepN_succ]
    -- (cycleStep s').level = s'.level (hlvl_eq), so hj transports directly.
    rw [hlvl_eq] at hj
    exact hj

/-! ## Phase 23d-1 — LIV-003 fat axiom REFACTORED into three smaller pieces

    Phase 23c-3c shipped a single fat axiom
    (`cumulative_progress_lifecycle_axiom`) that asserted EXISTENCE of
    a level-advancing iterate over the FULL state space under five
    hypotheses. The user feedback of 2026-06-01 directed: "Refine
    LIV-003. Fix the lazy reasoning."

    Phase 23d-1 DELETES the fat axiom and replaces it with three
    SMALLER, SINGLE-PURPOSE pieces aligned with the user mandate:

      (a) before taking any action, find the task unsatisfiable and
          must TaskCancel
      (b) take an action attempting the objective, deem the reward
          inexpedient, retry with a new target
      (c) take an action, observe measurable progress, obtaining
          confirmation N actions reach TaskSuccess

    The decomposition lives in `Formal.Liveness.LIV003Decomposition`:

      • LIV-003a — THEOREM `taskAccepted_implies_cancelOrPursueFires`
        (no axiom; provable from `ProductionLadder` fires defs)

      • LIV-003b — SMALL AXIOMS `lowYieldSampleThreshold`,
        `lowYieldSampleThreshold_pos`, `inProgress_decides_within_threshold`

      • LIV-003c — SMALL AXIOMS `taskPoolFinite`, `taskPoolFinite_pos`,
        `accept_cancel_loop_bound`

      • LIV-003-bridge — narrow composition axiom
        `lifecycle_progress_from_bounds` (replaces the fat axiom's
        structural existential claim; semantically only a Nat-bound
        composition).

    HONEST DISCLOSURE:

    - The old `cumulative_progress_lifecycle_axiom` is GONE from the
      audit. The new audit lists six smaller axioms (the four LIV-003b
      and LIV-003c components plus the LIV-003-bridge composition
      residual) — each narrower in semantic content than the old
      single fat axiom.

    - The user mandate "cumulative_progress_under_no_wait must NOT
      depend on it transitively" is satisfied: the new headline
      depends on `lifecycle_progress_from_bounds`, NOT on the deleted
      `cumulative_progress_lifecycle_axiom`.

    - The residual `lifecycle_progress_from_bounds` axiom is
      semantically a *composition* of the smaller pieces; closing it
      as a theorem requires an `actionsAttempted : Nat` State
      extension (mechanically preserved through Phase 19) plus
      sample-count monotonicity over the trajectory. Surfaced
      honestly as a TODO for a future phase.
-/

/-! ## Unrestricted headline — Phase 23d-1

    Drops `hrestricted` from Phase 23b's restricted form via the
    refactored LIV-003 decomposition (`lifecycle_progress_from_bounds`),
    which itself rests on the three smaller named pieces (LIV-003a/b/c).

    LIV-003a (the cancel-vs-pursue determinism theorem) is invoked
    inside `lifecycle_progress_from_bounds`'s closure; we surface it
    explicitly on the public surface below so the lifecycle reasoning
    is visible at the headline level. -/

/-- Sanity wrapper exposing LIV-003a at the cumulative-progress layer.

    User-mandate (a)/(b) restated structurally: in any `.accepted`
    state, the planner's ladder commits to Cancel OR Pursue — it does
    NOT stall. Provable from `ProductionLadder.taskCancelFires` /
    `pursueTaskFires` definitions; this theorem is a re-export
    convenience. -/
theorem accepted_state_decides_cancel_or_pursue (s : State)
    (h : s.taskLifecyclePhase = .accepted) :
    taskCancelFires s = true ∨ pursueTaskFires s = true :=
  taskAccepted_implies_cancelOrPursueFires s h

-- Item 1g-C: cumulative_progress_under_no_wait DELETED. Its body
-- depended on the now-deleted lifecycle_progress_from_bounds AXIOM.
-- Downstream consumers (LevelFiftyReachable.level_advances_once)
-- now call Formal.Liveness.LifecycleBound7.lifecycle_progress_from_bounds_proven
-- directly.

end Formal.Liveness.CumulativeProgress
