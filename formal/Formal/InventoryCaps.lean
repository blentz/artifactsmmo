/-
Formal model of `useful_quantity_cap` / `overstocked_items` from
`src/artifactsmmo_cli/ai/inventory_caps.py`.

The Python routine computes a per-item "useful quantity cap" — the maximum count
worth keeping; anything beyond is overstock. The cap is the max of FIVE
components (`useful_quantity_cap_excl_equipped`):

    recipe_cap     = (if recipe_max > 0 then max(recipe_max * BATCH_BUFFER, SAFETY_FLOOR) else 0)
    task_cap       = chain demand (active items-task transitive recipe input demand for this item, else 0)
    action_cap     = ACTION_CONSUMABLES_CAP[code]  (999 for tasks_coin post-602f7b4 — stacking-aware; else 0)
    equippable_cap = EQUIPPABLE_KEEP=1 if `ITEM_TYPE_TO_SLOTS.get(type_)` truthy AND NOT dominated by owned same-slot peers (55bc4d6, 1e23460); else 0
    consumable_cap = CONSUMABLE_KEEP=999 if `stats.hp_restore > 0` (f1f8941, c3b8dfa — stacking-aware); else 0

    cap_excl = max(recipe_cap, task_cap, action_cap, equippable_cap, consumable_cap)

Then `useful_quantity_cap` raises a floor of 1 for currently-equipped items:

    cap = (if equipped then max(1, cap_excl) else cap_excl)

`overstocked_items` walks the inventory: for each (code, qty) with qty > 0 and
qty > cap, it records excess = qty - cap.

The model takes the per-item component Int values directly so the Python
side can apply its source-of-truth per-item predicates (hp_restore
lookup, dominance walk, recipe-chain transitive demand) and pass the
resulting component value through. The differential test fixture
computes the same Python predicates and feeds the Int components in —
end-to-end agreement on the cap formula is what the model proves.

Component inputs:
* `recipeDemand`  = `game_data.max_recipe_demand(code)`                              (≥ 0)
* `taskRemaining` = `_task_chain_demand(code, state.task_code, remaining, gd)`       (≥ 0)
* `actionCap`     = `ACTION_CONSUMABLES_CAP.get(code, 0)`                            (≥ 0)
* `equippableCap` = `EQUIPPABLE_KEEP` if equippable AND not dominated, else 0        (≥ 0)
* `consumableCap` = `CONSUMABLE_KEEP` if `stats.hp_restore > 0`, else 0              (≥ 0)
* `equipped`      = the code is currently equipped (bool)

Lean core only — no mathlib. Integer arithmetic via `omega`.
-/

namespace Formal.InventoryCaps

/-- Craft batches worth of material to keep (mirrors `BATCH_BUFFER`). -/
def batchBuffer : Int := 5

/-- Minimum to keep of any recipe-used item (mirrors `SAFETY_FLOOR`). -/
def safetyFloor : Int := 3

/-- Keep this many of any equippable item Robby can wear (mirrors
`EQUIPPABLE_KEEP`). -/
def equippableKeep : Int := 1

/-- Keep this many of any healing consumable (mirrors `CONSUMABLE_KEEP`).
Stacking-aware floor: hp-restoring items stack in one inventory slot, so
capping low frees zero slots while losing healing stock. -/
def consumableKeep : Int := 999

/-! ### Per-item predicate models

The five cap components are computed from per-item predicates on the
Python side (`useful_quantity_cap_excl_equipped`). We model the predicate
→ component mappings explicitly so the differential side can check that
the Python predicates compose into the Lean-modeled component values. -/

/-- `equipCapValue` mirrors the Python `equippable_cap` component:
`EQUIPPABLE_KEEP` when the item has at least one ITEM_TYPE_TO_SLOTS entry
(`isEquippable = true`) AND is NOT dominated by enough strictly-better
same-slot peers (`isDominated = false`), else 0. The dominance predicate
is computed on the Python side (`_is_equippable_dominated`); this
function pins how its Bool output composes into the Int component. -/
def equipCapValue (isEquippable isDominated : Bool) : Int :=
  if isEquippable && !isDominated then equippableKeep else 0

/-- `consumableCapValue` mirrors the Python `consumable_cap` component:
`CONSUMABLE_KEEP` when the item has `hp_restore > 0`, else 0. -/
def consumableCapValue (hpRestore : Int) : Int :=
  if hpRestore > 0 then consumableKeep else 0

/-- A non-equippable item never has a positive equippable cap. -/
theorem equipCap_zero_of_not_equippable (isDominated : Bool) :
    equipCapValue false isDominated = 0 := by
  unfold equipCapValue
  simp

