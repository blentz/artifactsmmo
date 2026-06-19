import Formal.Liveness.Leveling
import Mathlib.Tactic

/-! # FightReady — leveling DECOUPLED from bank unlock (O5.2 gear-tier realignment)

`Settled`/`Leveling` wrongly required `bankAccessible` and `level ≥ bankRequiredLevel`,
making the leveling steady-state contingent on the bank unlock — which happens LATE
(bank monster ~level 44; `reachUnlockLevel` fires only within `MAX_ACHIEVABLE_GAP = 5`
of it, i.e. levels 39–43). The real leveling driver is the `CharacterObjective`
(objectiveStep): target = char level 50 + every skill 50 + best gear, pursued by
gather/craft/fight, gated by winnability — the gear-tier progression.

`FightReady` is the faithful, bank-INDEPENDENT invariant: the NON-fight blockers are
quiet (hp restored + inventory flags clear + task parked) and a combat objective is
committed. At such a state the selected means is ALWAYS A FIGHT — whichever of
`bankUnlock` / `reachUnlockLevel` / `objectiveStep` fires first (all three are
`.fight`). `.fight` preserves every `FightReady` field (it touches only
level/xp/bankAccessible/actionsAttempted, none of which a `FightReady` condition
depends on), so `FightReady` is `cycleStep`-invariant — at EVERY level < 50, NOT just
post-bank-unlock. Hence the 3-way `hfightFires` holds and the planner reaches 50.

NO new axioms (standard set + LIV-001 via the imports).
-/

set_option linter.dupNamespace false

namespace Formal.Liveness.FightReady

open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.FightFairness
open Formal.Liveness.BlockerSettled
open Formal.Liveness.WarmupCleared
open Formal.Liveness.Leveling
open Formal.Liveness.SettledReach

/-- The bank-INDEPENDENT leveling invariant: non-fight blockers quiet + a committed
    combat objective. Crucially NO `bankAccessible` / `level ≥ bankRequiredLevel`. -/
structure FightReady (s : State) : Prop where
  hpFull         : s.hp = s.maxHp
  overstock      : s.hasOverstockItems = false
  deposits       : s.selectBankDepositsNonempty = false
  gear           : s.gearReviewFires = false
  pending        : s.pendingItemsNonempty = false
  sellable       : s.sellableInventoryNonempty = false
  craft          : s.craftReliefFires = false
  recycleNonempty : s.recyclableSurplusNonempty = false
  parked         : TaskParked s
  objFires       : s.objectiveStepFires = true
  objFight       : s.objectiveStepIsFight = true

/-- **The crux selection lemma.** With the twelve non-fight blockers quiet and a
    committed combat objective firing, the ladder selects a FIGHT means — the first
    of `bankUnlock` / `reachUnlockLevel` / `objectiveStep`. -/
theorem productionLadder_fight_of_fightReady (s : State) (h : FightReady s) :
    productionLadder s = some .bankUnlock
    ∨ productionLadder s = some .reachUnlockLevel
    ∨ productionLadder s = some .objectiveStep := by
  obtain ⟨htc, hlyc, htcan⟩ := TaskParked_blockers_quiet s h.parked
  -- The twelve non-fight blockers are quiet.
  have q0 : fires .hpCritical s = false := by
    simp only [fires, hpCriticalFires]
    rcases Nat.eq_zero_or_pos s.maxHp with hz | hpos
    · simp [hz]
    · have hlt : ¬ (CRITICAL_HP_DEN * s.hp < CRITICAL_HP_NUM * s.maxHp) := by
        rw [h.hpFull]; simp only [CRITICAL_HP_DEN, CRITICAL_HP_NUM]; omega
      simp [hlt]
  have q1 : fires .restForCombat s = false := by simp [fires, restForCombatFires, h.hpFull]
  have q4 : fires .discardCritical s = false := by simp [fires, discardCriticalFires, h.overstock]
  have q5 : fires .craftRelief s = false := by simp [fires, ProductionLadder.craftReliefFires, h.craft]
  have q5b : fires .recycleRelief s = false := by simp [fires, recycleReliefFires, h.recycleNonempty]
  have q6 : fires .depositFull s = false := by simp [fires, depositFullFires, h.deposits]
  have q7 : fires .discardHigh s = false := by simp [fires, discardHighFires, h.overstock]
  have q8 : fires .gearReview s = false := by simp [fires, ProductionLadder.gearReviewFires, h.gear]
  have q9 : fires .claimPending s = false := by simp [fires, claimPendingFires, h.pending]
  have q11 : fires .sellPressured s = false := by simp [fires, sellPressuredFires, h.sellable]
  have hobj : fires .objectiveStep s = true := by
    simp [fires, ProductionLadder.objectiveStepFires, h.objFires]
  -- Reduce productionLadder = findSome? over the explicit ladder; the quiet means
  -- collapse, leaving bankUnlock?.or reachUnlockLevel?.or (some objectiveStep).
  unfold productionLadder
  simp only [allInLadderOrder, List.findSome?_cons,
             q0, q1, q4, q5, q5b, q6, q7, q8, q9, htc, q11, hlyc, htcan, hobj]
  -- Goal now: (if bankUnlockFires then some bankUnlock else none).or
  --           ((if reachUnlockLevelFires then some reachUnlockLevel else none).or
  --             (some objectiveStep)) ∈ the 3-way.
  by_cases hbu : fires .bankUnlock s = true
  · left; simp [fires] at hbu ⊢; simp [hbu]
  · by_cases hru : fires .reachUnlockLevel s = true
    · right; left
      simp only [fires] at hbu hru ⊢
      simp [hbu, hru]
    · right; right
      simp only [fires] at hbu hru ⊢
      simp [hbu, hru]

