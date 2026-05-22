# Selective Sell-Value-Ordered Bank Deposits — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Tasks are tightly coupled through one shared selector; do not parallelize. Steps use checkbox (`- [ ]`) syntax.

**Goal:** When banking, deposit only items the bot doesn't need, ordered by NPC sell-back value (most valuable first), keeping the current task item, crafting-target materials, the best fighting weapon, task coins, and HP-restoring consumables.

**Architecture:** A pure `select_bank_deposits(state, game_data)` returns the ordered deposit list (inventory minus a keep-set). `DepositAllAction` deposits exactly that list (planner sim + live execute); `DepositInventoryGoal` is satisfied when the list is empty. Both consume the one selector so they never disagree.

**Tech Stack:** Python 3.13, uv, pytest.

---

## File Structure
- Create `src/artifactsmmo_cli/ai/bank_selection.py` — `select_bank_deposits` (pure).
- Modify `src/artifactsmmo_cli/ai/actions/bank.py` — `DepositAllAction` selective `apply`/`execute`/`is_applicable` + `game_data` field.
- Modify `src/artifactsmmo_cli/ai/goals/survival.py` — `DepositInventoryGoal` satisfaction/value via selector + `game_data` ctor arg.
- Modify `src/artifactsmmo_cli/ai/player.py` — pass `game_data` into `DepositAllAction` and `DepositInventoryGoal`.
- Tests: `tests/test_ai/test_bank_selection.py` (new), `tests/test_ai/test_actions.py`, `tests/test_ai/test_goals.py`.

---

## Task 1: `select_bank_deposits` selector

**Files:**
- Create: `src/artifactsmmo_cli/ai/bank_selection.py`
- Test: `tests/test_ai/test_bank_selection.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_bank_selection.py`:

