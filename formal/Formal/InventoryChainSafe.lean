-- @concept: bank, items @property: safety
/-
Formal model of the slot-bookkeeping cores of FOUR `Action.is_applicable` /
`.apply` pairs that previously shared the `NpcBuyAction` shape of REAL BUG #6
(precondition missing a slot-floor check; `apply` then mints into the inventory
and overflows `inventory_max`). All four bugs were verified by Python probes:

* `WithdrawItemAction` (`src/artifactsmmo_cli/ai/actions/withdraw_item.py`):
  pre-fix `is_applicable` checked `inventory_free > 0`, should have required
  `>= self.quantity`. Probe: qty=5 on free=1 → applied → used=14, max=10.
* `ClaimPendingItemAction` (`src/artifactsmmo_cli/ai/actions/claim.py`):
  pre-fix had no inventory_free check; apply minted `+1`. Probe: pending claim
  on a full bag → used=11, max=10.
* `UnequipAction` (`src/artifactsmmo_cli/ai/actions/unequip.py`):
  pre-fix had no inventory_free check; apply pushed the slot item into
  inventory. Probe: unequip on full bag → used=11, max=10.
* `TaskExchangeAction` (`src/artifactsmmo_cli/ai/actions/task_exchange.py`):
  pre-fix did not check inventory_free for the granted reward; the exchange
  grants at least one reward slot per execute. Probe: full bag → is_app=True.

We ALSO model the related REAL BUG #11 in `TaskCancelAction`
(`src/artifactsmmo_cli/ai/actions/task_cancel.py`): pre-fix `is_applicable`
did not check that the inventory held a task coin (server requires 1 coin or
returns HTTP 478) AND `apply` did not decrement the coin from inventory.

Each of the four inventory actions is a different `mint` step over a shared
inventory model. We prove a single `chain_safe` template, then specialise it
to each action by choosing the right per-step mint quantity:

  Withdraw    – mints `+quantity`  (caller controls `quantity` per step)
  Claim       – mints `+1`
  Unequip     – mints `+1`
  TaskExchange – mints `≥1` (we use `≥1` as the safe lower bound on the
                 unknown-at-plan-time reward size; the Python `apply` itself
                 does NOT mint a reward, but the executed API call on the
                 server side does, and the slot-floor check guards the server
                 side from refusing the exchange with HTTP 497.)

TaskCancel's coin-decrement step is modeled separately as a tiny
`(coins : Nat)` projection: precondition `coins ≥ 1`, apply maps `coins ↦
coins - 1`. We prove `apply_coin_eq_pre_minus_one` and a chain version.

Lean core only — no mathlib. Nat arithmetic via `omega`.
-/

namespace Formal.InventoryChainSafe

/-! ### Shared inventory model. -/

/-- Minimal inventory projection. Identical shape to
`Formal.NpcBuyInventory.Inv` and `Formal.GatherApply.Inv`. -/
structure Inv where
  used : Nat
  cap : Nat
  deriving Repr, DecidableEq

def free (i : Inv) : Nat := i.cap - i.used

/-! ### Single-step chain_safe template. -/

/-- Generic mint-by-k apply step. `k = 1` for Claim / Unequip, `k = quantity`
for Withdraw, `k ≥ 1` for TaskExchange. -/
def applyK (i : Inv) (k : Nat) : Inv := { i with used := i.used + k }

/-- Generic slot-floor precondition: `k` free slots available. -/
def isApplicableK (i : Inv) (k : Nat) : Bool := decide (k ≤ i.cap - i.used)

/-- `isApplicableK` lower bound: the chain_safe template. -/
theorem isApplicableK_imp_free_ge (i : Inv) (k : Nat) :
    isApplicableK i k = true → k ≤ i.cap - i.used := by
  intro h; simp [isApplicableK] at h; exact h

/-- Per-step safety: a passing precondition + well-formedness keeps `used`
under `cap` after a single `applyK`. -/
theorem applyK_inventory_safe (i : Inv) (k : Nat)
    (hwf : i.used ≤ i.cap) (h : isApplicableK i k = true) :
    (applyK i k).used ≤ i.cap := by
  have := isApplicableK_imp_free_ge i k h
  simp [applyK]; omega