/-- A dominated equippable has its keep-cap zeroed (becomes
discard-eligible). -/
theorem equipCap_zero_of_dominated (isEquippable : Bool) :
    equipCapValue isEquippable true = 0 := by
  unfold equipCapValue
  cases isEquippable <;> simp

/-- A non-dominated equippable yields exactly `EQUIPPABLE_KEEP`. -/
theorem equipCap_eq_keep_of_undominated_equippable :
    equipCapValue true false = equippableKeep := by
  unfold equipCapValue
  simp

/-- A non-healing item never has a positive consumable cap. -/
theorem consumableCap_zero_of_not_healing :
    consumableCapValue 0 = 0 := by
  unfold consumableCapValue
  simp

/-- A non-healing item (hp_restore ≤ 0) never has a positive consumable
cap — strict version covering negative hp_restore too. -/
theorem consumableCap_zero_iff_nonpositive (hpRestore : Int) :
    consumableCapValue hpRestore = 0 ↔ ¬ (hpRestore > 0) := by
  unfold consumableCapValue
  by_cases h : hpRestore > 0
  · simp [h, consumableKeep]
  · simp [h]

/-- A healing item (hp_restore > 0) yields exactly `CONSUMABLE_KEEP`. -/
theorem consumableCap_eq_keep_of_healing (hpRestore : Int)
    (h : hpRestore > 0) : consumableCapValue hpRestore = consumableKeep := by
  unfold consumableCapValue
  simp [h]

/-! ### Equippable dominance algorithm

The Python `_is_equippable_dominated(item_code, state, game_data)` walks
the owned items (inventory + bank + equipped), filters to peers that:
  (a) fill every slot the item could fill,
  (b) have strictly higher equip_value,
  (c) cover every skill_effect of the item with equal-or-better magnitude
      (compared on abs() because skill_effects are negative cooldown
      reductions),
and sums their owned counts. The item is dominated when the total reaches
`len(ITEM_TYPE_TO_SLOTS[stats.type_])` — enough strictly-better peers to
fill every slot the item could occupy.

We model the algorithm as a fold over a `List Peer` where each peer
carries the trio of dominance criteria already evaluated, plus its owned
count. This is the per-peer evaluation the Python side performs against
`game_data.item_stats(peer_code)`. -/

/-- A peer entry in the dominance walk: each criterion's verdict +
the peer's owned count (inv + bank + equipped). -/
structure Peer where
  /-- Peer fits every slot the candidate item fits. -/
  fitsAllSlots : Bool
  /-- Peer's equip_value strictly greater than candidate's. -/
  strictlyHigher : Bool
  /-- Peer covers every skill_effect of candidate at >= magnitude. -/
  coversSkillEffects : Bool
  /-- Owned count of this peer code across inv + bank + equipped. -/
  ownedCount : Int

/-- A peer qualifies as a DOMINATOR iff all three criteria hold. -/
def Peer.qualifies (p : Peer) : Bool :=
  p.fitsAllSlots && p.strictlyHigher && p.coversSkillEffects

/-- Owned count contributed by a peer when (and only when) it qualifies. -/
def Peer.contribution (p : Peer) : Int :=
  if p.qualifies then p.ownedCount else 0

/-- Sum of owned counts across all qualifying peers. -/
def dominatorOwned (peers : List Peer) : Int :=
  (peers.map Peer.contribution).foldl (· + ·) 0

/-- The item is DOMINATED when qualifying-peer owned count meets or
exceeds the slot count of the item's equipment type. For single-slot
types (weapon, helmet, body_armor, shield, boots, amulet, leg_armor),
slotCount = 1 — a single qualifying peer suffices. Multi-slot types
require enough copies to fill every slot:
* ring     → slotCount = 2
* utility  → slotCount = 2
* artifact → slotCount = 3
-/
def isDominatedBy (peers : List Peer) (slotCount : Int) : Bool :=
  decide (dominatorOwned peers ≥ slotCount)

/-- A non-qualifying peer contributes 0 to the dominator-owned total. -/
theorem contribution_zero_of_not_qualifies (p : Peer) (h : p.qualifies = false) :
    p.contribution = 0 := by
  unfold Peer.contribution
  simp [h]

/-- A qualifying peer contributes its full owned count. -/
theorem contribution_eq_owned_of_qualifies (p : Peer) (h : p.qualifies = true) :
    p.contribution = p.ownedCount := by
  unfold Peer.contribution
  simp [h]

/-- A peer fails to qualify the moment ANY of its three criteria is false.
Pin each branch explicitly so future renames stay structural. -/
theorem qualifies_false_of_missing_slots (p : Peer)
    (h : p.fitsAllSlots = false) : p.qualifies = false := by
  unfold Peer.qualifies
  simp [h]

