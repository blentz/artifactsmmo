-- @concept: core @property: safety
/-
Formal model of the **Action.apply baseline-preservation** contract.

# Bug fixed (REAL BUG #5)

Pre-fix, 21+ of the 24 concrete `Action.apply` methods constructed a NEW
`WorldState(field=…, field=…, …)` listing only the fields the action mutates.
The dataclass-based `WorldState` carries eight server-snapshot stat-baseline
fields with `field(default_factory=…)` defaults; the explicit constructor calls
**silently dropped** them, so the planner saw `attack={}`, `skill_xp={}`,
`resistance={}`, `dmg=0`, `wisdom=0`, `critical_strike=0`, `initiative=0`,
`dmg_elements={}` after Move/Equip/Fight/…  Probe-verified for Move and Equip
in the pre-fix tree.

The baseline fields are SERVER-COMPUTED snapshots (post-equipment); the bot's
GOAP planner has no authority to recompute them locally. Hypothetical loadout
projections for combat planning go through the separate `project_loadout_stats`
mechanism (`equipment/projection.py`) which returns a `ProjectedStats`
dataclass — not a `WorldState`. Therefore the correct contract is:

  ∀ s. ∀ action. apply(s) preserves the 8 baseline fields of s.

# Lean model — Phase-14 ALL 24 ACTIONS

We model a Python-faithful `WorldStateLean` carrying the 8 baseline stat fields
PLUS the union of mutable fields touched by ANY of the 24 concrete `apply`
methods. Every Python apply uses `dataclasses.replace(state, <fields>)` post-fix;
each Lean apply mirrors this with a record `with`-update touching ONLY the
fields the Python source mutates. By construction the baseline fields are
untouched syntactically, and the preservation theorems are 1-line `rfl`-style.

**All 24 actions are modeled below**, grouped by structural family:

  1. **Position-only**: Move, MoveSemantic, MapTransition
  2. **Inventory-mint**: Gather, NpcBuy, WithdrawGold, WithdrawItem, Claim
  3. **Inventory-consume**: Craft, Recycle, NpcSell, DepositGold, DepositAll,
     UseConsumable, Delete
  4. **Equipment-swap**: Equip, Unequip, OptimizeLoadout
  5. **Task transition**: AcceptTask, CompleteTask, TaskCancel, TaskExchange,
     TaskTrade
  6. **Misc**: Rest (hp restore), BuyBankExpansion (bank_capacity)
  7. **Fight**: combat + task_progress + cooldown + hp

The headline `all_actions_preserve_baseline` enumerates the union.

Lean core only — no mathlib. Axioms ⊆ {propext, Classical.choice, Quot.sound}.

# Phase-4 addendum: `projected_skill_xp_delta`

A NEW Python field `WorldState.projected_skill_xp_delta : dict[str, int]` was
added (post the 8-field baseline contract) as a per-plan-path XP accumulator
for `LevelSkillGoal.is_satisfied`. It is intentionally OUTSIDE the modeled
baseline: it is NOT a server-snapshot field, and Gather/Craft.apply DO mutate
it (by design — the planner needs projection-based satisfaction). It IS modeled
as a mutable field in `WorldStateLean` below so the Gather/Craft apply
functions can reflect the Python mutation.
-/

namespace Formal.ApplyBaseline

/-- Python-faithful `WorldStateLean` carrying the 8 baseline stat fields plus
    the union of mutable fields used by all 24 modeled `apply` methods.
    The baseline-OUTSIDE fields are the targets of `dataclasses.replace`. -/
structure WorldStateLean where
  -- mutable (action-touched) fields, in dataclass field order
  hp                       : Nat
  max_hp                   : Nat
  gold                     : Int
  x                        : Int
  y                        : Int
  inventory                : List (String × Nat)
  equipment                : List (String × Option String)
  cooldown_expires         : Option Nat      -- model `datetime | None` as `Option Nat`
  task_code                : Option String
  task_type                : Option String
  task_progress            : Nat
  task_total               : Nat
  bank_items               : Option (List (String × Nat))
  bank_gold                : Option Int
  pending_items            : Option (List (String × String))
  bank_capacity            : Option Nat
  projected_skill_xp_delta : List (String × Int)
  -- the 8 baseline stat fields (server-snapshot, must be preserved)
  attack          : List (String × Nat)
  dmg             : Int
  dmg_elements    : List (String × Nat)
  resistance      : List (String × Nat)
  critical_strike : Nat
  initiative      : Nat
  wisdom          : Nat
  skill_xp        : List (String × Nat)
  deriving Repr, DecidableEq

/-! ## Baseline-preservation predicate

The 8-conjunct property: post-apply state's baseline fields are pointwise
equal to pre-apply state's baseline fields. -/

