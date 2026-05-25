# Batched PursueTask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and deliver K task units per PursueTask plan (K bounded by remaining units and inventory space) instead of one, amortizing craft/trade/travel.

**Architecture:** A single `task_batch_size(state, game_data)` computes K from remaining units, a quantity-aware recipe cost, and free inventory (counting already-held recipe mats as free-equivalent). K is shared by `PursueTaskGoal.desired_state` (= `progress+K`) and the `Craft×K`/`TaskTrade×K` actions `player._build_actions` builds for the task item. The planner then gathers K×mats, crafts K in one action, trades K in one.

**Tech Stack:** Python 3.13, `uv run` (pytest, ruff line-length 120, mypy --strict), GOAP planner.

**Spec:** `docs/superpowers/specs/2026-05-25-pursue-task-batching-design.md`

**Conventions:** All commands `uv run`-prefixed. One class per file; functions may share a module. Imports top/absolute, no inline imports, no `if TYPE_CHECKING`, never `except Exception`, no multiple error-handling layers. Tests use `tests/test_ai/fixtures.py::make_state`. Success: 0 errors/warnings/skips, 100% on changed code. End commits with the `Co-Authored-By` trailer.

---

## File Structure

- **Modify** `src/artifactsmmo_cli/ai/recipe_closure.py` — add `raw_material_units` (quantity-multiplied raw cost per unit) beside `recipe_closure`.
- **Create** `src/artifactsmmo_cli/ai/task_batch.py` — `BATCH_CAP` + `task_batch_size(state, game_data)`.
- **Modify** `src/artifactsmmo_cli/ai/goals/pursue_task.py` — `batch` ctor param + `desired_state`.
- **Modify** `src/artifactsmmo_cli/ai/strategy_driver.py` — `map_means` PURSUE_TASK feasible branch passes `batch=task_batch_size(...)`.
- **Modify** `src/artifactsmmo_cli/ai/player.py` — build `Craft×K` + `TaskTrade×K` for the task item.
- **Tests** — `test_recipe_closure.py`, new `test_task_batch.py`, `test_pursue_task_goal.py`, `test_strategy_driver.py`, `test_player_run.py`.

---

### Task 1: `raw_material_units` — quantity-multiplied raw cost

**Files:**
- Modify: `src/artifactsmmo_cli/ai/recipe_closure.py`
- Test: `tests/test_ai/test_recipe_closure.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_ai/test_recipe_closure.py` (it already has `_gd(recipes, drops)` and imports `recipe_closure`; add `raw_material_units` to the import):

```python
def test_raw_material_units_single_level():
    gd = _gd({"copper_bar": {"copper_ore": 10}}, {"copper_rocks": "copper_ore"})
    assert raw_material_units(gd, "copper_bar") == 10


def test_raw_material_units_nested():
    gd = _gd(
        {"steel_bar": {"iron_bar": 1, "coal": 2}, "iron_bar": {"iron_ore": 6}},
        {"iron_rocks": "iron_ore", "coal_rocks": "coal"},
    )
    assert raw_material_units(gd, "steel_bar") == 8   # 1*6 + 2*1


def test_raw_material_units_raw_resource_is_one():
    gd = _gd({}, {"ash_tree": "ash_wood"})
    assert raw_material_units(gd, "ash_wood") == 1


def test_raw_material_units_unknown_is_one():
    assert raw_material_units(_gd({}, {}), "mystery") == 1


def test_raw_material_units_cyclic_terminates():
    gd = _gd({"a": {"b": 1}, "b": {"a": 1}}, {})
    assert raw_material_units(gd, "a") == 1   # cycle guard returns 1 on revisit
```

- [ ] **Step 2: Run** `uv run pytest tests/test_ai/test_recipe_closure.py -q` — expect FAIL (ImportError: `raw_material_units`).

- [ ] **Step 3: Implement** — add to `src/artifactsmmo_cli/ai/recipe_closure.py` (the file already imports `GameData`):