```python
"""Tests for select_bank_deposits — the bank keep-set + sell-value ordering."""

from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd(**overrides) -> GameData:
    gd = GameData()
    # sell-back prices: npc -> {item: price}
    gd._npc_sell_prices = {
        "merchant": {"gold_ore": 50, "copper_ore": 8, "sap": 3},
        "trader": {"gold_ore": 60},  # higher buy-back for gold_ore
    }
    gd._item_stats = {
        "gold_ore": ItemStats(code="gold_ore", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "sap": ItemStats(code="sap", level=1, type_="resource"),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable", hp_restore=25),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon", attack={"fire": 12}),
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon", attack={"air": 4}),
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    attack={"earth": 5}, skill_effects={"mining": -10}),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
        "spruce_plank": ItemStats(code="spruce_plank", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"iron_dagger": {"iron_bar": 6, "spruce_plank": 2}}
    for k, v in overrides.items():
        setattr(gd, k, v)
    return gd


def test_orders_by_sell_value_desc_then_code():
    gd = _gd()
    state = make_state(inventory={"gold_ore": 1, "copper_ore": 2, "sap": 5})
    assert select_bank_deposits(state, gd) == [("gold_ore", 1), ("copper_ore", 2), ("sap", 5)]


def test_unknown_price_sorts_last():
    gd = _gd()
    state = make_state(inventory={"sap": 1, "mystery": 9})  # mystery has no buy-back
    assert select_bank_deposits(state, gd) == [("sap", 1), ("mystery", 9)]


def test_keeps_task_item_and_task_coins():
    gd = _gd()
    state = make_state(inventory={"copper_ore": 9, "tasks_coin": 3, "sap": 1},
                       task_code="copper_ore", task_type="items")
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_keeps_hp_consumables():
    gd = _gd()
    state = make_state(inventory={"cooked_chicken": 4, "sap": 1})
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_keeps_best_fighting_weapon_deposits_worse_one():
    gd = _gd()
    # copper_dagger (atk 12) is the best; wooden_stick (atk 4) is bankable.
    state = make_state(inventory={"copper_dagger": 1, "wooden_stick": 1, "sap": 1})
    result = select_bank_deposits(state, gd)
    codes = [c for c, _ in result]
    assert "copper_dagger" not in codes
    assert "wooden_stick" in codes and "sap" in codes


def test_best_weapon_considers_equipped_slot():
    gd = _gd()
    # Equipped copper_dagger is the best weapon; an inventory wooden_stick is bankable.
    state = make_state(inventory={"wooden_stick": 1},
                       equipment={"weapon_slot": "copper_dagger"})
    assert ("wooden_stick", 1) in select_bank_deposits(state, gd)


def test_tool_is_not_treated_as_fighting_weapon():
    gd = _gd()
    # copper_pickaxe is a tool (skill_effects) — not the kept fighting weapon, so
    # it is bankable; wooden_stick (real weapon, only one) is kept.
    state = make_state(inventory={"copper_pickaxe": 1, "wooden_stick": 1})
    codes = [c for c, _ in select_bank_deposits(state, gd)]
    assert "copper_pickaxe" in codes
    assert "wooden_stick" not in codes


def test_keeps_crafting_target_materials():
    gd = _gd()
    state = make_state(inventory={"iron_bar": 6, "spruce_plank": 2, "sap": 1},
                       crafting_target="iron_dagger")
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_empty_when_everything_kept():
    gd = _gd()
    state = make_state(inventory={"tasks_coin": 1, "copper_ore": 5}, task_code="copper_ore")
    assert select_bank_deposits(state, gd) == []


def test_ignores_zero_quantity():
    gd = _gd()
    state = make_state(inventory={"sap": 0, "copper_ore": 2})
    assert select_bank_deposits(state, gd) == [("copper_ore", 2)]
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_bank_selection.py -q`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.bank_selection`.

- [ ] **Step 3: Implement the selector**

Create `src/artifactsmmo_cli/ai/bank_selection.py`:

```python
"""Selective bank-deposit policy: what to bank, ordered by sell value."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

TASK_COIN_CODE = "tasks_coin"


def _best_fighting_weapon(state: WorldState, game_data: GameData) -> str | None:
    """Highest-attack non-tool weapon among inventory + equipped, or None.

    Tools (pickaxe/axe/net) have skill_effects and are excluded — they are
    gathering aids, not the combat weapon to protect."""
    candidates: set[str] = set(state.inventory)
    candidates.update(c for c in state.equipment.values() if c)
    best: tuple[int, str] | None = None
    for code in candidates:
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "weapon" or stats.skill_effects:
            continue
        attack = sum(stats.attack.values()) if stats.attack else 0
        # Higher attack wins; tie broken by code ascending (deterministic).
        if best is None or attack > best[0] or (attack == best[0] and code < best[1]):
            best = (attack, code)
    return best[1] if best else None


def _crafting_target_materials(state: WorldState, game_data: GameData) -> set[str]:
    """All material codes in the crafting target's recipe tree."""
    materials: set[str] = set()
    if not state.crafting_target:
        return materials
    visited: set[str] = set()

    def walk(item: str) -> None:
        if item in visited:
            return
        visited.add(item)
        recipe = game_data._crafting_recipes.get(item) or {}
        for mat in recipe:
            materials.add(mat)
            walk(mat)

    walk(state.crafting_target)
    return materials


def _keep_codes(state: WorldState, game_data: GameData) -> set[str]:
    keep: set[str] = {TASK_COIN_CODE}
    if state.task_code:
        keep.add(state.task_code)
    for code in state.inventory:
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > 0:
            keep.add(code)
    weapon = _best_fighting_weapon(state, game_data)
    if weapon is not None:
        keep.add(weapon)
    keep |= _crafting_target_materials(state, game_data)
    return keep


