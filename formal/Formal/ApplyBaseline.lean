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

**All 25 actions are modeled below**, grouped by structural family:

  1. **Position**: Move, MoveSemantic, MapTransition, Teleport (+inventory)
  2. **Inventory-mint**: Gather, NpcBuy, WithdrawGold, WithdrawItem, Claim
  3. **Inventory-consume**: Craft, Recycle, NpcSell, DepositGold, DepositAll,
     UseConsumable, Delete
  4. **Equipment-swap**: Equip, Unequip, OptimizeLoadout. Since Task 14f these
     do NOT preserve the gear-moved totals: the sheet's invariant is
     totals = base + worn non-utility gear (measured live, Task 14b), so a
     planned swap writes the totals `project_loadout_stats` projects
     (`equipment/projection.py:wear_gear`). They preserve `skill_xp`, and the
     whole baseline when the swap moves no stat (`t = totalsOf s`).
  5. **Task transition**: AcceptTask, CompleteTask, TaskCancel, TaskExchange,
     TaskTrade
  6. **Misc**: Rest (hp restore), BuyBankExpansion (bank_capacity)
  7. **Fight**: combat + task_progress + cooldown + hp

The headline `all_actions_preserve_baseline` enumerates the union, for every
action but the swaps; `all_actions_preserve_skill_xp` covers all of them.

Lean core only — no mathlib. Axioms ⊆ {propext, Classical.choice, Quot.sound}.
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

/-! ## Family 1 — Position

`MoveAction`, `MoveTo` (`movement_semantic`), `MapTransitionAction` mutate ONLY
position fields (`x`, `y`) and clear `cooldown_expires`. `TeleportAction`
(PLAN #6b) also lives here: it sets position and clears cooldown like the others,
but additionally decrements the consumed teleport item in `inventory`. None of
the four touches a baseline stat field. -/

/-- `MoveAction.apply` model: `dataclasses.replace(state, x, y, cooldown_expires=None)`. -/
def moveApply (s : WorldStateLean) (newX newY : Int) : WorldStateLean :=
  { s with x := newX, y := newY, cooldown_expires := none }

/-- `MoveTo.apply` model (movement_semantic.py): same shape as Move. -/
def moveSemanticApply (s : WorldStateLean) (newX newY : Int) : WorldStateLean :=
  { s with x := newX, y := newY, cooldown_expires := none }

/-- `MapTransitionAction.apply` model: identity transition (no fields change). -/
def mapTransitionApply (s : WorldStateLean) : WorldStateLean := s

/-- `TeleportAction.apply` model (PLAN #6b): warp to the consumable's destination
    — position set, the teleport item decremented in inventory, cooldown cleared. -/
def teleportApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newX newY : Int) : WorldStateLean :=
  { s with x := newX, y := newY, inventory := newInv, cooldown_expires := none }

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

theorem teleportApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (newX newY : Int) :
    preservesBaseline s (teleportApply s i newX newY) := by
  unfold preservesBaseline teleportApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 2 — Inventory-mint

`GatherAction`, `NpcBuyAction`, `WithdrawGoldAction`, `WithdrawItemAction`,
`ClaimPendingItemAction`. Inventory (or gold) grows; cooldown cleared. -/

/-- `GatherAction.apply` model: inventory grows by one drop. Position move +
    cooldown clear also occur in the Python source. -/
def gatherApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv
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
    (x y : Int) :
    preservesBaseline s (gatherApply s i x y) := by
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

/-- `CraftAction.apply` model: inventory consumed/minted; position moves to
    workshop; cooldown cleared. -/
def craftApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newX newY : Int) : WorldStateLean :=
  { s with inventory := newInv
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

/-- `UseGoldBagAction.apply` model: gold up, inventory down (same shape as
    `npcSellApply` minus position, like `useConsumableApply` crediting gold not hp). -/
def useGoldBagApply (s : WorldStateLean) (newGold : Int)
    (newInv : List (String × Nat)) : WorldStateLean :=
  { s with gold := newGold, inventory := newInv, cooldown_expires := none }

/-- `DeleteItemAction.apply` model: inventory shrinks. -/
def deleteApply (s : WorldStateLean) (newInv : List (String × Nat)) : WorldStateLean :=
  { s with inventory := newInv, cooldown_expires := none }

theorem craftApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (x y : Int) :
    preservesBaseline s (craftApply s i x y) := by
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

theorem useGoldBagApply_preserves_baseline (s : WorldStateLean) (g : Int)
    (i : List (String × Nat)) :
    preservesBaseline s (useGoldBagApply s g i) := by
  unfold preservesBaseline useGoldBagApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem deleteApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) :
    preservesBaseline s (deleteApply s i) := by
  unfold preservesBaseline deleteApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Family 4 — Equipment-swap

