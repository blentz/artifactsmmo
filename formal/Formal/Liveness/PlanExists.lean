/-
  Formal.Liveness.PlanExists

  Phase 21a deliverable #3. Per-firing-means plan-existence lemmas for the
  8 "trivial" `MeansKind` constructors whose corresponding production
  action satisfies the firing predicate in a single step.

  ## Lemma shape

  For each in-scope `k : MeansKind`:

      ∀ s, fires k s = true → ∃ p : Plan, planAchieves p s k

  where `planAchieves p s k := fires k (applyPlan p s) = false`. The
  witness `p` is the singleton list containing the corresponding
  `ActionKind`. The proof simp's through `applyPlan` and `applyActionKind`
  to expose the post-state, then discharges the firing predicate with
  `decide` / `omega`.

  ## Wait — honest special case

  `WaitGoal` is the last-resort fallback: `waitFires` is unconditionally
  `true`, and `WaitAction.apply` is the identity. Therefore `[.wait]`
  does NOT satisfy `planAchieves`: the post-state still fires wait. The
  honest Phase 21a statement for wait is the weaker existence claim:

      ∀ s, fires .wait s = true → ∃ p : Plan, applyPlan p s = s

  (a plan exists that preserves the state — i.e. the planner CAN return
  a plan for a wait-firing state). This is NOT a "plan achieves the
  means" claim; it's the honest formulation given wait's no-op semantics.
  See `wait.py:34` for the production no-op.

  ## Deferred lemmas (Phase 21b/c)

  For the 10 remaining firing means, plan construction requires multiple
  steps and parameter modeling beyond Phase 21a's scope. They are listed
  by name in a comment block at the bottom of this file, with no
  `theorem` declared (NOT a stub — per phase plan: "no sorry, no
  axioms"). Phase 21b/c will add the multi-step machinery (e.g.
  MoveTo+Rest for `restoreHp`-style means).

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.MeansKind
import Formal.Liveness.ProductionLadder
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.PlanExists

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction

/-- A plan `p` achieves the means `k` from state `s` if applying it
    results in a state where `k` no longer fires. -/
def planAchieves (p : Plan) (s : State) (k : MeansKind) : Prop :=
  fires k (applyPlan p s) = false

/-! ## Trivial plan-existence lemmas (7 means satisfied in a single action) -/

/-- `[.rest]` clears `hpCritical`. `RestAction` sets `hp := maxHp`; with
    `maxHp > 0` (forced by the firing hypothesis itself), the post-state
    has `100 * maxHp < 25 * maxHp` which is false. -/
theorem plan_exists_for_hpCritical :
    ∀ s, fires .hpCritical s = true →
      ∃ p : Plan, planAchieves p s .hpCritical := by
  intro s h
  refine ⟨[.rest], ?_⟩
  -- fires .hpCritical (applyPlan [.rest] s)
  --   = hpCriticalFires { s with hp := s.maxHp }
  --   = decide (s.maxHp > 0) && decide (100 * s.maxHp < 25 * s.maxHp)
  -- The second conjunct is impossible (a positive maxHp can't be less
  -- than a quarter of itself), so simp + omega closes the goal.
  simp [planAchieves, applyActionKind, fires,
        hpCriticalFires, CRITICAL_HP_DEN, CRITICAL_HP_NUM] at h ⊢
  omega

/-- `[.claimPendingItem]` clears `claimPending`. -/
theorem plan_exists_for_claimPending :
    ∀ s, fires .claimPending s = true →
      ∃ p : Plan, planAchieves p s .claimPending := by
  intro s h
  refine ⟨[.claimPendingItem], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        claimPendingFires]

/-- `[.completeTask]` clears `completeTask` (post-state has
    `taskCode = none`, so `taskCode.isSome = false`). -/
theorem plan_exists_for_completeTask :
    ∀ s, fires .completeTask s = true →
      ∃ p : Plan, planAchieves p s .completeTask := by
  intro s h
  refine ⟨[.completeTask], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        completeTaskFires]