def preservesBaseline (s s' : WorldStateLean) : Prop :=
  s.attack          = s'.attack          ∧
  s.dmg             = s'.dmg             ∧
  s.dmg_elements    = s'.dmg_elements    ∧
  s.resistance      = s'.resistance      ∧
  s.critical_strike = s'.critical_strike ∧
  s.initiative      = s'.initiative      ∧
  s.wisdom          = s'.wisdom          ∧
  s.skill_xp        = s'.skill_xp

/-- Reflexivity: every state preserves its own baseline. -/
theorem preservesBaseline_refl (s : WorldStateLean) : preservesBaseline s s := by
  unfold preservesBaseline
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Transitivity. -/
theorem preservesBaseline_trans {a b c : WorldStateLean}
    (hab : preservesBaseline a b) (hbc : preservesBaseline b c) :
    preservesBaseline a c := by
  unfold preservesBaseline at *
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · exact hab.1.trans hbc.1
  · exact hab.2.1.trans hbc.2.1
  · exact hab.2.2.1.trans hbc.2.2.1
  · exact hab.2.2.2.1.trans hbc.2.2.2.1
  · exact hab.2.2.2.2.1.trans hbc.2.2.2.2.1
  · exact hab.2.2.2.2.2.1.trans hbc.2.2.2.2.2.1
  · exact hab.2.2.2.2.2.2.1.trans hbc.2.2.2.2.2.2.1
  · exact hab.2.2.2.2.2.2.2.trans hbc.2.2.2.2.2.2.2

/-! ## Helper tactic shorthand

Every apply below is a record `with`-update touching only the declared mutable
fields. The 8 baseline fields are syntactically untouched, so the preservation
proof is always `⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩` after unfolding. -/

private theorem rfl8 : ∀ {α₁ α₂ α₃ α₄ α₅ α₆ α₇ α₈ : Type}
    (a₁ : α₁) (a₂ : α₂) (a₃ : α₃) (a₄ : α₄) (a₅ : α₅) (a₆ : α₆) (a₇ : α₇) (a₈ : α₈),
    (a₁ = a₁ ∧ a₂ = a₂ ∧ a₃ = a₃ ∧ a₄ = a₄ ∧ a₅ = a₅ ∧ a₆ = a₆ ∧ a₇ = a₇ ∧ a₈ = a₈) :=
  fun _ _ _ _ _ _ _ _ => ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 1 — Position-only

`MoveAction`, `MoveTo` (`movement_semantic`), `MapTransitionAction`. All three
mutate ONLY position fields (`x`, `y`) and clear `cooldown_expires`. -/

/-- `MoveAction.apply` model: `dataclasses.replace(state, x, y, cooldown_expires=None)`. -/
def moveApply (s : WorldStateLean) (newX newY : Int) : WorldStateLean :=
  { s with x := newX, y := newY, cooldown_expires := none }

/-- `MoveTo.apply` model (movement_semantic.py): same shape as Move. -/
def moveSemanticApply (s : WorldStateLean) (newX newY : Int) : WorldStateLean :=
  { s with x := newX, y := newY, cooldown_expires := none }

/-- `MapTransitionAction.apply` model: identity transition (no fields change). -/
def mapTransitionApply (s : WorldStateLean) : WorldStateLean := s

theorem moveApply_preserves_baseline (s : WorldStateLean) (newX newY : Int) :
    preservesBaseline s (moveApply s newX newY) := by
  unfold preservesBaseline moveApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem moveSemanticApply_preserves_baseline (s : WorldStateLean) (newX newY : Int) :
    preservesBaseline s (moveSemanticApply s newX newY) := by
  unfold preservesBaseline moveSemanticApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem mapTransitionApply_preserves_baseline (s : WorldStateLean) :
    preservesBaseline s (mapTransitionApply s) := by
  unfold preservesBaseline mapTransitionApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 2 — Inventory-mint

`GatherAction`, `NpcBuyAction`, `WithdrawGoldAction`, `WithdrawItemAction`,
`ClaimPendingItemAction`. Inventory (or gold) grows; cooldown cleared. -/

/-- `GatherAction.apply` model: inventory grows by one drop; projected delta
    increments. Position move + cooldown clear also occur in the Python source. -/
def gatherApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newDelta : List (String × Int)) (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv, projected_skill_xp_delta := newDelta
         , x := newX, y := newY, cooldown_expires := none }

/-- `NpcBuyAction.apply` model: gold decrements, inventory grows; cooldown. -/
def npcBuyApply (s : WorldStateLean) (newGold : Int)
    (newInv : List (String × Nat)) (newX newY : Int) : WorldStateLean :=
  { s with gold := newGold, inventory := newInv
         , x := newX, y := newY, cooldown_expires := none }