`EquipAction`, `UnequipAction`, `OptimizeLoadoutAction`. Inventory and
equipment rearranged; cooldown cleared; the gear totals moved (Task 14f).

The server reports totals only (base + worn non-utility gear). A swap keeps
that invariant by moving each total by the changed slots: the new item's stat
in, the displaced item's stat out (`swapStat`). Python computes the moved
totals with `project_loadout_stats`, the one stat arithmetic, and writes them
(`wear_gear`).

THE MODEL ABSTRACTS THE TOTALS: a swap takes them as the `GearTotals`
argument `t` and does not compute them from item stats, so
`*_writes_totals` holds by construction, and `swapStat_roundtrip` is the
integer identity behind the per-slot delta, not a theorem about the applies.
The round trip of the real transitions (apply then the reverse apply restores
every total) is enforced by the Python tests (`test_planned_totals`,
`test_apply_baseline_diff`'s swap property). What the model does prove about
the applies: the baseline is kept when `t` moves nothing, `skill_xp` always,
and HP never exceeds the moved max HP (`*_hp_le_max_hp`: the swap clamps HP,
as the server does). A utility slot moves no total (a worn potion is not in
the sheet). -/

/-- The totals a swap moves, as `WorldStateLean` carries them. -/
structure GearTotals where
  max_hp          : Nat
  attack          : List (String × Nat)
  dmg             : Int
  dmg_elements    : List (String × Nat)
  resistance      : List (String × Nat)
  critical_strike : Nat
  initiative      : Nat
  wisdom          : Nat
  deriving Repr, DecidableEq

/-- The totals a state carries. -/
def totalsOf (s : WorldStateLean) : GearTotals :=
  { max_hp := s.max_hp, attack := s.attack, dmg := s.dmg
  , dmg_elements := s.dmg_elements, resistance := s.resistance
  , critical_strike := s.critical_strike, initiative := s.initiative
  , wisdom := s.wisdom }

/-- `s` carrying the totals `t`. -/
def withTotals (s : WorldStateLean) (t : GearTotals) : WorldStateLean :=
  { s with hp := min s.hp t.max_hp, max_hp := t.max_hp, attack := t.attack, dmg := t.dmg
         , dmg_elements := t.dmg_elements, resistance := t.resistance
         , critical_strike := t.critical_strike, initiative := t.initiative
         , wisdom := t.wisdom }

/-- One total moved by one slot's swap: the incoming item's stat in, the
    displaced item's out (`project_loadout_stats`'s per-slot delta; an empty
    slot contributes 0). -/
def swapStat (total incoming displaced : Int) : Int := total + incoming - displaced

/-- The integer identity behind a swap's round trip: moving a total in and
    back out restores it. The applies take their totals abstractly (`t`), so
    this does not by itself prove the transitions round-trip; the Python tests
    do (module doc of this section). -/
theorem swapStat_roundtrip (total a b : Int) :
    swapStat (swapStat total a b) b a = total := by
  unfold swapStat; omega

/-- A slot that keeps its item moves nothing. -/
theorem swapStat_same (total c : Int) : swapStat total c c = total := by
  unfold swapStat; omega

/-- `EquipAction.apply` model: inventory + equipment updated, totals moved. -/
def equipApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newEq : List (String × Option String)) (t : GearTotals) : WorldStateLean :=
  { withTotals s t with inventory := newInv, equipment := newEq, cooldown_expires := none }

