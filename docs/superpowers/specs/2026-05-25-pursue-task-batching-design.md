# Batched PursueTask

Date: 2026-05-25
Status: Draft (for review)

Produce and deliver multiple task units per `PursueTask` plan instead of one,
bounded by remaining task units and available inventory space, so the bot
amortizes craft/deliver actions and the workshop↔taskmaster travel across a
whole batch.

## Problem

`PursueTaskGoal` targets `desired_state = {task_progress: initial+1}` — one unit
per plan. Actions are built `quantity=1`. Per unit the bot runs a full circuit:
gather the unit's raw materials, travel to the workshop and craft one item,
travel to the taskmaster and trade one. For `copper_bar` (10 ore/unit, 20 units)
that is ~240 cooldown cycles, and the craft+trade+travel is repeated 20×.

Gathering is irreducible (the server yields one resource per gather action), but
the per-unit craft, trade, and the round-trips between gather spot, workshop, and
taskmaster are not — they can be done once per batch. Batching K units means
gather `K × mats_per_unit`, then a single `Craft×K` and a single `TaskTrade×K`.

## Design

K is computed once per cycle from live state and shared by the goal (so the
planner targets the whole batch) and the built actions (so one craft/trade can
satisfy it). The arbiter still executes `plan[0]` and re-plans each cycle; the
batch only changes how far ahead each plan reaches and the quantity on the craft
and trade actions.

### 1. `raw_material_units(game_data, item) -> int`

Extend the recipe-closure walk to multiply ingredient quantities down the tree to
the raw resources gathered per crafted unit. Lives in
`src/artifactsmmo_cli/ai/recipe_closure.py` beside `recipe_closure`.

```
raw_material_units(game_data, item, visited=None):
    visited = visited or set()
    if item in visited:                  # cyclic/self-referential recipe guard
        return 1
    visited = visited | {item}
    recipe = game_data._crafting_recipes.get(item)
    if not recipe:                       # raw resource (gathered directly)
        return 1
    return sum(qty * raw_material_units(game_data, sub, visited) for sub, qty in recipe.items())
```

`copper_bar {copper_ore: 10}` → `10`. `steel_bar {iron_bar: 1, coal: 2}` with
`iron_bar {iron_ore: 6}` → `1×6 + 2×1 = 8`. A cyclic/self-referential recipe is
guarded with a `visited` set (return 1 on revisit), matching `recipe_closure`.

### 2. `task_batch_size(state, game_data) -> int`

New module `src/artifactsmmo_cli/ai/task_batch.py`, one function. Single source of
K, called by both `map_means` and `player._build_actions`.

```
BATCH_CAP = 10
MIN_FREE_SLOTS = 3          # mirror GatherAction._MIN_FREE_SLOTS so gathering stays applicable

task_batch_size(state, game_data):
    # caller guarantees an active items task; defensive 1 if not
    if state.task_type != "items" or not state.task_code or state.task_total <= 0:
        return 1
    remaining = state.task_total - state.task_progress
    if remaining <= 0:
        return 1
    mats_per_unit = raw_material_units(game_data, state.task_code)
    if mats_per_unit <= 0:
        return 1
    needed_resources, _ = recipe_closure(game_data, [state.task_code])
    drops = {game_data._resource_drops[r] for r in needed_resources}
    held_recipe = sum(state.inventory.get(item, 0) for item in drops)
    usable = (state.inventory_free + held_recipe) - MIN_FREE_SLOTS
    fit = usable // mats_per_unit
    return max(1, min(remaining, fit, BATCH_CAP))
```

Counting `held_recipe` (recipe raw mats already in inventory) as free-equivalent
keeps K stable across the gather cycles: `inventory_free` drops as ore
accumulates, but `held_recipe` rises to compensate, so K does not shrink mid-batch
and the planned `Craft×K`/`Trade×K` stay reachable. `fit` can be ≤ 0 when
inventory is nearly full; `max(1, …)` floors K at 1 (today's behavior) and the
`DEPOSIT_FULL` guard handles a genuinely full inventory upstream.

### 3. `PursueTaskGoal` carries the batch

```
def __init__(self, task_code: str, initial_progress: int, batch: int = 1) -> None:
    ...
    self._batch = batch

def desired_state(self, state, game_data):
    return {"task_progress": self._initial_progress + self._batch}
```

`is_satisfied` is unchanged: `task_progress` only advances at the single
`TaskTrade×K`, so the goal stays unsatisfied through gathering/crafting and trips
once the batch is delivered, after which the arbiter re-decides with a fresh K.
`relevant_actions` is unchanged — the recipe-closure scope already admits the
gather/craft/trade for the task item.

### 4. Quantity-K actions in `player._build_actions`

In the items-task block (today builds `TaskTradeAction(quantity=1)`), compute
`k = task_batch_size(self.state, self.game_data)` once and build:

```
actions.append(CraftAction(code=task_code, quantity=k, workshop_location=workshop))
actions.append(TaskTradeAction(code=task_code, quantity=k, taskmaster_location=taskmaster))
```

The generic per-item craft loop still emits a `quantity=1` craft for the task
item; both survive `relevant_actions`, and A* prefers the single `Craft×K` +
`TaskTrade×K` because it is far cheaper than K separate craft/trade actions at the
same locations. `workshop` is the task item's workshop location (the generic loop
already resolves it; reuse the same lookup).

