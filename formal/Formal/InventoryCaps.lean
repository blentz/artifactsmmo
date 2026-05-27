/-
Formal model of `useful_quantity_cap` / `overstocked_items` from
`src/artifactsmmo_cli/ai/inventory_caps.py`.

The Python routine computes a per-item "useful quantity cap" — the maximum count
worth keeping; anything beyond is overstock. The cap is the max of four
components (`useful_quantity_cap_excl_equipped`):

    recipe_cap    = (if recipe_max > 0 then max(recipe_max * BATCH_BUFFER, SAFETY_FLOOR) else 0)
    task_cap      = remaining   (active items-task demand for this item, else 0)
    action_cap    = ACTION_CONSUMABLES_CAP[code]  (9 for tasks_coin, else 0)
    equippable_cap = (if equippable then EQUIPPABLE_KEEP else 0)

    cap_excl = max(recipe_cap, task_cap, action_cap, equippable_cap)

Then `useful_quantity_cap` raises a floor of 1 for currently-equipped items:

    cap = (if equipped then max(1, cap_excl) else cap_excl)

`overstocked_items` walks the inventory: for each (code, qty) with qty > 0 and
qty > cap, it records excess = qty - cap.

We abstract the game_data getters as direct integer/bool inputs:
* `recipeDemand` = `game_data.max_recipe_demand(code)`  (≥ 0)
* `equippable`   = `ITEM_TYPE_TO_SLOTS.get(stats.type_)` is truthy
* `actionCap`    = `ACTION_CONSUMABLES_CAP.get(code, 0)`  (≥ 0; 9 for tasks_coin)
* `taskRemaining`= `max(0, task_total - task_progress)` when this is the active
  items-task item, else 0  (≥ 0)
* `equipped`     = the code is currently equipped (bool)

Lean core only — no mathlib. Integer arithmetic via `omega`.
-/

namespace Formal.InventoryCaps

/-- Craft batches worth of material to keep (mirrors `BATCH_BUFFER`). -/
def batchBuffer : Int := 5

/-- Minimum to keep of any recipe-used item (mirrors `SAFETY_FLOOR`). -/
def safetyFloor : Int := 3

/-- Keep one of each equippable item (mirrors `EQUIPPABLE_KEEP`). -/
def equippableKeep : Int := 1

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

/-- The equippable component: `EQUIPPABLE_KEEP` if equippable, else 0. -/
def equipCap (equippable : Bool) : Int :=
  if equippable then equippableKeep else 0

/-- `useful_quantity_cap_excl_equipped` (parametric): max of the four components. -/
def capExclWith (batchBuf safetyFlr recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) : Int :=
  max (recipeCapWith batchBuf safetyFlr recipeDemand)
    (max taskRemaining (max actionCap (equipCap equippable)))

/-- `useful_quantity_cap` (parametric): equipped floor of 1 on top of `capExclWith`. -/
def capWith (batchBuf safetyFlr recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) (equipped : Bool) : Int :=
  if equipped then max 1 (capExclWith batchBuf safetyFlr recipeDemand equippable actionCap taskRemaining)
  else capExclWith batchBuf safetyFlr recipeDemand equippable actionCap taskRemaining

/-- `useful_quantity_cap_excl_equipped`: max of the four components (default consts). -/
def capExcl (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) : Int :=
  capExclWith batchBuffer safetyFloor recipeDemand equippable actionCap taskRemaining

/-- `useful_quantity_cap`: the equipped floor of 1 is applied on top of `capExcl`. -/
def cap (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) (equipped : Bool) : Int :=
  capWith batchBuffer safetyFloor recipeDemand equippable actionCap taskRemaining equipped

/-- The excess for one inventory item with quantity `qty` and cap `c`:
`qty - c` when `qty > 0 ∧ qty > c`, else `0` (meaning "not overstocked"). -/
def itemExcess (qty c : Int) : Int :=
  if qty > 0 ∧ qty > c then qty - c else 0

/-- Whether an inventory item is recorded as overstocked. -/
def isOverstocked (qty c : Int) : Bool := decide (qty > 0 ∧ qty > c)

/-- `overstocked_items` over a model inventory: a list of `(recipeDemand,
equippable, actionCap, taskRemaining, equipped, qty)` per item. Returns the list
of `(excess)` for items that are overstocked, paired with the original index so
the contract can pin "exactly qty - cap, and nothing else". We model the
per-item computation; the dict assembly is a straightforward filter-map. -/
def overstockWith (batchBuf safetyFlr recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) (equipped : Bool) (qty : Int) : Int :=
  itemExcess qty (capWith batchBuf safetyFlr recipeDemand equippable actionCap taskRemaining equipped)

/-- `overstock` at the default `BATCH_BUFFER`/`SAFETY_FLOOR`. -/
def overstock (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) (equipped : Bool) (qty : Int) : Int :=
  itemExcess qty (cap recipeDemand equippable actionCap taskRemaining equipped)

/-! ### Theorems (the strong contracts). -/

/-- `cap_eq_max_of_four`: when NOT equipped, the cap is exactly the max of the
four components (recipe, task, action, equippable). -/
theorem cap_eq_max_of_four (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) :
    cap recipeDemand equippable actionCap taskRemaining false
      = max (recipeCap recipeDemand)
          (max taskRemaining (max actionCap (equipCap equippable))) := by
  unfold cap capWith capExclWith recipeCap
  simp

/-- `cap_eq_max_of_four` (equipped form): when equipped, the cap is exactly
`max(1, max-of-four)`. -/
theorem cap_eq_max_one_of_four (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) :
    cap recipeDemand equippable actionCap taskRemaining true
      = max 1 (max (recipeCap recipeDemand)
          (max taskRemaining (max actionCap (equipCap equippable)))) := by
  unfold cap capWith capExclWith recipeCap
  simp

/-- `equipped_ge_one`: an equipped item always has `1 ≤ cap`. -/
theorem equipped_ge_one (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) :
    1 ≤ cap recipeDemand equippable actionCap taskRemaining true := by
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
theorem overstock_exact (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) (equipped : Bool) (qty : Int) :
    overstock recipeDemand equippable actionCap taskRemaining equipped qty
      = (if qty > 0 ∧ qty > cap recipeDemand equippable actionCap taskRemaining equipped
         then qty - cap recipeDemand equippable actionCap taskRemaining equipped
         else 0) := by
  unfold overstock itemExcess
  rfl

/-- Overstocked items report a strictly positive excess (never records junk). -/
theorem overstock_pos_of_over (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) (equipped : Bool) (qty : Int)
    (hq : qty > 0)
    (hover : qty > cap recipeDemand equippable actionCap taskRemaining equipped) :
    0 < overstock recipeDemand equippable actionCap taskRemaining equipped qty := by
  unfold overstock itemExcess
  simp only [hq, hover, and_self, if_true]
  omega

/-- Non-overstocked items contribute exactly 0 (kept entirely). -/
theorem overstock_zero_of_not_over (recipeDemand : Int) (equippable : Bool)
    (actionCap taskRemaining : Int) (equipped : Bool) (qty : Int)
    (hnot : ¬ (qty > 0 ∧ qty > cap recipeDemand equippable actionCap taskRemaining equipped)) :
    overstock recipeDemand equippable actionCap taskRemaining equipped qty = 0 := by
  unfold overstock itemExcess
  simp only [hnot, if_false]

end Formal.InventoryCaps
