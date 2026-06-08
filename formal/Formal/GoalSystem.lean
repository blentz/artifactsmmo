-- @concept: core, planner @property: safety
/-
Phase-18: Value-range theorems for the 14 Goals in `src/artifactsmmo_cli/ai/goals/`
that were not already covered by Phase-1/16/17 (PriorityBand, GoalValueBands,
LowYieldCancel, GrindCharacterXP).

For each goal we model:
  * `<goal>Value`  — a pure Rat function that mirrors `<Goal>.value(...)` from
    Python (1:1 on the arithmetic; opaque state lookups are abstracted as Bool /
    Rat parameters at the model boundary).
  * `<goal>_value_in_range` — the closed interval the value can occupy.
  * `<goal>_cold_returns_zero` — the "inactive" branch returns exactly 0.

Goals modeled in this file:

CONSTANT-VALUE (value ∈ {0, K}):
  * AcceptTask          {0, 20}
  * ClaimPending        {0, 25}
  * TaskExchange        {0, 22}
  * TaskCancel          {0, 12}
  * LevelSkill          {0, 55}
  * ExpandBank          {0, 40}
  * CompleteTask        {0, 90}
  * ReachUnlockLevel    {0, 85}
  * LowYieldCancel      {0, 70}    (decision-only — boundary itself lives in
                                    `Formal.LowYieldCancel`; here we pin the value)

BRANCHING-CONSTANT:
  * UnlockBank          {0, 30, 90}
  * DiscardOverstock    {0, 40, 55, 85}
  * UpgradeEquipment    {0, 35, 51}

COMPUTED (Rat-modeled fractions, bit-exact under `fractions.Fraction`):
  * RestoreHP           [0, 110]
  * DepositInventory    [0, 80]
  * SellInventory       [0, 100]

Disclosed gaps (HONEST DECLARATION — see CLAUDE.md / Phase-1 lesson):

  * Goals that consult game_data / LearningStore / state in ways that cannot be
    expressed as a closed-form Rat expression (e.g. UnlockBank's
    `_target_monster_is_unreachable`, DiscardOverstock's `overstocked_items`,
    UpgradeEquipment's `_find_upgrade`, LowYieldCancel's `low_yield_cancel_fires`)
    are modeled with the OPAQUE branch outcomes as Bool/decision inputs. The
    arithmetic on each branch is modeled exactly; the routing-to-branch
    *decision* is treated as a parameter (the Python tests exercise the routing
    against real production helpers).
  * RestoreHP's `hp_percent` is modeled as a `Rat` in [0,1]; Python returns
    `float`, so the bridge lifts to `Fraction(state.hp, state.max_hp)` for
    exact comparison.
  * DepositInventory and SellInventory likewise lift `inventory_used /
    inventory_max` to `Fraction` at the bridge.

Lean core only — no mathlib. Linear-arith via `grind`.
-/

namespace Formal.GoalSystem

/-! ## Section A. Constant-value goals (value ∈ {0, K}). -/

/-! ### AcceptTaskGoal — {0, 20}. -/

def acceptTaskValue (satisfied : Bool) : Rat :=
  if satisfied then 0 else 20

theorem acceptTask_value_in_range (s : Bool) :
    0 ≤ acceptTaskValue s ∧ acceptTaskValue s ≤ 20 := by
  unfold acceptTaskValue; cases s <;> grind

theorem acceptTask_cold_returns_zero :
    acceptTaskValue true = 0 := by
  unfold acceptTaskValue; decide

/-! ### ClaimPendingGoal — {0, 25}. -/

def claimPendingValue (satisfied : Bool) : Rat :=
  if satisfied then 0 else 25

theorem claimPending_value_in_range (s : Bool) :
    0 ≤ claimPendingValue s ∧ claimPendingValue s ≤ 25 := by
  unfold claimPendingValue; cases s <;> grind

theorem claimPending_cold_returns_zero :
    claimPendingValue true = 0 := by
  unfold claimPendingValue; decide

/-! ### TaskExchangeGoal — {0, 22}. -/

def taskExchangeValue (satisfied : Bool) : Rat :=
  if satisfied then 0 else 22

theorem taskExchange_value_in_range (s : Bool) :
    0 ≤ taskExchangeValue s ∧ taskExchangeValue s ≤ 22 := by
  unfold taskExchangeValue; cases s <;> grind

theorem taskExchange_cold_returns_zero :
    taskExchangeValue true = 0 := by
  unfold taskExchangeValue; decide

/-! ### TaskCancelGoal — {0, 12}. -/

def taskCancelValue (satisfied pivots : Bool) : Rat :=
  if satisfied then 0
  else if pivots then 12
  else 0

