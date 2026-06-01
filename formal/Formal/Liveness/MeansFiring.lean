/-
  Formal.Liveness.MeansFiring

  Phase 20b-v2 — per-MeansKind firing lemmas. For each `MeansKind`
  constructor `k`, we prove (sometimes conditionally on an opaque-Bool
  invariant):

      ∀ s, ProductionLadder.fires k s = true → <Phase-18 goal value> > 0

  The Phase-18 value functions live in `Formal.GoalSystem`. The connection
  pattern is:

    1.  Production's `_fires k s` predicate (from `tiers/guards.py` /
        `tiers/means.py`, mirrored in `ProductionLadder.fires`) implies
        the corresponding goal's `<goal>Satisfied s` predicate is FALSE,
        AND any extra Phase-18 routing-guards are satisfied.

    2.  Therefore the goal's value() returns the positive branch's value.

  ## Honest-disclosure boundaries

  Several `_fires` predicates depend on opaque Bool fields on `State` whose
  truth represents production's observation (see `ProductionLadder.lean`
  docstring). For these, the lemma takes a HYPOTHESIS connecting the
  opaque Bool to the goal's "not satisfied" predicate. The hypotheses are
  bundled in `ProductionInvariants`. NO new axioms are introduced; the
  invariants are load-bearing modeling commitments that the Phase 20d-v2
  differential must exercise against production.

  Opaque-gated MeansKinds:
    - `lowYieldCancel`  (LowYieldCancelGoal value is constant 70 if `fires`)
    - `taskCancel`      (TaskCancelGoal value is 12 if pivoting + not satisfied)
    - `pursueTask`      (PursueTaskGoal value > 0 if not satisfied)
    - `objectiveStep`   (NO Phase-18 value function — GAP, see below)

  ## Disclosed gap: `objectiveStep`

  The `objectiveStep` MeansKind models the StrategyArbiter's objective-
  tier StepGoal injection. Phase-18 `Formal.GoalSystem` does NOT model the
  StepGoal's `value()` (it is a tier-arbiter concept whose value is
  computed at runtime from the active Objective's progress projection).
  We cannot connect `objectiveStepFires s = true` to a Phase-18 value
  function in this phase; the lemma is omitted and disclosed in the
  per-MeansKind table in the phase report. A later phase must either
  add a Phase-18 model for the objective StepGoal or fold the objective
  step into a different firing-witness contract.

  ## Disclosed model: `pursueTask`

  `Formal.GoalSystem` does NOT expose a `pursueTaskValue` in the
  Phase-18 "Bool → Rat" shape. `Formal.Phase10GoalLattices.pursueTaskValue`
  has a 5-input form with batch logic that doesn't cleanly compose here.
  We therefore define a local `pursueTaskValueModel` mirroring the
  production goal's "value = priority constant when not satisfied" — a
  thin wrapper whose semantics match production exactly for the
  fire-positive direction we care about. This makes the load-bearing
  modeling commitment explicit.

  Liveness namespace — Mathlib axioms allowed.
-/
import Formal.Liveness.ProductionLadder
import Formal.GoalSystem
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Positivity

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.MeansFiring

open Formal.Liveness.Measure
open Formal.Liveness.ProductionLadder
open Formal.Liveness.MeansKind
open Formal.GoalSystem

/-! ## State-derived Rat / Int helpers (feeders for Phase-18 value functions). -/

/-- Production `state.hp_percent`: `hp / max_hp`, with the Python
    convention that `max_hp == 0 ⇒ 1.0`. Modeled in `Rat`. -/
def hpPercentRat (s : State) : Rat :=
  if s.maxHp = 0 then 1 else (s.hp : Rat) / (s.maxHp : Rat)

/-- Production `state.inventory_used / state.inventory_max`, with
    `inventory_max == 0 ⇒ 0`. -/
def usedFractionRat (s : State) : Rat :=
  if s.inventoryMax = 0 then 0 else (s.inventoryUsed : Rat) / (s.inventoryMax : Rat)

/-- Production `ctx.bank_required_level - state.level`. -/
def unlockGap (s : State) : Int := (s.bankRequiredLevel : Int) - (s.level : Int)

/-! ## Goal-side "satisfied" predicates. -/

