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
import Mathlib.Tactic.Ring
import Mathlib.Tactic.Set

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

/-! ## Phase 21c — Fight-based plan-existence lemmas

  Phase 21c covers the two firing means resolved by `FightAction`:
  `bankUnlock` and `reachUnlockLevel`. Both witnesses are sequences of
  `.fight` actions. The Plan.lean extension of `applyActionKind .fight`
  (a) flips `bankAccessible := true` when the pre-state satisfies the
  bank-unlock firing conditions, and (b) handles xp/level rollover so
  that bounded fight sequences advance `level` (capped at 50). See
  `Plan.lean::applyActionKind` for the honest-disclosure block on each
  extension.
-/

/-- `[.fight]` clears `bankUnlock`. The pre-state satisfies the
    `bankUnlockFires` predicate; the Phase 21c `.fight` apply detects
    this exact predicate and flips `bankAccessible := true`. The
    post-state then has `bankAccessible = true`, killing the
    firing-predicate conjunct `!bankAccessible`. -/
theorem plan_exists_for_bankUnlock :
    ∀ s, fires .bankUnlock s = true →
      ∃ p : Plan, planAchieves p s .bankUnlock := by
  intro s h
  refine ⟨[.fight], ?_⟩
  -- The fight apply's `unlockMonsterReady` guard equals
  -- `bankUnlockFires` exactly. Pre-state has it true, so the post-state
  -- has bankAccessible = true, killing the `!bankAccessible` conjunct.
  -- Unfold planAchieves / applyPlan and the apply.
  unfold planAchieves
  rw [applyPlan_singleton]
  -- Goal: fires .bankUnlock (applyActionKind .fight s) = false.
  -- The fight apply on bankUnlock-firing pre-state sets bankAccessible = true.
  have hReady :
      (s.bankUnlockMonsterPresent
        && !s.bankAccessible
        && decide (s.xp ≤ s.initialXp)
        && (decide (s.unlockMonsterLevel = 0)
            || decide (s.level + 1 ≥ s.unlockMonsterLevel))) = true := by
    -- This IS the bankUnlockFires predicate from production.
    have := h
    unfold fires ProductionLadder.bankUnlockFires at this
    exact this
  -- Now compute (applyActionKind .fight s).bankAccessible = true.
  have hbank : (applyActionKind .fight s).bankAccessible = true := by
    simp only [applyActionKind]
    -- The let-binding for unlockMonsterReady evaluates to hReady = true,
    -- so newBankAccessible = true.
    simp [hReady]
  -- Show fires .bankUnlock (applyActionKind .fight s) = false.
  unfold fires ProductionLadder.bankUnlockFires
  rw [hbank]
  simp

/-! ### Auxiliary lemmas for reachUnlockLevel plan construction

The `.fight` apply either bumps `xp += 10` (when `xp + 10 < xpToNextLevel
level`) or rolls over (`level += 1`, `xp := 0`). To show plan-existence
for `reachUnlockLevel`, we need: from any state with `level < target ≤
50`, repeated fights eventually push `level ≥ target`.

Strategy:
  1. `applyFightN`: n-fight projection.
  2. `fight_level_monotone`: per-fight level never decreases.
  3. `applyFightN_no_levelup_xp`: if `n` fights kept level constant,
     then xp grew by exactly `10 * n`. (Induction on n with the bound
     on the LAST step derived inside.)
  4. `bound_fights_advance_level`: `n := xpToNextLevel s.level` fights
     strictly advance level (provided `level < 50`). Contradiction
     using (3): if level stayed constant, then xp = s.xp + 10*n, but
     this requires (from no-rollover invariant) `s.xp + 10*n <
     xpToNextLevel = n`, contradicting `10n ≥ n` for `n ≥ 1`
     (LIV-001).
  5. `exists_fights_reach_level`: induction on `target - level` using
     (4) per step.
-/

/-- `applyFightN n s = applyPlan (List.replicate n .fight) s`. -/
noncomputable def applyFightN (n : Nat) (s : State) : State :=
  applyPlan (List.replicate n .fight) s

@[simp] theorem applyFightN_zero (s : State) : applyFightN 0 s = s := by
  simp [applyFightN, applyPlan]

theorem applyFightN_succ_left (n : Nat) (s : State) :
    applyFightN (n+1) s = applyFightN n (applyActionKind .fight s) := by
  simp [applyFightN, applyPlan, List.replicate_succ]

/-- Per-fight level monotonicity. -/
theorem fight_level_monotone (s : State) :
    s.level ≤ (applyActionKind .fight s).level := by
  simp only [applyActionKind]
  split <;> omega