theorem taskCancel_value_in_range (s p : Bool) :
    0 ≤ taskCancelValue s p ∧ taskCancelValue s p ≤ 12 := by
  unfold taskCancelValue
  cases s <;> cases p <;> grind

theorem taskCancel_cold_satisfied_zero (p : Bool) :
    taskCancelValue true p = 0 := by
  unfold taskCancelValue; cases p <;> simp

theorem taskCancel_cold_no_pivot_zero :
    taskCancelValue false false = 0 := by
  unfold taskCancelValue; decide

/-! ### LevelSkillGoal — {0, 55}. -/

def maxSkillGap : Int := 5

def levelSkillValue (satisfied : Bool) (gap : Int) (hasCraftable : Bool) : Rat :=
  if satisfied then 0
  else if gap ≤ 0 ∨ gap > maxSkillGap then 0
  else if ¬ hasCraftable then 0
  else 55

theorem levelSkill_value_in_range
    (s : Bool) (gap : Int) (hc : Bool) :
    0 ≤ levelSkillValue s gap hc ∧ levelSkillValue s gap hc ≤ 55 := by
  unfold levelSkillValue
  grind

theorem levelSkill_cold_satisfied_zero (gap : Int) (hc : Bool) :
    levelSkillValue true gap hc = 0 := by
  unfold levelSkillValue; simp

theorem levelSkill_cold_gap_too_big_zero (s : Bool) (hc : Bool) :
    levelSkillValue s 100 hc = 0 := by
  unfold levelSkillValue maxSkillGap
  cases s <;> grind

theorem levelSkill_cold_no_craftable_zero (gap : Int)
    (h1 : 1 ≤ gap) (h2 : gap ≤ maxSkillGap) :
    levelSkillValue false gap false = 0 := by
  unfold levelSkillValue
  have hgnz : ¬ gap ≤ 0 := by omega
  have hgnt : ¬ gap > maxSkillGap := by omega
  simp [hgnz, hgnt]

/-! ### ExpandBankGoal — {0, 40}. -/

def expandBankTriggerFill : Rat := 95 / 100

def expandBankValue
    (accessible : Bool) (satisfied : Bool) (unknown : Bool)
    (fill : Rat) (canAfford : Bool) : Rat :=
  if ¬ accessible then 0
  else if satisfied then 0
  else if unknown then 0
  else if fill < expandBankTriggerFill then 0
  else if ¬ canAfford then 0
  else 40

theorem expandBank_value_in_range
    (a s u : Bool) (fill : Rat) (c : Bool) :
    0 ≤ expandBankValue a s u fill c ∧ expandBankValue a s u fill c ≤ 40 := by
  unfold expandBankValue
  grind

theorem expandBank_cold_not_accessible_zero
    (s u : Bool) (fill : Rat) (c : Bool) :
    expandBankValue false s u fill c = 0 := by
  unfold expandBankValue; simp

theorem expandBank_cold_satisfied_zero
    (u : Bool) (fill : Rat) (c : Bool) :
    expandBankValue true true u fill c = 0 := by
  unfold expandBankValue; simp

/-! ### CompleteTaskGoal — {0, 90}. -/

def completeTaskValue (satisfied : Bool) (progressFull : Bool) : Rat :=
  if satisfied then 0
  else if ¬ progressFull then 0
  else 90

theorem completeTask_value_in_range (s pf : Bool) :
    0 ≤ completeTaskValue s pf ∧ completeTaskValue s pf ≤ 90 := by
  unfold completeTaskValue
  grind

theorem completeTask_cold_satisfied_zero (pf : Bool) :
    completeTaskValue true pf = 0 := by
  unfold completeTaskValue; simp

theorem completeTask_cold_not_full_zero :
    completeTaskValue false false = 0 := by
  unfold completeTaskValue; simp

/-! ### ReachUnlockLevelGoal — {0, 85}. -/

def maxAchievableGap : Int := 5

def reachUnlockLevelValue
    (satisfied : Bool) (targetLevel : Int) (gap : Int) : Rat :=
  if satisfied then 0
  else if targetLevel ≤ 0 then 0
  else if gap > maxAchievableGap then 0
  else 85

theorem reachUnlockLevel_value_in_range
    (s : Bool) (tl gap : Int) :
    0 ≤ reachUnlockLevelValue s tl gap ∧ reachUnlockLevelValue s tl gap ≤ 85 := by
  unfold reachUnlockLevelValue
  grind

theorem reachUnlockLevel_cold_satisfied_zero (tl gap : Int) :
    reachUnlockLevelValue true tl gap = 0 := by
  unfold reachUnlockLevelValue; simp

theorem reachUnlockLevel_cold_zero_target (s : Bool) (gap : Int) :
    reachUnlockLevelValue s 0 gap = 0 := by
  unfold reachUnlockLevelValue
  cases s <;> simp