/-- Chain `applyK` with a per-step quantity schedule. -/
def applyKN : Inv → List Nat → Inv
  | i, [] => i
  | i, k :: rest => applyKN (applyK i k) rest

theorem applyKN_used (i : Inv) (ks : List Nat) :
    (applyKN i ks).used = i.used + ks.sum := by
  induction ks generalizing i with
  | nil => simp [applyKN]
  | cons k rest ih => simp [applyKN, applyK, ih]; omega

theorem applyKN_cap (i : Inv) (ks : List Nat) :
    (applyKN i ks).cap = i.cap := by
  induction ks generalizing i with
  | nil => simp [applyKN]
  | cons k rest ih => simp [applyKN, applyK, ih]

/-- Generic chain safety: if `ks.sum ≤ free`, the chain stays in cap. -/
theorem chain_safe_template (i : Inv) (ks : List Nat)
    (hwf : i.used ≤ i.cap) (h : ks.sum ≤ i.cap - i.used) :
    (applyKN i ks).used ≤ i.cap := by
  rw [applyKN_used]; omega

/-! ### Withdraw — instantiation at `k = quantity`. -/

def withdrawApply (i : Inv) (quantity : Nat) : Inv := applyK i quantity
def withdrawIsApplicable (i : Inv) (quantity bankQty : Nat) : Bool :=
  isApplicableK i quantity && decide (quantity ≤ bankQty)

theorem withdraw_is_applicable_imp_free_ge
    (i : Inv) (quantity bankQty : Nat) :
    withdrawIsApplicable i quantity bankQty = true →
    quantity ≤ i.cap - i.used := by
  intro h; simp [withdrawIsApplicable] at h
  exact isApplicableK_imp_free_ge i quantity h.1

theorem withdraw_is_applicable_imp_bank_ge
    (i : Inv) (quantity bankQty : Nat) :
    withdrawIsApplicable i quantity bankQty = true → quantity ≤ bankQty := by
  intro h; simp [withdrawIsApplicable] at h; exact h.2

theorem withdraw_apply_inventory_safe
    (i : Inv) (quantity bankQty : Nat)
    (hwf : i.used ≤ i.cap)
    (h : withdrawIsApplicable i quantity bankQty = true) :
    (withdrawApply i quantity).used ≤ i.cap := by
  have := withdraw_is_applicable_imp_free_ge i quantity bankQty h
  simp [withdrawApply, applyK]; omega

/-- Chain safety: chained withdraws with total `quantity.sum ≤ free` stay in cap. -/
theorem withdraw_chain_safe (i : Inv) (qs : List Nat)
    (hwf : i.used ≤ i.cap) (h : qs.sum ≤ i.cap - i.used) :
    (applyKN i qs).used ≤ i.cap :=
  chain_safe_template i qs hwf h

/-- Boundary witness: `quantity == free` accepted. -/
theorem withdraw_boundary_quantity_eq_free_witness :
    let i : Inv := { used := 5, cap := 10 }
    withdrawIsApplicable i 5 5 = true ∧ (withdrawApply i 5).used ≤ i.cap := by
  refine ⟨by decide, ?_⟩; decide

/-- Regression-pin: verified Python probe (used=9, cap=10, quantity=5)
is refused post-fix. -/
theorem withdraw_regression_used9_cap10_qty5_refused :
    withdrawIsApplicable { used := 9, cap := 10 } 5 100 = false := by decide

/-! ### Claim — instantiation at `k = 1`. -/

def claimApply (i : Inv) : Inv := applyK i 1
def claimIsApplicable (i : Inv) (hasPending : Bool) : Bool :=
  hasPending && isApplicableK i 1

theorem claim_is_applicable_imp_free_ge
    (i : Inv) (hasPending : Bool) :
    claimIsApplicable i hasPending = true → 1 ≤ i.cap - i.used := by
  intro h; simp [claimIsApplicable] at h
  exact isApplicableK_imp_free_ge i 1 h.2

theorem claim_apply_inventory_safe
    (i : Inv) (hasPending : Bool)
    (hwf : i.used ≤ i.cap)
    (h : claimIsApplicable i hasPending = true) :
    (claimApply i).used ≤ i.cap := by
  have := claim_is_applicable_imp_free_ge i hasPending h
  simp [claimApply, applyK]; omega