/-- `UnequipAction.apply` model: inventory + equipment updated, totals moved. -/
def unequipApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newEq : List (String × Option String)) (t : GearTotals) : WorldStateLean :=
  { withTotals s t with inventory := newInv, equipment := newEq, cooldown_expires := none }

/-- `OptimizeLoadoutAction.apply` model: same shape as Equip. -/
def optimizeLoadoutApply (s : WorldStateLean) (newInv : List (String × Nat))
    (newEq : List (String × Option String)) (t : GearTotals) : WorldStateLean :=
  { withTotals s t with inventory := newInv, equipment := newEq, cooldown_expires := none }

/-- A swap carries exactly the totals it is given (true by construction:
    the totals are abstract). -/
theorem equipApply_writes_totals (s : WorldStateLean) (i : List (String × Nat))
    (e : List (String × Option String)) (t : GearTotals) :
    totalsOf (equipApply s i e t) = t := by
  cases t; rfl

/-- A swap never leaves HP above the moved max HP: it clamps (the server
    does; learning.db: no recorded sheet reads hp > max_hp). -/
theorem equipApply_hp_le_max_hp (s : WorldStateLean) (i : List (String × Nat))
    (e : List (String × Option String)) (t : GearTotals) :
    (equipApply s i e t).hp ≤ (equipApply s i e t).max_hp := by
  show min s.hp t.max_hp ≤ t.max_hp
  exact Nat.min_le_right _ _

theorem unequipApply_hp_le_max_hp (s : WorldStateLean) (i : List (String × Nat))
    (e : List (String × Option String)) (t : GearTotals) :
    (unequipApply s i e t).hp ≤ (unequipApply s i e t).max_hp := by
  show min s.hp t.max_hp ≤ t.max_hp
  exact Nat.min_le_right _ _

theorem optimizeLoadoutApply_hp_le_max_hp (s : WorldStateLean) (i : List (String × Nat))
    (e : List (String × Option String)) (t : GearTotals) :
    (optimizeLoadoutApply s i e t).hp ≤ (optimizeLoadoutApply s i e t).max_hp := by
  show min s.hp t.max_hp ≤ t.max_hp
  exact Nat.min_le_right _ _

theorem unequipApply_writes_totals (s : WorldStateLean) (i : List (String × Nat))
    (e : List (String × Option String)) (t : GearTotals) :
    totalsOf (unequipApply s i e t) = t := by
  cases t; rfl

theorem optimizeLoadoutApply_writes_totals (s : WorldStateLean) (i : List (String × Nat))
    (e : List (String × Option String)) (t : GearTotals) :
    totalsOf (optimizeLoadoutApply s i e t) = t := by
  cases t; rfl

/-- A swap that moves no stat preserves the whole baseline. -/
theorem equipApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (e : List (String × Option String)) (t : GearTotals)
    (ht : t = totalsOf s) :
    preservesBaseline s (equipApply s i e t) := by
  subst ht
  unfold preservesBaseline equipApply withTotals totalsOf
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem unequipApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (e : List (String × Option String)) (t : GearTotals)
    (ht : t = totalsOf s) :
    preservesBaseline s (unequipApply s i e t) := by
  subst ht
  unfold preservesBaseline unequipApply withTotals totalsOf
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem optimizeLoadoutApply_preserves_baseline (s : WorldStateLean)
    (i : List (String × Nat)) (e : List (String × Option String)) (t : GearTotals)
    (ht : t = totalsOf s) :
    preservesBaseline s (optimizeLoadoutApply s i e t) := by
  subst ht
  unfold preservesBaseline optimizeLoadoutApply withTotals totalsOf
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
cooldown cleared, inventory may grow with drops, and the pocket gains the
gold one win pays (plan B Task 15, ruling T15d: `win_gold`, the mean of the
API's `min_gold`/`max_gold`, so the planner sees a gold leg's progress). -/

/-- `FightAction.apply` model: hp/gold/inventory/task_progress mutated;
    cooldown. `newGold` is `s.gold + win_gold`. -/
