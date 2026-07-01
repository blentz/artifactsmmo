# Consumable Batch-Cook at Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the bot crafts a consumable or utility item (cooked food, potions), issue one batched craft API call sized to the held ingredient pile, instead of `quantity=1`. Robby cooks all his raw chicken at once.

**Architecture:** A pure helper `consumable_craft_quantity` computes the batched run count from held ingredients (reusing the proven `max_batch_from_held_pure`). `GamePlayer._execute` calls it to rewrite the `CraftAction.quantity` at dispatch — after planning, so GOAP search is untouched.

**Tech Stack:** Python 3.13, pytest. Run everything with `uv run`.

## Global Constraints

- All Python commands prefixed with `uv run`.
- Imports at top of file only — no inline, no `...` imports, no `if TYPE_CHECKING`.
- One behavioral class per file; `consumable_craft_quantity` is a pure module-level function in the existing `consumable_supply.py` (which already holds pure heal helpers).
- Never catch `Exception`.
- Predicate is `stats.type_ in ("consumable", "utility")`. Batch is `max(planned_qty, runs_from_held)` — never shrinks. Held-only (no gather).
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.

---

### Task 1: `consumable_craft_quantity` pure helper

**Files:**
- Modify: `src/artifactsmmo_cli/ai/consumable_supply.py` — add the function + import.
- Test: `tests/test_ai/test_consumable_supply.py` (new file).

**Interfaces:**
- Consumes: `max_batch_from_held_pure` (`ai/max_batch_from_held.py`), `GameData.item_stats`/`crafting_recipe`/`craft_yield`, `WorldState.inventory`.
- Produces: `consumable_craft_quantity(code: str, planned_qty: int, state: WorldState, game_data: GameData) -> int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_consumable_supply.py`:

```python
from artifactsmmo_cli.ai.consumable_supply import consumable_craft_quantity
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        "small_health_potion": ItemStats(code="small_health_potion", level=1, type_="utility",
                                          crafting_skill="alchemy", crafting_level=5),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {
        "cooked_chicken": {"raw_chicken": 1},
        "small_health_potion": {"sunflower": 3},
        "copper_dagger": {"copper_bar": 6},
    }
    return gd


class TestConsumableCraftQuantity:
    def test_cooks_the_whole_held_pile(self):
        gd = _gd()
        state = make_state(inventory={"raw_chicken": 9})
        # recipe raw_chicken:1, yield 1 -> 9 runs from held; planned 1 -> 9
        assert consumable_craft_quantity("cooked_chicken", 1, state, gd) == 9

    def test_no_raws_held_returns_planned(self):
        gd = _gd()
        state = make_state(inventory={})
        assert consumable_craft_quantity("cooked_chicken", 1, state, gd) == 1

    def test_utility_potion_batches(self):
        gd = _gd()
        state = make_state(inventory={"sunflower": 12})  # 12//3 = 4 runs
        assert consumable_craft_quantity("small_health_potion", 1, state, gd) == 4

    def test_non_consumable_unchanged(self):
        gd = _gd()
        state = make_state(inventory={"copper_bar": 60})  # 60//6 = 10, but weapon
        assert consumable_craft_quantity("copper_dagger", 1, state, gd) == 1

    def test_multi_ingredient_bounded_by_scarcest(self):
        gd = _gd()
        # potion needs sunflower:3; hold 12 -> 4 runs (scarcest ingredient bounds)
        state = make_state(inventory={"sunflower": 11})  # 11//3 = 3 runs
        assert consumable_craft_quantity("small_health_potion", 1, state, gd) == 3

    def test_never_shrinks_below_planned(self):
        gd = _gd()
        state = make_state(inventory={"raw_chicken": 2})  # 2 runs from held
        assert consumable_craft_quantity("cooked_chicken", 5, state, gd) == 5

    def test_unknown_code_returns_planned(self):
        gd = _gd()
        assert consumable_craft_quantity("nonexistent", 3, make_state(), gd) == 3

    def test_no_recipe_returns_planned(self):
        gd = _gd()
        gd._item_stats["raw_egg"] = ItemStats(code="raw_egg", level=1, type_="consumable")
        # type_ consumable but no crafting recipe -> planned
        assert consumable_craft_quantity("raw_egg", 4, make_state(), gd) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_consumable_supply.py -v`
Expected: FAIL — `ImportError: cannot import name 'consumable_craft_quantity'`.

- [ ] **Step 3: Implement the helper**