/-- `WithdrawGoldAction.apply` model: gold up, bank_gold down. -/
def withdrawGoldApply (s : WorldStateLean) (newGold : Int)
    (newBankGold : Option Int) (newX newY : Int) : WorldStateLean :=
  { s with gold := newGold, bank_gold := newBankGold
         , x := newX, y := newY, cooldown_expires := none }

/-- `WithdrawItemAction.apply` model: inventory up, bank_items down. -/
def withdrawItemApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newBank : Option (List (String × Nat))) (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv, bank_items := newBank
         , x := newX, y := newY, cooldown_expires := none }

/-- `ClaimPendingItemAction.apply` model: inventory grows; pending_items shrinks. -/
def claimApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newPending : Option (List (String × String))) : WorldStateLean :=
  { s with inventory := newInv, pending_items := newPending
         , cooldown_expires := none }

theorem gatherApply_preserves_baseline (s : WorldStateLean) (i : List (String × Nat))
    (d : List (String × Int)) (x y : Int) :
    preservesBaseline s (gatherApply s i d x y) := by
  unfold preservesBaseline gatherApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem npcBuyApply_preserves_baseline (s : WorldStateLean) (g : Int)
    (i : List (String × Nat)) (x y : Int) :
    preservesBaseline s (npcBuyApply s g i x y) := by
  unfold preservesBaseline npcBuyApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem withdrawGoldApply_preserves_baseline (s : WorldStateLean) (g : Int)
    (bg : Option Int) (x y : Int) :
    preservesBaseline s (withdrawGoldApply s g bg x y) := by
  unfold preservesBaseline withdrawGoldApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem withdrawItemApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (b : Option (List (String × Nat))) (x y : Int) :
    preservesBaseline s (withdrawItemApply s i b x y) := by
  unfold preservesBaseline withdrawItemApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem claimApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (p : Option (List (String × String))) :
    preservesBaseline s (claimApply s i p) := by
  unfold preservesBaseline claimApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 3 — Inventory-consume

`CraftAction`, `RecycleAction`, `NpcSellAction`, `DepositGoldAction`,
`DepositAllAction`, `UseConsumableAction`, `DeleteItemAction`. Inventory (or
gold) shrinks; banking-style ones also bump bank_*. -/

/-- `CraftAction.apply` model: inventory consumed/minted; projected delta bumped;
    position moves to workshop; cooldown cleared. -/
def craftApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newDelta : List (String × Int)) (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv, projected_skill_xp_delta := newDelta
         , x := newX, y := newY, cooldown_expires := none }

/-- `RecycleAction.apply` model: inventory consumed, mats restored. -/
def recycleApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv, x := newX, y := newY, cooldown_expires := none }

/-- `NpcSellAction.apply` model: inventory shrinks, gold grows. -/
def npcSellApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newGold : Int) (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv, gold := newGold
         , x := newX, y := newY, cooldown_expires := none }

/-- `DepositGoldAction.apply` model: gold down, bank_gold up. -/
def depositGoldApply (s : WorldStateLean) (newGold : Int)
    (newBankGold : Option Int) (newX newY : Int) : WorldStateLean :=
  { s with gold := newGold, bank_gold := newBankGold
         , x := newX, y := newY, cooldown_expires := none }

/-- `DepositAllAction.apply` model: inventory drained, bank_items grow. -/
def depositAllApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newBank : Option (List (String × Nat))) (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv, bank_items := newBank
         , x := newX, y := newY, cooldown_expires := none }

/-- `UseConsumableAction.apply` model: hp up, inventory down. -/
def useConsumableApply (s : WorldStateLean) (newHp : Nat)
    (newInv : List (String × Nat)) : WorldStateLean :=
  { s with hp := newHp, inventory := newInv, cooldown_expires := none }

/-- `DeleteItemAction.apply` model: inventory shrinks. -/
def deleteApply (s : WorldStateLean) (newInv : List (String × Nat)) : WorldStateLean :=
  { s with inventory := newInv, cooldown_expires := none }

theorem craftApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (d : List (String × Int)) (x y : Int) :
    preservesBaseline s (craftApply s i d x y) := by
  unfold preservesBaseline craftApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem recycleApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (x y : Int) :
    preservesBaseline s (recycleApply s i x y) := by
  unfold preservesBaseline recycleApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem npcSellApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (g : Int) (x y : Int) :
    preservesBaseline s (npcSellApply s i g x y) := by
  unfold preservesBaseline npcSellApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem depositGoldApply_preserves_baseline (s : WorldStateLean) (g : Int)
    (bg : Option Int) (x y : Int) :
    preservesBaseline s (depositGoldApply s g bg x y) := by
  unfold preservesBaseline depositGoldApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem depositAllApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (b : Option (List (String × Nat))) (x y : Int) :
    preservesBaseline s (depositAllApply s i b x y) := by
  unfold preservesBaseline depositAllApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem useConsumableApply_preserves_baseline (s : WorldStateLean) (h : Nat)
    (i : List (String × Nat)) :
    preservesBaseline s (useConsumableApply s h i) := by
  unfold preservesBaseline useConsumableApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem deleteApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) :
    preservesBaseline s (deleteApply s i) := by
  unfold preservesBaseline deleteApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 4 — Equipment-swap