def fightApply (s : WorldStateLean) (newHp : Nat) (newGold : Int)
    (newInv : List (String × Nat)) (newProgress : Nat)
    (newX newY : Int) : WorldStateLean :=
  { s with hp := newHp, gold := newGold, inventory := newInv, task_progress := newProgress
         , x := newX, y := newY, cooldown_expires := none }

theorem fightApply_preserves_baseline (s : WorldStateLean) (h : Nat) (g : Int)
    (i : List (String × Nat)) (p : Nat) (x y : Int) :
    preservesBaseline s (fightApply s h g i p x y) := by
  unfold preservesBaseline fightApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-! ## Headline: the uniform contract holds across ALL 25 modeled actions.

Quantifies over an exhaustive enumeration of the 25 modeled `apply` functions
so a single statement seals the property for every modeled action — closing
the Phase-4 disclosed gap. -/

/-- Exhaustive enumeration of all 25 modeled apply functions. Each constructor
    packs the action + its arguments. -/
inductive ModeledApply where
  -- Family 1: position-only
  | move              (newX newY : Int) : ModeledApply
  | moveSemantic      (newX newY : Int) : ModeledApply
  | mapTransition                       : ModeledApply
  | teleport          (newInv : List (String × Nat))
                      (newX newY : Int) : ModeledApply
  -- Family 2: inventory-mint
  | gather            (newInv : List (String × Nat))
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
  | useGoldBag        (newGold : Int) (newInv : List (String × Nat)) : ModeledApply
  | delete            (newInv : List (String × Nat)) : ModeledApply
  -- Family 4: equipment-swap
  | equip             (newInv : List (String × Nat))
                      (newEq : List (String × Option String)) (t : GearTotals) : ModeledApply
  | unequip           (newInv : List (String × Nat))
                      (newEq : List (String × Option String)) (t : GearTotals) : ModeledApply
  | optimizeLoadout   (newInv : List (String × Nat))
                      (newEq : List (String × Option String)) (t : GearTotals) : ModeledApply
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
  | fight             (h : Nat) (g : Int) (i : List (String × Nat)) (p : Nat)
                      (x y : Int) : ModeledApply

/-- Dispatch: run an enumerated action on a state. -/
def ModeledApply.run (a : ModeledApply) (s : WorldStateLean) : WorldStateLean :=
  match a with
  | .move x y                       => moveApply s x y
  | .moveSemantic x y               => moveSemanticApply s x y
  | .mapTransition                  => mapTransitionApply s
  | .teleport i x y                 => teleportApply s i x y
  | .gather i x y                   => gatherApply s i x y
  | .npcBuy g i x y                 => npcBuyApply s g i x y
  | .withdrawGold g bg x y          => withdrawGoldApply s g bg x y
  | .withdrawItem i b x y           => withdrawItemApply s i b x y
  | .claim i p                      => claimApply s i p
  | .craft i x y                    => craftApply s i x y
  | .recycle i x y                  => recycleApply s i x y
  | .npcSell i g x y                => npcSellApply s i g x y
  | .depositGold g bg x y           => depositGoldApply s g bg x y
  | .depositAll i b x y             => depositAllApply s i b x y
  | .useConsumable h i              => useConsumableApply s h i
  | .useGoldBag g i                 => useGoldBagApply s g i
  | .delete i                       => deleteApply s i
  | .equip i e t                    => equipApply s i e t
  | .unequip i e t                  => unequipApply s i e t
  | .optimizeLoadout i e t          => optimizeLoadoutApply s i e t
  | .acceptTask c t p tot x y       => acceptTaskApply s c t p tot x y
  | .completeTask c t p tot pe x y  => completeTaskApply s c t p tot pe x y
  | .taskCancel c t p tot i x y     => taskCancelApply s c t p tot i x y
  | .taskExchange i pe x y          => taskExchangeApply s i pe x y
  | .taskTrade i p x y              => taskTradeApply s i p x y
  | .rest                           => restApply s
  | .buyBankExpansion g c b x y     => buyBankExpansionApply s g c b x y
  | .fight h g i p x y              => fightApply s h g i p x y

