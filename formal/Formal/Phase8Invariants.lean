/-
Phase 8 mixed batch: four targets from the recon shortlist.

* Target A — `RecycleAction.is_applicable` (REAL BUG, FIXED):
  The pre-fix precondition checked workshop + item-in-bag + recipe-known but
  not (i) the crafting-skill level required by the recipe nor (ii) the slot
  floor needed for the recovered materials. Probe (verified):
    inventory={dagger:1, pad:19} (used=20, free=0, cap=20),
    skill=1, recipe={ore:6} (recovered=3, net=+2):
      pre-fix is_applicable = True; apply produced used=22 > cap=20.
    skill=1 with stats.crafting_level=10:
      pre-fix is_applicable = True; server would HTTP 493.
  Post-fix: both probes refused. We model the slot-floor and skill-gate as
  a `chain_safe` instantiation of the existing template.

* Target B — `BuyBankExpansionAction.apply` (BLOCKED-FOR-DECISION):
  `ExpandBankGoal.is_satisfied` reads `len(bank_items) < capacity*0.9` where
  `capacity = game_data._bank_capacity`. `BuyBankExpansionAction.apply` does
  NOT modify `game_data._bank_capacity` (game_data is read-only at planning
  time) and does NOT modify `state.bank_items`. So no plan composed from
  the exposed action set ever flips the goal's `is_satisfied` from `False`
  to `True` — the goal is unreachable through projection. We prove a
  `bank_expansion_projection_gap` lemma stating exactly this.

* Target C — Task-sentinel cross-action invariant:
  `AcceptTaskAction.apply` sets `task_code = "__pending__"` and `task_total
  = 1`. `CompleteTaskAction.apply` sets `task_code = ""` and `task_total =
  0`. `TaskCancelAction.apply` sets `task_code = None` and `task_total =
  0`. Every consumer treats `not task_code` (Python boolean) as "no task."
  We model `task_code` as a 3-valued tag {Pending, Empty, None_, Real} and
  prove the cross-action invariant: after any of the three transitions,
  `(task_code == Empty ∨ task_code == None_) ↔ task_total = 0`. The Real
  case is the API-snapshot baseline (server-issued task code).

* Target D — `ClaimPendingGoal.value` priority (NOT-A-BUG):
  Phase 6 fixed `ClaimPendingItemAction.is_applicable` to require
  `inventory_free ≥ 1`. The goal's `value` returns 25 unconditionally on a
  non-empty `pending_items`. Concern: with a full bag, planner picks
  ClaimPending but cannot fire. RESOLUTION: the planner considers
  multi-step plans (Deposit → Claim) and StrategyArbiter falls through to
  the next top-plannable goal if no plan exists; gating `value` to 0 on
  full bag would suppress reachable Deposit→Claim chains. We prove the
  invariant `value > 0 ↔ pending_items ≠ []` (the literal current
  contract) and pin the post-Phase-6 chain_safe witness.

Lean core only — no mathlib. Imports the Phase-6 chain_safe template.
-/

import Formal.InventoryChainSafe

namespace Formal.Phase8Invariants

open Formal.InventoryChainSafe

/-! ### Target A — Recycle slot-floor + skill gate. -/

/-- Recycle projection: inventory model + skill table. We reuse the Phase-6
`Inv` and add a skill snapshot. -/
structure RecycleCtx where
  inv : Inv
  /-- Player's level in the recipe's crafting skill. -/
  skillLevel : Nat
  /-- Recipe's required crafting level (from `stats.crafting_level`). -/
  requiredLevel : Nat
  /-- True when game_data has stats and stats.crafting_skill is non-null. -/
  hasCraftingSkill : Bool
  /-- True when the player holds `≥ quantity` of the recycled code. -/
  itemInBag : Bool
  /-- True when game_data.crafting_recipe(code) is non-None. -/
  recipeKnown : Bool
  /-- Workshop tile resolved. -/
  hasWorkshop : Bool
  deriving Repr, DecidableEq

/-- Net slot delta on apply: `sum(recovered) - quantity`. We model this as
the net-positive case (when net ≤ 0 the slot floor is trivially satisfied).
-/
def recycleNetMint (ctx : RecycleCtx) (net : Nat) : Inv :=
  if net = 0 then ctx.inv else applyK ctx.inv net