`EquipAction`, `UnequipAction`, `OptimizeLoadoutAction`. Inventory and
equipment rearranged; cooldown cleared. -/

/-- `EquipAction.apply` model: inventory + equipment updated. -/
def equipApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newEq : List (String × Option String)) : WorldStateLean :=
  { s with inventory := newInv, equipment := newEq, cooldown_expires := none }

/-- `UnequipAction.apply` model: inventory + equipment updated. -/
def unequipApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newEq : List (String × Option String)) : WorldStateLean :=
  { s with inventory := newInv, equipment := newEq, cooldown_expires := none }

/-- `OptimizeLoadoutAction.apply` model: same shape as Equip. -/
def optimizeLoadoutApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newEq : List (String × Option String)) : WorldStateLean :=
  { s with inventory := newInv, equipment := newEq, cooldown_expires := none }

theorem equipApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (e : List (String × Option String)) :
    preservesBaseline s (equipApply s i e) := by
  unfold preservesBaseline equipApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem unequipApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (e : List (String × Option String)) :
    preservesBaseline s (unequipApply s i e) := by
  unfold preservesBaseline unequipApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem optimizeLoadoutApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (e : List (String × Option String)) :
    preservesBaseline s (optimizeLoadoutApply s i e) := by
  unfold preservesBaseline optimizeLoadoutApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 5 — Task transition

`AcceptTaskAction`, `CompleteTaskAction`, `TaskCancelAction`,
`TaskExchangeAction`, `TaskTradeAction`. Task fields rotated; pending_items,
inventory, or coins also possibly touched; cooldown cleared. -/

/-- `AcceptTaskAction.apply` model: task fields set; position moves to taskmaster. -/
def acceptTaskApply (s : WorldStateLean) (newCode : Option String)
    (newType : Option String) (newProgress newTotal : Nat)
    (newX newY : Int) : WorldStateLean :=
  { s with task_code := newCode, task_type := newType
         , task_progress := newProgress, task_total := newTotal
         , x := newX, y := newY, cooldown_expires := none }

/-- `CompleteTaskAction.apply` model: task fields cleared; pending_items appended. -/
def completeTaskApply (s : WorldStateLean) (newCode : Option String)
    (newType : Option String) (newProgress newTotal : Nat)
    (newPending : Option (List (String × String))) (newX newY : Int) : WorldStateLean :=
  { s with task_code := newCode, task_type := newType
         , task_progress := newProgress, task_total := newTotal
         , pending_items := newPending
         , x := newX, y := newY, cooldown_expires := none }

/-- `TaskCancelAction.apply` model: task cleared + 1 coin consumed. -/
def taskCancelApply (s : WorldStateLean) (newCode : Option String)
    (newType : Option String) (newProgress newTotal : Nat)
    (newInv : List (String × Nat)) (newX newY : Int) : WorldStateLean :=
  { s with task_code := newCode, task_type := newType
         , task_progress := newProgress, task_total := newTotal
         , inventory := newInv
         , x := newX, y := newY, cooldown_expires := none }

/-- `TaskExchangeAction.apply` model: coins consumed; pending_items grows. -/
def taskExchangeApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newPending : Option (List (String × String))) (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv, pending_items := newPending
         , x := newX, y := newY, cooldown_expires := none }

/-- `TaskTradeAction.apply` model: trade items for task progress. -/
def taskTradeApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newProgress : Nat) (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv, task_progress := newProgress
         , x := newX, y := newY, cooldown_expires := none }

theorem acceptTaskApply_preserves_baseline (s : WorldStateLean)
    (c : Option String) (t : Option String) (p tot : Nat) (x y : Int) :
    preservesBaseline s (acceptTaskApply s c t p tot x y) := by
  unfold preservesBaseline acceptTaskApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem completeTaskApply_preserves_baseline (s : WorldStateLean)
    (c : Option String) (t : Option String) (p tot : Nat)
    (pend : Option (List (String × String))) (x y : Int) :
    preservesBaseline s (completeTaskApply s c t p tot pend x y) := by
  unfold preservesBaseline completeTaskApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem taskCancelApply_preserves_baseline (s : WorldStateLean)
    (c : Option String) (t : Option String) (p tot : Nat)
    (i : List (String × Nat)) (x y : Int) :
    preservesBaseline s (taskCancelApply s c t p tot i x y) := by
  unfold preservesBaseline taskCancelApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem taskExchangeApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (pend : Option (List (String × String))) (x y : Int) :
    preservesBaseline s (taskExchangeApply s i pend x y) := by
  unfold preservesBaseline taskExchangeApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem taskTradeApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (p : Nat) (x y : Int) :
    preservesBaseline s (taskTradeApply s i p x y) := by
  unfold preservesBaseline taskTradeApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 6 — Misc