/-- The totals an action writes: a swap's `t` (Task 14f), none otherwise. -/
def ModeledApply.swapTotals : ModeledApply → Option GearTotals
  | .equip _ _ t           => some t
  | .unequip _ _ t         => some t
  | .optimizeLoadout _ _ t => some t
  | _                      => none

/-- **HEADLINE — Phase-14 disclosed-gap closure**: every one of the 25 modeled
    apply transitions preserves the 8-field baseline, unless it is a swap that
    moves a total (Task 14f: a swap writes the totals the gear it changes
    moves; `equipApply_writes_totals`). -/
theorem all_actions_preserve_baseline (s : WorldStateLean) (a : ModeledApply)
    (ha : ∀ t, a.swapTotals = some t → t = totalsOf s) :
    preservesBaseline s (a.run s) := by
  cases a with
  | move x y                      => exact moveApply_preserves_baseline s x y
  | moveSemantic x y              => exact moveSemanticApply_preserves_baseline s x y
  | mapTransition                 => exact mapTransitionApply_preserves_baseline s
  | teleport i x y                => exact teleportApply_preserves_baseline s i x y
  | gather i x y                  => exact gatherApply_preserves_baseline s i x y
  | npcBuy g i x y                => exact npcBuyApply_preserves_baseline s g i x y
  | withdrawGold g bg x y         => exact withdrawGoldApply_preserves_baseline s g bg x y
  | withdrawItem i b x y          => exact withdrawItemApply_preserves_baseline s i b x y
  | claim i p                     => exact claimApply_preserves_baseline s i p
  | craft i x y                   => exact craftApply_preserves_baseline s i x y
  | recycle i x y                 => exact recycleApply_preserves_baseline s i x y
  | npcSell i g x y               => exact npcSellApply_preserves_baseline s i g x y
  | depositGold g bg x y          => exact depositGoldApply_preserves_baseline s g bg x y
  | depositAll i b x y            => exact depositAllApply_preserves_baseline s i b x y
  | useConsumable h i             => exact useConsumableApply_preserves_baseline s h i
  | useGoldBag g i                => exact useGoldBagApply_preserves_baseline s g i
  | delete i                      => exact deleteApply_preserves_baseline s i
  | equip i e t                   => exact equipApply_preserves_baseline s i e t (ha t rfl)
  | unequip i e t                 => exact unequipApply_preserves_baseline s i e t (ha t rfl)
  | optimizeLoadout i e t         => exact optimizeLoadoutApply_preserves_baseline s i e t (ha t rfl)
  | acceptTask c t p tot x y      => exact acceptTaskApply_preserves_baseline s c t p tot x y
  | completeTask c t p tot pe x y => exact completeTaskApply_preserves_baseline s c t p tot pe x y
  | taskCancel c t p tot i x y    => exact taskCancelApply_preserves_baseline s c t p tot i x y
  | taskExchange i pe x y         => exact taskExchangeApply_preserves_baseline s i pe x y
  | taskTrade i p x y             => exact taskTradeApply_preserves_baseline s i p x y
  | rest                          => exact restApply_preserves_baseline s
  | buyBankExpansion g c b x y    => exact buyBankExpansionApply_preserves_baseline s g c b x y
  | fight h g i p x y             => exact fightApply_preserves_baseline s h g i p x y

/-- Backwards-compatible alias: the pre-Phase-14 headline name referenced from
    Manifest/Contracts. Same content, now covering all 24. -/
theorem headline_preserves_baseline (s : WorldStateLean) (a : ModeledApply)
    (ha : ∀ t, a.swapTotals = some t → t = totalsOf s) :
    preservesBaseline s (a.run s) :=
  all_actions_preserve_baseline s a ha

/-- Every modeled apply, a swap included, preserves `skill_xp`: no gear moves
    a skill's xp. -/
theorem all_actions_preserve_skill_xp (s : WorldStateLean) (a : ModeledApply) :
    (a.run s).skill_xp = s.skill_xp := by
  cases a <;> rfl

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
    s'.pending_items = s.pending_items ∧ s'.bank_capacity = s.bank_capacity := by
  unfold moveApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

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