def select_bank_deposits(state: WorldState, game_data: GameData) -> list[tuple[str, int]]:
    """Items to deposit, ordered (sell_value desc, code asc), excluding the
    keep-set (task item, task coins, HP consumables, best fighting weapon,
    crafting-target materials). Items with no known NPC buy-back price get
    value 0 and sort last."""
    keep = _keep_codes(state, game_data)

    def sell_value(code: str) -> int:
        buyers = game_data.npcs_buying_item(code)
        return max((price for _, price in buyers), default=0)

    deposits = [
        (code, qty) for code, qty in state.inventory.items()
        if qty > 0 and code not in keep
    ]
    deposits.sort(key=lambda cq: (-sell_value(cq[0]), cq[0]))
    return deposits
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_bank_selection.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/bank_selection.py tests/test_ai/test_bank_selection.py
git commit -m "feat(ai): select_bank_deposits — keep-set + sell-value ordering"
```

---

## Task 2: `DepositAllAction` deposits the selected list

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/bank.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (pass `game_data`)
- Test: `tests/test_ai/test_actions.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_actions.py` (top-level imports already include `GatherAction` etc.; add `from artifactsmmo_cli.ai.game_data import ItemStats` if missing, and reuse the file's `make_game_data`/`make_state`). Append a class:

```python
class TestDepositAllSelective:
    def _gd(self):
        gd = make_game_data()
        gd._npc_sell_prices = {"m": {"gold_ore": 50, "sap": 3}}
        gd._item_stats = {
            "gold_ore": ItemStats(code="gold_ore", level=1, type_="resource"),
            "sap": ItemStats(code="sap", level=1, type_="resource"),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        return gd

    def test_apply_deposits_only_selected_keeps_task_item(self):
        gd = self._gd()
        action = DepositAllAction(bank_location=(4, 1), accessible=True, game_data=gd)
        state = make_state(x=0, y=0, inventory={"gold_ore": 1, "copper_ore": 5},
                           task_code="copper_ore", task_type="items", bank_items={})
        new_state = action.apply(state, gd)
        assert new_state.inventory == {"copper_ore": 5}   # task item kept
        assert new_state.bank_items == {"gold_ore": 1}    # junk banked
        assert (new_state.x, new_state.y) == (4, 1)

    def test_not_applicable_when_nothing_bankable(self):
        gd = self._gd()
        action = DepositAllAction(bank_location=(4, 1), accessible=True, game_data=gd)
        state = make_state(inventory={"copper_ore": 5}, task_code="copper_ore")
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_without_game_data(self):
        action = DepositAllAction(bank_location=(4, 1), accessible=True)
        state = make_state(inventory={"sap": 1})
        assert action.is_applicable(state, make_game_data()) is False

    def test_not_applicable_when_inaccessible(self):
        gd = self._gd()
        action = DepositAllAction(bank_location=(4, 1), accessible=False, game_data=gd)
        state = make_state(inventory={"sap": 1})
        assert action.is_applicable(state, gd) is False
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_actions.py -k DepositAllSelective -q`
Expected: FAIL — `DepositAllAction` has no `game_data` field / `apply` deposits everything.

- [ ] **Step 3: Implement selective DepositAllAction**

In `src/artifactsmmo_cli/ai/actions/bank.py`, add the import at top with the others:

```python
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
```

Replace the `DepositAllAction` class body's `accessible` field, `is_applicable`, `apply`, and `execute` (keep `tags`, `bank_location`, `cost`, `__repr__`):

```python
    bank_location: tuple[int, int] = field(default=(0, 0), repr=False)
    accessible: bool = True  # False when bank is gated behind an unmet achievement (HTTP 496)
    game_data: GameData | None = field(default=None, repr=False)

    def _deposits(self, state: WorldState) -> list[tuple[str, int]]:
        """Items to bank this trip (selective + sell-value ordered), or [] when
        no game_data is available (no banking without data)."""
        if self.game_data is None:
            return []
        return select_bank_deposits(state, self.game_data)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return self.accessible and bool(self._deposits(state))

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location
        new_inventory = dict(state.inventory)
        new_bank = dict(state.bank_items or {})
        for code, qty in self._deposits(state):
            new_bank[code] = new_bank.get(code, 0) + qty
            new_inventory.pop(code, None)
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=new_bank,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            crafting_target=state.crafting_target,
        )
```

Then update `execute` to deposit only the selected list, in order. Replace the
`for code, qty in list(state.inventory.items()):` loop header with:

```python
        for code, qty in self._deposits(state):