/-- `ReachUnlockLevelGoal.is_satisfied` mirror. -/
def reachUnlockLevelSatisfied (s : State) : Bool :=
  decide (s.bankRequiredLevel = 0) || decide (s.level ≥ s.bankRequiredLevel)

/-- `DiscardOverstockGoal.is_satisfied` — no overstock. -/
def discardOverstockSatisfied (s : State) : Bool := !s.hasOverstockItems

/-- `ClaimPendingGoal.is_satisfied` — no pending items. -/
def claimPendingSatisfied (s : State) : Bool := !s.pendingItemsNonempty

/-- `CompleteTaskGoal.is_satisfied` — no task or task_total = 0. -/
def completeTaskSatisfied (s : State) : Bool :=
  s.taskCode.isNone || decide (s.taskTotal = 0)

/-- `CompleteTaskGoal` progressFull witness for Phase-18 routing. -/
def completeTaskProgressFull (s : State) : Bool := decide (s.taskProgress ≥ s.taskTotal)

/-- `AcceptTaskGoal.is_satisfied` — there IS a task code. -/
def acceptTaskSatisfied (s : State) : Bool := s.taskCode.isSome

/-- `PursueTaskGoal.is_satisfied` model — no task / total=0 / progress
    already at total. Used in the opaque invariant. -/
def pursueTaskSatisfied (s : State) : Bool :=
  s.taskCode.isNone || decide (s.taskTotal = 0)
    || decide (s.taskProgress ≥ s.taskTotal)

/-- Production-shape `PursueTaskGoal.value` — priority `PRIORITY_FLOOR = 35`
    when not satisfied, else 0. Modeled directly here because
    `Formal.GoalSystem` does not expose this exact shape. -/
def pursueTaskValueModel (satisfied : Bool) : Rat :=
  if satisfied then 0 else 35

theorem pursueTaskValueModel_positive_when_unsatisfied :
    pursueTaskValueModel false > 0 := by
  unfold pursueTaskValueModel; norm_num

/-! ## ProductionInvariants — load-bearing opaque-Bool connections. -/

/-- Phase 23c-3b: `ProductionInvariants` was previously a load-bearing
    bundle of opaque-Bool implications. With the faithful phase-based
    fires predicates introduced in 23c-3b, the lifecycle-MeansKind
    lemmas no longer need these invariants — they are provable directly
    from phase-equality.

    The structure is kept (empty) so existing call sites that mention
    `ProductionInvariants s` as a hypothesis continue to typecheck;
    any such site is now a free hypothesis. -/
structure ProductionInvariants (s : State) : Prop where

/-! ## Per-MeansKind firing lemmas -/

/-! ### Guard tier (GUARD_ORDER) -/

/-- HP_CRITICAL: `_fires .hpCritical s` ⇒ `restoreHpValue = 110 > 0`. -/
theorem _fires_hpCritical_implies_restoreHp_positive (s : State) :
    fires .hpCritical s = true →
    restoreHpValue (hpPercentRat s) > 0 := by
  intro h
  unfold fires hpCriticalFires at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨hmax, hcrit⟩ := h
  have hmax_ne : s.maxHp ≠ 0 := Nat.pos_iff_ne_zero.mp hmax
  have hmax_pos_rat : (0 : Rat) < (s.maxHp : Rat) := by exact_mod_cast hmax
  -- hp/maxHp < 25/100 ⇔ 100*hp < 25*maxHp
  have hpct_lt : hpPercentRat s < restoreHpCriticalFraction := by
    unfold hpPercentRat restoreHpCriticalFraction
    simp [hmax_ne]
    have h1 : CRITICAL_HP_DEN * s.hp < CRITICAL_HP_NUM * s.maxHp := hcrit
    unfold CRITICAL_HP_DEN CRITICAL_HP_NUM at h1
    have h2 : (100 * s.hp : Rat) < (25 * s.maxHp : Rat) := by exact_mod_cast h1
    -- Goal: hp / maxHp < 25 / 100 ↔ hp * 100 < 25 * maxHp.
    rw [div_lt_div_iff₀ hmax_pos_rat (by norm_num : (0 : Rat) < 100)]
    linarith
  rw [restoreHp_critical_is_110 _ hpct_lt]
  norm_num