/-- Equip only mutates (inventory, equipment, cooldown, the gear totals incl.
    max_hp, and hp clamped to it, Task 14f). Position, gold, tasks, banking all
    preserved —
    this is the load-bearing one for the gear swap UX. -/
theorem equip_mutates_only_declared_fields (s : WorldStateLean)
    (i : List (String × Nat)) (e : List (String × Option String)) (t : GearTotals) :
    let s' := equipApply s i e t
    s'.gold = s.gold ∧
    s'.x = s.x ∧ s'.y = s.y ∧
    s'.task_code = s.task_code ∧ s'.task_type = s.task_type ∧
    s'.task_progress = s.task_progress ∧ s'.task_total = s.task_total ∧
    s'.bank_items = s.bank_items ∧ s'.bank_gold = s.bank_gold ∧
    s'.pending_items = s.pending_items ∧ s'.bank_capacity = s.bank_capacity := by
  unfold equipApply withTotals
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

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
    s'.bank_capacity = s.bank_capacity := by
  unfold claimApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Fight only mutates (hp, gold, inventory, task_progress, x, y, cooldown):
    gold becomes the declared `g` (`s.gold + win_gold`, ruling T15d).
    Equipment, max_hp, task_code/type/total, banking, pending all preserved. -/
theorem fight_mutates_only_declared_fields (s : WorldStateLean) (h : Nat) (g : Int)
    (i : List (String × Nat)) (p : Nat) (x y : Int) :
    let s' := fightApply s h g i p x y
    s'.gold = g ∧ s'.max_hp = s.max_hp ∧
    s'.equipment = s.equipment ∧
    s'.task_code = s.task_code ∧ s'.task_type = s.task_type ∧
    s'.task_total = s.task_total ∧
    s'.bank_items = s.bank_items ∧ s'.bank_gold = s.bank_gold ∧
    s'.pending_items = s.pending_items ∧ s'.bank_capacity = s.bank_capacity := by
  unfold fightApply
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

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

/-- Witness: an Equip of a stat-less sword preserves the baseline. -/
example : preservesBaseline witnessState
    (equipApply witnessState [] [("weapon_slot", some "sword")] (totalsOf witnessState)) :=
  equipApply_preserves_baseline witnessState [] [("weapon_slot", some "sword")]
    (totalsOf witnessState) rfl

/-- Witness: a swap that lowers max HP to 40 clamps HP 50 to 40 (the clamp
    theorems are not vacuous). -/
example : (equipApply witnessState [] [("body_armor_slot", none)]
      { totalsOf witnessState with max_hp := 40 }).hp = 40 := by decide

/-- Witness: an Equip of a +10 fire sword moves the fire attack 30 -> 40, and
    the Unequip back round-trips it (so the swap hypothesis of the headline is
    not vacuous: a swap CAN move a total). -/
example : swapStat 30 10 0 = 40 := by decide
example : swapStat (swapStat 30 10 0) 0 10 = 30 := swapStat_roundtrip 30 10 0
example : (equipApply witnessState [] [("weapon_slot", some "sword")]
      { totalsOf witnessState with attack := [("fire", 40)] }).attack
    ≠ witnessState.attack := by decide

/-- Witness: Fight preserves the baseline. -/
example : preservesBaseline witnessState (fightApply witnessState 30 104 [("egg", 1)] 1 0 0) :=
  fightApply_preserves_baseline witnessState 30 104 [("egg", 1)] 1 0 0

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

/-- Witness: Fight mutates gold (a win's 4 gold, ruling T15d), so its declared
    gold mutation is non-vacuous. -/
example : (fightApply witnessState 30 104 [("egg", 1)] 1 0 0).gold ≠ witnessState.gold := by
  decide

/-- Witness: BuyBankExpansion mutates bank_capacity. -/
example : (buyBankExpansionApply witnessState 0 (some 30) (some []) 4 0).bank_capacity
        ≠ witnessState.bank_capacity := by decide

end Formal.ApplyBaseline