/-- `FightReady` ⇒ the cycle is a `.fight` (the 3-way fight-firing, with the
    `objectiveStepIsFight` conjunct supplied for the objectiveStep case). -/
theorem fightFires_of_fightReady (s : State) (h : FightReady s) :
    productionLadder s = some .bankUnlock
    ∨ productionLadder s = some .reachUnlockLevel
    ∨ (productionLadder s = some .objectiveStep ∧ s.objectiveStepIsFight = true) := by
  rcases productionLadder_fight_of_fightReady s h with hb | hr | ho
  · exact Or.inl hb
  · exact Or.inr (Or.inl hr)
  · exact Or.inr (Or.inr ⟨ho, h.objFight⟩)

theorem cycleStep_eq_fight_of_fightReady (s : State) (h : FightReady s) :
    cycleStep s = applyActionKind .fight s :=
  cycleStep_eq_fight_when_fightCycleFires s (fightFires_of_fightReady s h)

/-- `FightReady` is `cycleStep`-invariant — a `.fight` preserves hp/flags/task/
    perception, with NO dependence on level or bank state. -/
theorem FightReady_cycleStep (s : State) (h : FightReady s) : FightReady (cycleStep s) := by
  have hcs := cycleStep_eq_fight_of_fightReady s h
  rw [hcs]
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · exact h.hpFull        -- hpFull (fight touches neither hp nor maxHp)
  · exact h.overstock
  · exact h.deposits
  · exact h.gear
  · exact h.pending
  · exact h.sellable
  · exact h.craft
  · exact h.recycleNonempty  -- fight does not touch recyclableSurplusNonempty
  · exact TaskParked_fight s h.parked
  · simp only [applyActionKind]; exact h.objFires
  · simp only [applyActionKind]; exact h.objFight

theorem FightReady_cycleStepN :
    ∀ (n : Nat) (s : State), FightReady s → FightReady (cycleStepN n s)
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact FightReady_cycleStepN n (cycleStep s) (FightReady_cycleStep s h)

/-- A single `FightReady` state drives the 3-way `hfightFires` at every step. -/
theorem hfightFires_of_fightReady (s : State) (h : FightReady s) :
    ∀ N, ∃ k ≥ N,
      productionLadder (cycleStepN k s) = some .bankUnlock
      ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel
      ∨ (productionLadder (cycleStepN k s) = some .objectiveStep
          ∧ (cycleStepN k s).objectiveStepIsFight = true) := by
  intro N
  exact ⟨N, le_refl N, fightFires_of_fightReady (cycleStepN N s) (FightReady_cycleStepN N s h)⟩

/-- **End-to-end, bank-INDEPENDENT.** Config-positivity + a `FightReady` state ⇒
    level 50 — valid at EVERY level < 50, via gear-tier combat, not gated on the
    level-44 bank unlock. -/
theorem ai_reaches_level_fifty_of_fightReady (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (h : FightReady s) :
    ∃ k, (cycleStepN k s).level ≥ 50 :=
  Formal.Liveness.ReducedReachability.ai_reaches_level_fifty_config_positive
    s htec hnec (hfightFires_of_fightReady s h)

end Formal.Liveness.FightReady