```python
def raw_material_units(game_data: GameData, item: str, visited: frozenset[str] | None = None) -> int:
    """Total raw-resource quantity gathered to craft one `item`, multiplying
    ingredient quantities down the recipe tree. A raw (gathered) or unknown item
    costs 1. Cyclic recipes terminate via the visited guard (revisit -> 1)."""
    visited = visited or frozenset()
    if item in visited:
        return 1
    recipe = game_data._crafting_recipes.get(item)
    if not recipe:
        return 1
    deeper = visited | {item}
    return sum(qty * raw_material_units(game_data, sub, deeper) for sub, qty in recipe.items())
```

- [ ] **Step 4: Run** `uv run pytest tests/test_ai/test_recipe_closure.py -q` — expect PASS. Then `uv run ruff check src/artifactsmmo_cli/ai/recipe_closure.py tests/test_ai/test_recipe_closure.py` and `uv run mypy src/artifactsmmo_cli/ai/recipe_closure.py`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/recipe_closure.py tests/test_ai/test_recipe_closure.py
git commit -m "feat(ai): add raw_material_units recipe cost helper

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `task_batch_size` — inventory-bounded K

**Files:**
- Create: `src/artifactsmmo_cli/ai/task_batch.py`
- Test: `tests/test_ai/test_task_batch.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_ai/test_task_batch.py`:

```python
"""Tests for task_batch_size — the inventory-bounded units-per-plan count."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_batch import BATCH_CAP, task_batch_size
from tests.test_ai.fixtures import make_state


def _gd():
    gd = GameData()
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    return gd


def _task_state(progress=0, total=20, inventory=None, inventory_max=100):
    return make_state(task_code="copper_bar", task_type="items",
                      task_progress=progress, task_total=total,
                      inventory=inventory or {}, inventory_max=inventory_max)


def test_fill_inventory_fit_clamp():
    # free=97 (used 0..1 from defaults? make_state used computed from inventory), mats=10
    # inventory empty, max 100 -> free 100; usable 97; fit 9; remaining 18 -> K=9
    state = _task_state(progress=2, total=20, inventory={}, inventory_max=100)
    assert task_batch_size(state, _gd()) == 9


def test_remaining_clamp():
    state = _task_state(progress=18, total=20, inventory={}, inventory_max=100)
    assert task_batch_size(state, _gd()) == 2   # only 2 units left


def test_cap_clamp():
    state = _task_state(progress=0, total=50, inventory={}, inventory_max=1000)
    assert task_batch_size(state, _gd()) == BATCH_CAP   # fit huge, remaining 50 -> capped


def test_nearly_full_floors_at_one():
    # 95 of 100 used by unrelated junk -> usable 2 < 10 -> fit 0 -> K=1
    state = _task_state(progress=0, total=20, inventory={"junk": 95}, inventory_max=100)
    assert task_batch_size(state, _gd()) == 1


def test_held_recipe_keeps_k_stable():
    gd = _gd()
    empty = _task_state(progress=0, total=20, inventory={}, inventory_max=100)
    # 40 ore already gathered: free drops by 40, but held_recipe adds 40 back.
    holding = _task_state(progress=0, total=20, inventory={"copper_ore": 40}, inventory_max=100)
    assert task_batch_size(holding, gd) == task_batch_size(empty, gd)


def test_non_items_task_returns_one():
    state = make_state(task_code="chicken", task_type="monsters", task_total=20, task_progress=0)
    assert task_batch_size(state, _gd()) == 1


def test_no_task_returns_one():
    assert task_batch_size(make_state(), _gd()) == 1


def test_completed_task_returns_one():
    state = _task_state(progress=20, total=20)
    assert task_batch_size(state, _gd()) == 1
```