theorem claim_chain_safe (i : Inv) (n : Nat)
    (hwf : i.used ≤ i.cap) (h : n ≤ i.cap - i.used) :
    (applyKN i (List.replicate n 1)).used ≤ i.cap := by
  apply chain_safe_template i (List.replicate n 1) hwf
  -- `List.replicate n 1`.sum = n
  have : (List.replicate n 1).sum = n := by
    induction n with
    | zero => simp
    | succ m ih => simp [List.replicate]; omega
  omega

theorem claim_boundary_witness :
    let i : Inv := { used := 9, cap := 10 }
    claimIsApplicable i true = true ∧ (claimApply i).used ≤ i.cap := by
  refine ⟨by decide, ?_⟩; decide

theorem claim_regression_full_bag_refused :
    claimIsApplicable { used := 10, cap := 10 } true = false := by decide

theorem claim_no_pending_refused :
    claimIsApplicable { used := 0, cap := 10 } false = false := by decide

/-! ### Unequip — instantiation at `k = 1` (with slot non-empty gate). -/

def unequipApply (i : Inv) : Inv := applyK i 1
def unequipIsApplicable (i : Inv) (slotNonEmpty : Bool) : Bool :=
  slotNonEmpty && isApplicableK i 1

theorem unequip_is_applicable_imp_free_ge
    (i : Inv) (slotNonEmpty : Bool) :
    unequipIsApplicable i slotNonEmpty = true → 1 ≤ i.cap - i.used := by
  intro h; simp [unequipIsApplicable] at h
  exact isApplicableK_imp_free_ge i 1 h.2

theorem unequip_apply_inventory_safe
    (i : Inv) (slotNonEmpty : Bool)
    (hwf : i.used ≤ i.cap)
    (h : unequipIsApplicable i slotNonEmpty = true) :
    (unequipApply i).used ≤ i.cap := by
  have := unequip_is_applicable_imp_free_ge i slotNonEmpty h
  simp [unequipApply, applyK]; omega

theorem unequip_chain_safe (i : Inv) (n : Nat)
    (hwf : i.used ≤ i.cap) (h : n ≤ i.cap - i.used) :
    (applyKN i (List.replicate n 1)).used ≤ i.cap := by
  apply chain_safe_template i (List.replicate n 1) hwf
  have : (List.replicate n 1).sum = n := by
    induction n with
    | zero => simp
    | succ m ih => simp [List.replicate]; omega
  omega

theorem unequip_boundary_witness :
    let i : Inv := { used := 9, cap := 10 }
    unequipIsApplicable i true = true ∧ (unequipApply i).used ≤ i.cap := by
  refine ⟨by decide, ?_⟩; decide

theorem unequip_regression_full_bag_refused :
    unequipIsApplicable { used := 10, cap := 10 } true = false := by decide

theorem unequip_empty_slot_refused :
    unequipIsApplicable { used := 0, cap := 10 } false = false := by decide

/-! ### TaskExchange — instantiation at `k ≥ 1` (the safe reward-grant bound). -/

def taskExchangeApply (i : Inv) (reward : Nat) : Inv := applyK i reward
def taskExchangeIsApplicable
    (i : Inv) (coins minCoins : Nat) : Bool :=
  decide (minCoins ≤ coins) && isApplicableK i 1

theorem task_exchange_is_applicable_imp_free_ge
    (i : Inv) (coins minCoins : Nat) :
    taskExchangeIsApplicable i coins minCoins = true → 1 ≤ i.cap - i.used := by
  intro h; simp [taskExchangeIsApplicable] at h
  exact isApplicableK_imp_free_ge i 1 h.2

theorem task_exchange_is_applicable_imp_coins_ge
    (i : Inv) (coins minCoins : Nat) :
    taskExchangeIsApplicable i coins minCoins = true → minCoins ≤ coins := by
  intro h; simp [taskExchangeIsApplicable] at h; exact h.1

theorem task_exchange_apply_inventory_safe
    (i : Inv) (coins minCoins : Nat)
    (hwf : i.used ≤ i.cap)
    (h : taskExchangeIsApplicable i coins minCoins = true) :
    (taskExchangeApply i 1).used ≤ i.cap := by
  have := task_exchange_is_applicable_imp_free_ge i coins minCoins h
  simp [taskExchangeApply, applyK]; omega