`RestAction` (hp restore), `BuyBankExpansionAction` (bank_capacity bump). -/

/-- `RestAction.apply` model: hp ← max_hp; cooldown cleared. -/
def restApply (s : WorldStateLean) : WorldStateLean :=
  { s with hp := s.max_hp, cooldown_expires := none }

/-- `BuyBankExpansionAction.apply` model: gold debited; bank_capacity +SLOTS;
    bank_items updated; position moves to bank. -/
def buyBankExpansionApply (s : WorldStateLean) (newGold : Int)
    (newCap : Option Nat) (newBank : Option (List (String × Nat)))
    (newX newY : Int) : WorldStateLean :=
  { s with gold := newGold, bank_capacity := newCap, bank_items := newBank
         , x := newX, y := newY, cooldown_expires := none }

theorem restApply_preserves_baseline (s : WorldStateLean) :
    preservesBaseline s (restApply s) := by
  unfold preservesBaseline restApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem buyBankExpansionApply_preserves_baseline (s : WorldStateLean) (g : Int)
    (c : Option Nat) (b : Option (List (String × Nat))) (x y : Int) :
    preservesBaseline s (buyBankExpansionApply s g c b x y) := by
  unfold preservesBaseline buyBankExpansionApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 7 — Fight

`FightAction`: combat resolves → hp decreases, task_progress may advance,
cooldown cleared, inventory may grow with drops. -/

/-- `FightAction.apply` model: hp/inventory/task_progress mutated; cooldown. -/
def fightApply (s : WorldStateLean) (newHp : Nat)
    (newInv : List (String × Nat)) (newProgress : Nat)
    (newX newY : Int) : WorldStateLean :=
  { s with hp := newHp, inventory := newInv, task_progress := newProgress
         , x := newX, y := newY, cooldown_expires := none }

theorem fightApply_preserves_baseline (s : WorldStateLean) (h : Nat)
    (i : List (String × Nat)) (p : Nat) (x y : Int) :
    preservesBaseline s (fightApply s h i p x y) := by
  unfold preservesBaseline fightApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Headline: the uniform contract holds across ALL 24 modeled actions.

Quantifies over an exhaustive enumeration of the 24 modeled `apply` functions
so a single statement seals the property for every modeled action — closing
the Phase-4 disclosed gap. -/

/-- Exhaustive enumeration of all 24 modeled apply functions. Each constructor
    packs the action + its arguments. -/
inductive ModeledApply where
  -- Family 1: position-only
  | move              (newX newY : Int) : ModeledApply
  | moveSemantic      (newX newY : Int) : ModeledApply
  | mapTransition                       : ModeledApply
  -- Family 2: inventory-mint
  | gather            (newInv : List (String × Nat))
                      (newDelta : List (String × Int))
                      (newX newY : Int) : ModeledApply
  | npcBuy            (newGold : Int) (newInv : List (String × Nat))
                      (newX newY : Int) : ModeledApply
  | withdrawGold      (newGold : Int) (newBankGold : Option Int)
                      (newX newY : Int) : ModeledApply
  | withdrawItem      (newInv : List (String × Nat))
                      (newBank : Option (List (String × Nat)))
                      (newX newY : Int) : ModeledApply
  | claim             (newInv : List (String × Nat))
                      (newPending : Option (List (String × String))) : ModeledApply
  -- Family 3: inventory-consume
  | craft             (newInv : List (String × Nat))
                      (newDelta : List (String × Int))
                      (newX newY : Int) : ModeledApply
  | recycle           (newInv : List (String × Nat)) (newX newY : Int) : ModeledApply
  | npcSell           (newInv : List (String × Nat)) (newGold : Int)
                      (newX newY : Int) : ModeledApply
  | depositGold       (newGold : Int) (newBankGold : Option Int)
                      (newX newY : Int) : ModeledApply
  | depositAll        (newInv : List (String × Nat))
                      (newBank : Option (List (String × Nat)))
                      (newX newY : Int) : ModeledApply
  | useConsumable     (newHp : Nat) (newInv : List (String × Nat)) : ModeledApply
  | delete            (newInv : List (String × Nat)) : ModeledApply
  -- Family 4: equipment-swap
  | equip             (newInv : List (String × Nat))
                      (newEq : List (String × Option String)) : ModeledApply
  | unequip           (newInv : List (String × Nat))
                      (newEq : List (String × Option String)) : ModeledApply
  | optimizeLoadout   (newInv : List (String × Nat))
                      (newEq : List (String × Option String)) : ModeledApply
  -- Family 5: task transition
  | acceptTask        (c : Option String) (t : Option String)
                      (p tot : Nat) (x y : Int) : ModeledApply
  | completeTask      (c : Option String) (t : Option String) (p tot : Nat)
                      (pend : Option (List (String × String)))
                      (x y : Int) : ModeledApply
  | taskCancel        (c : Option String) (t : Option String) (p tot : Nat)
                      (i : List (String × Nat)) (x y : Int) : ModeledApply
  | taskExchange      (i : List (String × Nat))
                      (pend : Option (List (String × String)))
                      (x y : Int) : ModeledApply
  | taskTrade         (i : List (String × Nat)) (p : Nat) (x y : Int) : ModeledApply
  -- Family 6: misc
  | rest                                                          : ModeledApply
  | buyBankExpansion  (g : Int) (c : Option Nat)
                      (b : Option (List (String × Nat)))
                      (x y : Int) : ModeledApply
  -- Family 7: fight
  | fight             (h : Nat) (i : List (String × Nat)) (p : Nat)
                      (x y : Int) : ModeledApply