### 5. `map_means` passes K

The PURSUE_TASK feasible branch (`strategy_driver.map_means`) becomes:

```
return PursueTaskGoal(task_code=state.task_code,
                      initial_progress=state.task_progress,
                      batch=task_batch_size(state, game_data))
```

The skill-gated branch (LevelSkillGoal) is unchanged — batching only applies once
the item is craftable.

## Error handling

- `mats_per_unit <= 0` or no recipe → K floored at 1 (the item is gathered
  directly or unknown; one-per-plan is correct).
- Inventory nearly full (`fit <= 0`) → K = 1; the `DEPOSIT_FULL` guard frees space
  upstream when the inventory is actually full of unrelated items.
- K never exceeds `remaining`, so the final batch delivers exactly the units left.
- Pure logic; no API; no `except Exception`. Recipe recursion is `visited`-guarded.

## Testing

Per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`raw_material_units`:** single-level (`copper_bar`→10), nested
  (`steel_bar`→8), raw resource (→1), unknown item (→1), cyclic recipe terminates.
- **`task_batch_size`:**
  - roomy inventory → `min(remaining, fit, CAP)` (e.g. remaining 18, fit 9, CAP 10
    → 9);
  - `CAP` clamp (remaining 50, fit 40 → 10);
  - `remaining` clamp (remaining 3, fit 9 → 3);
  - nearly-full inventory (`fit <= 0`) → 1;
  - `held_recipe` keeps K stable: same K with 0 ore held vs N ore held and
    correspondingly less free space;
  - non-items / no task / `remaining <= 0` → 1.
- **`PursueTaskGoal`:** `desired_state` is `progress + batch`; `batch` defaults to
  1 (back-compat); `is_satisfied` still trips only on a progress advance.
- **`map_means`:** PURSUE_TASK feasible → `PursueTaskGoal` whose `desired_state`
  reflects the computed batch (assert via a seeded recipe + inventory).
- **`player._build_actions`:** with an items task, the built `CraftAction` and
  `TaskTradeAction` for the task item carry `quantity == task_batch_size(...)`.
- **Planner integration (decisive):** seed `copper_bar` (recipe `{copper_ore:10}`),
  inventory empty, `inventory_max` large, with `Gather/Craft×K/TaskTrade×K` plus
  the `quantity=1` variants and unrelated-action noise; assert the plan ends in a
  single `TaskTrade(copper_bar×K)` with `K > 1` and that progress would advance by
  K — proving one batch delivers many units.
- **Regression:** existing `PursueTask`/means/player tests still pass; the
  `quantity=1` default keeps the previous single-unit behavior where K resolves
  to 1.

## Files

- Modify `src/artifactsmmo_cli/ai/recipe_closure.py` — add `raw_material_units`.
- Create `src/artifactsmmo_cli/ai/task_batch.py` — `task_batch_size` + `BATCH_CAP`.
- Modify `src/artifactsmmo_cli/ai/goals/pursue_task.py` — `batch` param +
  `desired_state`.
- Modify `src/artifactsmmo_cli/ai/strategy_driver.py` — `map_means` passes
  `batch=task_batch_size(...)`.
- Modify `src/artifactsmmo_cli/ai/player.py` — build `Craft×K` + `TaskTrade×K` for
  the task item.
- Tests: `tests/test_ai/test_recipe_closure.py` (raw_material_units),
  `tests/test_ai/test_task_batch.py` (new), `tests/test_ai/test_pursue_task_goal.py`,
  `tests/test_ai/test_strategy_driver.py`, `tests/test_ai/test_player_run.py`.

## Out of scope

- Reducing the gather count (irreducible: one resource per gather action).
- Partial-batch early delivery / time-boxing a batch.
- Bank withdrawal of pre-existing materials to seed a batch.
- Tuning `BATCH_CAP` beyond 10 (one-line change later if traces justify).
