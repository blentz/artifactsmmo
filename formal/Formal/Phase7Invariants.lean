-- @concept: items, core @property: safety
/-
Phase-7 invariants covering three independently-verifiable contracts surfaced
during the Phase-6 recon batch:

* **Target A — GatherMaterialsGoal._compute_base_value div-by-zero defense.**
  Pre-fix the function returned `1.0 - total_effective / total_needed` where
  `total_needed = sum(self._needed.values())`. The `is_satisfied` early-return
  handles the all-non-positive-quantity case (vacuously satisfied), but a
  mixed-sign `needed` whose entries sum to zero (e.g. `{a: -5, b: 5}` against an
  empty inventory) reaches the divide and crashes with `ZeroDivisionError`.
  Verified Python probe (recorded in the Phase-7 report): the pre-fix
  function raised; the post-fix guard returns 0.0. We model the structural
  contract: the gathering value function is finite and non-negative for every
  `total_needed`, with the documented `total_needed ≤ 0 ⇒ 0` branch.

* **Target D — EquipAction.is_applicable slot/type compatibility.**
  Pre-fix `is_applicable` checked inventory + level only; a slot/type mismatch
  (e.g. equipping a ring code into a helmet slot) projected successfully and
  was caught only at execute time on the server. The production caller in
  `player.py` enumerates `EquipAction(code, slot)` over `ITEM_TYPE_TO_SLOTS[
  stats.type_]`, so a mismatched slot is unreachable through the normal action
  builder, BUT the precondition is now load-bearing for any stale-plan replay
  or future caller. Post-fix `is_applicable` also requires
  `self.slot ∈ ITEM_TYPE_TO_SLOTS[stats.type_]`.

  **2026-06-10 extension — code-already-worn gate (HTTP 485).** The server
  rejects equipping an item code already worn in ANOTHER slot ("This item is
  already equipped"). Without the gate the planner projects a second copy of
  an already-worn consumable into the empty sibling utility slot, the equip
  485s with state unchanged, and the identical plan re-derives every cycle
  (the Robby utility2 livelock). `isApplicable` now also requires
  `¬ wornElsewhere`: no OTHER slot holds this item code. Keying on code (not
  slot-group occupancy) keeps two DIFFERENT codes across sibling slots legal,
  and exempting the target slot itself keeps own-slot re-equip (utility
  stacking) governed by the inventory clause alone.

* **Target E — WorldState property invariants (regression-locks).**
  Three properties on the planner state class:
    * `inventory_used = Σ inventory.values()`,
    * `inventory_free = inventory_max - inventory_used`,
    * `hp_percent = if max_hp = 0 then 1 else hp / max_hp`.
  The integer-only bookkeeping bounds (used ≥ 0 when all entries ≥ 0, the
  inventory-overflow Phase-6 fix that writers never produce used > max, and the
  div-zero guard on hp_percent) are pinned here as cheap regression-locks.

Lean core only — no mathlib. Nat arithmetic via `omega`; `Rat` for the
fractional output of `baseValue` / `hpPercent`, using the same patterns as
`Formal.ActionCostNonneg`. -/

namespace Formal.Phase7Invariants

/-! ## Target A — GatherMaterialsGoal._compute_base_value. -/

/-- Compute the rational base value. Branches:
* `totalNeeded ≤ 0`: return 0 (the Phase-7 guard).
* `totalNeeded > 0`: return `max(1, 40 * (1 - totalEffective / totalNeeded))`.
The `max(·, 1)` floor matches `max(1.0, 40.0 * fraction_remaining)`. -/
def baseValue (totalNeeded : Int) (totalEffective : Rat) : Rat :=
  if totalNeeded ≤ 0 then 0
  else
    let fracRemaining : Rat := 1 - totalEffective / (totalNeeded : Rat)
    let scaled : Rat := 40 * fracRemaining
    if scaled < 1 then 1 else scaled

/-- The div-by-zero guard branch: `totalNeeded ≤ 0` yields 0 (no division). -/
theorem baseValue_nonpos_zero (totalEffective : Rat) (totalNeeded : Int)
    (h : totalNeeded ≤ 0) : baseValue totalNeeded totalEffective = 0 := by
  unfold baseValue; simp [h]

/-- Positive-`totalNeeded` lower bound: the clamp floors the result at 1. -/
theorem baseValue_pos_ge_one (totalEffective : Rat) (totalNeeded : Int)
    (h : 0 < totalNeeded) : 1 ≤ baseValue totalNeeded totalEffective := by
  unfold baseValue
  have hnot : ¬ totalNeeded ≤ 0 := by omega
  simp [hnot]
  split
  · exact Rat.le_refl
  · rename_i hge
    exact Rat.not_lt.mp hge

/-- Non-negativity on every branch (the value is always a valid GOAP priority). -/
theorem baseValue_nonneg (totalEffective : Rat) (totalNeeded : Int) :
    0 ≤ baseValue totalNeeded totalEffective := by
  unfold baseValue
  by_cases h : totalNeeded ≤ 0
  · simp [h]
  · simp [h]
    split
    · exact (by decide : (0 : Rat) ≤ 1)
    · rename_i hge
      have : (1 : Rat) ≤ 40 * (1 - totalEffective / (totalNeeded : Rat)) :=
        Rat.not_lt.mp hge
      exact Rat.le_trans (by decide : (0 : Rat) ≤ 1) this

/-- Total: the value is always finite (definitionally — `baseValue` is total
on `(Int, Rat)`). This is the headline invariant: no input combination
diverges or raises. -/
theorem baseValue_total (totalEffective : Rat) (totalNeeded : Int) :
    ∃ v : Rat, v = baseValue totalNeeded totalEffective ∧ 0 ≤ v :=
  ⟨_, rfl, baseValue_nonneg totalEffective totalNeeded⟩

/-- Pre-fix counter-example witness: `totalNeeded = 0` (verified Python probe
with `needed = {a:-5, b:5}` summing to 0). The post-fix guard returns 0
instead of dividing. -/
theorem baseValue_total_needed_zero_returns_zero (totalEffective : Rat) :
    baseValue 0 totalEffective = 0 := by
  unfold baseValue; simp

/-- Negative `totalNeeded` also returns 0 (the guard catches `≤ 0`, not just `=0`). -/
theorem baseValue_total_needed_neg_returns_zero (totalEffective : Rat) :
    baseValue (-3) totalEffective = 0 := by
  unfold baseValue; simp

/-! ## Target D — EquipAction.is_applicable slot/type compatibility. -/

/-- Minimal item-stats projection: just the level requirement and the item
type (the string identifier — modeled as `Nat` for decidability). -/
structure ItemStats where
  itemType : Nat
  level : Nat
  deriving Repr, DecidableEq

/-- Minimal state projection: the planner-relevant fields. `equipment` is the
worn-gear map as (slot, itemCode) pairs — only occupied slots appear (the
Python `state.equipment` maps empty slots to `None`, which can never equal a
real item code, so omitting them is faithful). `itemCode` is the candidate
item's code (`self.code`). -/
structure EquipState where
  invQty : Nat       -- inventory count of the candidate code
  charLevel : Nat
  itemCode : Nat     -- the candidate code being equipped (`self.code`)
  equipment : List (Nat × Nat)  -- occupied (slot, code) pairs
  deriving Repr, DecidableEq

/-- Slot table: `ITEM_TYPE_TO_SLOTS` in `equip.py`. A type maps to the list
of equipment-slot codes (also modeled as `Nat`) it can occupy. Unknown types
return `[]`. -/
def SlotTable : Type := Nat → List Nat

/-- The HTTP-485 clause: the candidate code is already worn in some slot
OTHER than the target slot. Mirrors
`any(equipped == self.code for slot, equipped in state.equipment.items()
     if slot != self.slot)` in `equip.py`. -/
def wornElsewhere (equipment : List (Nat × Nat)) (itemCode slot : Nat) : Bool :=
  equipment.any (fun p => p.2 == itemCode && p.1 != slot)

/-- Post-fix `is_applicable` (2026-06-10: plus the code-already-worn gate). -/
def isApplicable (st : EquipState) (stats : Option ItemStats) (slot : Nat)
    (tbl : SlotTable) : Bool :=
  match stats with
  | none => false
  | some s =>
    decide (0 < st.invQty) &&
      decide (slot ∈ tbl s.itemType) &&
      !wornElsewhere st.equipment st.itemCode slot &&
      decide (s.level ≤ st.charLevel)

/-- Slot/type contract: a passing precondition implies the slot is a valid
equip-target for the item's type. -/
theorem isApplicable_imp_slot_in_table
    (st : EquipState) (stats : Option ItemStats) (slot : Nat) (tbl : SlotTable) :
    isApplicable st stats slot tbl = true →
      ∃ s, stats = some s ∧ slot ∈ tbl s.itemType := by
  intro h
  unfold isApplicable at h
  cases stats with
  | none => simp at h
  | some s => simp at h; exact ⟨s, rfl, h.1.1.2⟩

/-- Inventory contract: a passing precondition implies the code is held. -/
theorem isApplicable_imp_inv_pos
    (st : EquipState) (stats : Option ItemStats) (slot : Nat) (tbl : SlotTable) :
    isApplicable st stats slot tbl = true → 0 < st.invQty := by
  intro h
  unfold isApplicable at h
  cases stats with
  | none => simp at h
  | some s => simp at h; exact h.1.1.1

/-- HTTP-485 contract: a passing precondition implies the candidate code is
NOT already worn in another slot — so the planner can never emit the
server-doomed second-copy equip (the Robby utility2 livelock). -/
theorem isApplicable_imp_not_worn_elsewhere
    (st : EquipState) (stats : Option ItemStats) (slot : Nat) (tbl : SlotTable) :
    isApplicable st stats slot tbl = true →
      wornElsewhere st.equipment st.itemCode slot = false := by
  intro h
  unfold isApplicable at h
  cases stats with
  | none => simp at h
  | some s => simp at h; exact h.1.2

/-- Level contract: a passing precondition implies the character meets the
level requirement. -/
theorem isApplicable_imp_level_ge
    (st : EquipState) (stats : Option ItemStats) (slot : Nat) (tbl : SlotTable) :
    isApplicable st stats slot tbl = true →
      ∃ s, stats = some s ∧ s.level ≤ st.charLevel := by
  intro h
  unfold isApplicable at h
  cases stats with
  | none => simp at h
  | some s => simp at h; exact ⟨s, rfl, h.2⟩

/-- Code-already-worn regression-pin: when the candidate code is worn in a
different slot, the precondition refuses — even with inventory, level, and
slot/type all fine. -/
theorem isApplicable_worn_elsewhere_refused
    (st : EquipState) (s : ItemStats) (slot : Nat) (tbl : SlotTable)
    (hworn : wornElsewhere st.equipment st.itemCode slot = true) :
    isApplicable st (some s) slot tbl = false := by
  unfold isApplicable
  simp [hworn]

/-- Mismatched-slot regression-pin: a verified-bug input (helmet slot for a
ring) is now refused, even when level + inventory are fine. -/
theorem isApplicable_slot_mismatch_refused
    (st : EquipState) (s : ItemStats) (slot : Nat) (tbl : SlotTable)
    (_hinv : 0 < st.invQty) (_hlvl : s.level ≤ st.charLevel)
    (hslot : slot ∉ tbl s.itemType) :
    isApplicable st (some s) slot tbl = false := by
  unfold isApplicable
  simp [hslot]

/-- No-stats refused: missing item stats refuses. -/
theorem isApplicable_no_stats_refused
    (st : EquipState) (slot : Nat) (tbl : SlotTable) :
    isApplicable st none slot tbl = false := by
  unfold isApplicable; rfl

/-- Boundary witness: matched slot + held inventory + met level + nothing
worn ⇒ accepted. -/
theorem isApplicable_boundary_witness :
    let tbl : SlotTable := fun t => if t = 7 then [3, 4] else []
    let s : ItemStats := { itemType := 7, level := 1 }
    let st : EquipState := { invQty := 1, charLevel := 1, itemCode := 42, equipment := [] }
    isApplicable st (some s) 3 tbl = true := by decide

/-- Pre-fix bug counter-example: ring (`itemType = 7`, slots `{ring1, ring2} =
{3, 4}`) attempted into helmet (`slot = 9`) — pre-fix accepted (inv + level
ok), post-fix refuses. -/
theorem isApplicable_ring_into_helmet_refused :
    let tbl : SlotTable := fun t => if t = 7 then [3, 4] else []
    let s : ItemStats := { itemType := 7, level := 1 }
    let st : EquipState := { invQty := 1, charLevel := 1, itemCode := 42, equipment := [] }
    isApplicable st (some s) 9 tbl = false := by decide

/-- 2026-06-10 livelock counter-example (the Robby trace): utility
(`itemType = 9`, slots `{utility1, utility2} = {112, 113}`), the code (42)
already worn in utility1 (112), second copy targeted at the EMPTY utility2
(113) — pre-fix accepted (inv + slot + level ok), the server 485s forever;
post-fix refuses. -/
theorem isApplicable_same_code_sibling_refused :
    let tbl : SlotTable := fun t => if t = 9 then [112, 113] else []
    let s : ItemStats := { itemType := 9, level := 1 }
    let st : EquipState :=
      { invQty := 1, charLevel := 1, itemCode := 42, equipment := [(112, 42)] }
    isApplicable st (some s) 113 tbl = false := by decide

/-- Legality witness promised by the gate's comment: a DIFFERENT code (7)
worn in utility1 does not block code 42 from the sibling utility2 — the gate
keys on item code, not slot-group occupancy. -/
theorem isApplicable_different_code_sibling_accepted :
    let tbl : SlotTable := fun t => if t = 9 then [112, 113] else []
    let s : ItemStats := { itemType := 9, level := 1 }
    let st : EquipState :=
      { invQty := 1, charLevel := 1, itemCode := 42, equipment := [(112, 7)] }
    isApplicable st (some s) 113 tbl = true := by decide

/-- Own-slot exemption witness: the code already worn in the TARGET slot
itself (utility stacking / re-equip) is not "worn elsewhere"; with a spare
copy in inventory the precondition still accepts. -/
theorem isApplicable_own_slot_reequip_accepted :
    let tbl : SlotTable := fun t => if t = 9 then [112, 113] else []
    let s : ItemStats := { itemType := 9, level := 1 }
    let st : EquipState :=
      { invQty := 1, charLevel := 1, itemCode := 42, equipment := [(112, 42)] }
    isApplicable st (some s) 112 tbl = true := by decide

/-! ## Target E — WorldState property invariants. -/

/-- Minimal inventory projection. -/
structure WS where
  inventory : List (Nat × Nat)
  invMax : Nat
  hp : Nat
  maxHp : Nat
  deriving Repr

def inventoryUsed (s : WS) : Nat := (s.inventory.map Prod.snd).sum

def inventoryFree (s : WS) : Nat := s.invMax - inventoryUsed s

/-- `hp_percent`: 1 when maxHp = 0, else hp / maxHp. -/
def hpPercent (s : WS) : Rat :=
  if s.maxHp = 0 then 1
  else (s.hp : Rat) / (s.maxHp : Rat)

theorem inventoryUsed_nonneg (s : WS) : 0 ≤ inventoryUsed s := Nat.zero_le _

theorem inventoryUsed_eq_sum (s : WS) :
    inventoryUsed s = (s.inventory.map Prod.snd).sum := rfl

theorem inventoryFree_eq_diff (s : WS) :
    inventoryFree s = s.invMax - inventoryUsed s := rfl

/-- Capacity invariant: if `used ≤ max`, then `free + used = max`. -/
theorem inventoryFree_plus_used_eq_max (s : WS) (h : inventoryUsed s ≤ s.invMax) :
    inventoryFree s + inventoryUsed s = s.invMax := by
  unfold inventoryFree; omega

theorem hpPercent_maxhp_zero (s : WS) (h : s.maxHp = 0) : hpPercent s = 1 := by
  unfold hpPercent; simp [h]

theorem hpPercent_maxhp_pos (s : WS) (h : s.maxHp ≠ 0) :
    hpPercent s = (s.hp : Rat) / (s.maxHp : Rat) := by
  unfold hpPercent; simp [h]

/-- `hp_percent` is always non-negative. -/
theorem hpPercent_nonneg (s : WS) : 0 ≤ hpPercent s := by
  unfold hpPercent
  by_cases h : s.maxHp = 0
  · simp [h]; decide
  · simp [h]
    rw [Rat.div_def]
    apply Rat.mul_nonneg
    · exact_mod_cast Nat.zero_le _
    · apply Rat.le_of_lt
      apply Rat.inv_pos.mpr
      have : 0 < s.maxHp := Nat.pos_of_ne_zero h
      exact_mod_cast this

/-- All-empty inventory ⇒ used = 0. -/
theorem inventoryUsed_empty (max hp maxHp : Nat) :
    inventoryUsed { inventory := [], invMax := max, hp := hp, maxHp := maxHp } = 0 := by
  unfold inventoryUsed; simp

theorem inventoryFree_empty (max hp maxHp : Nat) :
    inventoryFree { inventory := [], invMax := max, hp := hp, maxHp := maxHp } = max := by
  unfold inventoryFree; simp [inventoryUsed_empty]

theorem inventoryUsed_singleton_witness :
    inventoryUsed { inventory := [(0, 5)], invMax := 10, hp := 10, maxHp := 10 } = 5 := by
  decide

theorem inventoryFree_singleton_witness :
    inventoryFree { inventory := [(0, 5)], invMax := 10, hp := 10, maxHp := 10 } = 5 := by
  decide

/-- Regression-pin for the Phase-6 overflow case: at `used = max`, `free = 0`. -/
theorem inventoryFree_at_full_is_zero :
    inventoryFree { inventory := [(0, 10)], invMax := 10, hp := 10, maxHp := 10 } = 0 := by
  decide

theorem hpPercent_max_hp_zero_witness :
    hpPercent { inventory := [], invMax := 0, hp := 0, maxHp := 0 } = 1 := by
  decide

end Formal.Phase7Invariants