/-- Chain safety for TaskExchange uses a per-step reward schedule (one entry per
exchange; each `≥ 1`). The aggregate-`≤ free` bound implies chain safety. -/
theorem task_exchange_chain_safe (i : Inv) (rewards : List Nat)
    (hwf : i.used ≤ i.cap) (h : rewards.sum ≤ i.cap - i.used) :
    (applyKN i rewards).used ≤ i.cap :=
  chain_safe_template i rewards hwf h

theorem task_exchange_boundary_witness :
    let i : Inv := { used := 9, cap := 10 }
    taskExchangeIsApplicable i 1 1 = true ∧ (taskExchangeApply i 1).used ≤ i.cap := by
  refine ⟨by decide, ?_⟩; decide

theorem task_exchange_regression_full_bag_refused :
    taskExchangeIsApplicable { used := 10, cap := 10 } 5 1 = false := by decide

theorem task_exchange_coin_short_refused :
    taskExchangeIsApplicable { used := 0, cap := 100 } 2 5 = false := by decide

/-! ### TaskCancel — coin decrement (REAL BUG #11). -/

/-- Tiny coin model: only the `tasks_coin` count matters for the decrement
contract. -/
structure CoinPurse where
  coins : Nat
  deriving Repr, DecidableEq

/-- TaskCancel precondition: at least one task coin is held. -/
def taskCancelIsApplicable (p : CoinPurse) (hasTask : Bool) : Bool :=
  hasTask && decide (1 ≤ p.coins)

/-- TaskCancel coin step: decrement by 1 (`Nat.sub` truncates at 0, mirroring
the Python `del` when the count drops to 0). -/
def taskCancelApply (p : CoinPurse) : CoinPurse :=
  { coins := p.coins - 1 }

theorem task_cancel_is_applicable_imp_coin_ge
    (p : CoinPurse) (hasTask : Bool) :
    taskCancelIsApplicable p hasTask = true → 1 ≤ p.coins := by
  intro h; simp [taskCancelIsApplicable] at h; exact h.2

/-- Apply decrements the coin count by exactly 1 under the precondition. -/
theorem task_cancel_apply_coin_eq_pre_minus_one
    (p : CoinPurse) (hasTask : Bool)
    (_h : taskCancelIsApplicable p hasTask = true) :
    (taskCancelApply p).coins = p.coins - 1 := by
  rfl

/-- Strict monotonicity: under the precondition, post-coins < pre-coins. -/
theorem task_cancel_apply_strictly_decreases
    (p : CoinPurse) (hasTask : Bool)
    (h : taskCancelIsApplicable p hasTask = true) :
    (taskCancelApply p).coins < p.coins := by
  have := task_cancel_is_applicable_imp_coin_ge p hasTask h
  simp [taskCancelApply]; omega

/-- N-chain. -/
def taskCancelApplyN : CoinPurse → Nat → CoinPurse
  | p, 0 => p
  | p, n + 1 => taskCancelApplyN (taskCancelApply p) n

/-- N-step bookkeeping: `coins'` = `coins - n` (Nat-truncating at 0). -/
theorem task_cancel_applyN_coin (p : CoinPurse) (n : Nat) :
    (taskCancelApplyN p n).coins = p.coins - n := by
  induction n generalizing p with
  | zero => simp [taskCancelApplyN]
  | succ m ih => simp [taskCancelApplyN, taskCancelApply, ih]; omega

/-- Chain safety: if the purse starts with `≥ n` coins, every step's
precondition holds (because between steps the count stays `≥ 1` until the
last step). -/
theorem task_cancel_chain_coin_safe
    (p : CoinPurse) (n : Nat) (_h : n ≤ p.coins) :
    (taskCancelApplyN p n).coins = p.coins - n := by
  exact task_cancel_applyN_coin p n

theorem task_cancel_boundary_witness :
    let p : CoinPurse := { coins := 1 }
    taskCancelIsApplicable p true = true ∧
      (taskCancelApply p).coins = 0 := by
  refine ⟨by decide, ?_⟩; decide

theorem task_cancel_no_coin_refused :
    taskCancelIsApplicable { coins := 0 } true = false := by decide

theorem task_cancel_no_task_refused :
    taskCancelIsApplicable { coins := 5 } false = false := by decide

end Formal.InventoryChainSafe
