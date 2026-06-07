-- @concept: tasks, crafting, bank @property: safety, totality

/-! # Items-Task Termination — conformance models (Task 1 of tasks-termination)

This module models the two decisions that items-task pursuit termination
depends on, faithfully mirroring the live Python:

* `keepSet` ↔ `src/artifactsmmo_cli/ai/bank_selection.py::_keep_codes`
  (the deposit keep-set). The Python computes:
    `keep = {TASKS_COIN, task_code} ∪ {HP consumables} ∪ {best weapon}
            ∪ _recipe_materials([crafting_target?, task_code])`
  where `_recipe_materials` walks the transitive recipe tree of the roots.
  We model exactly the *task-relevant* subset that the termination
  contracts concern: the task item code plus the transitive recipe-input
  item codes of the task item (and a coin marker). The non-task keeps
  (best fighting weapon, HP-restore consumables, equipment crafting-target
  materials) are deliberately OUT OF MODEL SCOPE — they are irrelevant to
  the stall-prevention invariant proved here (a task recipe input is never
  banked). Modeling them would only widen the kept set, which can only
  *help* the SAFETY contracts, never break them.

* `batchK` ↔ `src/artifactsmmo_cli/ai/task_batch.py::task_batch_size`
  (units produced per PursueTask plan). On the items-task branch the
  Python returns `max(1, min(remaining, fit, BATCH_CAP))` where
    `remaining = task_total - task_progress`  (and the function early-returns
                 `1` when `remaining <= 0`),
    `fit       = ((inventory_free + held_recipe) - _MIN_FREE_SLOTS) // mats_per_unit`,
    `BATCH_CAP = 10`.
  We model `batchK = max 1 (min remaining (min fit batchCap))` over the
  abstract clamp inputs.

NOTE (forward-looking): this file will be EXTENDED by a later task with the
items-task termination capstone (`feasibleItemsTask`, `obtainAndTrade`,
`pursue`, and `feasible_items_task_terminates`). The namespace and the
`TaskInputs` structure are kept ready for that extension. The contracts
below are core-only (no Mathlib): `omega`/`List.mem` reasoning suffices.
-/

namespace Formal.Liveness.ItemsTaskTermination

/-- Abstract inputs to the two conformance models.

* `taskCode`    — the active items-task item code (a `Nat` item id).
* `recipeInputs`— the transitive recipe-input item codes of the task item,
                  i.e. what `_recipe_materials([task_code])` returns.
* `remaining`   — `task_total - task_progress` (the items still owed). The
                  Python clamps `remaining <= 0` to a batch of `1` via an
                  early return; here `remaining` is the already-nonnegative
                  units-remaining value fed into the clamp.
* `fit`         — `usable // mats_per_unit`, the inventory-fit cap.
* `batchCap`    — `BATCH_CAP` (10 in Python; abstract here). -/
structure TaskInputs where
  taskCode : Nat
  recipeInputs : List Nat
  remaining : Nat
  fit : Nat
  batchCap : Nat

/-- The task-relevant deposit keep-set: the task item code consed onto its
    transitive recipe-input codes. Mirrors the `{task_code} ∪
    _recipe_materials([task_code])` subset of `_keep_codes`. (Coin marker /
    weapon / HP-consumable keeps are out of model scope — see module
    docstring.) -/
def keepSet (inp : TaskInputs) : List Nat :=
  inp.taskCode :: inp.recipeInputs

/-- Units to produce in one PursueTask plan. Mirrors
    `task_batch_size`'s items-task return `max(1, min(remaining, fit, BATCH_CAP))`
    exactly: `min` is left-associative in Python (`min(a, b, c) = min(min(a, b), c)`),
    here written `min remaining (min fit batchCap)` which is equal by
    associativity/commutativity of `Nat.min`. -/
def batchK (inp : TaskInputs) : Nat :=
  max 1 (min inp.remaining (min inp.fit inp.batchCap))

/-! ## Contracts -/

/-- **SAFETY** — the task item is always in the keep-set (never banked). -/
theorem keepSet_contains_task_item (inp : TaskInputs) :
    inp.taskCode ∈ keepSet inp := by
  unfold keepSet
  exact List.mem_cons_self

/-- **SAFETY** — every transitive recipe input of the task item is in the
    keep-set; the deposit guard never banks a task recipe input. This is the
    stall-prevention invariant (banking a task input would starve
    gather→craft→TaskTrade and freeze progress). -/
theorem keepSet_contains_recipe_inputs (inp : TaskInputs) (m : Nat)
    (h : m ∈ inp.recipeInputs) : m ∈ keepSet inp := by
  unfold keepSet
  exact List.mem_cons_of_mem _ h

/-- **TOTALITY** — the batch size is always at least 1, so each plan makes
    progress (mirrors the Python `max(1, …)` floor; no-stall guarantee). -/
theorem batchK_ge_one (inp : TaskInputs) : batchK inp ≥ 1 := by
  unfold batchK
  omega

/-- **SAFETY** — when at least one unit remains, the batch never over-trades
    past the remaining count: `batchK ≤ remaining`.

    The hypothesis `remaining ≥ 1` faithfully matches the real
    `task_batch_size`: it early-returns `1` when `remaining <= 0`, so at
    `remaining = 0` the function yields `1 > 0` (the floor wins). The clamp
    `max 1 (min remaining …)` is `≤ remaining` exactly when `remaining ≥ 1`;
    conditioning on `remaining ≥ 1` mirrors the Python truth rather than
    forcing a false unconditional contract. -/
theorem batchK_le_remaining (inp : TaskInputs) (h : inp.remaining ≥ 1) :
    batchK inp ≤ inp.remaining := by
  unfold batchK
  omega

end Formal.Liveness.ItemsTaskTermination