> Note: `make_state` computes `inventory_used` from the `inventory` dict. Verify `inventory_free == inventory_max - inventory_used` against the real `WorldState` (`world_state.py:100-107`). If `inventory_used` counts total quantity, the numbers above hold (empty → free 100 → usable 97 → fit 9). If a default fixture inventory is non-empty, adjust the expected values to match the actual free space — keep the clamp/floor/stability *relationships* as the contract.

- [ ] **Step 2: Run** `uv run pytest tests/test_ai/test_task_batch.py -q` — expect FAIL (ModuleNotFoundError `task_batch`).

- [ ] **Step 3: Implement** — create `src/artifactsmmo_cli/ai/task_batch.py`:

```python
"""task_batch_size: how many task units to produce per PursueTask plan.

Bounded by the units the task still needs, the inventory space available for the
raw materials (counting already-held recipe mats as free-equivalent so K stays
stable as ore accumulates), and a depth cap. Floors at 1 (today's behavior).
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import raw_material_units, recipe_closure
from artifactsmmo_cli.ai.world_state import WorldState

BATCH_CAP = 10
"""Max units per plan — bounds planner search depth and per-trip risk. Tunable."""

_MIN_FREE_SLOTS = 3
"""Mirror GatherAction._MIN_FREE_SLOTS so gathering stays applicable to the end."""


def task_batch_size(state: WorldState, game_data: GameData) -> int:
    """Units to produce/deliver in one PursueTask plan; >= 1."""
    if state.task_type != "items" or not state.task_code or state.task_total <= 0:
        return 1
    remaining = state.task_total - state.task_progress
    if remaining <= 0:
        return 1
    mats_per_unit = raw_material_units(game_data, state.task_code)
    if mats_per_unit <= 0:
        return 1
    needed_resources, _ = recipe_closure(game_data, [state.task_code])
    held_recipe = sum(
        state.inventory.get(game_data._resource_drops[r], 0) for r in needed_resources
    )
    usable = (state.inventory_free + held_recipe) - _MIN_FREE_SLOTS
    fit = usable // mats_per_unit
    return max(1, min(remaining, fit, BATCH_CAP))
```

