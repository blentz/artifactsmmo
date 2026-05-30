/-
Phase 10 — Goal value-lattice contracts for previously untouched Goal
subclasses (recon Area A).

Each modelled goal exposes a `value : State → Float` returning urgency. The
arbiter uses the value to rank candidate goals, so the value function must
respect documented invariants:
  (a) satisfied ⇒ value = 0
  (b) value is bounded
  (c) pressure/state-dependent tiers strictly order
  (d) the firing/satisfaction predicate is well-defined and reachable.

Targets (all NOT-A-BUG — verdicts pinned as regression contracts):
* `DepositInventoryGoal` — linear ramp from used/max=0.5 → 1.0 onto
  [0, _MAX_VALUE=80]. Below ramp ⇒ 0. Satisfied ⇒ 0.
* `DiscardOverstockGoal` — strict 3-tier ladder by inventory pressure:
  base 40 < high 55 < critical 85; thresholds 0.85 / 0.95. Satisfied ⇒ 0.
* `UnlockBankGoal` — bank_locked=False ⇒ 0; xp advanced ⇒ 0;
  inventory ≥ 0.85 with sellable ⇒ defer to 30; otherwise 90.
* `ReachUnlockLevelGoal` — satisfied (level ≥ target) ⇒ 0; gap > 5 ⇒ 0;
  active fires at PRIORITY_WHEN_BLOCKER_ACTIVE = 85.
* `PursueTaskGoal` — empty task or task_total=0 ⇒ satisfied;
  progress ≥ total ⇒ satisfied; progress ≥ initial + batch ⇒ satisfied;
  otherwise fires at PRIORITY_WHEN_FIRING = 35.
* `TaskExchangeGoal` — satisfied iff total (inv+bank) coins < min_coins;
  fires at 22 otherwise.

We model `Float`-valued urgency as `Nat`-scaled to avoid Float in the
kernel. Constants match the Python source: 80, 40, 55, 85, 90, 30, 85,
35, 22.
-/

namespace Formal.Phase10GoalLattices

/-! ### DepositInventoryGoal -/

/-- Ramp start fraction: below this, value = 0. Modeled as numerator/100. -/
def rampStartNum : Nat := 50
def rampStartDen : Nat := 100
def depositMaxValue : Nat := 80

/-- Deposit goal value, scaled to integer arithmetic to avoid Float.
Input: `used` and `cap` (both Nat). Returns a Nat ≤ depositMaxValue.
The Python formula is:
  if used_frac < 0.5: 0
  else: (used_frac - 0.5) / 0.5 * 80 = (used*200/cap - 100) * 80 / 100
We model it discretely: scaled value = (2*used*depositMaxValue - cap*depositMaxValue) / cap
clamped to [0, depositMaxValue]. -/
def depositValue (used cap : Nat) (satisfied : Bool) : Nat :=
  if satisfied then 0
  else if cap = 0 then 0
  else if 2 * used < cap then 0      -- used/cap < 0.5
  else
    let raw := (2 * used * depositMaxValue - cap * depositMaxValue) / cap
    if raw > depositMaxValue then depositMaxValue else raw

theorem deposit_satisfied_zero (used cap : Nat) :
    depositValue used cap true = 0 := by
  unfold depositValue; simp

theorem deposit_zero_cap_zero (used : Nat) :
    depositValue used 0 false = 0 := by
  unfold depositValue; simp

theorem deposit_below_ramp_zero (used cap : Nat) (h : 2 * used < cap) :
    depositValue used cap false = 0 := by
  unfold depositValue
  have hcap : cap ≠ 0 := by
    intro hz
    rw [hz] at h
    exact Nat.not_lt_zero _ h
  simp [h, hcap]

theorem deposit_bounded (used cap : Nat) (sat : Bool) :
    depositValue used cap sat ≤ depositMaxValue := by
  unfold depositValue
  split
  · exact Nat.zero_le _
  split
  · exact Nat.zero_le _
  split
  · exact Nat.zero_le _
  · -- raw branch with a let
    by_cases hraw :
      ((2 * used * depositMaxValue - cap * depositMaxValue) / cap) > depositMaxValue
    · simp [hraw]
    · simp [hraw]
      exact Nat.le_of_not_lt hraw

/-- Witness: at used=cap (100% full), the formula yields depositMaxValue=80
(via the clamp branch — raw = (2cap·80 - cap·80)/cap = 80). -/
theorem deposit_full_value : depositValue 100 100 false = 80 := by decide

/-- Witness: at used=50 (50% full, the ramp start), raw = (100·80 - 100·80)/100 = 0. -/
theorem deposit_ramp_start_value : depositValue 50 100 false = 0 := by decide

/-- Witness: at used=75 (75% full), value should be 40 (halfway through ramp). -/
theorem deposit_midramp_value : depositValue 75 100 false = 40 := by decide

/-! ### DiscardOverstockGoal value lattice (3-tier) -/

def overstockBase : Nat := 40
def overstockHigh : Nat := 55
def overstockCritical : Nat := 85