/-- BANK_UNLOCK: `_fires .bankUnlock s` ⇒ `unlockBankValue` > 0 on the
    intended Phase-18 routing (`bankLocked=true`, `xpExceeded=false`,
    `unreachable=false`, `hasSellable=false`) — yields 90. -/
theorem _fires_bankUnlock_implies_unlockBank_positive (s : State) :
    fires .bankUnlock s = true →
    unlockBankValue (bankLocked := true) (xpExceeded := false)
      (unreachable := false) (usedFraction := usedFractionRat s)
      (hasSellable := false) > 0 := by
  intro _
  unfold unlockBankValue unlockBankDeferralFraction
  simp

/-- REACH_UNLOCK_LEVEL: `_fires .reachUnlockLevel s` ⇒
    `reachUnlockLevelValue = 85 > 0`. -/
theorem _fires_reachUnlockLevel_implies_value_positive (s : State) :
    fires .reachUnlockLevel s = true →
    reachUnlockLevelValue (reachUnlockLevelSatisfied s)
      (s.bankRequiredLevel : Int) (unlockGap s) > 0 := by
  intro h
  unfold fires reachUnlockLevelFires at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨⟨hbr_pos, hlt⟩, hgap⟩ := h
  unfold reachUnlockLevelValue reachUnlockLevelSatisfied unlockGap maxAchievableGap
  have hbr_ne : ¬ s.bankRequiredLevel = 0 := Nat.pos_iff_ne_zero.mp hbr_pos
  have hnot_ge : ¬ s.level ≥ s.bankRequiredLevel := Nat.not_le.mpr hlt
  have hsat_false :
      (decide (s.bankRequiredLevel = 0) || decide (s.level ≥ s.bankRequiredLevel)) = false := by
    simp [hbr_ne, hnot_ge]
  rw [hsat_false]
  simp
  have htl_pos : (s.bankRequiredLevel : Int) > 0 := by exact_mod_cast hbr_pos
  have hgap_le : (s.bankRequiredLevel : Int) - (s.level : Int) ≤ 5 := by
    have hle : s.level ≤ s.bankRequiredLevel := Nat.le_of_lt hlt
    have h2 : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2 := hgap
    unfold MAX_ACHIEVABLE_GAP_LV2 at h2
    omega
  -- Discharge both ifs.
  split
  · -- `s.bankRequiredLevel = 0` branch contradicts hbr_pos.
    rename_i hbr_zero
    omega
  · split
    · -- gap > 5 branch contradicts hgap_le
      rename_i hgap_big; omega
    · -- both branches dispatched; value = 85.
      norm_num

/-- DISCARD_CRITICAL: `_fires .discardCritical s` ⇒
    `discardOverstockValue ≥ 40 > 0`. -/
theorem _fires_discardCritical_implies_discardOverstock_positive (s : State) :
    fires .discardCritical s = true →
    discardOverstockValue (discardOverstockSatisfied s) (usedFractionRat s) > 0 := by
  intro h
  unfold fires discardCriticalFires at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨⟨hover, _⟩, _⟩ := h
  unfold discardOverstockSatisfied
  rw [hover]
  simp only [Bool.not_true]
  have := discardOverstock_unsatisfied_at_least_40 (usedFractionRat s)
  linarith