/-- Post-fix RecycleAction.is_applicable, modeled as a single Bool. -/
def recycleIsApplicable (ctx : RecycleCtx) (net : Nat) : Bool :=
  ctx.hasWorkshop &&
  ctx.itemInBag &&
  ctx.recipeKnown &&
  ctx.hasCraftingSkill &&
  decide (ctx.requiredLevel ≤ ctx.skillLevel) &&
  (decide (net = 0) || isApplicableK ctx.inv net)

theorem recycle_is_applicable_imp_skill_ge (ctx : RecycleCtx) (net : Nat) :
    recycleIsApplicable ctx net = true → ctx.requiredLevel ≤ ctx.skillLevel := by
  intro h
  simp [recycleIsApplicable, Bool.and_eq_true] at h
  obtain ⟨⟨⟨⟨⟨_, _⟩, _⟩, _⟩, hskill⟩, _⟩ := h
  exact hskill

theorem recycle_is_applicable_imp_free_ge_net
    (ctx : RecycleCtx) (net : Nat) (hpos : 0 < net) :
    recycleIsApplicable ctx net = true → net ≤ ctx.inv.cap - ctx.inv.used := by
  intro h
  simp [recycleIsApplicable, Bool.and_eq_true, Bool.or_eq_true] at h
  obtain ⟨_, hor⟩ := h
  rcases hor with hzero | happ
  · omega
  · exact isApplicableK_imp_free_ge ctx.inv net happ

/-- Apply-safety: when net > 0, the post-mint inventory stays within cap. -/
theorem recycle_apply_inventory_safe
    (ctx : RecycleCtx) (net : Nat)
    (hwf : ctx.inv.used ≤ ctx.inv.cap)
    (hpos : 0 < net)
    (h : recycleIsApplicable ctx net = true) :
    (recycleNetMint ctx net).used ≤ ctx.inv.cap := by
  have := recycle_is_applicable_imp_free_ge_net ctx net hpos h
  have hne : net ≠ 0 := Nat.pos_iff_ne_zero.mp hpos
  simp [recycleNetMint, applyK, hne]; omega

/-- When net = 0 the inventory is unchanged, so well-formedness suffices. -/
theorem recycle_apply_inventory_safe_zero_net
    (ctx : RecycleCtx)
    (hwf : ctx.inv.used ≤ ctx.inv.cap) :
    (recycleNetMint ctx 0).used ≤ ctx.inv.cap := by
  unfold recycleNetMint
  split
  · exact hwf
  · contradiction

/-- Chain-safety: chained recycles whose summed positive nets stay in free
keep the inventory within cap. Schedules with `0` entries (net non-positive)
are no-ops; we use `applyKN` with only the positive entries. -/
theorem recycle_chain_safe (i : Inv) (nets : List Nat)
    (hwf : i.used ≤ i.cap) (h : nets.sum ≤ i.cap - i.used) :
    (applyKN i nets).used ≤ i.cap :=
  chain_safe_template i nets hwf h

/-- Boundary witness: net == free is accepted. -/
theorem recycle_boundary_witness :
    let ctx : RecycleCtx := {
      inv := { used := 18, cap := 20 },
      skillLevel := 10, requiredLevel := 10,
      hasCraftingSkill := true, itemInBag := true,
      recipeKnown := true, hasWorkshop := true
    }
    recycleIsApplicable ctx 2 = true := by decide

/-- Regression: full-bag positive-net is refused (was true pre-fix). Probe
inv={used:=20,cap:=20}, net:=2. -/
theorem recycle_regression_full_bag_net2_refused :
    let ctx : RecycleCtx := {
      inv := { used := 20, cap := 20 },
      skillLevel := 10, requiredLevel := 10,
      hasCraftingSkill := true, itemInBag := true,
      recipeKnown := true, hasWorkshop := true
    }
    recycleIsApplicable ctx 2 = false := by decide

/-- Regression: skill below requirement is refused (was true pre-fix when
the pre-fix had no skill gate at all). -/
theorem recycle_regression_skill_low_refused :
    let ctx : RecycleCtx := {
      inv := { used := 0, cap := 20 },
      skillLevel := 1, requiredLevel := 10,
      hasCraftingSkill := true, itemInBag := true,
      recipeKnown := true, hasWorkshop := true
    }
    recycleIsApplicable ctx 2 = false := by decide

/-- Regression: missing crafting skill metadata is refused. -/
theorem recycle_no_crafting_skill_refused :
    let ctx : RecycleCtx := {
      inv := { used := 0, cap := 20 },
      skillLevel := 50, requiredLevel := 0,
      hasCraftingSkill := false, itemInBag := true,
      recipeKnown := true, hasWorkshop := true
    }
    recycleIsApplicable ctx 0 = false := by decide