- [ ] **Step 4: Run** `uv run pytest tests/test_ai/test_task_batch.py -q` — expect PASS (adjust expected numbers per the Step 1 note if the fixture's free space differs). Then ruff + `uv run mypy src/artifactsmmo_cli/ai/task_batch.py`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/task_batch.py tests/test_ai/test_task_batch.py
git commit -m "feat(ai): add task_batch_size (inventory-bounded units per plan)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `PursueTaskGoal` carries the batch

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/pursue_task.py`
- Test: `tests/test_ai/test_pursue_task_goal.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/test_ai/test_pursue_task_goal.py` inside `class TestPursueTaskGoal`:

```python
    def test_batch_defaults_to_one(self):
        g = PursueTaskGoal("copper_bar", 5)
        assert g.desired_state(_items_task(progress=5), GameData()) == {"task_progress": 6}

    def test_desired_state_reflects_batch(self):
        g = PursueTaskGoal("copper_bar", 5, batch=9)
        assert g.desired_state(_items_task(progress=5), GameData()) == {"task_progress": 14}

    def test_is_satisfied_unaffected_by_batch(self):
        g = PursueTaskGoal("copper_bar", 5, batch=9)
        assert not g.is_satisfied(_items_task(progress=5))   # stalled
        assert g.is_satisfied(_items_task(progress=6))        # any advance trips it
```

- [ ] **Step 2: Run** `uv run pytest tests/test_ai/test_pursue_task_goal.py -q` — expect FAIL (`PursueTaskGoal()` takes no `batch`).

- [ ] **Step 3: Implement** — in `src/artifactsmmo_cli/ai/goals/pursue_task.py`, update the ctor and `desired_state`:

```python
    def __init__(self, task_code: str, initial_progress: int, batch: int = 1) -> None:
        self._task_code = task_code
        self._initial_progress = initial_progress
        self._batch = batch
```
```python
    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_progress": self._initial_progress + self._batch}
```
Leave `value`, `is_satisfied`, `relevant_actions`, `max_depth`, `__repr__` unchanged.

- [ ] **Step 4: Run** `uv run pytest tests/test_ai/test_pursue_task_goal.py -q` — expect PASS (all, including the existing ones). Then ruff + `uv run mypy src/artifactsmmo_cli/ai/goals/pursue_task.py`. Coverage: `uv run pytest tests/test_ai/test_pursue_task_goal.py --cov=artifactsmmo_cli.ai.goals.pursue_task --cov-report=term-missing -q` → 100%.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/pursue_task.py tests/test_ai/test_pursue_task_goal.py
git commit -m "feat(ai): PursueTaskGoal targets a batch of units

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `map_means` passes the batch

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py`
- Test: `tests/test_ai/test_strategy_driver.py`

- [ ] **Step 1: Write the failing test** — add to `tests/test_ai/test_strategy_driver.py` `class TestPursueTaskMapping` (it already imports `map_means`, `MeansKind`, `make_state`, `GameData`; add `from artifactsmmo_cli.ai.game_data import ItemStats` if absent):

```python
    def test_pursue_task_goal_carries_batch(self):
        gd = GameData()
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=2, inventory={}, inventory_max=100)
        goal = map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)
        # desired_state task_progress = progress(2) + batch; batch == task_batch_size(state, gd)
        from artifactsmmo_cli.ai.task_batch import task_batch_size
        expected = 2 + task_batch_size(state, gd)
        assert goal.desired_state(state, gd) == {"task_progress": expected}
        assert task_batch_size(state, gd) > 1   # this state genuinely batches
```

- [ ] **Step 2: Run** `uv run pytest "tests/test_ai/test_strategy_driver.py::TestPursueTaskMapping::test_pursue_task_goal_carries_batch" -v` — expect FAIL (goal built with default batch=1 → desired_state {task_progress: 3}).

- [ ] **Step 3: Implement** — in `src/artifactsmmo_cli/ai/strategy_driver.py` add the import:

```python
from artifactsmmo_cli.ai.task_batch import task_batch_size
```
and change the PURSUE_TASK feasible return (currently `return PursueTaskGoal(task_code=state.task_code, initial_progress=state.task_progress)`):

```python
        return PursueTaskGoal(task_code=state.task_code,
                              initial_progress=state.task_progress,
                              batch=task_batch_size(state, game_data))
```

- [ ] **Step 4: Run** the new test (expect PASS), then the whole file `uv run pytest tests/test_ai/test_strategy_driver.py -q`. ruff + `uv run mypy src/artifactsmmo_cli/ai/strategy_driver.py`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(ai): map_means builds PursueTaskGoal with the computed batch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Build `Craft×K` + `TaskTrade×K` for the task item

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_player_run.py`

**Context:** `_build_actions` already has an items-task block that appends `TaskTradeAction(code=task_code, quantity=1, taskmaster_location=taskmaster)`. A generic craft loop earlier appends `CraftAction(code=item_code, quantity=1, workshop_location=...)` for every craftable item. This task adds, for the task item only, a `Craft×K` and `TaskTrade×K` (K = `task_batch_size`). The generic quantity-1 craft stays; the planner prefers the single high-quantity actions.

- [ ] **Step 1: Write the failing test** — add to `tests/test_ai/test_player_run.py` (it builds a `GamePlayer`, sets `player.game_data` and `player.state`, and calls `player._build_actions()`; mirror the existing `test_player_builds_phase_b_actions` setup):

```python
def test_items_task_builds_batched_craft_and_trade():
    """For an items task, the task-item Craft and TaskTrade are built with
    quantity == task_batch_size, so the planner can produce/deliver a batch."""
    from artifactsmmo_cli.ai.game_data import ItemStats
    from artifactsmmo_cli.ai.actions.crafting import CraftAction
    from artifactsmmo_cli.ai.task_batch import task_batch_size

    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._bank_location = (4, 0)
    player.game_data._taskmaster_location = (1, 2)
    player.game_data._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    player.game_data._resource_drops = {"copper_rocks": "copper_ore"}
    player.game_data._item_stats = {
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="weaponcrafting", crafting_level=1),
    }
    player.game_data._workshop_locations = {"weaponcrafting": (2, 0)}
    player._bank_accessible = True
    player.state = make_state(task_code="copper_bar", task_type="items",
                              task_total=20, task_progress=0, inventory={}, inventory_max=100)

    k = task_batch_size(player.state, player.game_data)
    assert k > 1   # sanity: this state batches

    actions = player._build_actions()
    trades = [a for a in actions if isinstance(a, TaskTradeAction) and a.code == "copper_bar"]
    crafts = [a for a in actions if isinstance(a, CraftAction) and a.code == "copper_bar"]
    assert any(t.quantity == k for t in trades), "expected a TaskTrade with quantity K"
    assert any(c.quantity == k for c in crafts), "expected a Craft with quantity K"