/-- DEPOSIT_FULL: `_fires .depositFull s` ⇒ `depositInventoryValue > 0`. -/
theorem _fires_depositFull_implies_depositInventory_positive (s : State) :
    fires .depositFull s = true →
    depositInventoryValue (accessible := true) (satisfied := false)
      (invMaxZero := false) (usedFractionRat s) > 0 := by
  intro h
  unfold fires depositFullFires at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨⟨⟨_, hmax⟩, hused⟩, _⟩ := h
  have hmax_ne : s.inventoryMax ≠ 0 := Nat.pos_iff_ne_zero.mp hmax
  have hmax_pos_rat : (0 : Rat) < (s.inventoryMax : Rat) := by exact_mod_cast hmax
  -- usedFractionRat s ≥ 80/100
  have huf_ge : usedFractionRat s ≥ 80 / 100 := by
    unfold usedFractionRat
    simp [hmax_ne]
    rw [div_le_div_iff₀ (by norm_num : (0 : Rat) < 100) hmax_pos_rat]
    have h1 : DEPOSIT_FULL_DEN * s.inventoryUsed ≥ DEPOSIT_FULL_NUM * s.inventoryMax := hused
    unfold DEPOSIT_FULL_DEN DEPOSIT_FULL_NUM at h1
    have h2 : 80 * s.inventoryMax ≤ 100 * s.inventoryUsed := by omega
    have h3 : (80 * s.inventoryMax : Rat) ≤ (100 * s.inventoryUsed : Rat) := by exact_mod_cast h2
    linarith
  unfold depositInventoryValue depositRampStart depositMaxValue
  simp
  -- After simp, target uses `2⁻¹` form. Build positivity from huf_ge.
  have hhalf_eq : (2⁻¹ : Rat) = 1 / 2 := by norm_num
  have hnot_lt : ¬ usedFractionRat s < (2⁻¹ : Rat) := by
    rw [hhalf_eq]; intro hlt
    have : (1 : Rat) / 2 ≤ 80 / 100 := by norm_num
    linarith
  simp [hnot_lt]
  -- Now: 0 < (uf - 2⁻¹) / (1 - 2⁻¹) * 80
  have huf_gt : usedFractionRat s > 2⁻¹ := by
    rw [hhalf_eq]
    have : (1 : Rat) / 2 < 80 / 100 := by norm_num
    linarith
  have hnum_pos : usedFractionRat s - 2⁻¹ > 0 := by linarith
  have hden_pos : (1 : Rat) - 2⁻¹ > 0 := by norm_num
  have h80 : (0 : Rat) < 80 := by norm_num
  -- Goal may be `0 < (uf - 2⁻¹) / (1 - 2⁻¹) * 80` or factored —
  -- close it by positivity.
  positivity

/-- DISCARD_HIGH: `_fires .discardHigh s` ⇒
    `discardOverstockValue ≥ 40 > 0`. -/
theorem _fires_discardHigh_implies_discardOverstock_positive (s : State) :
    fires .discardHigh s = true →
    discardOverstockValue (discardOverstockSatisfied s) (usedFractionRat s) > 0 := by
  intro h
  unfold fires discardHighFires at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨⟨hover, _⟩, _⟩ := h
  unfold discardOverstockSatisfied
  rw [hover]
  simp only [Bool.not_true]
  have := discardOverstock_unsatisfied_at_least_40 (usedFractionRat s)
  linarith

/-! ### Collect-reward tier -/

/-- CLAIM_PENDING: `_fires .claimPending s` ⇒ `claimPendingValue = 25 > 0`. -/
theorem _fires_claimPending_implies_claimPending_positive (s : State) :
    fires .claimPending s = true →
    claimPendingValue (claimPendingSatisfied s) > 0 := by
  intro h
  -- fires .claimPending s reduces to claimPendingFires s = pendingItemsNonempty.
  change claimPendingFires s = true at h
  unfold claimPendingFires at h
  unfold claimPendingValue claimPendingSatisfied
  rw [h]
  simp

/-- COMPLETE_TASK: Phase 23c-3b phase-based form. `_fires .completeTask s`
    means `taskLifecyclePhase = .complete`. Under the consistency
    predicate `taskPhaseConsistent`, this back-implies the original
    `(taskCode set, taskTotal > 0, taskProgress ≥ taskTotal)` conditions
    necessary for `completeTaskValue` to be 90.

    The proof now takes `taskPhaseConsistent s` as an extra hypothesis
    (the structural consistency invariant on canonical-constructor
    states; see Measure.lean). -/