/-- Critical threshold numerator (0.95 = 95/100). -/
def critNum : Nat := 95
def highNum : Nat := 85
def pressureDen : Nat := 100

/-- DiscardOverstockGoal.value. Pressure = used/cap. -/
def overstockValue (used cap : Nat) (satisfied : Bool) : Nat :=
  if satisfied then 0
  else if cap = 0 then overstockBase
  else if pressureDen * used ≥ critNum * cap then overstockCritical
  else if pressureDen * used ≥ highNum * cap then overstockHigh
  else overstockBase

theorem overstock_satisfied_zero (used cap : Nat) :
    overstockValue used cap true = 0 := by
  unfold overstockValue; simp

/-- The 3-tier ladder is strictly ordered. -/
theorem overstock_tier_order :
    overstockBase < overstockHigh ∧ overstockHigh < overstockCritical := by
  constructor <;> decide

/-- Critical tier dominates high tier. -/
theorem overstock_critical_at_threshold :
    overstockValue 95 100 false = overstockCritical := by decide

/-- High tier (85% pressure) returns overstockHigh, not critical. -/
theorem overstock_high_at_threshold :
    overstockValue 85 100 false = overstockHigh := by decide

/-- Below high threshold returns base. -/
theorem overstock_below_high :
    overstockValue 50 100 false = overstockBase := by decide

theorem overstock_bounded (used cap : Nat) (sat : Bool) :
    overstockValue used cap sat ≤ overstockCritical := by
  unfold overstockValue
  split
  · decide
  split
  · decide
  split
  · exact Nat.le_refl _
  split
  · decide
  · decide

/-! ### UnlockBankGoal -/

def unlockBankPriority : Nat := 90
def unlockBankDeferToSell : Nat := 30
def unlockBankPressureNum : Nat := 85   -- 0.85 inventory pressure
def unlockBankPressureDen : Nat := 100

/-- Inputs:
  bankLocked — flag
  xpAdvanced — state.xp > initial_xp (already grinded)
  targetUnreachable — over-level monster
  used cap — inventory pressure
  hasSellable — any NPC buys any held item

Returns 0 if not locked, xp advanced, or target unreachable; 30 if
sellable + pressure ≥ 0.85; 90 otherwise. -/
def unlockBankValue
    (bankLocked xpAdvanced targetUnreachable hasSellable : Bool)
    (used cap : Nat) : Nat :=
  if !bankLocked then 0
  else if xpAdvanced then 0
  else if targetUnreachable then 0
  else if cap > 0 ∧ unlockBankPressureDen * used ≥ unlockBankPressureNum * cap ∧ hasSellable then
    unlockBankDeferToSell
  else unlockBankPriority

theorem unlockBank_not_locked_zero (xpA tu hs : Bool) (u c : Nat) :
    unlockBankValue false xpA tu hs u c = 0 := by
  unfold unlockBankValue; simp

theorem unlockBank_xp_advanced_zero (tu hs : Bool) (u c : Nat) :
    unlockBankValue true true tu hs u c = 0 := by
  unfold unlockBankValue; simp

theorem unlockBank_unreachable_zero (hs : Bool) (u c : Nat) :
    unlockBankValue true false true hs u c = 0 := by
  unfold unlockBankValue; simp

theorem unlockBank_high_pressure_sellable_defers :
    unlockBankValue true false false true 90 100 = unlockBankDeferToSell := by
  decide

theorem unlockBank_low_pressure_fires :
    unlockBankValue true false false true 50 100 = unlockBankPriority := by
  decide

theorem unlockBank_no_sellable_fires_under_pressure :
    unlockBankValue true false false false 95 100 = unlockBankPriority := by
  decide

theorem unlockBank_bounded
    (bL xpA tu hs : Bool) (u c : Nat) :
    unlockBankValue bL xpA tu hs u c ≤ unlockBankPriority := by
  unfold unlockBankValue
  split
  · decide
  split
  · decide
  split
  · decide
  split
  · decide
  · exact Nat.le_refl _

/-! ### ReachUnlockLevelGoal -/

def reachUnlockPriority : Nat := 85
def maxAchievableGap : Nat := 5

/-- value: 0 if satisfied (level ≥ target), 0 if target ≤ 0, 0 if gap > 5,
otherwise PRIORITY_WHEN_BLOCKER_ACTIVE (85). -/
def reachUnlockValue (level target : Nat) : Nat :=
  if level ≥ target then 0
  else if target = 0 then 0
  else if target - level > maxAchievableGap then 0
  else reachUnlockPriority

theorem reachUnlock_satisfied_zero (level target : Nat) (h : level ≥ target) :
    reachUnlockValue level target = 0 := by
  unfold reachUnlockValue; simp [h]

theorem reachUnlock_target_zero (level : Nat) :
    reachUnlockValue level 0 = 0 := by
  unfold reachUnlockValue
  simp [show level ≥ 0 from Nat.zero_le _]

theorem reachUnlock_gap_huge_zero :
    reachUnlockValue 2 45 = 0 := by decide

theorem reachUnlock_active_fires :
    reachUnlockValue 8 10 = reachUnlockPriority := by decide