```

(The body — building `SimpleItemSchema`, calling `deposit_item`, refreshing
`last_state` — is unchanged.)

NOTE: `apply` must pass `crafting_target=state.crafting_target` (the field added
in the prior bank-fix work). If the surrounding `WorldState(...)` constructions
in this file already omit it and rely on the default, match the existing style;
the field defaults to `None`, but preserving it keeps the planner's keep-set
stable across a deposit.

- [ ] **Step 4: Wire `game_data` in the player**

In `src/artifactsmmo_cli/ai/player.py`, the `DepositAllAction(...)` construction (~line 828):

```python
            DepositAllAction(bank_location=bank, accessible=self._bank_accessible, game_data=self.game_data),
```

- [ ] **Step 5: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_actions.py -k DepositAllSelective -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/bank.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_actions.py
git commit -m "feat(ai): DepositAllAction banks only the selected items in value order"
```

---

## Task 3: `DepositInventoryGoal` satisfied when nothing bankable

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/survival.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (pass `game_data`)
- Test: `tests/test_ai/test_goals.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_goals.py` (imports already include `DepositInventoryGoal`, `ItemStats`, `make_state`, local `make_game_data`):

```python
class TestDepositInventorySelective:
    def _gd(self):
        gd = make_game_data()
        gd._npc_sell_prices = {"m": {"sap": 3}}
        gd._item_stats = {
            "sap": ItemStats(code="sap", level=1, type_="resource"),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        return gd

    def test_satisfied_when_no_bankable_items(self):
        gd = self._gd()
        goal = DepositInventoryGoal(bank_accessible=True, game_data=gd)
        # bag full of the task item only — nothing bankable even at 100% used.
        state = make_state(inventory={"copper_ore": 100}, inventory_max=104,
                           task_code="copper_ore")
        assert goal.is_satisfied(state) is True
        assert goal.value(state, gd) == 0.0

    def test_not_satisfied_when_bankable_present(self):
        gd = self._gd()
        goal = DepositInventoryGoal(bank_accessible=True, game_data=gd)
        state = make_state(inventory={"sap": 60}, inventory_max=104)
        assert goal.is_satisfied(state) is False

    def test_value_zero_when_bank_inaccessible(self):
        gd = self._gd()
        goal = DepositInventoryGoal(bank_accessible=False, game_data=gd)
        state = make_state(inventory={"sap": 100}, inventory_max=104)
        assert goal.value(state, gd) == 0.0
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_goals.py -k DepositInventorySelective -q`
Expected: FAIL — `DepositInventoryGoal.__init__` takes no `game_data`; `is_satisfied` uses the 30% rule.

- [ ] **Step 3: Implement selector-based satisfaction**

In `src/artifactsmmo_cli/ai/goals/survival.py`, add the import at top:

```python
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
```

Change `DepositInventoryGoal.__init__`, `value`, `is_satisfied`, `desired_state`:

```python
    def __init__(self, bank_accessible: bool = True, game_data: GameData | None = None) -> None:
        self._bank_accessible = bank_accessible
        self._game_data = game_data

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not self._bank_accessible or state.inventory_max == 0:
            return 0.0
        if self.is_satisfied(state):
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        if used_fraction < self._RAMP_START:
            return 0.0
        return (used_fraction - self._RAMP_START) / (1.0 - self._RAMP_START) * self._MAX_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        if state.inventory_max == 0 or self._game_data is None:
            return True
        # Satisfied once nothing remains to bank (the keep-set may itself exceed
        # 30% of the bag, so a fixed-fraction rule could never be reached).
        return not select_bank_deposits(state, self._game_data)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # Post-deposit inventory_used: current minus everything bankable. This is
        # exactly the satisfied state, so the A* heuristic stays reachable.
        bankable = sum(qty for _, qty in select_bank_deposits(state, self._game_data)) \
            if self._game_data is not None else 0
        return {"inventory_used": state.inventory_used - bankable}
```

(Keep `_RAMP_START`, `_RESET_TO`, `_MAX_VALUE`, `__repr__`. `_RESET_TO` is now
unused by `is_satisfied`/`desired_state`; remove it and update the class
docstring to say "satisfied when nothing remains to bank".)

- [ ] **Step 4: Wire `game_data` in the player**

In `src/artifactsmmo_cli/ai/player.py` (~line 986):

```python
            DepositInventoryGoal(bank_accessible=self._bank_accessible, game_data=self.game_data),
```