/-- Dispatch: run an enumerated action on a state. -/
def ModeledApply.run (a : ModeledApply) (s : WorldStateLean) : WorldStateLean :=
  match a with
  | .move x y                       => moveApply s x y
  | .moveSemantic x y               => moveSemanticApply s x y
  | .mapTransition                  => mapTransitionApply s
  | .gather i d x y                 => gatherApply s i d x y
  | .npcBuy g i x y                 => npcBuyApply s g i x y
  | .withdrawGold g bg x y          => withdrawGoldApply s g bg x y
  | .withdrawItem i b x y           => withdrawItemApply s i b x y
  | .claim i p                      => claimApply s i p
  | .craft i d x y                  => craftApply s i d x y
  | .recycle i x y                  => recycleApply s i x y
  | .npcSell i g x y                => npcSellApply s i g x y
  | .depositGold g bg x y           => depositGoldApply s g bg x y
  | .depositAll i b x y             => depositAllApply s i b x y
  | .useConsumable h i              => useConsumableApply s h i
  | .delete i                       => deleteApply s i
  | .equip i e                      => equipApply s i e
  | .unequip i e                    => unequipApply s i e
  | .optimizeLoadout i e            => optimizeLoadoutApply s i e
  | .acceptTask c t p tot x y       => acceptTaskApply s c t p tot x y
  | .completeTask c t p tot pe x y  => completeTaskApply s c t p tot pe x y
  | .taskCancel c t p tot i x y     => taskCancelApply s c t p tot i x y
  | .taskExchange i pe x y          => taskExchangeApply s i pe x y
  | .taskTrade i p x y              => taskTradeApply s i p x y
  | .rest                           => restApply s
  | .buyBankExpansion g c b x y     => buyBankExpansionApply s g c b x y
  | .fight h i p x y                => fightApply s h i p x y

/-- **HEADLINE — Phase-14 disclosed-gap closure**: every one of the 24 modeled
    apply transitions preserves the 8-field baseline. -/
theorem all_actions_preserve_baseline (s : WorldStateLean) (a : ModeledApply) :
    preservesBaseline s (a.run s) := by
  cases a with
  | move x y                      => exact moveApply_preserves_baseline s x y
  | moveSemantic x y              => exact moveSemanticApply_preserves_baseline s x y
  | mapTransition                 => exact mapTransitionApply_preserves_baseline s
  | gather i d x y                => exact gatherApply_preserves_baseline s i d x y
  | npcBuy g i x y                => exact npcBuyApply_preserves_baseline s g i x y
  | withdrawGold g bg x y         => exact withdrawGoldApply_preserves_baseline s g bg x y
  | withdrawItem i b x y          => exact withdrawItemApply_preserves_baseline s i b x y
  | claim i p                     => exact claimApply_preserves_baseline s i p
  | craft i d x y                 => exact craftApply_preserves_baseline s i d x y
  | recycle i x y                 => exact recycleApply_preserves_baseline s i x y
  | npcSell i g x y               => exact npcSellApply_preserves_baseline s i g x y
  | depositGold g bg x y          => exact depositGoldApply_preserves_baseline s g bg x y
  | depositAll i b x y            => exact depositAllApply_preserves_baseline s i b x y
  | useConsumable h i             => exact useConsumableApply_preserves_baseline s h i
  | delete i                      => exact deleteApply_preserves_baseline s i
  | equip i e                     => exact equipApply_preserves_baseline s i e
  | unequip i e                   => exact unequipApply_preserves_baseline s i e
  | optimizeLoadout i e           => exact optimizeLoadoutApply_preserves_baseline s i e
  | acceptTask c t p tot x y      => exact acceptTaskApply_preserves_baseline s c t p tot x y
  | completeTask c t p tot pe x y => exact completeTaskApply_preserves_baseline s c t p tot pe x y
  | taskCancel c t p tot i x y    => exact taskCancelApply_preserves_baseline s c t p tot i x y
  | taskExchange i pe x y         => exact taskExchangeApply_preserves_baseline s i pe x y
  | taskTrade i p x y             => exact taskTradeApply_preserves_baseline s i p x y
  | rest                          => exact restApply_preserves_baseline s
  | buyBankExpansion g c b x y    => exact buyBankExpansionApply_preserves_baseline s g c b x y
  | fight h i p x y               => exact fightApply_preserves_baseline s h i p x y