theorem qualifies_false_of_not_strictly_higher (p : Peer)
    (h : p.strictlyHigher = false) : p.qualifies = false := by
  unfold Peer.qualifies
  simp [h]

theorem qualifies_false_of_missing_skill_coverage (p : Peer)
    (h : p.coversSkillEffects = false) : p.qualifies = false := by
  unfold Peer.qualifies
  simp [h]

/-- An empty peer list yields zero dominator-owned (vacuously). -/
theorem dominatorOwned_nil : dominatorOwned [] = 0 := by
  unfold dominatorOwned
  simp

/-- An empty peer list never dominates (for slotCount ≥ 1). -/
theorem isDominatedBy_nil_of_positive_slot (slotCount : Int)
    (h : slotCount ≥ 1) : isDominatedBy [] slotCount = false := by
  unfold isDominatedBy
  rw [dominatorOwned_nil]
  simp
  omega

/-- Adding a non-qualifying peer doesn't change the dominator-owned total. -/
theorem dominatorOwned_cons_non_qualifying (p : Peer) (rest : List Peer)
    (h : p.qualifies = false) :
    dominatorOwned (p :: rest) = dominatorOwned rest := by
  unfold dominatorOwned
  simp [Peer.contribution, h, List.map]

/-- The composed predicate the Python side uses to gate `equippable_cap`:
if the item type has a slot AND the peers-list dominates it, the cap is 0;
otherwise the cap is `EQUIPPABLE_KEEP`. Combines `equipCapValue` (cap-from-
Bools) with the dominance check (`isDominatedBy`). This is the full
component-value derivation in Lean. -/
def equipCapFromPeers (isEquippable : Bool) (peers : List Peer)
    (slotCount : Int) : Int :=
  equipCapValue isEquippable (isDominatedBy peers slotCount)

/-- When the peer list doesn't dominate (e.g. empty list with slotCount ≥ 1),
the equippable-cap collapses to the unconstrained EQUIPPABLE_KEEP path. -/
theorem equipCapFromPeers_undominated (isEquippable : Bool)
    (peers : List Peer) (slotCount : Int)
    (hnotDom : isDominatedBy peers slotCount = false) :
    equipCapFromPeers isEquippable peers slotCount =
      equipCapValue isEquippable false := by
  unfold equipCapFromPeers
  rw [hnotDom]

/-- When the peer list dominates, the equippable-cap is 0 regardless of
whether the item is equippable (the dominance check supersedes the slot
gate — a dominated item is delete-eligible). -/
theorem equipCapFromPeers_dominated (isEquippable : Bool)
    (peers : List Peer) (slotCount : Int)
    (hdom : isDominatedBy peers slotCount = true) :
    equipCapFromPeers isEquippable peers slotCount = 0 := by
  unfold equipCapFromPeers
  rw [hdom]
  exact equipCap_zero_of_dominated isEquippable

/-- The recipe component of the cap, parametric on the batch buffer and safety
floor (Python's `batch_buffer`/`safety_floor` keyword args; defaults
`BATCH_BUFFER = 5`, `SAFETY_FLOOR = 3`).

`recipe_cap = recipe_max * batch_buffer if recipe_max > 0 else 0`, then raised to
`safety_floor` when `recipe_max > 0`. -/
def recipeCapWith (batchBuf safetyFlr recipeDemand : Int) : Int :=
  if recipeDemand > 0 then max (recipeDemand * batchBuf) safetyFlr else 0

/-- The recipe component at the default `BATCH_BUFFER`/`SAFETY_FLOOR`. -/
def recipeCap (recipeDemand : Int) : Int :=
  recipeCapWith batchBuffer safetyFloor recipeDemand

/-- `useful_quantity_cap_excl_equipped` (parametric): max of the five components. -/
def capExclWith (batchBuf safetyFlr recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) : Int :=
  max (recipeCapWith batchBuf safetyFlr recipeDemand)
    (max taskRemaining
      (max actionCap
        (max equippableCap consumableCap)))

/-- `useful_quantity_cap` (parametric): equipped floor of 1 on top of `capExclWith`. -/
def capWith (batchBuf safetyFlr recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) (equipped : Bool) : Int :=
  if equipped then
    max 1 (capExclWith batchBuf safetyFlr recipeDemand equippableCap consumableCap actionCap taskRemaining)
  else
    capExclWith batchBuf safetyFlr recipeDemand equippableCap consumableCap actionCap taskRemaining

/-- `useful_quantity_cap_excl_equipped`: max of the five components (default consts). -/
def capExcl (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) : Int :=
  capExclWith batchBuffer safetyFloor recipeDemand equippableCap consumableCap actionCap taskRemaining