- [ ] **Step 5: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_goals.py -k DepositInventorySelective -q`
Expected: PASS.

- [ ] **Step 6: Fix any existing DepositInventoryGoal tests**

Run: `uv run pytest tests/test_ai/ -k DepositInventory -q`
Existing tests constructing `DepositInventoryGoal(bank_accessible=...)` without
`game_data` now hit the `is_satisfied → True` (game_data None) path. Update any
that asserted the old 30% behavior to construct with a `game_data` carrying
`_npc_sell_prices`/`_item_stats` and assert against the selector (mirror the
patterns in Step 1). Show the actual edited assertions when you touch them.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/survival.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_goals.py
git commit -m "feat(ai): DepositInventory satisfied when nothing bankable remains"
```

---

## Task 4: Planner integration + full verification

**Files:**
- Test: `tests/test_ai/test_goals.py`

- [ ] **Step 1: Write the integration test**

Add to `tests/test_ai/test_goals.py` (import `GOAPPlanner` already present from prior work; `DepositAllAction` import — add `from artifactsmmo_cli.ai.actions.bank import DepositAllAction` at top if missing):

```python
    def test_planner_banks_junk_keeps_protected(self):
        gd = self._gd()
        gd._npc_sell_prices = {"m": {"sap": 3, "gold_ore": 50}}
        gd._item_stats.update({
            "gold_ore": ItemStats(code="gold_ore", level=1, type_="resource"),
            "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable", hp_restore=25),
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon", attack={"fire": 12}),
        })
        goal = DepositInventoryGoal(bank_accessible=True, game_data=gd)
        action = DepositAllAction(bank_location=(4, 1), accessible=True, game_data=gd)
        state = make_state(
            x=0, y=0, inventory_max=104, bank_items={},
            inventory={"gold_ore": 5, "sap": 5, "copper_ore": 5,
                       "tasks_coin": 2, "cooked_chicken": 3, "copper_dagger": 1},
            task_code="copper_ore", task_type="items",
        )
        plan = GOAPPlanner().plan(state, goal, [action], gd)
        assert plan, "expected a deposit plan"
        result = state
        for a in plan:
            result = a.apply(result, gd)
        # Junk banked; protected items kept.
        assert set(result.inventory) == {"copper_ore", "tasks_coin", "cooked_chicken", "copper_dagger"}
        assert result.bank_items == {"gold_ore": 5, "sap": 5}
```

- [ ] **Step 2: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_goals.py -k "planner_banks_junk" -q`
Expected: PASS.

- [ ] **Step 3: Full verification**

Run: `uv run pytest -q` → all pass, 0 skipped.
Run coverage on changed files:
`uv run pytest tests/test_ai -q --cov=artifactsmmo_cli.ai.bank_selection --cov=artifactsmmo_cli.ai.actions.bank --cov=artifactsmmo_cli.ai.goals.survival --cov-report=term-missing`
→ `bank_selection.py` 100%; add tests for any missed branch.
Run: `uv run ruff check <changed files>` → clean (mind 120-col).
Run: `uv run mypy <changed src files>` → no new errors.

- [ ] **Step 4: Commit**

```bash
git add tests/test_ai/test_goals.py
git commit -m "test(ai): planner banks junk and keeps protected items"
```

---

## Self-review notes
- **Spec coverage:** keep-set categories (task item, tasks_coin, hp consumables, best weapon, crafting-target mats) → Task 1; value-desc + unknown-last ordering → Task 1; selective apply/execute/is_applicable → Task 2; goal satisfied-when-empty + bank-locked gate → Task 3; planner integration → Task 4. All mapped.
- **Type consistency:** `select_bank_deposits(state, game_data) -> list[tuple[str,int]]` used identically in action `_deposits`, goal `is_satisfied`/`desired_state`, and tests. `DepositAllAction.game_data` and `DepositInventoryGoal._game_data` both `GameData | None`.
- **Shared selector** guarantees goal and action agree on "bankable" — no satisfied-but-can't-deposit loop.
- `_RESET_TO` removed in Task 3; ensure no other reference remains (grep after editing).