/-- `[.acceptTask]` clears `acceptTask` (post-state has
    `taskCode = some "__pending__"`, so `taskCode.isNone = false`). -/
theorem plan_exists_for_acceptTask :
    ∀ s, fires .acceptTask s = true →
      ∃ p : Plan, planAchieves p s .acceptTask := by
  intro s h
  refine ⟨[.acceptTask], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        acceptTaskFires]

/-- `[.taskExchange]` clears `taskExchange` PROVIDED the per-exchange
    minimum coin cost is positive AND the current coin total is less
    than two exchange's worth. Production's `TaskExchangeAction.apply`
    consumes `min_coins` task coins per exchange; the firing predicate
    is `taskCoinsTotal ≥ taskExchangeMinCoins`, so a single exchange
    drops the total below `min` exactly when `total < 2 * min`.

    Honest disclosure: with `taskCoinsTotal ≥ 2 * min`, the planner
    needs multiple exchanges (deferred to Phase 21b's multi-step
    machinery). With `min = 0`, the firing predicate is degenerate
    (always true) and no number of exchanges clears it; the positive-
    `min` precondition rules this out (HTTP 478 on `min = 0` would be a
    server bug). -/
theorem plan_exists_for_taskExchange :
    ∀ s, fires .taskExchange s = true →
      0 < s.taskExchangeMinCoins →
      s.taskCoinsTotal < 2 * s.taskExchangeMinCoins →
      ∃ p : Plan, planAchieves p s .taskExchange := by
  intro s hfire hmin hbound
  refine ⟨[.taskExchange], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        taskExchangeFires] at hfire ⊢
  omega

/-- `[.taskCancel]` clears `taskCancel`. The opaque Bool
    `taskCancelFires` is reset to `false` by the apply, mirroring
    production's post-cancel state observation. -/
theorem plan_exists_for_taskCancel :
    ∀ s, fires .taskCancel s = true →
      ∃ p : Plan, planAchieves p s .taskCancel := by
  intro s h
  refine ⟨[.taskCancel], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        ProductionLadder.taskCancelFires]

/-- `[.buyBankExpansion]` clears `bankExpand` PROVIDED the added 20
    slots suffice to drop the fill ratio below the 0.95 threshold.

    Honest disclosure: production's `BuyBankExpansionAction.apply` only
    grows capacity by 20 (it does not free items). The firing predicate is
    `100 * bankItemsCount ≥ 95 * bankCapacity`; whether the post-state's
    ratio falls below 0.95 depends on the pre-state `bankItemsCount`. The
    precondition `100 * bankItemsCount < 95 * (bankCapacity + 20)`
    formalizes "20 added slots are enough to clear the threshold." -/
theorem plan_exists_for_bankExpand :
    ∀ s, fires .bankExpand s = true →
      100 * s.bankItemsCount < 95 * (s.bankCapacity + bankExpansionSlots) →
      ∃ p : Plan, planAchieves p s .bankExpand := by
  intro s hfire henough
  refine ⟨[.buyBankExpansion], ?_⟩
  -- Unfold the slot constant in `henough` so omega sees a concrete `20`.
  unfold bankExpansionSlots at henough
  simp [planAchieves, applyActionKind, fires,
        bankExpandFires, BANK_EXPAND_FILL_DEN, BANK_EXPAND_FILL_NUM,
        bankExpansionSlots] at hfire ⊢
  -- After simp, the goal collapses to a numeric inequality refuted by
  -- `henough` together with the surviving conjuncts in `hfire`.
  omega

/-! ## Phase 21b — additional single-step plan-existence lemmas

  The state model has no position/coordinates, so MoveTo collapses out at
  this granularity — plans remain single-action even for means whose
  production execution involves a prior move (DepositFull, SellPressured,
  SellIdle, DiscardCritical, DiscardHigh, LowYieldCancel). Phase 21b adds
  6 lemmas covering these means. See `Plan.lean::applyActionKind` for the
  honest minimal-modeling disclosure (state effects updated only for the
  fields the firing predicate reads). -/