/-- `useful_quantity_cap`: the equipped floor of 1 is applied on top of `capExcl`. -/
def cap (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) (equipped : Bool) : Int :=
  capWith batchBuffer safetyFloor recipeDemand equippableCap consumableCap actionCap taskRemaining equipped

/-- The excess for one inventory item with quantity `qty` and cap `c`:
`qty - c` when `qty > 0 ∧ qty > c`, else `0` (meaning "not overstocked"). -/
def itemExcess (qty c : Int) : Int :=
  if qty > 0 ∧ qty > c then qty - c else 0

/-- Whether an inventory item is recorded as overstocked. -/
def isOverstocked (qty c : Int) : Bool := decide (qty > 0 ∧ qty > c)

/-- `overstocked_items` over a model inventory. We model the per-item
computation; the dict assembly is a straightforward filter-map. -/
def overstockWith (batchBuf safetyFlr recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) (equipped : Bool) (qty : Int) : Int :=
  itemExcess qty
    (capWith batchBuf safetyFlr recipeDemand equippableCap consumableCap actionCap taskRemaining equipped)

/-- `overstock` at the default `BATCH_BUFFER`/`SAFETY_FLOOR`. -/
def overstock (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) (equipped : Bool) (qty : Int) : Int :=
  itemExcess qty (cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped)

/-! ### Theorems (the strong contracts). -/

/-- `cap_eq_max_of_five`: when NOT equipped, the cap is exactly the max of the
five components (recipe, task, action, equippable, consumable). -/
theorem cap_eq_max_of_five (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) :
    cap recipeDemand equippableCap consumableCap actionCap taskRemaining false
      = max (recipeCap recipeDemand)
          (max taskRemaining
            (max actionCap
              (max equippableCap consumableCap))) := by
  unfold cap capWith capExclWith recipeCap
  simp

/-- `cap_eq_max_of_five` (equipped form): when equipped, the cap is exactly
`max(1, max-of-five)`. -/
theorem cap_eq_max_one_of_five (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) :
    cap recipeDemand equippableCap consumableCap actionCap taskRemaining true
      = max 1 (max (recipeCap recipeDemand)
          (max taskRemaining
            (max actionCap
              (max equippableCap consumableCap)))) := by
  unfold cap capWith capExclWith recipeCap
  simp

/-- `equipped_ge_one`: an equipped item always has `1 ≤ cap`. -/
theorem equipped_ge_one (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) :
    1 ≤ cap recipeDemand equippableCap consumableCap actionCap taskRemaining true := by
  unfold cap capWith
  simp only [if_true]
  exact Int.le_max_left 1 _

/-- `recipeCap` raises a demanded item to at least the safety floor. -/
theorem recipe_cap_ge_safety (recipeDemand : Int) (h : recipeDemand > 0) :
    safetyFloor ≤ recipeCap recipeDemand := by
  unfold recipeCap recipeCapWith
  simp only [h, if_true]
  exact Int.le_max_right _ _

/-- `overstock_exact`: for an inventory item, `overstock` keeps EXACTLY `qty - c`
when the item is overstocked (`qty > 0 ∧ qty > c`), and `0` (nothing) otherwise,
where `c` is the computed cap. This pins both the value and the membership rule. -/
theorem overstock_exact (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) (equipped : Bool) (qty : Int) :
    overstock recipeDemand equippableCap consumableCap actionCap taskRemaining equipped qty
      = (if qty > 0 ∧ qty > cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped
         then qty - cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped
         else 0) := by
  unfold overstock itemExcess
  rfl

/-- Overstocked items report a strictly positive excess (never records junk). -/
theorem overstock_pos_of_over (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) (equipped : Bool) (qty : Int)
    (hq : qty > 0)
    (hover : qty > cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped) :
    0 < overstock recipeDemand equippableCap consumableCap actionCap taskRemaining equipped qty := by
  unfold overstock itemExcess
  simp only [hq, hover, and_self, if_true]
  omega

/-- Non-overstocked items contribute exactly 0 (kept entirely). -/
theorem overstock_zero_of_not_over (recipeDemand : Int)
    (equippableCap consumableCap actionCap taskRemaining : Int) (equipped : Bool) (qty : Int)
    (hnot : ¬ (qty > 0 ∧ qty > cap recipeDemand equippableCap consumableCap actionCap taskRemaining equipped)) :
    overstock recipeDemand equippableCap consumableCap actionCap taskRemaining equipped qty = 0 := by
  unfold overstock itemExcess
  simp only [hnot, if_false]

end Formal.InventoryCaps