/-- Regression: missing workshop is refused. -/
theorem recycle_no_workshop_refused :
    let ctx : RecycleCtx := {
      inv := { used := 0, cap := 20 },
      skillLevel := 50, requiredLevel := 0,
      hasCraftingSkill := true, itemInBag := true,
      recipeKnown := true, hasWorkshop := false
    }
    recycleIsApplicable ctx 0 = false := by decide

/-! ### Target B — Bank expansion projection gap (BLOCKED-FOR-DECISION). -/

/-- The relevant projection for the goal. `bankItems` is the count of slots
filled, `capacity` is `game_data._bank_capacity`, fixed during planning. -/
structure BankProj where
  bankItems : Nat
  capacity : Nat
  gold : Nat
  expansionCost : Nat
  deriving Repr, DecidableEq

/-- `ExpandBankGoal.is_satisfied`, simplified: bank fill below 90% of
capacity. We use the integer inequality `10 * bankItems < 9 * capacity` as
a Nat-faithful proxy for `bankItems < 0.9 * capacity`. The capacity = 0
edge case is satisfied by definition (matches the Python). -/
def expandBankIsSatisfied (b : BankProj) : Bool :=
  decide (b.capacity = 0) || decide (10 * b.bankItems < 9 * b.capacity)

/-- The Python apply: subtracts `expansionCost` from `gold`. Does NOT
touch `bankItems` or `capacity`. -/
def buyBankExpansionApply (b : BankProj) : BankProj :=
  { b with gold := b.gold - b.expansionCost }

/-- The projection gap: any number of bank-expansion applies leave both
`bankItems` and `capacity` unchanged. -/
def buyBankExpansionApplyN : BankProj → Nat → BankProj
  | b, 0 => b
  | b, n + 1 => buyBankExpansionApplyN (buyBankExpansionApply b) n

theorem buyBankExpansion_preserves_bankItems (b : BankProj) (n : Nat) :
    (buyBankExpansionApplyN b n).bankItems = b.bankItems := by
  induction n generalizing b with
  | zero => rfl
  | succ m ih => simp [buyBankExpansionApplyN, buyBankExpansionApply, ih]

theorem buyBankExpansion_preserves_capacity (b : BankProj) (n : Nat) :
    (buyBankExpansionApplyN b n).capacity = b.capacity := by
  induction n generalizing b with
  | zero => rfl
  | succ m ih => simp [buyBankExpansionApplyN, buyBankExpansionApply, ih]

/-- **The projection gap.** If `expandBankIsSatisfied` is false initially,
no chain of bank-expansion applies makes it true. -/
theorem bank_expansion_projection_gap (b : BankProj) (n : Nat)
    (h : expandBankIsSatisfied b = false) :
    expandBankIsSatisfied (buyBankExpansionApplyN b n) = false := by
  simp [expandBankIsSatisfied, buyBankExpansion_preserves_bankItems,
        buyBankExpansion_preserves_capacity]
  simp [expandBankIsSatisfied] at h
  exact h

/-- Witness: a concrete unsatisfied state where the gap fires. cap=30,
items=30 (100% fill — the trigger condition), expansion mints gold. -/
theorem bank_expansion_gap_witness :
    let b : BankProj := { bankItems := 30, capacity := 30, gold := 1000, expansionCost := 100 }
    expandBankIsSatisfied b = false ∧
      expandBankIsSatisfied (buyBankExpansionApplyN b 5) = false := by
  refine ⟨by decide, ?_⟩
  apply bank_expansion_projection_gap
  decide

/-! ### Target C — Task sentinel cross-action invariant. -/

/-- The three task-code tags any consumer must handle. `Real` is the
server-issued, non-empty, non-sentinel task code. -/
inductive TaskCode
  | Real            -- "monsters", "items_x", etc.
  | Pending         -- "__pending__" (AcceptTask sentinel)
  | Empty           -- "" (CompleteTask sentinel)
  | None_           -- None (TaskCancel sentinel + initial)
  deriving Repr, DecidableEq

/-- The "no task" predicate: Python's `not task_code` evaluates True for
both `""` and `None`. `__pending__` is truthy. `Real` is truthy. -/
def noTask (tc : TaskCode) : Bool :=
  match tc with
  | TaskCode.Empty => true
  | TaskCode.None_ => true
  | TaskCode.Pending => false
  | TaskCode.Real => false