```

> Verify `GamePlayer`'s real attribute/method names for workshop resolution by reading `_build_actions` in `player.py` (the generic craft loop calls `self.game_data.workshop_location(stats.crafting_skill)`). Use whatever the code actually uses to set the workshop location in the fixture (`_workshop_locations` dict or a method) so `workshop_location("weaponcrafting")` returns `(2,0)`. If `TaskTradeAction`/`make_state` imports are missing in the test file, add them.

- [ ] **Step 2: Run** `uv run pytest "tests/test_ai/test_player_run.py::test_items_task_builds_batched_craft_and_trade" -v` — expect FAIL (only quantity=1 actions built).

- [ ] **Step 3: Implement** — in `src/artifactsmmo_cli/ai/player.py`, find the items-task block:

```python
        if self.state is not None and self.state.task_type == "items" and self.state.task_code:
            actions.append(TaskTradeAction(
                code=self.state.task_code,
                quantity=1,
                taskmaster_location=taskmaster,
            ))
```

Replace it with a batched build (compute K once, add `Craft×K` + `TaskTrade×K`; keep a `quantity=1` trade for the final single-unit remainder cases):

```python
        if self.state is not None and self.state.task_type == "items" and self.state.task_code:
            task_code = self.state.task_code
            k = task_batch_size(self.state, self.game_data)
            stats = self.game_data.item_stats(task_code)
            workshop = (self.game_data.workshop_location(stats.crafting_skill)
                        if stats is not None and stats.crafting_skill else None)
            if workshop is not None and k > 1:
                actions.append(CraftAction(code=task_code, quantity=k, workshop_location=workshop))
            actions.append(TaskTradeAction(code=task_code, quantity=k, taskmaster_location=taskmaster))
            if k > 1:
                actions.append(TaskTradeAction(code=task_code, quantity=1, taskmaster_location=taskmaster))