theorem reachUnlockLevel_cold_gap_too_big (s : Bool) (tl : Int) (h : 0 < tl) :
    reachUnlockLevelValue s tl 100 = 0 := by
  unfold reachUnlockLevelValue
  have htl : ¬ tl ≤ 0 := by omega
  have hg : (100 : Int) > maxAchievableGap := by unfold maxAchievableGap; decide
  cases s <;> simp [htl, hg]

/-! ### LowYieldCancelGoal — {0, 70}. -/

def lowYieldCancelValue : Rat := 70

def lowYieldCancelGoalValue (fires : Bool) : Rat :=
  if fires then lowYieldCancelValue else 0

theorem lowYieldCancel_value_in_range (f : Bool) :
    0 ≤ lowYieldCancelGoalValue f ∧ lowYieldCancelGoalValue f ≤ 70 := by
  unfold lowYieldCancelGoalValue lowYieldCancelValue
  cases f <;> grind

theorem lowYieldCancel_cold_returns_zero :
    lowYieldCancelGoalValue false = 0 := by
  unfold lowYieldCancelGoalValue; simp

/-! ## Section B. Branching-constant goals. -/

/-! ### UnlockBankGoal — {0, 30, 90}. -/

def unlockBankDeferralFraction : Rat := 85 / 100

def unlockBankValue
    (bankLocked : Bool) (xpExceeded : Bool) (unreachable : Bool)
    (usedFraction : Rat) (hasSellable : Bool) : Rat :=
  if ¬ bankLocked ∨ xpExceeded then 0
  else if unreachable then 0
  else if usedFraction ≥ unlockBankDeferralFraction ∧ hasSellable then 30
  else 90

theorem unlockBank_value_in_range
    (bl xe u : Bool) (uf : Rat) (hs : Bool) :
    0 ≤ unlockBankValue bl xe u uf hs ∧ unlockBankValue bl xe u uf hs ≤ 90 := by
  unfold unlockBankValue
  grind

theorem unlockBank_cold_not_locked_zero
    (xe u : Bool) (uf : Rat) (hs : Bool) :
    unlockBankValue false xe u uf hs = 0 := by
  unfold unlockBankValue; simp

theorem unlockBank_cold_xp_exceeded_zero
    (bl u : Bool) (uf : Rat) (hs : Bool) :
    unlockBankValue bl true u uf hs = 0 := by
  unfold unlockBankValue; simp

theorem unlockBank_cold_unreachable_zero
    (uf : Rat) (hs : Bool) :
    unlockBankValue true false true uf hs = 0 := by
  unfold unlockBankValue; simp

/-! ### DiscardOverstockGoal — {0, 40, 55, 85}. -/

def discardOverstockCritical : Rat := 95 / 100
def discardOverstockHigh : Rat := 85 / 100

def discardOverstockValue (satisfied : Bool) (pressure : Rat) : Rat :=
  if satisfied then 0
  else if pressure ≥ discardOverstockCritical then 85
  else if pressure ≥ discardOverstockHigh then 55
  else 40

theorem discardOverstock_value_in_range (s : Bool) (p : Rat) :
    0 ≤ discardOverstockValue s p ∧ discardOverstockValue s p ≤ 85 := by
  unfold discardOverstockValue
  grind

theorem discardOverstock_cold_satisfied_zero (p : Rat) :
    discardOverstockValue true p = 0 := by
  unfold discardOverstockValue; simp

theorem discardOverstock_unsatisfied_at_least_40 (p : Rat) :
    discardOverstockValue false p ≥ 40 := by
  unfold discardOverstockValue
  grind

/-! ### UpgradeEquipmentGoal — {0, 35, 51}. -/

def upgradeEquipmentRelevantTool : Rat := 51
def upgradeEquipmentBase : Rat := 35

def upgradeEquipmentValue
    (hasUpgrade : Bool) (relevantTool : Bool) : Rat :=
  if ¬ hasUpgrade then 0
  else if relevantTool then upgradeEquipmentRelevantTool
  else upgradeEquipmentBase

theorem upgradeEquipment_value_in_range (hu rt : Bool) :
    0 ≤ upgradeEquipmentValue hu rt ∧ upgradeEquipmentValue hu rt ≤ 51 := by
  unfold upgradeEquipmentValue upgradeEquipmentRelevantTool upgradeEquipmentBase
  cases hu <;> cases rt <;> grind

theorem upgradeEquipment_cold_no_upgrade_zero (rt : Bool) :
    upgradeEquipmentValue false rt = 0 := by
  unfold upgradeEquipmentValue; simp

theorem upgradeEquipment_base_eq_35 :
    upgradeEquipmentValue true false = 35 := by
  unfold upgradeEquipmentValue upgradeEquipmentBase; simp