/-- Backwards-compatible alias: the pre-Phase-14 headline name referenced from
    Manifest/Contracts. Same content, now covering all 24. -/
theorem headline_preserves_baseline (s : WorldStateLean) (a : ModeledApply) :
    preservesBaseline s (a.run s) :=
  all_actions_preserve_baseline s a

/-! ## Per-action declared-mutation contracts

Each `<action>_mutates_only_declared_fields` documents which fields the apply
intentionally changes. Stated as: every field NOT in the action's declared
mutable set equals its pre-state counterpart. The 8 baseline-field equalities
are already in `preservesBaseline` — these contracts cover the OTHER preserved
fields (per family). All proofs are `rfl` since each apply is a record-update
on a strict subset of fields. -/

/-- Move only mutates (x, y, cooldown_expires). All other fields preserved. -/
theorem move_mutates_only_declared_fields (s : WorldStateLean) (newX newY : Int) :
    let s' := moveApply s newX newY
    s'.hp = s.hp ∧ s'.max_hp = s.max_hp ∧ s'.gold = s.gold ∧
    s'.inventory = s.inventory ∧ s'.equipment = s.equipment ∧
    s'.task_code = s.task_code ∧ s'.task_type = s.task_type ∧
    s'.task_progress = s.task_progress ∧ s'.task_total = s.task_total ∧
    s'.bank_items = s.bank_items ∧ s'.bank_gold = s.bank_gold ∧
    s'.pending_items = s.pending_items ∧ s'.bank_capacity = s.bank_capacity ∧
    s'.projected_skill_xp_delta = s.projected_skill_xp_delta := by
  unfold moveApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Rest only mutates (hp, cooldown_expires). All other non-baseline fields preserved. -/
theorem rest_mutates_only_declared_fields (s : WorldStateLean) :
    let s' := restApply s
    s'.max_hp = s.max_hp ∧ s'.gold = s.gold ∧ s'.x = s.x ∧ s'.y = s.y ∧
    s'.inventory = s.inventory ∧ s'.equipment = s.equipment ∧
    s'.task_code = s.task_code ∧ s'.task_type = s.task_type ∧
    s'.task_progress = s.task_progress ∧ s'.task_total = s.task_total ∧
    s'.bank_items = s.bank_items ∧ s'.bank_gold = s.bank_gold ∧
    s'.pending_items = s.pending_items ∧ s'.bank_capacity = s.bank_capacity := by
  unfold restApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- BuyBankExpansion only mutates (gold, bank_capacity, bank_items, x, y, cooldown).
    HP, inventory, equipment, tasks, pending all preserved. -/
theorem buyBankExpansion_mutates_only_declared_fields (s : WorldStateLean) (g : Int)
    (c : Option Nat) (b : Option (List (String × Nat))) (x y : Int) :
    let s' := buyBankExpansionApply s g c b x y
    s'.hp = s.hp ∧ s'.max_hp = s.max_hp ∧
    s'.inventory = s.inventory ∧ s'.equipment = s.equipment ∧
    s'.task_code = s.task_code ∧ s'.task_type = s.task_type ∧
    s'.task_progress = s.task_progress ∧ s'.task_total = s.task_total ∧
    s'.pending_items = s.pending_items := by
  unfold buyBankExpansionApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Equip only mutates (inventory, equipment, cooldown). Position, gold, hp,
    tasks, banking all preserved — this is the load-bearing one for the gear
    swap UX. -/
theorem equip_mutates_only_declared_fields (s : WorldStateLean)
    (i : List (String × Nat)) (e : List (String × Option String)) :
    let s' := equipApply s i e
    s'.hp = s.hp ∧ s'.max_hp = s.max_hp ∧ s'.gold = s.gold ∧
    s'.x = s.x ∧ s'.y = s.y ∧
    s'.task_code = s.task_code ∧ s'.task_type = s.task_type ∧
    s'.task_progress = s.task_progress ∧ s'.task_total = s.task_total ∧
    s'.bank_items = s.bank_items ∧ s'.bank_gold = s.bank_gold ∧
    s'.pending_items = s.pending_items ∧ s'.bank_capacity = s.bank_capacity ∧
    s'.projected_skill_xp_delta = s.projected_skill_xp_delta := by
  unfold equipApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Claim only mutates (inventory, pending_items, cooldown). -/