theorem reachUnlock_at_boundary_fires :
    reachUnlockValue 5 10 = reachUnlockPriority := by decide

theorem reachUnlock_just_over_gap_zero :
    reachUnlockValue 4 10 = 0 := by decide

theorem reachUnlock_bounded (level target : Nat) :
    reachUnlockValue level target ≤ reachUnlockPriority := by
  unfold reachUnlockValue
  split
  · decide
  split
  · decide
  split
  · decide
  · exact Nat.le_refl _

/-! ### PursueTaskGoal -/

def pursueTaskPriority : Nat := 35

/-- The 3-pole is_satisfied for PursueTaskGoal:
  (a) no task / task_total = 0  ⇒ satisfied
  (b) progress ≥ total ⇒ satisfied
  (c) progress ≥ initial + batch ⇒ satisfied
  Models the Python disjunction. -/
def pursueTaskSatisfied
    (hasTask : Bool) (progress total initial batch : Nat) : Bool :=
  if !hasTask then true
  else if total = 0 then true
  else if progress ≥ total then true
  else if progress ≥ initial + batch then true
  else false

def pursueTaskValue
    (hasTask : Bool) (progress total initial batch : Nat) : Nat :=
  if pursueTaskSatisfied hasTask progress total initial batch then 0
  else pursueTaskPriority

theorem pursueTask_no_task_zero (p t i b : Nat) :
    pursueTaskValue false p t i b = 0 := by
  unfold pursueTaskValue pursueTaskSatisfied; simp

theorem pursueTask_total_zero_zero (p i b : Nat) :
    pursueTaskValue true p 0 i b = 0 := by
  unfold pursueTaskValue pursueTaskSatisfied; simp

theorem pursueTask_done_zero (p t i b : Nat) (h : p ≥ t) (ht : t > 0) :
    pursueTaskValue true p t i b = 0 := by
  unfold pursueTaskValue pursueTaskSatisfied
  simp [Nat.ne_of_gt ht, h]

theorem pursueTask_batch_done_zero
    (p t i b : Nat) (h : p ≥ i + b) (ht : t > 0) (hpt : p < t) :
    pursueTaskValue true p t i b = 0 := by
  unfold pursueTaskValue pursueTaskSatisfied
  simp [Nat.ne_of_gt ht, Nat.not_le_of_lt hpt, h]

theorem pursueTask_fires :
    pursueTaskValue true 5 10 5 3 = pursueTaskPriority := by decide

theorem pursueTask_bounded
    (hT : Bool) (p t i b : Nat) :
    pursueTaskValue hT p t i b ≤ pursueTaskPriority := by
  unfold pursueTaskValue
  split
  · decide
  · exact Nat.le_refl _

/-! ### TaskExchangeGoal -/

def taskExchangePriority : Nat := 22

/-- is_satisfied: inv_coins + bank_coins < min_coins. -/
def taskExchangeSatisfied (invCoins bankCoins minCoins : Nat) : Bool :=
  invCoins + bankCoins < minCoins

def taskExchangeValue (invCoins bankCoins minCoins : Nat) : Nat :=
  if taskExchangeSatisfied invCoins bankCoins minCoins then 0
  else taskExchangePriority

theorem taskExchange_below_min_zero :
    taskExchangeValue 0 0 3 = 0 := by decide

theorem taskExchange_at_min_fires :
    taskExchangeValue 3 0 3 = taskExchangePriority := by decide

theorem taskExchange_bank_only_fires :
    taskExchangeValue 0 5 3 = taskExchangePriority := by decide

theorem taskExchange_split_fires :
    taskExchangeValue 1 2 3 = taskExchangePriority := by decide

theorem taskExchange_bounded (inv bank min : Nat) :
    taskExchangeValue inv bank min ≤ taskExchangePriority := by
  unfold taskExchangeValue
  split
  · decide
  · exact Nat.le_refl _

/-- Anti-witness: pre-Phase-10 concern was that bank-only coins fire the
goal but the planner can't drain them via TaskExchange (only inventory
is consumed). RESOLUTION (NOT-A-BUG): player.py:857 plumbs a
`WithdrawItemAction(code=TASKS_COIN_CODE, quantity=1, ...)` so the planner
can compose Withdraw → TaskExchange chains that DO move bank coins through
inventory and drop the total below min, satisfying the goal. The witness
below pins that the goal can be satisfied by reducing both pools. -/
theorem taskExchange_reachable_via_drain
    (initInv initBank minC : Nat)
    (drainInv drainBank : Nat)
    (h : (initInv + initBank) - (drainInv + drainBank) < minC)
    (hInv : drainInv ≤ initInv) (hBank : drainBank ≤ initBank) :
    taskExchangeValue (initInv - drainInv) (initBank - drainBank) minC = 0 := by
  unfold taskExchangeValue taskExchangeSatisfied
  have key : (initInv - drainInv) + (initBank - drainBank) < minC := by
    have e1 : initInv - drainInv + (initBank - drainBank)
            = (initInv + initBank) - (drainInv + drainBank) := by
      omega
    rw [e1]; exact h
  simp [key]

end Formal.Phase10GoalLattices