```

Add the import at the top of `player.py`:

```python
from artifactsmmo_cli.ai.task_batch import task_batch_size
```

> Rationale for the extra `quantity=1` trade when `k > 1`: a batch crafts/holds exactly K, but if the planner ever reaches a state with fewer than K of the item in inventory it still needs a single-unit trade to make progress. The `Craft×K` is only added when a workshop exists and `k > 1` (when `k == 1` the generic quantity-1 craft already covers it).

- [ ] **Step 4: Run** the new test (expect PASS), then the whole file `uv run pytest tests/test_ai/test_player_run.py -q`. ruff + `uv run mypy src/artifactsmmo_cli/ai/player.py` (no new errors vs baseline).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_run.py
git commit -m "feat(ai): build batched Craft/TaskTrade for the active items task

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Planner integration (decisive) + full verification

**Files:**
- Test: `tests/test_ai/test_pursue_task_goal.py`

- [ ] **Step 1: Write the decisive integration test** — add to `tests/test_ai/test_pursue_task_goal.py` `class TestPursueTaskPlans` (it already imports `GOAPPlanner`, `ItemStats`, the actions, and has a `_gd()` building copper_bar). This proves one batch plan delivers many units:

```python
    def test_batched_plan_delivers_many_in_one_trade(self):
        gd = GameData()
        gd._item_stats = {
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                    crafting_skill="weaponcrafting", crafting_level=1),
        }
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 1}}   # 1 ore/unit keeps the search small
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        state = make_state(
            task_code="copper_bar", task_type="items", task_progress=0, task_total=20,
            skills={"weaponcrafting": 1}, inventory={}, inventory_max=100, x=0, y=0,
        )
        batch = 3
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset({(1, 0)})),
            CraftAction(code="copper_bar", quantity=batch, workshop_location=(2, 0)),
            TaskTradeAction(code="copper_bar", quantity=batch, taskmaster_location=(3, 0)),
            # single-unit variants + noise the planner could pick instead:
            CraftAction(code="copper_bar", quantity=1, workshop_location=(2, 0)),
            TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(3, 0)),
            GatherAction(resource_code="iron_rocks", locations=frozenset({(9, 9)})),
        ]
        goal = PursueTaskGoal("copper_bar", 0, batch=batch)
        plan = GOAPPlanner().plan(state, goal, actions, gd, None)

        assert plan, "expected a non-empty plan"
        traded = sum(a.quantity for a in plan if isinstance(a, TaskTradeAction))
        assert traded >= batch, "the plan must deliver the whole batch"
        # cheapest path is the single Craft x batch + single TaskTrade x batch
        assert any(isinstance(a, TaskTradeAction) and a.quantity == batch for a in plan)
```

- [ ] **Step 2: Run** `uv run pytest "tests/test_ai/test_pursue_task_goal.py::TestPursueTaskPlans::test_batched_plan_delivers_many_in_one_trade" -v` — expect PASS. If it fails because the planner picked single-unit actions, investigate cost (the batched trade at the same location should be cheaper than `batch` separate trades) — do not weaken the assertion to pass.

- [ ] **Step 3: Full verification gate:**

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
```
Expected: pytest all green, 0 skipped; ruff clean; mypy ≤ 129-error baseline with **zero new** in changed files (`recipe_closure.py`, `task_batch.py`, `pursue_task.py`, `strategy_driver.py`, `player.py`).

- [ ] **Step 4: Coverage on changed code:**

```bash
uv run pytest tests/test_ai/test_recipe_closure.py tests/test_ai/test_task_batch.py tests/test_ai/test_pursue_task_goal.py tests/test_ai/test_strategy_driver.py tests/test_ai/test_player_run.py \
  --cov=artifactsmmo_cli.ai.recipe_closure \
  --cov=artifactsmmo_cli.ai.task_batch \
  --cov=artifactsmmo_cli.ai.goals.pursue_task \
  --cov-report=term-missing -q
```
Expected: 100% on `recipe_closure.py`, `task_batch.py`, `pursue_task.py`. Add a test for any uncovered new line.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_pursue_task_goal.py
git commit -m "test(ai): batched PursueTask plan delivers the whole batch in one trade

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- **K is shared, computed twice from the same pure function** (`task_batch_size`) — once in `map_means` (goal target) and once in `player._build_actions` (action quantities). Both read the same `state`/`game_data`, so within a cycle they agree. Do not try to thread one value between them; the function is deterministic.
- **`_resource_drops[r]` is safe**: `recipe_closure` returns resource codes that are keys of `_resource_drops`, so the indexing in `task_batch_size` cannot KeyError.
- **Verify fixture free space**: `make_state` derives `inventory_used`; confirm `inventory_free` for an empty inventory at `inventory_max=100` is 100 before trusting the exact `K==9` expectations in Task 2 — adjust the literals if the model differs, keeping the clamp/floor/stability relationships.
- **Do not** reduce gather count or add bank-withdrawal sourcing — out of scope.