theorem claim_mutates_only_declared_fields (s : WorldStateLean)
    (i : List (String × Nat)) (p : Option (List (String × String))) :
    let s' := claimApply s i p
    s'.hp = s.hp ∧ s'.max_hp = s.max_hp ∧ s'.gold = s.gold ∧
    s'.x = s.x ∧ s'.y = s.y ∧
    s'.equipment = s.equipment ∧
    s'.task_code = s.task_code ∧ s'.task_type = s.task_type ∧
    s'.task_progress = s.task_progress ∧ s'.task_total = s.task_total ∧
    s'.bank_items = s.bank_items ∧ s'.bank_gold = s.bank_gold ∧
    s'.bank_capacity = s.bank_capacity ∧
    s'.projected_skill_xp_delta = s.projected_skill_xp_delta := by
  unfold claimApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Fight only mutates (hp, inventory, task_progress, x, y, cooldown). Equipment,
    gold, max_hp, task_code/type/total, banking, pending all preserved. -/
theorem fight_mutates_only_declared_fields (s : WorldStateLean) (h : Nat)
    (i : List (String × Nat)) (p : Nat) (x y : Int) :
    let s' := fightApply s h i p x y
    s'.max_hp = s.max_hp ∧ s'.gold = s.gold ∧
    s'.equipment = s.equipment ∧
    s'.task_code = s.task_code ∧ s'.task_type = s.task_type ∧
    s'.task_total = s.task_total ∧
    s'.bank_items = s.bank_items ∧ s'.bank_gold = s.bank_gold ∧
    s'.pending_items = s.pending_items ∧ s'.bank_capacity = s.bank_capacity ∧
    s'.projected_skill_xp_delta = s.projected_skill_xp_delta := by
  unfold fightApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Non-vacuity witnesses

Concrete states + apply → result with the 8 fields preserved AND the mutable
fields actually changing. These pin the property is real, not vacuously true
via an unsatisfiable hypothesis. -/

/-- Sample state with NON-ZERO baseline fields (mirrors the probe-witness
    state from the differential test). -/
def witnessState : WorldStateLean :=
  { hp := 50, max_hp := 100, gold := 100, x := 0, y := 0
  , inventory := [("sword", 1)]
  , equipment := [("weapon_slot", none)]
  , cooldown_expires := none
  , task_code := none, task_type := none
  , task_progress := 0, task_total := 0
  , bank_items := none, bank_gold := none
  , pending_items := none, bank_capacity := none
  , projected_skill_xp_delta := []
  , attack          := [("fire", 30)]
  , dmg             := 15
  , dmg_elements    := [("fire", 10)]
  , resistance      := [("fire", 5)]
  , critical_strike := 10
  , initiative      := 5
  , wisdom          := 12
  , skill_xp        := [("alchemy", 4500)] }

/-- Witness: Move preserves the baseline. -/
example : preservesBaseline witnessState (moveApply witnessState 1 0) :=
  moveApply_preserves_baseline witnessState 1 0

/-- Witness: Equip preserves the baseline. -/
example : preservesBaseline witnessState (equipApply witnessState [] [("weapon_slot", some "sword")]) :=
  equipApply_preserves_baseline witnessState [] [("weapon_slot", some "sword")]

/-- Witness: Fight preserves the baseline. -/
example : preservesBaseline witnessState (fightApply witnessState 30 [("egg", 1)] 1 0 0) :=
  fightApply_preserves_baseline witnessState 30 [("egg", 1)] 1 0 0

/-- Witness: Rest preserves the baseline. -/
example : preservesBaseline witnessState (restApply witnessState) :=
  restApply_preserves_baseline witnessState

/-- Witness: BuyBankExpansion preserves the baseline. -/
example : preservesBaseline witnessState
    (buyBankExpansionApply witnessState 0 (some 30) (some []) 4 0) :=
  buyBankExpansionApply_preserves_baseline witnessState 0 (some 30) (some []) 4 0

/-- Witness: the mutable fields ACTUALLY change (so the theorem is not vacuous
    by `s = s'`). -/
example : (moveApply witnessState 1 0).x ≠ witnessState.x := by decide

/-- Witness: Rest mutates hp (so the theorem is non-vacuous). -/
example : (restApply witnessState).hp ≠ witnessState.hp := by decide

/-- Witness: BuyBankExpansion mutates bank_capacity. -/
example : (buyBankExpansionApply witnessState 0 (some 30) (some []) 4 0).bank_capacity
        ≠ witnessState.bank_capacity := by decide

end Formal.ApplyBaseline