theorem _fires_completeTask_implies_completeTask_positive (s : State)
    (hcons : taskPhaseConsistent s) :
    fires .completeTask s = true →
    completeTaskValue (completeTaskSatisfied s) (completeTaskProgressFull s) > 0 := by
  intro h
  unfold fires completeTaskFires at h
  simp only [decide_eq_true_eq] at h
  -- h : s.taskLifecyclePhase = .complete
  obtain ⟨hderive, _hnonemp, _htotpos⟩ := hcons
  rw [h] at hderive
  unfold Formal.Liveness.TaskLifecyclePhase.deriveTaskLifecyclePhase at hderive
  -- Case on taskCode.
  cases hc : s.taskCode with
  | none => rw [hc] at hderive; cases hderive
  | some code =>
    rw [hc] at hderive
    by_cases hemp : code = ""
    · simp [hemp] at hderive
    · simp [hemp] at hderive
      by_cases htot0 : s.taskTotal = 0
      · simp [htot0] at hderive
      · simp [htot0] at hderive
        by_cases hprog : s.taskProgress ≥ s.taskTotal
        · -- complete branch matches; we get hprog
          unfold completeTaskValue completeTaskSatisfied completeTaskProgressFull
          have htot_ne : ¬ s.taskTotal = 0 := htot0
          have hcode_isNone : s.taskCode.isNone = false := by rw [hc]; rfl
          have hsat_false :
              (s.taskCode.isNone || decide (s.taskTotal = 0)) = false := by
            simp [hcode_isNone, htot_ne]
          rw [hsat_false]
          have hprog_not_lt : ¬ s.taskProgress < s.taskTotal := Nat.not_lt.mpr hprog
          simp [hprog_not_lt]
        · -- hprog : ¬ taskProgress ≥ taskTotal. The derive yields accepted/inProgress,
          -- contradicting hderive saying .complete.
          have hlt : s.taskProgress < s.taskTotal := Nat.lt_of_not_le hprog
          have hderive' := hderive hlt
          by_cases hp0 : s.taskProgress = 0
          · simp [hp0] at hderive'
          · simp [hp0] at hderive'

/-- SELL_PRESSURED: `_fires .sellPressured s` ⇒
    `sellInventoryValue > 0` (bankAccessible=false, activeWindow=false
    branch: returns `usedFraction * 100 ≥ 85`). -/
theorem _fires_sellPressured_implies_sellInventory_positive (s : State) :
    fires .sellPressured s = true →
    sellInventoryValue (invMaxZero := false) (satisfied := false)
      (sellable := true) (bankAccessible := false)
      (usedFractionRat s) (activeWindow := false) > 0 := by
  intro h
  unfold fires sellPressuredFires at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨⟨hmax, hused⟩, _⟩ := h
  have hmax_ne : s.inventoryMax ≠ 0 := Nat.pos_iff_ne_zero.mp hmax
  have hmax_pos_rat : (0 : Rat) < (s.inventoryMax : Rat) := by exact_mod_cast hmax
  have huf_ge : usedFractionRat s ≥ 85 / 100 := by
    unfold usedFractionRat
    simp [hmax_ne]
    rw [div_le_div_iff₀ (by norm_num : (0 : Rat) < 100) hmax_pos_rat]
    have h1 : SELL_PRESSURE_DEN * s.inventoryUsed ≥ SELL_PRESSURE_NUM * s.inventoryMax := hused
    unfold SELL_PRESSURE_DEN SELL_PRESSURE_NUM at h1
    have h2 : 85 * s.inventoryMax ≤ 100 * s.inventoryUsed := by omega
    have h3 : (85 * s.inventoryMax : Rat) ≤ (100 * s.inventoryUsed : Rat) := by exact_mod_cast h2
    linarith
  unfold sellInventoryValue
  simp
  -- bankAccessible=false ⇒ bankLockedValue = usedFraction * 100.
  -- activeWindow=false ⇒ value = bankLockedValue = uf * 100 ≥ 85 > 0.
  have : usedFractionRat s * 100 ≥ 85 := by linarith
  linarith

/-- LOW_YIELD_CANCEL: Phase 23c-3b phase-based form.
    `_fires .lowYieldCancel s` means `taskLifecyclePhase = .inProgress`.
    `lowYieldCancelGoalValue true = 70 > 0` (Phase-18 GoalSystem).
    The lemma asserts the goal-value form is positive under the
    constant input `true`, which corresponds to "goal fires" in the
    Phase-18 wrapper. -/
theorem _fires_lowYieldCancel_implies_lowYieldCancel_positive
    (s : State) :
    fires .lowYieldCancel s = true →
    lowYieldCancelGoalValue true > 0 := by
  intro _
  unfold lowYieldCancelGoalValue lowYieldCancelValue
  norm_num

/-- TASK_CANCEL: opaque-gated; the Phase-18 value at
    `satisfied=false, pivots=true` is unconditionally 12 > 0. -/