theorem upgradeEquipment_relevant_eq_51 :
    upgradeEquipmentValue true true = 51 := by
  unfold upgradeEquipmentValue upgradeEquipmentRelevantTool; simp

/-! ## Section C. Computed goals (Rat-modeled fractional inputs). -/

/-! ### RestoreHPGoal — value range [0, 110]. -/

def restoreHpCriticalFraction : Rat := 25 / 100
def restoreHpCriticalValue : Rat := 110

def restoreHpValue (hpPercent : Rat) : Rat :=
  if hpPercent < restoreHpCriticalFraction then restoreHpCriticalValue
  else (1 - hpPercent) * 100

theorem restoreHp_value_in_range (hp : Rat)
    (_h0 : 0 ≤ hp) (h1 : hp ≤ 1) :
    0 ≤ restoreHpValue hp ∧ restoreHpValue hp ≤ 110 := by
  unfold restoreHpValue restoreHpCriticalFraction restoreHpCriticalValue
  by_cases hc : hp < 25 / 100
  · simp [hc]; grind
  · simp [hc]; grind

theorem restoreHp_full_returns_zero :
    restoreHpValue 1 = 0 := by
  unfold restoreHpValue restoreHpCriticalFraction restoreHpCriticalValue
  grind

theorem restoreHp_critical_is_110 (hp : Rat)
    (h : hp < restoreHpCriticalFraction) :
    restoreHpValue hp = 110 := by
  unfold restoreHpValue restoreHpCriticalValue
  simp [h]

/-! ### DepositInventoryGoal — value range [0, 80]. -/

-- High watermark 0.85 (17/20) per spec 2026-06-07: deposit pressure only
-- appears near-full so the player uses most of the bag (raised from 1/2).
def depositRampStart : Rat := 17 / 20
def depositMaxValue : Rat := 80

def depositInventoryValue
    (accessible : Bool) (satisfied : Bool) (invMaxZero : Bool)
    (usedFraction : Rat) : Rat :=
  if ¬ accessible ∨ invMaxZero then 0
  else if satisfied then 0
  else if usedFraction < depositRampStart then 0
  else (usedFraction - depositRampStart) / (1 - depositRampStart) * depositMaxValue

theorem depositInventory_value_in_range
    (a s im : Bool) (uf : Rat) (_h0 : 0 ≤ uf) (h1 : uf ≤ 1) :
    0 ≤ depositInventoryValue a s im uf ∧ depositInventoryValue a s im uf ≤ 80 := by
  unfold depositInventoryValue depositRampStart depositMaxValue
  grind

theorem depositInventory_cold_inaccessible_zero
    (s im : Bool) (uf : Rat) :
    depositInventoryValue false s im uf = 0 := by
  unfold depositInventoryValue; simp

theorem depositInventory_cold_below_ramp_zero
    (a s im : Bool) :
    depositInventoryValue a s im 0 = 0 := by
  unfold depositInventoryValue depositRampStart
  cases a <;> cases s <;> cases im <;> grind

/-! ### SellInventoryGoal — value range [0, 100]. -/

def sellSeizeWindowValue : Rat := 60

def sellInventoryValue
    (invMaxZero : Bool) (satisfied : Bool) (sellable : Bool)
    (bankAccessible : Bool) (usedFraction : Rat) (activeWindow : Bool) : Rat :=
  if invMaxZero ∨ satisfied then 0
  else if ¬ sellable then 0
  else
    let bankLockedValue : Rat := if bankAccessible then 0 else usedFraction * 100
    if activeWindow then max bankLockedValue sellSeizeWindowValue
    else bankLockedValue

theorem sellInventory_value_in_range
    (im s sl ba : Bool) (uf : Rat) (aw : Bool)
    (h0 : 0 ≤ uf) (h1 : uf ≤ 1) :
    0 ≤ sellInventoryValue im s sl ba uf aw ∧
    sellInventoryValue im s sl ba uf aw ≤ 100 := by
  unfold sellInventoryValue sellSeizeWindowValue
  grind

theorem sellInventory_cold_satisfied_zero
    (im sl ba : Bool) (uf : Rat) (aw : Bool) :
    sellInventoryValue im true sl ba uf aw = 0 := by
  unfold sellInventoryValue; simp

theorem sellInventory_cold_inv_max_zero
    (s sl ba : Bool) (uf : Rat) (aw : Bool) :
    sellInventoryValue true s sl ba uf aw = 0 := by
  unfold sellInventoryValue; simp

theorem sellInventory_cold_not_sellable_zero
    (ba : Bool) (uf : Rat) (aw : Bool) :
    sellInventoryValue false false false ba uf aw = 0 := by
  unfold sellInventoryValue; simp

end Formal.GoalSystem