/-- The task projection. `progress`/`total` are the per-task counters. -/
structure TaskState where
  code : TaskCode
  total : Nat
  progress : Nat
  deriving Repr, DecidableEq

/-- AcceptTaskAction.apply: code → Pending, total → 1, progress → 0. -/
def acceptApply (_t : TaskState) : TaskState :=
  { code := TaskCode.Pending, total := 1, progress := 0 }

/-- CompleteTaskAction.apply: code → Empty, total → 0, progress → 0. -/
def completeApply (_t : TaskState) : TaskState :=
  { code := TaskCode.Empty, total := 0, progress := 0 }

/-- TaskCancelAction.apply: code → None_, total → 0, progress → 0. -/
def cancelApply (_t : TaskState) : TaskState :=
  { code := TaskCode.None_, total := 0, progress := 0 }

/-- AcceptTaskAction.is_applicable: `noTask AND total == 0`. -/
def acceptIsApplicable (t : TaskState) : Bool :=
  noTask t.code && decide (t.total = 0)

/-- The cross-action invariant: a `TaskState` is "consistent" iff
`noTask code ↔ total = 0`. -/
def consistent (t : TaskState) : Bool :=
  noTask t.code = decide (t.total = 0)

/-- All three transitions preserve `consistent`. -/
theorem accept_preserves_consistent (t : TaskState) :
    consistent (acceptApply t) = true := by
  simp [consistent, acceptApply, noTask]

theorem complete_preserves_consistent (t : TaskState) :
    consistent (completeApply t) = true := by
  simp [consistent, completeApply, noTask]

theorem cancel_preserves_consistent (t : TaskState) :
    consistent (cancelApply t) = true := by
  simp [consistent, cancelApply, noTask]

/-- After Accept, AcceptTask is no longer applicable (idempotence). -/
theorem accept_not_reapplicable (t : TaskState) :
    acceptIsApplicable (acceptApply t) = false := by
  simp [acceptIsApplicable, acceptApply, noTask]

/-- After Complete, AcceptTask is applicable (the loop closes). -/
theorem accept_applicable_after_complete (t : TaskState) :
    acceptIsApplicable (completeApply t) = true := by
  simp [acceptIsApplicable, completeApply, noTask]

/-- After Cancel, AcceptTask is applicable. -/
theorem accept_applicable_after_cancel (t : TaskState) :
    acceptIsApplicable (cancelApply t) = true := by
  simp [acceptIsApplicable, cancelApply, noTask]

/-- Regression: real-task state is NOT noTask (Python's `not "monsters"`
is False, so AcceptTask must not fire). -/
theorem accept_real_task_refused :
    acceptIsApplicable { code := TaskCode.Real, total := 5, progress := 0 } = false := by
  decide

/-- Regression: the Pending sentinel is truthy → AcceptTask refused. -/
theorem accept_pending_refused :
    acceptIsApplicable { code := TaskCode.Pending, total := 1, progress := 0 } = false := by
  decide

/-! ### Target D — ClaimPending value invariant (NOT-A-BUG). -/

/-- The relevant goal projection: `pending_items` non-emptiness. -/
structure ClaimProj where
  pendingNonEmpty : Bool
  deriving Repr, DecidableEq

/-- `ClaimPendingGoal.value`: 25 when pending is non-empty, else 0. -/
def claimValue (c : ClaimProj) : Nat :=
  if c.pendingNonEmpty then 25 else 0

/-- The literal invariant: `value > 0 ↔ pendingNonEmpty`. -/
theorem claim_value_pos_iff_pending (c : ClaimProj) :
    claimValue c > 0 ↔ c.pendingNonEmpty = true := by
  simp [claimValue]
  cases c.pendingNonEmpty <;> simp

/-- Post-Phase-6 chain_safe witness: with full bag and non-empty pending,
the GOAL value is still positive (signals desire) but the ACTION's
`is_applicable` (the Phase-6 fix) correctly refuses, so the planner builds
a Deposit→Claim chain instead of a single-step Claim. -/
theorem claim_value_pos_with_full_bag_witness :
    let c : ClaimProj := { pendingNonEmpty := true }
    let i : Inv := { used := 10, cap := 10 }
    claimValue c > 0 ∧ claimIsApplicable i true = false := by
  refine ⟨?_, ?_⟩
  · simp [claimValue]
  · decide

end Formal.Phase8Invariants