/-- `[.deleteItem]` clears `discardCritical`. `DeleteItemAction` removes
    the overstock item; the post-state has `hasOverstockItems = false`,
    which makes the firing predicate's first conjunct false. -/
theorem plan_exists_for_discardCritical :
    ∀ s, fires .discardCritical s = true →
      ∃ p : Plan, planAchieves p s .discardCritical := by
  intro s h
  refine ⟨[.deleteItem], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        discardCriticalFires]

/-- `[.deleteItem]` clears `discardHigh`. Same reasoning as
    `discardCritical`: post-state has `hasOverstockItems = false`. -/
theorem plan_exists_for_discardHigh :
    ∀ s, fires .discardHigh s = true →
      ∃ p : Plan, planAchieves p s .discardHigh := by
  intro s h
  refine ⟨[.deleteItem], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        discardHighFires]

/-- `[.depositAll]` clears `depositFull`. `DepositAllAction` deposits the
    curated subset; the post-state has `selectBankDepositsNonempty =
    false`, killing the firing predicate's final conjunct. -/
theorem plan_exists_for_depositFull :
    ∀ s, fires .depositFull s = true →
      ∃ p : Plan, planAchieves p s .depositFull := by
  intro s h
  refine ⟨[.depositAll], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        depositFullFires]

/-- `[.npcSell]` clears `sellPressured`. `NpcSellAction` sells the
    curated subset; the post-state has `sellableInventoryNonempty =
    false`, killing the firing predicate's final conjunct. -/
theorem plan_exists_for_sellPressured :
    ∀ s, fires .sellPressured s = true →
      ∃ p : Plan, planAchieves p s .sellPressured := by
  intro s h
  refine ⟨[.npcSell], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        sellPressuredFires]

/-- `[.npcSell]` clears `sellIdle`. Same reasoning as `sellPressured`:
    post-state has `sellableInventoryNonempty = false`. -/
theorem plan_exists_for_sellIdle :
    ∀ s, fires .sellIdle s = true →
      ∃ p : Plan, planAchieves p s .sellIdle := by
  intro s h
  refine ⟨[.npcSell], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        sellIdleFires]

/-- `[.taskCancel]` clears `lowYieldCancel`. The opaque Bool
    `lowYieldCancelFires` is reset to `false` by the apply — production's
    cancel clears the active task, so no low-yield cancellation can fire
    on the post-state. -/
theorem plan_exists_for_lowYieldCancel :
    ∀ s, fires .lowYieldCancel s = true →
      ∃ p : Plan, planAchieves p s .lowYieldCancel := by
  intro s h
  refine ⟨[.taskCancel], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        lowYieldCancelFires]

/-! ## Wait — honest weaker statement -/

/-- `WaitGoal` is unsatisfiable by waiting (the action is a no-op and
    the firing predicate is unconditionally `true`). The HONEST Phase
    21a claim is plan-existence with state preservation: there exists a
    plan that the planner can return, and it leaves the state unchanged.
    A `planAchieves` claim would be `true = false` — false. -/
theorem plan_exists_for_wait :
    ∀ s, fires .wait s = true → ∃ p : Plan, applyPlan p s = s := by
  intro s _
  exact ⟨[.wait], by simp [applyActionKind]⟩

/-! ## Deferred lemmas — Phase 21c/d

  After Phase 21b, 4 firing means remain deferred. Plan construction
  for each requires multi-step machinery (combat loops, recipe chains,
  or arbiter-internal lifting) beyond single-action semantics. No
  theorem is declared for any of them in this phase (per phase plan:
  "no sorry, no axioms, comment block only").

  -- Deferred to Phase 21c: bankUnlock        -- requires Fight outcome to satisfy achievement; lift FightProgress.
  -- Deferred to Phase 21c: reachUnlockLevel  -- requires Fight loop to gain levels; lift FightProgress.
  -- Deferred to Phase 21d: pursueTask        -- requires multi-step TaskTrade/Gather recipe-chain plan construction.
  -- Deferred to Phase 21d: objectiveStep     -- requires lifting the StrategyArbiter objective tier (varies by chosen step shape).
-/

end Formal.Liveness.PlanExists