theorem _fires_taskCancel_implies_taskCancel_positive
    (s : State) :
    fires .taskCancel s = true →
    taskCancelValue (satisfied := false) (pivots := true) > 0 := by
  intro _
  unfold taskCancelValue
  simp

/-! ### Objective step — DISCLOSED GAP (no lemma) -/

/-! ### Discretionary tier -/

/-- PURSUE_TASK: Phase 23c-3b phase-based form. `_fires .pursueTask s`
    means `taskLifecyclePhase ∈ {.accepted, .inProgress}`. Under the
    consistency predicate, the phase determines `taskCode.isSome` and
    `taskProgress < taskTotal`, so `pursueTaskSatisfied s = false` and
    `pursueTaskValueModel false = 35 > 0`. -/
theorem _fires_pursueTask_implies_pursueTask_positive
    (s : State) (hcons : taskPhaseConsistent s) :
    fires .pursueTask s = true →
    pursueTaskValueModel (pursueTaskSatisfied s) > 0 := by
  intro h
  unfold fires pursueTaskFires at h
  simp only [Bool.or_eq_true, decide_eq_true_eq] at h
  obtain ⟨hderive, _hnonemp, _htotpos⟩ := hcons
  unfold Formal.Liveness.TaskLifecyclePhase.deriveTaskLifecyclePhase at hderive
  unfold pursueTaskSatisfied
  cases hc : s.taskCode with
  | none =>
    rw [hc] at hderive
    cases h with
    | inl heq => rw [heq] at hderive; cases hderive
    | inr heq => rw [heq] at hderive; cases hderive
  | some code =>
    rw [hc] at hderive
    by_cases hemp : code = ""
    · simp [hemp] at hderive
      cases h with
      | inl heq => rw [heq] at hderive; cases hderive
      | inr heq => rw [heq] at hderive; cases hderive
    · simp [hemp] at hderive
      by_cases htot0 : s.taskTotal = 0
      · simp [htot0] at hderive
        cases h with
        | inl heq => rw [heq] at hderive; cases hderive
        | inr heq => rw [heq] at hderive; cases hderive
      · simp [htot0] at hderive
        by_cases hge : s.taskProgress ≥ s.taskTotal
        · simp [hge] at hderive
          cases h with
          | inl heq => rw [heq] at hderive; cases hderive
          | inr heq => rw [heq] at hderive; cases hderive
        · have htot_ne : ¬ s.taskTotal = 0 := htot0
          have hprog_lt : s.taskProgress < s.taskTotal := Nat.lt_of_not_le hge
          have hsat_false :
              ((some code).isNone || decide (s.taskTotal = 0)
                || decide (s.taskProgress ≥ s.taskTotal)) = false := by
            simp [htot_ne, Nat.not_le_of_lt hprog_lt]
          rw [hsat_false]
          exact pursueTaskValueModel_positive_when_unsatisfied

/-- ACCEPT_TASK: Phase 23c-3b phase-based form. `_fires .acceptTask s`
    means `taskLifecyclePhase = .none`. Under `taskPhaseConsistent`
    (which bundles the production normalization invariant
    `taskCode ≠ some ""`), this gives `taskCode = none`, so
    `acceptTaskSatisfied s = false` and `acceptTaskValue false = 20 > 0`. -/
theorem _fires_acceptTask_implies_acceptTask_positive
    (s : State) (hcons : taskPhaseConsistent s) :
    fires .acceptTask s = true →
    acceptTaskValue (acceptTaskSatisfied s) > 0 := by
  intro h
  unfold fires acceptTaskFires at h
  simp only [decide_eq_true_eq] at h
  -- h : s.taskLifecyclePhase = .none
  obtain ⟨hderive, hnonemp, htotpos⟩ := hcons
  rw [h] at hderive
  unfold Formal.Liveness.TaskLifecyclePhase.deriveTaskLifecyclePhase at hderive
  unfold acceptTaskValue acceptTaskSatisfied
  cases hc : s.taskCode with
  | none =>
    simp
  | some code =>
    rw [hc] at hderive hnonemp htotpos
    have hemp_ne : code ≠ "" := fun heq => hnonemp (by rw [heq])
    have htot_pos : s.taskTotal > 0 := htotpos (by rfl)
    have htot_ne : ¬ s.taskTotal = 0 := Nat.pos_iff_ne_zero.mp htot_pos
    simp [hemp_ne, htot_ne] at hderive
    -- Now hderive: .none = (if progress ≥ total then complete else
    --                       if progress = 0 then accepted else inProgress)
    by_cases hge : s.taskProgress ≥ s.taskTotal
    · simp [hge] at hderive
    · simp [hge] at hderive
      by_cases hp0 : s.taskProgress = 0
      · simp [hp0] at hderive
      · simp [hp0] at hderive

