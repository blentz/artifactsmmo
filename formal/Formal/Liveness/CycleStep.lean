/-
  Formal.Liveness.CycleStep

  Phase 22a — cycle-loop infrastructure (Tier 4 scaffold). One module
  defining the per-cycle pure transition that mirrors the production
  player loop at `src/artifactsmmo_cli/ai/player.py:190-270`.

  ## Pieces

  1. `planFor : MeansKind → State → Plan`
     The witness plan per firing means, mirroring the witnesses used in
     `Formal.Liveness.PlanExists`'s `plan_exists_for_X` theorems. All
     plans are SINGLE-ACTION (length 1) — the multi-Fight composition
     for `reachUnlockLevel` is handled by iteration over cycles, NOT by
     a single multi-step plan. See "Honest disclosure" below.

  2. `cycleStep : State → State`
     Composes `productionLadder + planFor + applyActionKind` into one
     cycle's pure transition. Mirrors production's:

         k = arbiter.select(s)        -- productionLadder
         plan = planner.plan(s, k)    -- planFor
         s' = execute(plan.head, s)   -- applyActionKind on plan[0]

  3. `cycleStep_total`
     Trivial: `cycleStep` is a total function on `State`. Stated for
     shape parity with `productionLadder_total`.

  4. `cycleStep_progress_or_waits`
     The headline: under a mild non-degeneracy hypothesis on
     `.taskExchange`, every cycle either changes state or is in a
     wait-only ladder configuration. Connects Phase 20's no-deadlock
     (`productionLadder_total`) with Phase 21's plan-exists witnesses.

  ## Honest disclosure: single-action plans

  Production's planner emits multi-action plans for some means (e.g.
  `reachUnlockLevel` may require N Fight actions). At the CYCLE
  granularity, the bot executes ONE action per cycle (mirroring the
  Python loop's single `execute` call before re-perceiving). We honor
  that here: `planFor` returns a 1-element list, and `cycleStep` runs
  exactly that one action.

  The multi-Fight composition needed to actually push `level ≥
  bankRequiredLevel` is iteration `cycleStep^N` (Tier 4 territory,
  out of scope for 22a). `Formal.Liveness.PlanExists`'s
  `plan_exists_for_reachUnlockLevel` proves the existence of an N-long
  plan over the WHOLE-plan abstraction; here we work at the per-cycle
  abstraction, which is faithful to the production loop.

  ## Honest disclosure: the `.wait` exception

  When `WaitGoal` fires (which it does as the last-resort fallback —
  see `Formal.Liveness.ProductionLadder.waitFires`), `cycleStep` is a
  no-op: `planFor .wait = [.wait]` and `applyActionKind .wait s = s`.
  The bot can loop on `.wait` indefinitely if NO other means ever
  fires. Phase 20's `productionLadder_total` guarantees something
  fires; the WAIT fallback is the honest model of the "nothing
  actionable right now" steady state.

  ## Honest disclosure: `.taskExchange` degeneracy

  `taskExchangeFires` is `s.taskCoinsTotal ≥ s.taskExchangeMinCoins`,
  which is trivially `true` when `taskExchangeMinCoins = 0`. In that
  degenerate case `applyActionKind .taskExchange` is a no-op (Nat
  saturating subtraction). `Formal.Liveness.PlanExists`'s
  `plan_exists_for_taskExchange` already flags this with a `0 <
  taskExchangeMinCoins` precondition; we mirror it here as a single
  hypothesis on the headline theorem. The HTTP 478 server contract on
  `min_coins = 0` would be a server bug.

  ## Integrity

  - No `sorry`/`admit`/`native_decide`.
  - No new `axiom` keyword.
  - `planFor` is `noncomputable` solely because `applyActionKind` is
    (transitive dependency on the LIV-001 `xpToNextLevel` axiom).
  - Axioms ⊆ {propext, Classical.choice, Quot.sound, xpToNextLevel}.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.MeansKind
import Formal.Liveness.ProductionLadder
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.NoDeadlockV2
import Formal.Liveness.TaskLifecyclePhase

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.CycleStep

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.NoDeadlockV2
open Formal.Liveness.TaskLifecyclePhase

/-! ## planFor — witness plan per MeansKind

Each kind returns a single-element `Plan` whose head action matches the
`PlanExists.plan_exists_for_<kind>` witness. For `reachUnlockLevel` we
return `[.fight]` (one Fight per cycle); the multi-Fight composition
needed to actually advance through several levels is iteration over
cycles, not a single plan.
-/

/-- Witness plan per firing `MeansKind`. Single-action plans only —
    one action per cycle, mirroring the production loop. -/
noncomputable def planFor : MeansKind → State → Plan
  | .hpCritical       , _ => [.rest]
  | .restForCombat    , _ => [.rest]
  | .bankUnlock       , _ => [.fight]
  | .reachUnlockLevel , _ => [.fight]
  | .discardCritical  , _ => [.deleteItem]
  | .craftRelief      , _ => [.craft]
  | .depositFull      , _ => [.depositAll]
  | .discardHigh      , _ => [.deleteItem]
  | .gearReview       , _ => [.optimizeLoadout]
  | .claimPending     , _ => [.claimPendingItem]
  | .completeTask     , _ => [.completeTask]
  | .sellPressured    , _ => [.npcSell]
  | .lowYieldCancel   , _ => [.taskCancel]
  | .taskCancel       , _ => [.taskCancel]
  | .objectiveStep    , s =>
      -- O5.2 (2026-06-16): a combat/char-leveling objective dispatches a
      -- Fight-led plan (production `ReachCharLevel` meta-goal + monster-task /
      -- combat objectives). When the objective step is a fight, the cycle
      -- FIGHTS (+10 char xp / rollover via `applyActionKind .fight`) — the
      -- model's faithful general leveling path. Otherwise the synthetic
      -- placeholder clears `objectiveStepFires` (legacy default: isFight=false).
      if s.objectiveStepIsFight then [.fight] else [.objectiveStep]
  | .pursueTask       , _ => [.taskTrade]
  | .acceptTask       , _ => [.acceptTask]
  | .taskExchange     , _ => [.taskExchange]
  | .sellIdle         , _ => [.npcSell]
  | .recycleSurplus   , _ => [.recycle]
  | .bankExpand       , _ => [.buyBankExpansion]
  | .wait             , _ => [.wait]

/-- `planFor k s` is always non-empty (single-element). -/
theorem planFor_ne_nil (k : MeansKind) (s : State) : planFor k s ≠ [] := by
  cases k <;> simp only [planFor]
  case objectiveStep => split <;> simp
  all_goals simp

/-! ## cycleStep — one cycle's pure transition -/

/-- One cycle: select firing means via `productionLadder`, plan via
    `planFor`, execute the plan's head action via `applyActionKind`.
    On the impossible `none` branch (ruled out by
    `productionLadder_total`) we return the input unchanged; this keeps
    the function total without introducing a Classical choice. -/
noncomputable def cycleStep (s : State) : State :=
  match productionLadder s with
  | none => s
  | some k =>
    match planFor k s with
    | []     => s
    | a :: _ => applyActionKind a s

/-! ## cycleStep_total — shape parity -/

/-- `cycleStep` is a total function. Trivial (it IS a function); stated
    for parity with `productionLadder_total`. -/
theorem cycleStep_total (s : State) : ∃ s', cycleStep s = s' := ⟨_, rfl⟩

/-! ## cycleStep_progress_or_waits

The headline. For each non-wait firing means `k`, the witness action
`(planFor k s).head` actually changes some field of `s`. The proof is
a 17-way case split; each branch reduces to "the firing-predicate
forces a pre-state field value that the action flips."
-/

/-- Helper: from `productionLadder s = some k`, extract `fires k s = true`.

    `productionLadder` is `findSome?` with body `λ k => if fires k s then
    some k else none`. The `findSome?_eq_some_iff` characterisation gives
    a witness element `x` with body `some k`. Since the body returns
    `some x` (or none), `x = k` and the if-branch fired. -/
private theorem fires_of_productionLadder
    {s : State} {k : MeansKind} (h : productionLadder s = some k) :
    fires k s = true := by
  unfold productionLadder at h
  rw [List.findSome?_eq_some_iff] at h
  obtain ⟨_pre, x, _suf, _hl, hbody, _hpre_none⟩ := h
  -- hbody : (if fires x s then some x else none) = some k.
  -- This forces fires x s = true and x = k.
  by_cases hfire : fires x s = true
  · simp [hfire] at hbody
    -- hbody : x = k, so fires k s = fires x s = true.
    rw [← hbody]; exact hfire
  · simp [hfire] at hbody

/-- Headline. Under the mild non-degeneracy hypothesis on
    `.taskExchange` (positive `taskExchangeMinCoins` whenever the
    ladder selects `.taskExchange`), every cycle either changes the
    state or sits in a wait-only ladder configuration. -/
theorem cycleStep_progress_or_waits
    (s : State)
    (hex : productionLadder s = some .taskExchange → s.taskExchangeMinCoins > 0) :
    cycleStep s ≠ s ∨ productionLadder s = some .wait := by
  -- productionLadder s = some k (by productionLadder_total).
  obtain ⟨k, hk⟩ := exists_firing_means s
  have hfires : fires k s = true := fires_of_productionLadder hk
  -- Case split on k.
  cases k with
  | wait =>
    right; exact hk
  | hpCritical =>
    left
    have hcs : cycleStep s = applyActionKind .rest s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    -- applyActionKind .rest s = { s with hp := s.maxHp }.
    -- hpCriticalFires forces hp < maxHp/4 < maxHp, so hp ≠ maxHp.
    show ({s with hp := s.maxHp} : State) ≠ s
    intro heq
    have hhp : s.maxHp = s.hp := by
      have := congrArg State.hp heq
      simpa using this
    simp only [fires, hpCriticalFires, CRITICAL_HP_DEN, CRITICAL_HP_NUM,
               Bool.and_eq_true, decide_eq_true_eq] at hfires
    omega
  | restForCombat =>
    left
    have hcs : cycleStep s = applyActionKind .rest s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    -- applyActionKind .rest s = { s with hp := s.maxHp }.
    -- restForCombatFires has the `hp < maxHp` conjunct, so hp ≠ maxHp.
    show ({s with hp := s.maxHp} : State) ≠ s
    intro heq
    have hhp : s.maxHp = s.hp := by
      have := congrArg State.hp heq
      simpa using this
    simp only [fires, restForCombatFires, Bool.and_eq_true,
               decide_eq_true_eq] at hfires
    omega
  | bankUnlock =>
    left
    have hcs : cycleStep s = applyActionKind .fight s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    -- hfires IS the bank-unlock guard verbatim → post-state bankAccessible = true.
    have hReady : (s.bankUnlockMonsterPresent
                    && !s.bankAccessible
                    && decide (s.xp ≤ s.initialXp)
                    && (decide (s.unlockMonsterLevel = 0)
                        || decide (s.level + 1 ≥ s.unlockMonsterLevel))) = true := by
      have := hfires
      simp only [fires, bankUnlockFires] at this
      exact this
    have hba_post : (applyActionKind .fight s).bankAccessible = true := by
      simp only [applyActionKind]
      simp [hReady]
    intro heq
    have hbacc : s.bankAccessible = true := by rw [← heq]; exact hba_post
    -- Extract bankAccessible = false from hReady.
    rw [hbacc] at hReady
    simp at hReady
  | reachUnlockLevel =>
    left
    have hcs : cycleStep s = applyActionKind .fight s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    intro heq
    by_cases hwill : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                       && decide (s.level < 50)) = true
    · -- Rollover branch.
      have hlvl : (applyActionKind .fight s).level = s.level + 1 := by
        simp only [applyActionKind]; simp [hwill]
      have hlvl_eq : (applyActionKind .fight s).level = s.level := by rw [heq]
      omega
    · -- No-rollover branch.
      have hwillf : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) = false := by
        cases hbv : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) with
        | true  => exact absurd hbv hwill
        | false => rfl
      have hxp : (applyActionKind .fight s).xp = s.xp + 10 := by
        simp only [applyActionKind]; simp [hwillf]
      have hxp_eq : (applyActionKind .fight s).xp = s.xp := by rw [heq]
      omega
  | discardCritical =>
    left
    have hcs : cycleStep s = applyActionKind .deleteItem s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, discardCriticalFires, Bool.and_eq_true,
               decide_eq_true_eq] at hfires
    have hpre : s.hasOverstockItems = true := hfires.1.1
    intro heq
    have hpost : ({s with hasOverstockItems := false} : State).hasOverstockItems = false := rfl
    have hpre' : s.hasOverstockItems = false := by
      have : (applyActionKind .deleteItem s).hasOverstockItems = false := hpost
      rw [heq] at this; exact this
    rw [hpre] at hpre'; cases hpre'
  | craftRelief =>
    -- CRAFT_RELIEF plans `.craft`, which advances `craftableSlots` by +1
    -- (Plan.lean line ≈387). The post-state's craftableSlots differs from
    -- the pre-state's, hence cycleStep s ≠ s. Mirrors the pursueTask /
    -- bankExpand pattern of "post.field = pre.field + 1 → state changed".
    left
    have hcs : cycleStep s = applyActionKind .craft s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    intro heq
    have hpost : (applyActionKind .craft s).craftableSlots
                  = s.craftableSlots + 1 := by
      simp [applyActionKind]
    have hpre' : s.craftableSlots = s.craftableSlots + 1 := by
      rw [heq] at hpost; exact hpost
    exact Nat.succ_ne_self _ hpre'.symm
  | depositFull =>
    left
    have hcs : cycleStep s = applyActionKind .depositAll s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, depositFullFires, Bool.and_eq_true] at hfires
    have hpre : s.selectBankDepositsNonempty = true := hfires.2
    intro heq
    have hpost : ({s with selectBankDepositsNonempty := false} : State).selectBankDepositsNonempty
                  = false := rfl
    have hpre' : s.selectBankDepositsNonempty = false := by
      have : (applyActionKind .depositAll s).selectBankDepositsNonempty = false := hpost
      rw [heq] at this; exact this
    rw [hpre] at hpre'; cases hpre'
  | discardHigh =>
    left
    have hcs : cycleStep s = applyActionKind .deleteItem s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, discardHighFires, Bool.and_eq_true,
               decide_eq_true_eq] at hfires
    have hpre : s.hasOverstockItems = true := hfires.1.1
    intro heq
    have hpost : ({s with hasOverstockItems := false} : State).hasOverstockItems = false := rfl
    have hpre' : s.hasOverstockItems = false := by
      have : (applyActionKind .deleteItem s).hasOverstockItems = false := hpost
      rw [heq] at this; exact this
    rw [hpre] at hpre'; cases hpre'
  | gearReview =>
    left
    have hcs : cycleStep s = applyActionKind .optimizeLoadout s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, ProductionLadder.gearReviewFires] at hfires
    intro heq
    have hpost : (applyActionKind .optimizeLoadout s).gearReviewFires = false := by
      simp [applyActionKind]
    have hpre' : s.gearReviewFires = false := by
      rw [heq] at hpost; exact hpost
    rw [hfires] at hpre'; cases hpre'
  | claimPending =>
    left
    have hcs : cycleStep s = applyActionKind .claimPendingItem s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, claimPendingFires] at hfires
    intro heq
    have hpost : ({s with pendingItemsNonempty := false} : State).pendingItemsNonempty = false := rfl
    have hpre' : s.pendingItemsNonempty = false := by
      have : (applyActionKind .claimPendingItem s).pendingItemsNonempty = false := hpost
      rw [heq] at this; exact this
    rw [hfires] at hpre'; cases hpre'
  | completeTask =>
    left
    have hcs : cycleStep s = applyActionKind .completeTask s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, completeTaskFires, decide_eq_true_eq] at hfires
    -- hfires : s.taskLifecyclePhase = .complete
    intro heq
    have hpost : (applyActionKind .completeTask s).taskLifecyclePhase
                  = TaskLifecyclePhase.TaskLifecyclePhase.none := by
      simp [applyActionKind]
    have hpre' : s.taskLifecyclePhase
                  = TaskLifecyclePhase.TaskLifecyclePhase.none := by
      rw [heq] at hpost; exact hpost
    rw [hfires] at hpre'; cases hpre'
  | sellPressured =>
    left
    have hcs : cycleStep s = applyActionKind .npcSell s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, sellPressuredFires, Bool.and_eq_true] at hfires
    have hpre : s.sellableInventoryNonempty = true := hfires.2
    intro heq
    have hpost : ({s with sellableInventoryNonempty := false} : State).sellableInventoryNonempty
                  = false := rfl
    have hpre' : s.sellableInventoryNonempty = false := by
      have : (applyActionKind .npcSell s).sellableInventoryNonempty = false := hpost
      rw [heq] at this; exact this
    rw [hpre] at hpre'; cases hpre'
  | lowYieldCancel =>
    left
    have hcs : cycleStep s = applyActionKind .taskCancel s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    -- Phase 23d-5: hfires = (decide phase=.inProgress) && (decide attempts ≥ T)
    simp only [fires, lowYieldCancelFires, Bool.and_eq_true, decide_eq_true_eq] at hfires
    -- hfires : phase = .inProgress ∧ actionsAttempted ≥ T
    intro heq
    have hpost : (applyActionKind .taskCancel s).taskLifecyclePhase
                  = TaskLifecyclePhase.TaskLifecyclePhase.none := by
      simp [applyActionKind]
    have hpre' : s.taskLifecyclePhase
                  = TaskLifecyclePhase.TaskLifecyclePhase.none := by
      rw [heq] at hpost; exact hpost
    rw [hfires.1] at hpre'; cases hpre'
  | taskCancel =>
    left
    have hcs : cycleStep s = applyActionKind .taskCancel s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, ProductionLadder.taskCancelFires, Bool.and_eq_true,
               Bool.or_eq_true, Bool.not_eq_true', decide_eq_true_eq] at hfires
    -- Item 1d: refined taskCancelFires now has additional
    -- `&& !taskFeasibleProjected` conjunct. hfires structure:
    -- ((phase = .accepted ∨ phase = .inProgress) ∧ taskFeasibleProjected = false)
    obtain ⟨hfPhase, _⟩ := hfires
    intro heq
    have hpost : (applyActionKind .taskCancel s).taskLifecyclePhase
                  = TaskLifecyclePhase.TaskLifecyclePhase.none := by
      simp [applyActionKind]
    have hpre' : s.taskLifecyclePhase
                  = TaskLifecyclePhase.TaskLifecyclePhase.none := by
      rw [heq] at hpost; exact hpost
    cases hfPhase with
    | inl h => rw [h] at hpre'; cases hpre'
    | inr h => rw [h] at hpre'; cases hpre'
  | objectiveStep =>
    left
    by_cases hisf : s.objectiveStepIsFight = true
    · -- O5.2: combat objective ⇒ cycle FIGHTS; xp+10 (or level rollover) ≠ s.
      have hcs : cycleStep s = applyActionKind .fight s := by
        unfold cycleStep; rw [hk]; simp [planFor, hisf]
      rw [hcs]
      intro heq
      by_cases hwill : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                         && decide (s.level < 50)) = true
      · have hlvl : (applyActionKind .fight s).level = s.level + 1 := by
          simp only [applyActionKind]; simp [hwill]
        have hlvl_eq : (applyActionKind .fight s).level = s.level := by rw [heq]
        omega
      · have hwillf : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                        && decide (s.level < 50)) = false := by
          cases hbv : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                        && decide (s.level < 50)) with
          | true  => exact absurd hbv hwill
          | false => rfl
        have hxp : (applyActionKind .fight s).xp = s.xp + 10 := by
          simp only [applyActionKind]; simp [hwillf]
        have hxp_eq : (applyActionKind .fight s).xp = s.xp := by rw [heq]
        omega
    · -- Placeholder branch (isFight = false): clears objectiveStepFires.
      have hisf' : s.objectiveStepIsFight = false := by
        cases h : s.objectiveStepIsFight with
        | true => exact absurd h hisf
        | false => rfl
      have hcs : cycleStep s = applyActionKind .objectiveStep s := by
        unfold cycleStep; rw [hk]; simp [planFor, hisf']
      rw [hcs]
      simp only [fires, ProductionLadder.objectiveStepFires] at hfires
      intro heq
      have hpost : ({s with objectiveStepFires := false} : State).objectiveStepFires = false := rfl
      have hpre' : s.objectiveStepFires = false := by
        have : (applyActionKind .objectiveStep s).objectiveStepFires = false := hpost
        rw [heq] at this; exact this
      rw [hfires] at hpre'; cases hpre'
  | pursueTask =>
    left
    have hcs : cycleStep s = applyActionKind .taskTrade s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    -- Phase 23d-5: applyActionKind .taskTrade advances taskProgress by +1.
    -- So the post-state's taskProgress differs from the pre-state's,
    -- hence the post-state is not s.
    intro heq
    have hpost : (applyActionKind .taskTrade s).taskProgress
                  = s.taskProgress + 1 := by
      simp [applyActionKind]
    have hpre' : s.taskProgress = s.taskProgress + 1 := by
      rw [heq] at hpost; exact hpost
    exact Nat.succ_ne_self _ hpre'.symm
  | acceptTask =>
    left
    have hcs : cycleStep s = applyActionKind .acceptTask s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, acceptTaskFires, decide_eq_true_eq] at hfires
    -- hfires : s.taskLifecyclePhase = .none
    intro heq
    have hpost : (applyActionKind .acceptTask s).taskLifecyclePhase
                  = TaskLifecyclePhase.TaskLifecyclePhase.accepted := by
      simp [applyActionKind]
    have hpre' : s.taskLifecyclePhase
                  = TaskLifecyclePhase.TaskLifecyclePhase.accepted := by
      rw [heq] at hpost; exact hpost
    rw [hfires] at hpre'; cases hpre'
  | taskExchange =>
    left
    have hcs : cycleStep s = applyActionKind .taskExchange s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    have hmin : s.taskExchangeMinCoins > 0 := hex hk
    intro heq
    have hpost_eq : (applyActionKind .taskExchange s).taskCoinsTotal
                    = s.taskCoinsTotal - s.taskExchangeMinCoins := by
      show ({s with taskCoinsTotal := s.taskCoinsTotal - s.taskExchangeMinCoins} : State).taskCoinsTotal
            = s.taskCoinsTotal - s.taskExchangeMinCoins
      rfl
    have heq2 : s.taskCoinsTotal - s.taskExchangeMinCoins = s.taskCoinsTotal := by
      rw [heq] at hpost_eq; exact hpost_eq.symm
    simp only [fires, taskExchangeFires, decide_eq_true_eq] at hfires
    omega
  | sellIdle =>
    left
    have hcs : cycleStep s = applyActionKind .npcSell s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, sellIdleFires, Bool.and_eq_true] at hfires
    have hpre : s.sellableInventoryNonempty = true := hfires.2
    intro heq
    have hpost : ({s with sellableInventoryNonempty := false} : State).sellableInventoryNonempty
                  = false := rfl
    have hpre' : s.sellableInventoryNonempty = false := by
      have : (applyActionKind .npcSell s).sellableInventoryNonempty = false := hpost
      rw [heq] at this; exact this
    rw [hpre] at hpre'; cases hpre'
  | recycleSurplus =>
    left
    have hcs : cycleStep s = applyActionKind .recycle s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    simp only [fires, recycleSurplusFires, Bool.and_eq_true] at hfires
    have hpre : s.recyclableSurplusNonempty = true := hfires.2
    intro heq
    have hpost : ({s with recyclableSurplusNonempty := false} : State).recyclableSurplusNonempty
                  = false := rfl
    have hpre' : s.recyclableSurplusNonempty = false := by
      have : (applyActionKind .recycle s).recyclableSurplusNonempty = false := hpost
      rw [heq] at this; exact this
    rw [hpre] at hpre'; cases hpre'
  | bankExpand =>
    left
    have hcs : cycleStep s = applyActionKind .buyBankExpansion s := by
      unfold cycleStep; rw [hk]; rfl
    rw [hcs]
    intro heq
    have hpost_eq : (applyActionKind .buyBankExpansion s).bankCapacity
                    = s.bankCapacity + bankExpansionSlots := by
      show ({s with bankCapacity := s.bankCapacity + bankExpansionSlots,
                    gold := s.gold - s.nextExpansionCost} : State).bankCapacity
            = s.bankCapacity + bankExpansionSlots
      rfl
    have habs : s.bankCapacity = s.bankCapacity + bankExpansionSlots := by
      rw [heq] at hpost_eq; exact hpost_eq
    unfold bankExpansionSlots at habs
    omega

end Formal.Liveness.CycleStep