/-- Per-fight no-rollover characterisation: when `xp + 10 <
    xpToNextLevel level`, the apply keeps level constant and bumps xp
    by 10. -/
theorem fight_no_rollover
    (s : State) (h : s.xp + 10 < xpToNextLevel s.level) :
    (applyActionKind .fight s).level = s.level
    ∧ (applyActionKind .fight s).xp = s.xp + 10 := by
  simp only [applyActionKind]
  have hwill :
      (decide (s.xp + 10 ≥ xpToNextLevel s.level)
        && decide (s.level < 50)) = false := by
    have hnot : ¬ s.xp + 10 ≥ xpToNextLevel s.level := Nat.not_le.mpr h
    simp [hnot]
  simp [hwill]

/-- If `n` fights from `s` leave `level` unchanged, then `xp` grew by
    exactly `10*n`. The "level unchanged" assumption is the hypothesis. -/
theorem applyFightN_no_levelup_xp
    (n : Nat) (s : State)
    (hlvl : (applyFightN n s).level = s.level) :
    (applyFightN n s).xp = s.xp + 10 * n := by
  induction n generalizing s with
  | zero => simp
  | succ k ih =>
    rw [applyFightN_succ_left] at hlvl ⊢
    -- The first fight either rolled over (level := s.level + 1) or didn't.
    -- Goal: extract that it didn't roll over.
    have hmono1 := fight_level_monotone s
    have hmono_k :
        (applyActionKind .fight s).level ≤
          (applyFightN k (applyActionKind .fight s)).level := by
      -- General monotonicity of applyFightN.
      clear ih hlvl
      generalize (applyActionKind .fight s) = s'
      induction k generalizing s' with
      | zero => simp
      | succ j ih2 =>
        rw [applyFightN_succ_left]
        exact Nat.le_trans (fight_level_monotone s') (ih2 _)
    -- From hlvl: (applyFightN k (applyActionKind .fight s)).level = s.level.
    -- Combine with mono: (applyActionKind .fight s).level = s.level.
    have hstep_lvl_eq : (applyActionKind .fight s).level = s.level := by
      have h1 : (applyActionKind .fight s).level ≤ s.level := by
        calc (applyActionKind .fight s).level
            ≤ (applyFightN k (applyActionKind .fight s)).level := hmono_k
          _ = s.level := hlvl
      exact Nat.le_antisymm h1 hmono1
    -- Now extract that the first fight didn't trigger rollover.
    have hno_roll : ¬ (s.xp + 10 ≥ xpToNextLevel s.level ∧ s.level < 50) := by
      intro ⟨hxp, hlt50⟩
      -- Then apply gives level := s.level + 1, contradicting hstep_lvl_eq.
      have : (applyActionKind .fight s).level = s.level + 1 := by
        simp only [applyActionKind]
        have hwill :
            (decide (s.xp + 10 ≥ xpToNextLevel s.level)
              && decide (s.level < 50)) = true := by simp [hxp, hlt50]
        simp [hwill]
      omega
    -- So either xp + 10 < xpToNextLevel level OR level ≥ 50.
    -- Case split: if level ≥ 50, the apply keeps state unchanged in level
    -- (the willLevel guard fails on the second conjunct), and xp += 10.
    by_cases hlt50 : s.level < 50
    · have hxp1 : s.xp + 10 < xpToNextLevel s.level := by
        by_contra hge
        have hge : s.xp + 10 ≥ xpToNextLevel s.level := Nat.le_of_not_lt hge
        exact hno_roll ⟨hge, hlt50⟩
      have ⟨hsl, hsx⟩ := fight_no_rollover s hxp1
      -- Recurse on ih.
      have hlvl' : (applyFightN k (applyActionKind .fight s)).level
                     = (applyActionKind .fight s).level := by
        rw [hsl]; exact hlvl
      have := ih _ hlvl'
      rw [this, hsx]
      ring
    · -- level ≥ 50: apply keeps level (willLevel false on second conjunct)
      -- but still bumps xp.
      have hsl : (applyActionKind .fight s).level = s.level := by
        simp only [applyActionKind]
        have hwill :
            (decide (s.xp + 10 ≥ xpToNextLevel s.level)
              && decide (s.level < 50)) = false := by
          have : ¬ s.level < 50 := hlt50
          simp [this]
        simp [hwill]
      have hsx : (applyActionKind .fight s).xp = s.xp + 10 := by
        simp only [applyActionKind]
        have hwill :
            (decide (s.xp + 10 ≥ xpToNextLevel s.level)
              && decide (s.level < 50)) = false := by
          have : ¬ s.level < 50 := hlt50
          simp [this]
        simp [hwill]
      have hlvl' : (applyFightN k (applyActionKind .fight s)).level
                     = (applyActionKind .fight s).level := by
        rw [hsl]; exact hlvl
      have := ih _ hlvl'
      rw [this, hsx]
      ring

/-- `n := xpToNextLevel s.level` fights strictly advance level (when
    `s.level < 50`). Proof: if not, then level stayed constant, which
    by `applyFightN_no_levelup_xp` gives xp = s.xp + 10*n, but then
    after n-1 fights the pre-state of step n had xp = s.xp + 10*(n-1),
    and the level-guard `xp + 10 ≥ xpToNextLevel level` becomes
    `s.xp + 10*n ≥ n`, which IS true (10n ≥ n for n ≥ 1, LIV-001),
    so the level WOULD have rolled over, contradiction. -/
theorem bound_fights_advance_level
    (s : State) (hlvl : s.level < 50) :
    s.level < (applyFightN (xpToNextLevel s.level) s).level := by
  set n := xpToNextLevel s.level with hn_def
  by_contra hle
  have hle : (applyFightN n s).level ≤ s.level := Nat.le_of_not_lt hle
  -- General mono.
  have hmono : ∀ k s', s'.level ≤ (applyFightN k s').level := by
    intro k
    induction k with
    | zero => intro s'; simp
    | succ j ih =>
      intro s'
      rw [applyFightN_succ_left]
      exact Nat.le_trans (fight_level_monotone s') (ih _)
  have hmn := hmono n s
  have heq : (applyFightN n s).level = s.level := Nat.le_antisymm hle hmn
  have hxp_eq : (applyFightN n s).xp = s.xp + 10 * n :=
    applyFightN_no_levelup_xp n s heq
  -- We need a contradiction. Use the n-th step decomposition.
  have hn_pos : 0 < n := xpToNextLevel_pos s.level hlvl
  -- n = (n-1) + 1. Decompose applyFightN n s = applyActionKind .fight (applyFightN (n-1) s).
  -- We need a right-step lemma.
  have hsucc_right : ∀ m s', applyFightN (m+1) s' =
      applyActionKind .fight (applyFightN m s') := by
    intro m
    induction m with
    | zero =>
      intro s'
      rw [applyFightN_succ_left, applyFightN_zero, applyFightN_zero]
    | succ j ih =>
      intro s'
      rw [applyFightN_succ_left, ih (applyActionKind .fight s'),
          ← applyFightN_succ_left]
  obtain ⟨m, hm_eq⟩ : ∃ m, n = m + 1 := ⟨n - 1, by omega⟩
  rw [hm_eq] at heq hxp_eq
  rw [hsucc_right m s] at heq hxp_eq
  -- Let t := applyFightN m s. We have:
  --   heq    : (applyActionKind .fight t).level = s.level
  --   hxp_eq : (applyActionKind .fight t).xp    = s.xp + 10 * (m + 1)
  -- Also, by mono and equality chain, t.level = s.level.
  have htmid_lvl_eq : (applyFightN m s).level = s.level := by
    -- (applyFightN m s).level ≤ (applyActionKind .fight (applyFightN m s)).level (mono)
    --                       = s.level (from heq).
    have h1 : (applyFightN m s).level ≤ s.level := by
      have hstep := fight_level_monotone (applyFightN m s)
      -- hstep : (applyFightN m s).level ≤ (applyActionKind .fight (applyFightN m s)).level
      rw [heq] at hstep
      exact hstep
    have h2 := hmono m s
    omega
  have htmid_xp_eq : (applyFightN m s).xp = s.xp + 10 * m :=
    applyFightN_no_levelup_xp m s htmid_lvl_eq
  -- Now examine the (m+1)-th fight applied to t := applyFightN m s.
  set t := applyFightN m s
  -- Step apply: if t.xp + 10 ≥ xpToNextLevel t.level AND t.level < 50,
  -- then level := t.level + 1. We have t.level = s.level, t.xp = s.xp + 10*m,
  -- t.level < 50 (= s.level), and t.xp + 10 = s.xp + 10*(m+1) = s.xp + 10n ≥ n
  -- = xpToNextLevel s.level = xpToNextLevel t.level (since t.level = s.level).
  -- That triggers rollover, but heq says level stays = s.level.
  have hge : t.xp + 10 ≥ xpToNextLevel t.level := by
    rw [htmid_xp_eq, htmid_lvl_eq]
    -- Goal: s.xp + 10*m + 10 ≥ xpToNextLevel s.level.
    -- xpToNextLevel s.level = n, and n = m + 1, so RHS = m + 1.
    -- LHS = s.xp + 10*m + 10 ≥ 10*m + 10 = 10*(m+1) ≥ m+1.
    have hxptn : xpToNextLevel s.level = m + 1 := by rw [← hn_def, hm_eq]
    rw [hxptn]
    have h10m : 10 * m + 10 ≥ m + 1 := by
      have : 10 * m ≥ m := Nat.le_mul_of_pos_left m (by norm_num)
      omega
    omega
  have hlt : t.level < 50 := by rw [htmid_lvl_eq]; exact hlvl
  have hroll : (applyActionKind .fight t).level = t.level + 1 := by
    simp only [applyActionKind]
    have hwill :
        (decide (t.xp + 10 ≥ xpToNextLevel t.level)
          && decide (t.level < 50)) = true := by simp [hge, hlt]
    simp [hwill]
  rw [hroll, htmid_lvl_eq] at heq
  omega

/-- Additivity of `applyFightN`. -/
theorem applyFightN_add (a b : Nat) (s : State) :
    applyFightN (a + b) s = applyFightN b (applyFightN a s) := by
  induction a generalizing s with
  | zero => simp
  | succ k ih =>
    rw [show k + 1 + b = (k + b) + 1 from by ring,
        applyFightN_succ_left, ih, applyFightN_succ_left]

/-- Iterated form: for every target ≤ 50, there exists `N` such that
    `N` fights from `s` push `level ≥ target`. Strong induction on
    `target - s.level` (which strictly decreases on each level-up). -/
theorem exists_fights_reach_target :
    ∀ (gap : Nat) (target : Nat) (s : State),
      target ≤ 50 →
      target - s.level ≤ gap →
      ∃ N, (applyFightN N s).level ≥ target := by
  intro gap
  induction gap with
  | zero =>
    intro target s _ hgap
    -- target - s.level = 0 ⇒ s.level ≥ target.
    refine ⟨0, ?_⟩
    simp
    omega
  | succ k ih =>
    intro target s htarget hgap
    by_cases hreached : s.level ≥ target
    · exact ⟨0, by simp; exact hreached⟩
    · -- s.level < target ≤ 50.
      have hslt : s.level < 50 := by omega
      have hadv := bound_fights_advance_level s hslt
      -- After N1 = xpToNextLevel s.level fights, level strictly advances.
      set N1 := xpToNextLevel s.level with hN1
      set s1 := applyFightN N1 s with hs1
      -- s1.level > s.level, so target - s1.level < target - s.level ≤ k+1,
      -- i.e. target - s1.level ≤ k.
      have hgap' : target - s1.level ≤ k := by
        have : s1.level ≥ s.level + 1 := hadv
        omega
      obtain ⟨N2, h2⟩ := ih target s1 htarget hgap'
      refine ⟨N1 + N2, ?_⟩
      rw [applyFightN_add]
      exact h2

/-- `applyFightN` preserves `bankRequiredLevel` (ctx field unaffected by
    any of the in-scope ActionKind apply branches). -/
theorem fight_preserves_bankRequiredLevel (N : Nat) (s : State) :
    (applyFightN N s).bankRequiredLevel = s.bankRequiredLevel := by
  induction N generalizing s with
  | zero => simp
  | succ k ih =>
    rw [applyFightN_succ_left, ih (applyActionKind .fight s)]
    simp [applyActionKind]

/-- `[.fight]^N` for sufficiently-large `N` clears `reachUnlockLevel`.

    Precondition `s.bankRequiredLevel ≤ 50` is a server bound (the
    bank-required level is one of the server's monster levels, all
    ≤ 50 per `/v3/server/details`). Without it, `level` cannot reach
    `bankRequiredLevel` via fights because the apply caps level at 50.

    The plan-length bound is `N = Σ_{i=0}^{gap-1} xpToNextLevel
    (s.level + i)` in closed form, where `gap = bankRequiredLevel -
    s.level ≤ 5` (`MAX_ACHIEVABLE_GAP_LV2`). This proof EXHIBITS the
    existence via `exists_fights_reach_level` without computing N in
    closed form (Phase 23 will pin it down). The witness's length is
    bounded by `Σ xpToNextLevel`, finite per LIV-001.
-/
theorem plan_exists_for_reachUnlockLevel :
    ∀ s, fires .reachUnlockLevel s = true →
      s.bankRequiredLevel ≤ 50 →
      ∃ p : Plan, planAchieves p s .reachUnlockLevel := by
  intro s h hbound
  -- Decompose firing hypothesis.
  simp only [fires, ProductionLadder.reachUnlockLevelFires,
             Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨⟨hbr_pos, hlt⟩, _hgap⟩ := h
  -- Use exists_fights_reach_target with target := bankRequiredLevel
  -- and gap := bankRequiredLevel - s.level.
  obtain ⟨N, hN⟩ := exists_fights_reach_target
    (s.bankRequiredLevel - s.level) s.bankRequiredLevel s hbound (le_refl _)
  -- The plan is List.replicate N .fight; planAchieves means
  -- fires .reachUnlockLevel (applyPlan ... s) = false.
  refine ⟨List.replicate N .fight, ?_⟩
  -- bankRequiredLevel field is preserved by .fight. Use the file-scope
  -- helper to keep the IH free of extraneous hypotheses.
  have hbr_preserved : (applyFightN N s).bankRequiredLevel = s.bankRequiredLevel :=
    fight_preserves_bankRequiredLevel N s
  -- The plan equals applyFightN N s on the projection side.
  show fires .reachUnlockLevel (applyPlan (List.replicate N .fight) s) = false
  have hplan_eq : applyPlan (List.replicate N .fight) s = applyFightN N s := rfl
  rw [hplan_eq]
  -- Now: fires .reachUnlockLevel s' = false where s' = applyFightN N s.
  unfold fires ProductionLadder.reachUnlockLevelFires
  -- s'.level ≥ s.bankRequiredLevel = s'.bankRequiredLevel, so the
  -- second conjunct (decide (level < bankRequiredLevel)) is false.
  have hsl_not_lt :
      ¬ (applyFightN N s).level < (applyFightN N s).bankRequiredLevel := by
    rw [hbr_preserved]; omega
  simp [hsl_not_lt]

/-! ## Phase 21d-1 — final Tier-3 plan-existence lemmas

Two lemmas closing Tier-3 plan-existence coverage:

  - `plan_exists_for_pursueTask`: witness `[.taskTrade]`, collapsing a
    multi-trade delivery into one step (honest disclosure in
    `Plan.lean`'s `.taskTrade` branch).
  - `plan_exists_for_objectiveStep`: witness `[.objectiveStep]`, the
    synthetic placeholder ActionKind (honest disclosure in
    `PlanAction.lean`'s docstring "Phase 21d-1: synthetic
    `.objectiveStep` placeholder").
-/

/-- `[.taskTrade, .completeTask]` clears `pursueTask`.

    Phase 23d-5 update: with the refined `.taskTrade` semantics
    (taskProgress += 1, NOT taskProgress := taskTotal), one `.taskTrade`
    step may leave the phase at `.inProgress` if `taskProgress + 1 <
    taskTotal`. To guarantee clearing of `pursueTaskFires` (which
    requires `phase ∉ {.accepted, .inProgress}`), we follow with a
    `.completeTask` step. The `.completeTask` apply (Plan.lean line 149)
    unconditionally clears `taskCode`, `taskProgress`, `taskTotal`, and
    sets `taskLifecyclePhase := .none` — regardless of whether the task
    is structurally ready for completion. This is a planner-side
    projection; production would never sequence these two without an
    intervening progress check, but the existential plan-existence claim
    is about model-side state transitions, not production sequencing.

    Honest disclosure: the witness `[.taskTrade, .completeTask]` is a
    two-step plan that the planner WOULD NOT actually emit in production
    (the strategy arbiter sequences them via the ladder, one at a time).
    The plan-existence claim is purely about the Lean state-machine: a
    plan EXISTS that flips the post-state's firing predicate to false. -/
theorem plan_exists_for_pursueTask :
    ∀ s, fires .pursueTask s = true →
      ∃ p : Plan, planAchieves p s .pursueTask := by
  intro s h
  refine ⟨[.taskTrade, .completeTask], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        ProductionLadder.pursueTaskFires, applyPlan]

/-- `[.objectiveStep]` clears `objectiveStep`. The Phase 21d-1 synthetic
    placeholder ActionKind flips the opaque `objectiveStepFires` Bool to
    `false`. Honest disclosure: `.objectiveStep` is NOT a production
    Action subclass — it is a tier-dispatch tag. Production composes the
    sub-goal's plan from ordinary Action subclasses; Phase 22 (Cycle
    Loop) will refine this composition. The existential claim "the
    objective tier IS plannable" is sufficient here. -/
theorem plan_exists_for_objectiveStep :
    ∀ s, fires .objectiveStep s = true →
      ∃ p : Plan, planAchieves p s .objectiveStep := by
  intro s h
  refine ⟨[.objectiveStep], ?_⟩
  simp [planAchieves, applyActionKind, fires,
        ProductionLadder.objectiveStepFires]

end Formal.Liveness.PlanExists