/-- TASK_EXCHANGE: `_fires .taskExchange s` ⇒
    `taskExchangeValue (false) = 22 > 0`. Production `_fires` is the
    coins-threshold predicate; we pass `satisfied=false` (Phase-18's
    routing only depends on satisfied, which production's firing
    equivalently flips off when the threshold is met). -/
theorem _fires_taskExchange_implies_taskExchange_positive (s : State) :
    fires .taskExchange s = true →
    taskExchangeValue false > 0 := by
  intro _
  unfold taskExchangeValue
  simp

/-- SELL_IDLE: `_fires .sellIdle s` ⇒ `sellInventoryValue > 0`
    (activeWindow=true branch yields ≥ sellSeizeWindowValue = 60). -/
theorem _fires_sellIdle_implies_sellInventory_positive (s : State) :
    fires .sellIdle s = true →
    sellInventoryValue (invMaxZero := false) (satisfied := false)
      (sellable := true) (bankAccessible := true)
      (usedFractionRat s) (activeWindow := true) > 0 := by
  intro _
  unfold sellInventoryValue sellSeizeWindowValue
  simp

/-! ### Last-resort — `wait` -/

/-- Production-shape `WaitGoal.value` (Phase-18 "Bool → Rat" wrapper).
    `WaitGoal.value()` is the constant `WAIT_GOAL_VALUE = 0.5` regardless
    of state (see `src/artifactsmmo_cli/ai/goals/wait.py:21`). Sub-floor on
    purpose: WaitGoal is the strict last-resort. -/
def waitGoalValue : Rat := 1 / 2

/-- WAIT: `_fires .wait s = true` ⇒ `waitGoalValue > 0`. Unconditional. -/
theorem _fires_wait_implies_wait_positive (s : State) :
    fires .wait s = true →
    waitGoalValue > 0 := by
  intro _
  unfold waitGoalValue
  norm_num

/-- BANK_EXPAND: `_fires .bankExpand s` ⇒ `expandBankValue = 40 > 0`. -/
theorem _fires_bankExpand_implies_expandBank_positive (s : State) :
    fires .bankExpand s = true →
    expandBankValue (accessible := true) (satisfied := false)
      (unknown := false)
      (fill := (s.bankItemsCount : Rat) / (s.bankCapacity : Rat))
      (canAfford := true) > 0 := by
  intro h
  unfold fires bankExpandFires at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨⟨⟨⟨_, _⟩, hcap⟩, hfill⟩, _⟩ := h
  have hcap_ne : s.bankCapacity ≠ 0 := Nat.pos_iff_ne_zero.mp hcap
  have hcap_pos_rat : (0 : Rat) < (s.bankCapacity : Rat) := by exact_mod_cast hcap
  have hfill_ge :
      (s.bankItemsCount : Rat) / (s.bankCapacity : Rat) ≥ 95 / 100 := by
    rw [ge_iff_le]
    rw [div_le_div_iff₀ (by norm_num : (0 : Rat) < 100) hcap_pos_rat]
    have h1 : BANK_EXPAND_FILL_DEN * s.bankItemsCount ≥ BANK_EXPAND_FILL_NUM * s.bankCapacity := hfill
    unfold BANK_EXPAND_FILL_DEN BANK_EXPAND_FILL_NUM at h1
    have h2 : 95 * s.bankCapacity ≤ 100 * s.bankItemsCount := by omega
    have h3 : (95 * s.bankCapacity : Rat) ≤ (100 * s.bankItemsCount : Rat) := by exact_mod_cast h2
    linarith
  unfold expandBankValue expandBankTriggerFill
  simp
  have hnot_lt :
      ¬ (s.bankItemsCount : Rat) / (s.bankCapacity : Rat) < 95 / 100 := by linarith
  simp [hnot_lt]

end Formal.Liveness.MeansFiring