Add to `src/artifactsmmo_cli/ai/consumable_supply.py`. Add the import at the top with the other imports:

```python
from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure
```

Add the function (below the existing helpers):

```python
def consumable_craft_quantity(code: str, planned_qty: int,
                              state: WorldState, game_data: GameData) -> int:
    """Craft runs for a consumable/utility item, batched to the held pile.

    For a consumable or utility item (`stats.type_ in ("consumable", "utility")`)
    with a recipe, return max(planned_qty, runs producible from the ingredients
    already in inventory) so one batched API craft cooks the whole held pile.
    For any other type, an unknown code, a recipe-less item, or when no
    ingredients are held, return planned_qty unchanged. Held only — never gathers.

    Reuses the kernel-proved max_batch_from_held_pure (MaxBatchFromHeld.lean) with
    yield=1, which returns the run count directly (runs = min held//need; the
    CraftAction.quantity field is runs, independent of per-run yield)."""
    stats = game_data.item_stats(code)
    if stats is None or stats.type_ not in ("consumable", "utility"):
        return planned_qty
    recipe = game_data.crafting_recipe(code)
    if not recipe:
        return planned_qty
    needs = [qty for _c, qty in recipe.items()]
    held = [state.inventory.get(c, 0) for c, _qty in recipe.items()]
    runs = max_batch_from_held_pure(needs, held, 1)
    return max(planned_qty, runs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_consumable_supply.py -v`
Expected: PASS (all 8 cases).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/consumable_supply.py tests/test_ai/test_consumable_supply.py
git commit -m "feat(consumable): consumable_craft_quantity batches to held pile"
```

---

### Task 2: Wire the batch rewrite into `_execute`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` — `_execute` (line ~756), and add the import.
- Test: `tests/test_ai/test_player.py` — add a `TestConsumableBatchDispatch` group.

**Interfaces:**
- Consumes: `consumable_craft_quantity` (Task 1); `GamePlayer.game_data`, `GamePlayer.state`.
- Produces: `_execute` dispatches consumable/utility CraftActions with the batched quantity.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_player.py` (the file already imports `GameData`, `ItemStats`, `make_state`, `GamePlayer`, `CraftAction`; add `field`/`dataclass` from dataclasses if not present, and `ItemStats` if not present — check the existing imports first and only add what's missing):

```python
from dataclasses import dataclass, field

from artifactsmmo_cli.ai.actions.crafting import CraftAction


@dataclass
class _CapturingCraft(CraftAction):
    """CraftAction whose execute records the quantity it would send, so the test
    can assert the batch rewrite without a live API."""
    captured: list = field(default_factory=list, compare=False, repr=False)

    def execute(self, state, client):  # type: ignore[override]
        self.captured.append(self.quantity)
        return state


def _batch_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"cooked_chicken": {"raw_chicken": 1},
                            "copper_dagger": {"copper_bar": 6}}
    return gd


class TestConsumableBatchDispatch:
    def _player(self, gd: GameData, state) -> GamePlayer:
        player = GamePlayer(character="hero")
        player.game_data = gd
        player.state = state
        return player

    def test_cooking_batches_the_held_pile(self):
        gd = _batch_gd()
        player = self._player(gd, make_state(inventory={"raw_chicken": 9}))
        cap: list = []
        action = _CapturingCraft(code="cooked_chicken", quantity=1,
                                 workshop_location=(0, 0), captured=cap)
        _new_state, outcome = player._execute(action, client=None)
        assert outcome == "ok"
        assert cap == [9]   # rewritten from 1 to the held-pile batch

    def test_non_consumable_not_batched(self):
        gd = _batch_gd()
        player = self._player(gd, make_state(inventory={"copper_bar": 60}))
        cap: list = []
        action = _CapturingCraft(code="copper_dagger", quantity=1,
                                 workshop_location=(0, 0), captured=cap)
        player._execute(action, client=None)
        assert cap == [1]   # weapon craft untouched
```

Note: `workshop_location=(0, 0)` matches `state`'s position (make_state default x=0,y=0), so the CraftAction's execute does not try to move. The capturing subclass returns state unchanged, so `_execute` returns `(state, "ok")`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_player.py::TestConsumableBatchDispatch -v`
Expected: FAIL — `test_cooking_batches_the_held_pile` sees `cap == [1]` (no rewrite yet), assertion fails.

- [ ] **Step 3: Wire the rewrite into `_execute`**

In `src/artifactsmmo_cli/ai/player.py`, add the import at the top with the other `ai` imports:

```python
from artifactsmmo_cli.ai.consumable_supply import consumable_craft_quantity
```

In `_execute` (currently):

```python
        assert self.state is not None
        if isinstance(action, CraftAction):
            action.history = self.history
```

change the `CraftAction` block to:

```python
        assert self.state is not None
        if isinstance(action, CraftAction):
            action.history = self.history
            if self.game_data is not None:
                batched = consumable_craft_quantity(
                    action.code, action.quantity, self.state, self.game_data)
                if batched != action.quantity:
                    action = replace(action, quantity=batched)
```

(`replace` is already imported at player.py:7; `consumable_craft_quantity` reads `self.state`/`self.game_data`, both in scope. `replace` on the `_CapturingCraft` subclass preserves its `captured` list field.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_player.py::TestConsumableBatchDispatch -v`
Expected: PASS (both cases — cooking batches to 9, weapon stays 1).

- [ ] **Step 5: Run the player + consumable modules + mypy**

Run: `uv run pytest tests/test_ai/test_player.py tests/test_ai/test_consumable_supply.py -q && uv run mypy src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/consumable_supply.py`
Expected: all pass; mypy clean. If a pre-existing player test regresses, investigate — do not edit a passing test to pass.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit -m "feat(player): batch consumable/utility crafts to held pile at dispatch"
```

---

### Task 3: Full-suite verification + offline repro

**Files:** none (verification only).

- [ ] **Step 1: Full suite with coverage**

Run: `uv run pytest`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage. New lines covered by Tasks 1-2.

- [ ] **Step 2: Type check**

Run: `uv run mypy src/artifactsmmo_cli/ai`
Expected: no errors.

- [ ] **Step 3: Offline repro of the bug scenario**

Write a throwaway check at `/tmp/claude-1000/-home-blentz-git-artifactsmmo/af5e7528-26a6-4da7-86d6-519dbdf71ff7/scratchpad/repro_cook.py` proving the raw_chicken pile now cooks in one batch. Run with `PYTHONPATH=.`:

```python
from artifactsmmo_cli.ai.consumable_supply import consumable_craft_quantity
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state

gd = GameData()
gd._item_stats = {"cooked_chicken": ItemStats(code="cooked_chicken", level=1,
                  type_="consumable", crafting_skill="cooking", crafting_level=1)}
gd._crafting_recipes = {"cooked_chicken": {"raw_chicken": 1}}
state = make_state(inventory={"raw_chicken": 14})
q = consumable_craft_quantity("cooked_chicken", 1, state, gd)
print("planned 1 raw_chicken pile 14 -> batched craft quantity:", q)
assert q == 14, q
print("OK - cooks the whole pile in one craft")
```

Run: `cd /home/blentz/git/artifactsmmo && PYTHONPATH=. uv run python <path>` then delete the file.
Expected: prints `batched craft quantity: 14` then `OK`.

- [ ] **Step 4: If coverage < 100%, add the missing-line test**

Identify the uncovered line, add a targeted case (e.g. `craft_yield == 0` guard, or the `game_data is None` skip in `_execute`), re-run `uv run pytest`. Do not lower the bar.

---

## Self-Review

- **Spec coverage:** execution-locus rewrite (Task 2 Step 3); pure helper with predicate `type_ in ("consumable","utility")` + held-only + max(planned,runs) (Task 1 Step 3); reuse of proven `max_batch_from_held_pure` (Task 1); zero planner impact — rewrite only in `_execute`, not in `is_applicable`/`cost`/`apply` (Task 2); tests for cook-the-pile, no-raws, utility batches, non-consumable unchanged, yield>1, never-shrink, dispatch wiring (Tasks 1-2); offline repro (Task 3). All spec sections mapped.
- **Placeholder scan:** none — every step has full code/commands.
- **Type consistency:** `consumable_craft_quantity(code, planned_qty, state, game_data) -> int` identical across Task 1 def, Task 1 tests, Task 2 wiring, Task 3 repro; `_CapturingCraft` carries `captured` and overrides `execute` to record `self.quantity`; `replace`/`CraftAction` already imported in player.py (verified lines 7, 28), only `consumable_craft_quantity` import is added.
- **Runs vs yield:** the CraftAction `quantity` field is the run count. `runs = min(held//need)` is independent of per-run yield, so the helper calls `max_batch_from_held_pure(needs, held, 1)` to get runs directly — no `craft_yield` call, no division, no `y==0` guard (which would be untestable defensive code).
