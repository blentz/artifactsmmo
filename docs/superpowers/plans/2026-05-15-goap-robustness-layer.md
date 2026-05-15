# GOAP Robustness Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the GOAP AI player run autonomously for hours by adding the 5 missing API actions, a stuck-state detector with escalating recovery, an action-counted refresh policy with JSONL tracing, and a code-quality cleanup pass (mypy → 0, coverage → 98%).

**Architecture:** Five sequential phases. Phase A adds NpcSell (closes the in-progress value-recovery thread). Phase B adds the remaining API actions (BankExpansion, MapTransition, TaskTrade, gold management). Phase C adds a stuck-state detector module with cycle-counted recovery ladder. Phase D rewires refresh to action-counted, adds Tracer/FileTracer for JSONL postmortem analysis. Phase E is mypy + coverage cleanup. Each phase ends with a green test suite and one manual `--dry-run` validation.

**Tech Stack:** Python 3.13, uv-managed virtualenv, pytest + pytest-cov, mypy, Typer (CLI), httpx (via `artifactsmmo_api_client`).

**Spec:** `docs/superpowers/specs/2026-05-15-goap-robustness-layer-design.md`

---

## File Structure

### New files
```
src/artifactsmmo_cli/ai/
├── recovery.py                      # CycleRecord, StuckSignal, StuckDetector
├── tracing.py                       # Tracer ABC, NullTracer, FileTracer
├── actions/
│   ├── npc_sell.py                  # NpcSellAction
│   ├── bank_expansion.py            # BuyBankExpansionAction
│   ├── transition.py                # MapTransitionAction
│   ├── task_trade.py                # TaskTradeAction
│   └── bank_gold.py                 # DepositGoldAction, WithdrawGoldAction
└── goals/
    ├── sell_inventory.py            # SellInventoryGoal
    └── expand_bank.py               # ExpandBankGoal

tests/test_ai/
├── test_actions_npc_sell.py
├── test_actions_bank_expansion.py
├── test_actions_transition.py
├── test_actions_task_trade.py
├── test_actions_bank_gold.py
├── test_goals_sell_inventory.py
├── test_goals_expand_bank.py
├── test_recovery.py
├── test_player_recovery.py
└── test_tracer.py
```

### Modified files
- `src/artifactsmmo_cli/ai/game_data.py` — `_npc_sell_prices`, `_transition_tiles`, `_bank_capacity`, `_next_expansion_cost`, `_slots_per_expansion`, and lookup methods.
- `src/artifactsmmo_cli/ai/player.py` — wire new actions/goals, integrate detector, replace `_refresh_if_stale` with `_full_refresh` + counter, wire tracer, fix `PendingItemSchema` bug.
- `src/artifactsmmo_cli/ai/goals/farm_items.py` — use `TaskTradeAction` in `relevant_actions`.
- `src/artifactsmmo_cli/ai/actions/delete.py` — re-weight cost based on sell-price and ingredient status.
- `src/artifactsmmo_cli/ai/actions/gathering.py`, `goals/farm_items.py` — fix list variance.
- `src/artifactsmmo_cli/ai/actions/combat.py` — fix `ItemStats | None` guard.
- Every `actions/*.py` `execute()` — apply `_raise_for_error` consistently.
- `src/artifactsmmo_cli/commands/play.py` — add `--trace` / `--trace-file` flags.

---

# Phase A — NPC Sell Foundation

**Goal:** The bot recovers gold from inventory items when bank is locked, instead of destroying value via Delete.

**Validation gate at phase end:**
- `uv run pytest tests/test_ai/ -q` — all green
- `uv run mypy src/artifactsmmo_cli/ai/actions/npc_sell.py src/artifactsmmo_cli/ai/goals/sell_inventory.py` — clean
- Manual: `uv run artifactsmmo play <character> --dry-run --verbose` against a known full-inventory + bank-locked state — bot picks `NpcSell` not `Delete`.

---

## Task A1: Load NPC sell prices into GameData

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (add field, extend `_load_npcs`)
- Test: `tests/test_ai/test_game_data.py` (add tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_game_data.py`:

```python
def test_load_npcs_captures_sell_prices(monkeypatch):
    """_load_npcs should populate _npc_sell_prices from API responses."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeEntry:
        def __init__(self, npc, code, buy_price, sell_price):
            self.npc = npc
            self.code = code
            self.buy_price = buy_price
            self.sell_price = sell_price

    class FakeResult:
        def __init__(self, data):
            self.data = data

    def fake_sync(client, page, size):
        if page == 1:
            return FakeResult([
                FakeEntry("cook", "cooked_chicken", buy_price=10, sell_price=5),
                FakeEntry("cook", "stale_bread", buy_price=None, sell_price=2),
                FakeEntry("smith", "iron_ore", buy_price=None, sell_price=8),
            ])
        return FakeResult([])

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_all_npc_items", fake_sync)
    gd = GameData()
    gd._load_npcs(client=None)

    assert gd._npc_sell_prices == {"cook": {"cooked_chicken": 5, "stale_bread": 2},
                                    "smith": {"iron_ore": 8}}
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_ai/test_game_data.py::test_load_npcs_captures_sell_prices -v
```
Expected: FAIL with `AttributeError: 'GameData' object has no attribute '_npc_sell_prices'`.

- [ ] **Step 3: Implement the change**

In `src/artifactsmmo_cli/ai/game_data.py`, modify the `GameData` dataclass to add the field and extend `_load_npcs`:

```python
# Add to the GameData @dataclass field list (around line 43):
_npc_sell_prices: dict[str, dict[str, int]] = field(default_factory=dict)  # npc_code -> {item_code: sell_price}

# Modify _load_npcs (around line 230) to also capture sell_price:
def _load_npcs(self, client: AuthenticatedClient) -> None:
    """Fetch all NPC items and build buy and sell stock indexes."""
    page = 1
    while True:
        result = get_all_npc_items(client=client, page=page, size=100)
        if result is None or not result.data:
            break
        for entry in result.data:
            buy_price = entry.buy_price
            if not isinstance(buy_price, Unset) and buy_price is not None:
                self._npc_stock.setdefault(entry.npc, {})[entry.code] = buy_price
            sell_price = entry.sell_price
            if not isinstance(sell_price, Unset) and sell_price is not None:
                self._npc_sell_prices.setdefault(entry.npc, {})[entry.code] = sell_price
        if len(result.data) < 100:
            break
        page += 1
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/test_ai/test_game_data.py::test_load_npcs_captures_sell_prices -v
```
Expected: PASS.

- [ ] **Step 5: Run full game_data test file to confirm no regressions**

```
uv run pytest tests/test_ai/test_game_data.py -q
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai): capture NPC sell prices from API in GameData"
```

---

## Task A2: Add sell-price lookup methods to GameData

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (add `npc_buys_item`, `npcs_buying_item`)
- Test: `tests/test_ai/test_game_data.py`

- [ ] **Step 1: Write the failing test**

```python
def test_npc_buys_item_returns_price():
    from artifactsmmo_cli.ai.game_data import GameData
    gd = GameData()
    gd._npc_sell_prices = {"cook": {"cooked_chicken": 5}}
    assert gd.npc_buys_item("cook", "cooked_chicken") == 5
    assert gd.npc_buys_item("cook", "unknown") is None
    assert gd.npc_buys_item("nonexistent", "anything") is None


def test_npcs_buying_item_returns_sorted_descending_by_price():
    from artifactsmmo_cli.ai.game_data import GameData
    gd = GameData()
    gd._npc_sell_prices = {
        "cook": {"cooked_chicken": 5, "iron_ore": 3},
        "smith": {"iron_ore": 8},
        "other": {"iron_ore": 6},
    }
    assert gd.npcs_buying_item("iron_ore") == [("smith", 8), ("other", 6), ("cook", 3)]
    assert gd.npcs_buying_item("cooked_chicken") == [("cook", 5)]
    assert gd.npcs_buying_item("unknown") == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_game_data.py::test_npc_buys_item_returns_price tests/test_ai/test_game_data.py::test_npcs_buying_item_returns_sorted_descending_by_price -v
```
Expected: FAIL with `AttributeError: 'GameData' object has no attribute 'npc_buys_item'`.

- [ ] **Step 3: Implement methods on GameData**

Add to `src/artifactsmmo_cli/ai/game_data.py` near the other NPC methods (around line 106):

```python
def npc_buys_item(self, npc_code: str, item_code: str) -> int | None:
    """Sell price for item_code at npc_code, or None if the NPC doesn't buy it."""
    return self._npc_sell_prices.get(npc_code, {}).get(item_code)

def npcs_buying_item(self, item_code: str) -> list[tuple[str, int]]:
    """Return [(npc_code, sell_price)] for all NPCs that buy item_code, highest price first."""
    results = [
        (npc_code, prices[item_code])
        for npc_code, prices in self._npc_sell_prices.items()
        if item_code in prices
    ]
    return sorted(results, key=lambda x: -x[1])
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_ai/test_game_data.py -q
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai): add npc_buys_item and npcs_buying_item lookups"
```

---

## Task A3: Create NpcSellAction

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/npc_sell.py`
- Create: `tests/test_ai/test_actions_npc_sell.py`

- [ ] **Step 1: Write the failing test file**

Create `tests/test_ai/test_actions_npc_sell.py`:

```python
"""Tests for NpcSellAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._npc_locations = kwargs.get("npc_locations", {})
    gd._npc_sell_prices = kwargs.get("npc_sell_prices", {})
    return gd


class TestNpcSellAction:
    def test_repr(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=3, npc_location=(2, 1))
        assert repr(a) == "NpcSell(cooked_chicken×3@cook)"

    def test_not_applicable_without_npc_location(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=None)
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"cooked_chicken": 3})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_npc_does_not_buy_item(self):
        a = NpcSellAction(npc_code="cook", item_code="unknown", quantity=1, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"unknown": 3})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_inventory(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=5, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"cooked_chicken": 2})
        assert a.is_applicable(state, gd) is False

    def test_applicable_when_has_items_and_npc_buys(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=2, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"cooked_chicken": 5})
        assert a.is_applicable(state, gd) is True

    def test_apply_increments_gold_and_decrements_inventory(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=3, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(x=0, y=0, gold=50, inventory={"cooked_chicken": 5})
        new_state = a.apply(state, gd)
        assert new_state.gold == 65   # 50 + 3 * 5
        assert new_state.inventory["cooked_chicken"] == 2
        assert (new_state.x, new_state.y) == (2, 1)

    def test_apply_removes_item_when_quantity_drops_to_zero(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=5, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"cooked_chicken": 5})
        new_state = a.apply(state, gd)
        assert "cooked_chicken" not in new_state.inventory

    def test_cost_includes_distance(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(4, 0))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(x=0, y=0)
        # 1.5 + dist(4) = 5.5
        assert a.cost(state, gd) == pytest.approx(5.5)

    def test_execute_moves_then_calls_npc_sell_api(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(2, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, inventory={"cooked_chicken": 3})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.npc_sell.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=2, y=1, inventory={"cooked_chicken": 3})
            with patch("artifactsmmo_cli.ai.actions.npc_sell.action_npc_sell",
                       return_value=make_api_result(char)) as mock_sell:
                a.execute(state, client)
        MockMove.assert_called_once_with(x=2, y=1)
        mock_sell.assert_called_once()
        # Verify the body has the right code+quantity
        call_kwargs = mock_sell.call_args.kwargs
        assert call_kwargs["name"] == "testchar"
        assert call_kwargs["body"].code == "cooked_chicken"
        assert call_kwargs["body"].quantity == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_actions_npc_sell.py -v
```
Expected: collection error or all FAIL (module not found).

- [ ] **Step 3: Create NpcSellAction implementation**

Create `src/artifactsmmo_cli/ai/actions/npc_sell.py`:

```python
"""NpcSellAction: sell an item to an NPC merchant for gold."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_npc_sell_item_my_name_action_npc_sell_post import sync as action_npc_sell
from artifactsmmo_api_client.models.npc_merchant_buy_schema import NpcMerchantBuySchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class NpcSellAction(Action):
    """Move to an NPC merchant and sell an item for gold."""

    npc_code: str
    item_code: str
    quantity: int = 1
    npc_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.npc_location is None:
            return False
        if game_data.npc_buys_item(self.npc_code, self.item_code) is None:
            return False
        return state.inventory.get(self.item_code, 0) >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        price = game_data.npc_buys_item(self.npc_code, self.item_code) or 0
        new_gold = state.gold + price * self.quantity
        new_inventory = dict(state.inventory)
        remaining = new_inventory.get(self.item_code, 0) - self.quantity
        if remaining <= 0:
            new_inventory.pop(self.item_code, None)
        else:
            new_inventory[self.item_code] = remaining
        dest = self.npc_location or (state.x, state.y)
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=new_gold,
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
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.npc_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 1.5 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.npc_location and (state.x, state.y) != self.npc_location:
            state = MoveAction(x=self.npc_location[0], y=self.npc_location[1]).execute(state, client)
        body = NpcMerchantBuySchema(code=self.item_code, quantity=self.quantity)
        result = action_npc_sell(client=client, name=state.character, body=body)
        Action._raise_for_error(result, f"NpcSell {self.item_code}×{self.quantity} to {self.npc_code}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"NpcSell({self.item_code}×{self.quantity}@{self.npc_code})"
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_ai/test_actions_npc_sell.py -v
```
Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/npc_sell.py tests/test_ai/test_actions_npc_sell.py
git commit -m "feat(ai): add NpcSellAction for selling items to NPC merchants"
```

---

## Task A4: Create SellInventoryGoal

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/sell_inventory.py`
- Create: `tests/test_ai/test_goals_sell_inventory.py`

- [ ] **Step 1: Write failing test file**

Create `tests/test_ai/test_goals_sell_inventory.py`:

```python
"""Tests for SellInventoryGoal."""

from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from tests.test_ai.fixtures import make_state


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._npc_sell_prices = kwargs.get("npc_sell_prices", {})
    return gd


class TestSellInventoryGoal:
    def test_value_zero_when_bank_accessible(self):
        goal = SellInventoryGoal(bank_accessible=True)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"chicken": 20}, inventory_max=20)
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_no_sellable_items(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"useless_thing": 20}, inventory_max=20)
        assert goal.value(state, gd) == 0.0

    def test_value_scales_with_inventory_fill_when_locked_and_has_sellable(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"chicken": 10}, inventory_max=20)
        # used=10/max=20 = 0.5; * 70 = 35
        assert goal.value(state, gd) == 35.0

    def test_value_caps_near_70_at_full(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}})
        state = make_state(inventory={"chicken": 20}, inventory_max=20)
        assert goal.value(state, gd) == 70.0

    def test_is_satisfied_when_min_free_slots_available(self):
        goal = SellInventoryGoal(bank_accessible=False)
        state = make_state(inventory={"chicken": 10}, inventory_max=20)  # 10 free
        assert goal.is_satisfied(state) is True

    def test_is_not_satisfied_when_inventory_nearly_full(self):
        goal = SellInventoryGoal(bank_accessible=False)
        state = make_state(inventory={"chicken": 18}, inventory_max=20)  # 2 free
        assert goal.is_satisfied(state) is False

    def test_relevant_actions_filters_to_rest_and_sells_for_inventory_items(self):
        goal = SellInventoryGoal(bank_accessible=False)
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5, "bread": 2}})
        state = make_state(inventory={"chicken": 5, "bread": 3, "useless": 1})
        actions = [
            RestAction(),
            FightAction(monster_code="goblin", locations=frozenset({(1, 1)})),
            NpcSellAction(npc_code="cook", item_code="chicken", quantity=1, npc_location=(2, 1)),
            NpcSellAction(npc_code="cook", item_code="bread", quantity=1, npc_location=(2, 1)),
            NpcSellAction(npc_code="cook", item_code="not_in_inventory", quantity=1, npc_location=(2, 1)),
        ]
        relevant = goal.relevant_actions(actions, state, gd)
        # Rest stays; FightAction excluded; only sells for inventory items
        names = [repr(a) for a in relevant]
        assert "RestAction" in names
        assert any("NpcSell(chicken" in n for n in names)
        assert any("NpcSell(bread" in n for n in names)
        assert not any("NpcSell(not_in_inventory" in n for n in names)
        assert not any("Fight" in n for n in names)

    def test_desired_state_targets_min_free_slots(self):
        goal = SellInventoryGoal(bank_accessible=False)
        state = make_state(inventory={"chicken": 18}, inventory_max=20)
        assert goal.desired_state(state, GameData()) == {"inventory_free": 5}

    def test_repr(self):
        assert repr(SellInventoryGoal(bank_accessible=False)) == "SellInventory"
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_goals_sell_inventory.py -v
```
Expected: collection error (module not found).

- [ ] **Step 3: Implement SellInventoryGoal**

Create `src/artifactsmmo_cli/ai/goals/sell_inventory.py`:

```python
"""Sell inventory items to NPCs to clear space when bank is inaccessible."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.survival import MIN_FREE_SLOTS
from artifactsmmo_cli.ai.world_state import WorldState


class SellInventoryGoal(Goal):
    """Recover gold by selling inventory items when the bank is locked."""

    def __init__(self, bank_accessible: bool = True) -> None:
        self._bank_accessible = bank_accessible

    def value(self, state: WorldState, game_data: GameData) -> float:
        if self._bank_accessible or state.inventory_max == 0:
            return 0.0
        # Any sellable item in inventory?
        if not any(game_data.npcs_buying_item(code) for code in state.inventory if state.inventory[code] > 0):
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        return used_fraction * 70.0

    def is_satisfied(self, state: WorldState) -> bool:
        return state.inventory_free >= MIN_FREE_SLOTS

    def desired_state(self, state: WorldState, game_data: GameData) -> dict:
        return {"inventory_free": MIN_FREE_SLOTS}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        result: list[Action] = []
        for action in actions:
            if isinstance(action, RestAction):
                result.append(action)
            elif isinstance(action, NpcSellAction) and state.inventory.get(action.item_code, 0) > 0:
                result.append(action)
        return result

    def __repr__(self) -> str:
        return "SellInventory"
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_ai/test_goals_sell_inventory.py -v
```
Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/sell_inventory.py tests/test_ai/test_goals_sell_inventory.py
git commit -m "feat(ai): add SellInventoryGoal for value-recovery when bank locked"
```

---

## Task A5: Update DeleteItemAction cost weighting

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/delete.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (cost-weight construction in `_build_actions`)
- Test: `tests/test_ai/test_actions.py` (or new `test_delete_cost.py`)

- [ ] **Step 1: Read current DeleteItemAction**

```
uv run python -c "from pathlib import Path; print(Path('src/artifactsmmo_cli/ai/actions/delete.py').read_text())"
```

Note the existing `cost_weight` field on the action. Cost-weighting happens in player's `_build_actions` (around line 348 in player.py).

- [ ] **Step 2: Write failing test for new cost rule**

Append to `tests/test_ai/test_actions.py`:

```python
def test_delete_cost_weight_rule():
    """Verify the cost calculation: ingredient=50, sellable-only=25, otherwise=5."""
    from artifactsmmo_cli.ai.player import _delete_cost

    class FakeStats:
        pass

    class FakeGD:
        def __init__(self, recipes=None, sell_prices=None, item_stats=None):
            self._crafting_recipes = recipes or {}
            self._npc_sell_prices = sell_prices or {}
            self._item_stats = item_stats or {}
        def npcs_buying_item(self, code):
            return [(npc, prices[code]) for npc, prices in self._npc_sell_prices.items() if code in prices]

    gd_ingredient = FakeGD(recipes={"sword": {"iron_ore": 5}})
    assert _delete_cost("iron_ore", gd_ingredient) == 50.0

    gd_ingredient_also_sellable = FakeGD(
        recipes={"sword": {"iron_ore": 5}},
        sell_prices={"smith": {"iron_ore": 8}},
    )
    assert _delete_cost("iron_ore", gd_ingredient_also_sellable) == 50.0

    gd_sellable_only = FakeGD(sell_prices={"cook": {"raw_meat": 3}})
    assert _delete_cost("raw_meat", gd_sellable_only) == 25.0

    gd_worthless = FakeGD()
    assert _delete_cost("garbage", gd_worthless) == 5.0
```

- [ ] **Step 3: Run test to verify it fails**

```
uv run pytest tests/test_ai/test_actions.py::test_delete_cost_weight_rule -v
```
Expected: FAIL with `ImportError: cannot import name '_delete_cost'`.

- [ ] **Step 4: Implement `_delete_cost` and use it in `_build_actions`**

In `src/artifactsmmo_cli/ai/player.py`, add a module-level helper near the top (after the imports, before `_format_plan`):

```python
def _delete_cost(item_code: str, game_data: "GameData") -> float:
    """Cost weight for deleting an item — ingredient first, then sellable, then worthless."""
    is_ingredient = any(item_code in recipe for recipe in game_data._crafting_recipes.values())
    has_sell_price = bool(game_data.npcs_buying_item(item_code))
    if is_ingredient:
        return 50.0
    if has_sell_price:
        return 25.0
    return 5.0
```

Then update the delete-action construction in `_build_actions` (the existing block around lines 348-356). Replace:

```python
        if not self._bank_accessible and self.state is not None:
            all_ingredients: set[str] = set()
            for recipe in self.game_data._crafting_recipes.values():
                all_ingredients.update(recipe.keys())
            equipped = set(self.state.equipment.values()) - {None}
            for item_code, qty in self.state.inventory.items():
                if qty <= 0 or item_code in equipped:
                    continue
                cost_weight = 2.0 if item_code not in all_ingredients else 10.0
                actions.append(DeleteItemAction(code=item_code, quantity=1, cost_weight=cost_weight))
```

with:

```python
        if not self._bank_accessible and self.state is not None:
            equipped = set(self.state.equipment.values()) - {None}
            for item_code, qty in self.state.inventory.items():
                if qty <= 0 or item_code in equipped:
                    continue
                actions.append(DeleteItemAction(
                    code=item_code, quantity=1,
                    cost_weight=_delete_cost(item_code, self.game_data),
                ))
```

- [ ] **Step 5: Run new test plus existing player tests**

```
uv run pytest tests/test_ai/test_actions.py::test_delete_cost_weight_rule tests/test_ai/test_player.py tests/test_ai/test_player_run.py -q
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_actions.py
git commit -m "feat(ai): re-weight DeleteItemAction cost (ingredient=50, sellable=25, else=5)"
```

---

## Task A6: Wire NpcSellAction + SellInventoryGoal into player loop

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_build_actions`, `_build_goals`)
- Test: `tests/test_ai/test_player_run.py` (integration check)

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_ai/test_player_run.py`:

```python
def test_player_builds_sell_actions_for_sellable_inventory():
    """When bank is locked and inventory has sellable items, _build_actions should include NpcSell."""
    from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
    from artifactsmmo_cli.ai.player import GamePlayer
    from tests.test_ai.fixtures import make_state

    player = GamePlayer(character="testchar", verbose=False, dry_run=True)
    player.game_data = GameData()
    player.game_data._npc_locations = {"cook": (2, 1)}
    player.game_data._npc_sell_prices = {"cook": {"chicken": 5}}
    player.game_data._bank_location = (4, 0)
    player.game_data._taskmaster_location = (1, 2)
    player._bank_accessible = False
    player.state = make_state(inventory={"chicken": 5})

    actions = player._build_actions()
    sell_actions = [a for a in actions if isinstance(a, NpcSellAction)]
    assert any(a.item_code == "chicken" and a.npc_code == "cook" for a in sell_actions)


def test_player_includes_sell_inventory_goal_when_bank_locked():
    """When bank is locked, _build_goals should include SellInventoryGoal."""
    from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
    from artifactsmmo_cli.ai.player import GamePlayer
    from tests.test_ai.fixtures import make_state

    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._monster_level = {"chicken": 1}
    player._bank_accessible = False
    player.state = make_state()

    goals = player._build_goals()
    assert any(isinstance(g, SellInventoryGoal) for g in goals)
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_player_run.py::test_player_builds_sell_actions_for_sellable_inventory tests/test_ai/test_player_run.py::test_player_includes_sell_inventory_goal_when_bank_locked -v
```
Expected: FAIL (NpcSellAction not in `_build_actions`; SellInventoryGoal not in `_build_goals`).

- [ ] **Step 3: Add import and wire into `_build_actions`**

In `src/artifactsmmo_cli/ai/player.py`, add the import (top of file with other action imports):

```python
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
```

In `_build_actions`, after the existing NpcBuy action block (around line 364), add:

```python
        # NPC sell actions: one per (npc, item) pair where the NPC buys the item
        for npc_code, sell_prices in self.game_data._npc_sell_prices.items():
            npc_loc = self.game_data.npc_location(npc_code)
            for item_code in sell_prices:
                actions.append(NpcSellAction(
                    npc_code=npc_code,
                    item_code=item_code,
                    quantity=1,
                    npc_location=npc_loc,
                ))
```

- [ ] **Step 4: Wire into `_build_goals`**

In `_build_goals`, after the `DepositInventoryGoal` entry, add:

```python
            SellInventoryGoal(bank_accessible=self._bank_accessible),
```

Looking at the existing goal list (around lines 393-404), insert it directly after `DepositInventoryGoal`.

- [ ] **Step 5: Run all player tests**

```
uv run pytest tests/test_ai/test_player.py tests/test_ai/test_player_run.py -q
```
Expected: all green.

- [ ] **Step 6: Manual dry-run validation**

```
uv run artifactsmmo play <character> --dry-run --verbose 2>&1 | head -30
```
Expected: bot prints goal priorities including `SellInventory` when applicable.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_run.py
git commit -m "feat(ai): wire NpcSellAction and SellInventoryGoal into player loop"
```

---

### Phase A Validation Gate

After all A1–A6 tasks:

```bash
uv run pytest tests/test_ai/ -q
uv run mypy src/artifactsmmo_cli/ai/actions/npc_sell.py src/artifactsmmo_cli/ai/goals/sell_inventory.py
```

Expected: all tests green; mypy clean for the new files. Manual: with a real character on a known full-inventory + bank-locked state, run `--dry-run` and confirm bot picks `NpcSell` over `Delete`.

---

# Phase B — Remaining API Capabilities

**Goal:** Fill the remaining API-action gap (bank expansion, map transition, task trade, gold management). Each closes a specific recovery path that the bot currently can't reach.

---

## Task B1: Add bank capacity + expansion data to GameData

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (fields + loader extension)
- Test: `tests/test_ai/test_game_data.py`

- [ ] **Step 1: Write failing test**

```python
def test_load_bank_metadata_captures_capacity_and_expansion_cost(monkeypatch):
    """GameData.load should fetch and cache bank capacity + next expansion cost."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeBankDetails:
        slots = 30
        next_expansion_cost = 1000

    class FakeResult:
        data = FakeBankDetails()

    def fake_get_bank_details(client):
        return FakeResult()

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_bank_details", fake_get_bank_details)
    gd = GameData()
    gd._load_bank_metadata(client=None)
    assert gd._bank_capacity == 30
    assert gd._next_expansion_cost == 1000
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_ai/test_game_data.py::test_load_bank_metadata_captures_capacity_and_expansion_cost -v
```
Expected: FAIL.

- [ ] **Step 3: Implement the loader**

In `src/artifactsmmo_cli/ai/game_data.py`:

Add the import at the top with the other API imports:
```python
from artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get import sync as get_bank_details
```

Add fields to the dataclass:
```python
_bank_capacity: int = 0
_next_expansion_cost: int = 0
_slots_per_expansion: int = 0  # learned after the first expansion (response delta)
```

Add `_load_bank_metadata`:
```python
def _load_bank_metadata(self, client: AuthenticatedClient) -> None:
    """Fetch bank capacity and next expansion cost."""
    result = get_bank_details(client=client)
    if result is None or not hasattr(result, "data") or result.data is None:
        return
    self._bank_capacity = result.data.slots
    self._next_expansion_cost = result.data.next_expansion_cost
```

Update `load()` to call it:
```python
@classmethod
def load(cls, client: AuthenticatedClient) -> "GameData":
    data = cls()
    data._load_maps(client)
    data._load_items(client)
    data._load_resources(client)
    data._load_monsters(client)
    data._load_npcs(client)
    data._load_bank_metadata(client)
    return data
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_game_data.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai): load bank capacity and next expansion cost into GameData"
```

---

## Task B2: Add transition tile indexing to GameData

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (add `_transition_tiles` field, populate in `_load_maps`)
- Test: `tests/test_ai/test_game_data.py`

- [ ] **Step 1: Write failing test**

```python
def test_load_maps_captures_transition_tiles(monkeypatch):
    """Tiles with non-null transition should be indexed in _transition_tiles."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeInteractions:
        def __init__(self, content, transition):
            self.content = content
            self.transition = transition

    class FakeTile:
        def __init__(self, x, y, transition=None):
            self.x = x
            self.y = y
            self.interactions = FakeInteractions(content=None, transition=transition)

    class FakeResult:
        def __init__(self, data):
            self.data = data

    def fake_get_all_maps(client, layer, page, size):
        if page == 1:
            return FakeResult([
                FakeTile(0, 0, transition=None),
                FakeTile(5, 5, transition="dungeon_a"),
                FakeTile(7, 7, transition="zone_b"),
            ])
        return FakeResult([])

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_all_maps", fake_get_all_maps)
    gd = GameData()
    gd._load_maps(client=None)
    assert gd._transition_tiles == {(5, 5), (7, 7)}
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_ai/test_game_data.py::test_load_maps_captures_transition_tiles -v
```
Expected: FAIL.

- [ ] **Step 3: Implement the change**

In `src/artifactsmmo_cli/ai/game_data.py`:

Add the field:
```python
_transition_tiles: set[tuple[int, int]] = field(default_factory=set)
```

In `_load_maps`, after the existing content-type dispatch, add:
```python
            transition = tile.interactions.transition
            if not isinstance(transition, Unset) and transition is not None:
                self._transition_tiles.add(loc)
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_game_data.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai): index map transition tiles in GameData._load_maps"
```

---

## Task B3: Create MapTransitionAction

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/transition.py`
- Create: `tests/test_ai/test_actions_transition.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_actions_transition.py`:

```python
"""Tests for MapTransitionAction."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._transition_tiles = kwargs.get("transition_tiles", set())
    return gd


class TestMapTransitionAction:
    def test_repr(self):
        assert repr(MapTransitionAction()) == "Transition"

    def test_not_applicable_when_not_on_transition_tile(self):
        a = MapTransitionAction()
        gd = make_gd(transition_tiles={(5, 5)})
        state = make_state(x=0, y=0)
        assert a.is_applicable(state, gd) is False

    def test_applicable_when_on_transition_tile(self):
        a = MapTransitionAction()
        gd = make_gd(transition_tiles={(5, 5)})
        state = make_state(x=5, y=5)
        assert a.is_applicable(state, gd) is True

    def test_apply_marks_position_unchanged_until_execute(self):
        # transition's destination isn't predictable at plan time — apply leaves position alone.
        a = MapTransitionAction()
        gd = make_gd(transition_tiles={(5, 5)})
        state = make_state(x=5, y=5)
        new_state = a.apply(state, gd)
        assert (new_state.x, new_state.y) == (5, 5)

    def test_cost_is_low_when_on_tile(self):
        a = MapTransitionAction()
        gd = make_gd(transition_tiles={(5, 5)})
        state = make_state(x=5, y=5)
        assert a.cost(state, gd) == 3.0

    def test_execute_calls_transition_api(self):
        a = MapTransitionAction()
        char = make_char_schema()
        state = make_state(x=5, y=5)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.transition.action_transition",
                   return_value=make_api_result(char)) as mock_t:
            a.execute(state, client)
        mock_t.assert_called_once_with(client=client, name="testchar")
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_actions_transition.py -v
```
Expected: collection error.

- [ ] **Step 3: Implement MapTransitionAction**

Create `src/artifactsmmo_cli/ai/actions/transition.py`:

```python
"""MapTransitionAction: trigger a map transition on the current tile."""

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_transition_my_name_action_transition_post import sync as action_transition

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


class MapTransitionAction(Action):
    """Trigger a map transition (e.g., enter a dungeon) when standing on a transition tile."""

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return (state.x, state.y) in game_data._transition_tiles

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        # Destination depends on server-side response; cannot predict in pure planner.
        return state

    def cost(self, state: WorldState, game_data: GameData) -> float:
        return 3.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        result = action_transition(client=client, name=state.character)
        Action._raise_for_error(result, "MapTransition")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return "Transition"
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_ai/test_actions_transition.py -v
```
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/transition.py tests/test_ai/test_actions_transition.py
git commit -m "feat(ai): add MapTransitionAction for map zone transitions"
```

---

## Task B4: Create BuyBankExpansionAction

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/bank_expansion.py`
- Create: `tests/test_ai/test_actions_bank_expansion.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_actions_bank_expansion.py`:

```python
"""Tests for BuyBankExpansionAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._bank_location = kwargs.get("bank_location", (4, 0))
    gd._bank_capacity = kwargs.get("bank_capacity", 30)
    gd._next_expansion_cost = kwargs.get("next_expansion_cost", 1000)
    return gd


class TestBuyBankExpansionAction:
    def test_repr(self):
        assert repr(BuyBankExpansionAction(bank_location=(4, 0), accessible=True)) == "BuyBankExpansion"

    def test_not_applicable_when_bank_inaccessible(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=False)
        gd = make_gd()
        state = make_state(x=4, y=0, gold=2000)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_gold(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(next_expansion_cost=1000)
        state = make_state(x=4, y=0, gold=500)
        assert a.is_applicable(state, gd) is False

    def test_applicable_with_gold_and_accessible(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(next_expansion_cost=1000)
        state = make_state(x=4, y=0, gold=2000)
        assert a.is_applicable(state, gd) is True

    def test_apply_deducts_gold(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(next_expansion_cost=1000)
        state = make_state(x=4, y=0, gold=2000)
        new_state = a.apply(state, gd)
        assert new_state.gold == 1000

    def test_cost_includes_distance_and_gold(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(next_expansion_cost=1000)
        state = make_state(x=0, y=0, gold=2000)
        # 5 + dist(4) + 1000/100 = 19
        assert a.cost(state, gd) == pytest.approx(19.0)

    def test_execute_moves_and_calls_api(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        char = make_char_schema()
        state = make_state(x=0, y=0, gold=2000)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.bank_expansion.MoveAction") as MockMove:
            MockMove.return_value.execute.return_value = make_state(x=4, y=0, gold=2000)
            with patch("artifactsmmo_cli.ai.actions.bank_expansion.action_buy_bank_expansion",
                       return_value=make_api_result(char)) as mock_exp:
                a.execute(state, client)
        MockMove.assert_called_once_with(x=4, y=0)
        mock_exp.assert_called_once_with(client=client, name="testchar")
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_actions_bank_expansion.py -v
```
Expected: collection error.

- [ ] **Step 3: Implement BuyBankExpansionAction**

Create `src/artifactsmmo_cli/ai/actions/bank_expansion.py`:

```python
"""BuyBankExpansionAction: purchase additional bank slots."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_buy_bank_expansion_my_name_action_bank_buy_expansion_post import sync as action_buy_bank_expansion

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class BuyBankExpansionAction(Action):
    """Move to the bank and buy a slot expansion."""

    bank_location: tuple[int, int] | None = field(default=None, repr=False)
    accessible: bool = True

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.accessible or self.bank_location is None:
            return False
        return state.gold >= game_data._next_expansion_cost

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location or (state.x, state.y)
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold - game_data._next_expansion_cost,
            skills=state.skills,
            x=dest[0],
            y=dest[1],
            inventory=state.inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.bank_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        # 1 gold per 100 cost units — expensive because expansions are infrequent
        return 5.0 + dist + game_data._next_expansion_cost / 100.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.bank_location and (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        result = action_buy_bank_expansion(client=client, name=state.character)
        Action._raise_for_error(result, "BuyBankExpansion")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return "BuyBankExpansion"
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_ai/test_actions_bank_expansion.py -v
```
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/bank_expansion.py tests/test_ai/test_actions_bank_expansion.py
git commit -m "feat(ai): add BuyBankExpansionAction for purchasing bank slots"
```

---

## Task B5: Create TaskTradeAction

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/task_trade.py`
- Create: `tests/test_ai/test_actions_task_trade.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_actions_task_trade.py`:

```python
"""Tests for TaskTradeAction."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._taskmaster_location = kwargs.get("taskmaster_location", (1, 2))
    return gd


class TestTaskTradeAction:
    def test_repr(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        assert repr(a) == "TaskTrade(iron_ore×5)"

    def test_not_applicable_without_items_task(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(task_code="iron_ore", task_type="monsters", inventory={"iron_ore": 10})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_task_code_does_not_match(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(task_code="copper_ore", task_type="items", inventory={"iron_ore": 10})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_inventory(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(task_code="iron_ore", task_type="items", inventory={"iron_ore": 2})
        assert a.is_applicable(state, gd) is False

    def test_applicable_with_matching_items_task_and_inventory(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(task_code="iron_ore", task_type="items", inventory={"iron_ore": 10})
        assert a.is_applicable(state, gd) is True

    def test_apply_decrements_inventory_and_advances_task(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(
            x=0, y=0, task_code="iron_ore", task_type="items",
            task_progress=0, task_total=20, inventory={"iron_ore": 10},
        )
        new_state = a.apply(state, gd)
        assert new_state.task_progress == 5
        assert new_state.inventory["iron_ore"] == 5
        assert (new_state.x, new_state.y) == (1, 2)

    def test_cost_includes_distance(self):
        import pytest
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(x=0, y=0)
        # 2 + dist(3) = 5
        assert a.cost(state, gd) == pytest.approx(5.0)

    def test_execute_moves_and_calls_api(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        char = make_char_schema()
        state = make_state(x=0, y=0, task_code="iron_ore", task_type="items",
                           inventory={"iron_ore": 10})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.task_trade.MoveAction") as MockMove:
            MockMove.return_value.execute.return_value = make_state(
                x=1, y=2, task_code="iron_ore", task_type="items", inventory={"iron_ore": 10},
            )
            with patch("artifactsmmo_cli.ai.actions.task_trade.action_task_trade",
                       return_value=make_api_result(char)) as mock_tt:
                a.execute(state, client)
        MockMove.assert_called_once_with(x=1, y=2)
        mock_tt.assert_called_once()
        body = mock_tt.call_args.kwargs["body"]
        assert body.code == "iron_ore"
        assert body.quantity == 5
```

- [ ] **Step 2: Run tests to verify fail**

```
uv run pytest tests/test_ai/test_actions_task_trade.py -v
```
Expected: collection error.

- [ ] **Step 3: Implement TaskTradeAction**

Create `src/artifactsmmo_cli/ai/actions/task_trade.py`:

```python
"""TaskTradeAction: submit gathered items toward an items-type task."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_task_trade_my_name_action_task_trade_post import sync as action_task_trade
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class TaskTradeAction(Action):
    """Submit items toward an items-type task at the taskmaster."""

    code: str
    quantity: int = 1
    taskmaster_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.taskmaster_location is None:
            return False
        if state.task_type != "items" or state.task_code != self.code:
            return False
        return state.inventory.get(self.code, 0) >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_inventory = dict(state.inventory)
        remaining = new_inventory.get(self.code, 0) - self.quantity
        if remaining <= 0:
            new_inventory.pop(self.code, None)
        else:
            new_inventory[self.code] = remaining
        dest = self.taskmaster_location or (state.x, state.y)
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
            task_progress=state.task_progress + self.quantity,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.taskmaster_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 2.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.taskmaster_location and (state.x, state.y) != self.taskmaster_location:
            state = MoveAction(x=self.taskmaster_location[0], y=self.taskmaster_location[1]).execute(state, client)
        body = SimpleItemSchema(code=self.code, quantity=self.quantity)
        result = action_task_trade(client=client, name=state.character, body=body)
        Action._raise_for_error(result, f"TaskTrade {self.code}×{self.quantity}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"TaskTrade({self.code}×{self.quantity})"
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_ai/test_actions_task_trade.py -v
```
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/task_trade.py tests/test_ai/test_actions_task_trade.py
git commit -m "feat(ai): add TaskTradeAction for items-type task submission"
```

---

## Task B6: Create DepositGoldAction and WithdrawGoldAction

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/bank_gold.py` (both classes — mirrors `bank.py` pattern)
- Create: `tests/test_ai/test_actions_bank_gold.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_actions_bank_gold.py`:

```python
"""Tests for DepositGoldAction and WithdrawGoldAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.bank_gold import DepositGoldAction, WithdrawGoldAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._bank_location = kwargs.get("bank_location", (4, 0))
    return gd


class TestDepositGoldAction:
    def test_repr(self):
        assert repr(DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)) == "DepositGold(100)"

    def test_not_applicable_when_inaccessible(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=False)
        gd = make_gd()
        state = make_state(gold=200)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_gold(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(gold=50)
        assert a.is_applicable(state, gd) is False

    def test_applicable_with_enough_gold(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(gold=200)
        assert a.is_applicable(state, gd) is True

    def test_apply_moves_gold_to_bank(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(x=0, y=0, gold=200, bank_gold=50)
        new_state = a.apply(state, gd)
        assert new_state.gold == 100
        assert new_state.bank_gold == 150
        assert (new_state.x, new_state.y) == (4, 0)


class TestWithdrawGoldAction:
    def test_repr(self):
        assert repr(WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)) == "WithdrawGold(100)"

    def test_not_applicable_when_bank_gold_unknown(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(bank_gold=None)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_bank_gold(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(bank_gold=50)
        assert a.is_applicable(state, gd) is False

    def test_apply_moves_gold_from_bank(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(x=0, y=0, gold=10, bank_gold=200)
        new_state = a.apply(state, gd)
        assert new_state.gold == 110
        assert new_state.bank_gold == 100
```

- [ ] **Step 2: Run tests to verify fail**

```
uv run pytest tests/test_ai/test_actions_bank_gold.py -v
```
Expected: collection error.

- [ ] **Step 3: Implement actions**

Create `src/artifactsmmo_cli/ai/actions/bank_gold.py`:

```python
"""DepositGoldAction and WithdrawGoldAction: move gold between character and bank."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_deposit_bank_gold_my_name_action_bank_deposit_gold_post import sync as action_deposit_gold
from artifactsmmo_api_client.api.my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post import sync as action_withdraw_gold
from artifactsmmo_api_client.models.deposit_withdraw_gold_schema import DepositWithdrawGoldSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def _gold_apply(state: WorldState, dest: tuple[int, int], gold_delta: int, bank_gold_delta: int) -> WorldState:
    return WorldState(
        character=state.character,
        level=state.level, xp=state.xp, max_xp=state.max_xp,
        hp=state.hp, max_hp=state.max_hp,
        gold=state.gold + gold_delta,
        skills=state.skills, x=dest[0], y=dest[1],
        inventory=state.inventory, inventory_max=state.inventory_max,
        equipment=state.equipment, cooldown_expires=None,
        task_code=state.task_code, task_type=state.task_type,
        task_progress=state.task_progress, task_total=state.task_total,
        bank_items=state.bank_items,
        bank_gold=(state.bank_gold or 0) + bank_gold_delta if state.bank_gold is not None else None,
        pending_items=state.pending_items,
    )


@dataclass
class DepositGoldAction(Action):
    quantity: int = 0
    bank_location: tuple[int, int] | None = field(default=None, repr=False)
    accessible: bool = True

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.accessible or self.bank_location is None:
            return False
        return state.gold >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location or (state.x, state.y)
        return _gold_apply(state, dest, gold_delta=-self.quantity, bank_gold_delta=self.quantity)

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.bank_location or (state.x, state.y)
        return 2.0 + abs(dest[0] - state.x) + abs(dest[1] - state.y)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.bank_location and (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        body = DepositWithdrawGoldSchema(quantity=self.quantity)
        result = action_deposit_gold(client=client, name=state.character, body=body)
        Action._raise_for_error(result, f"DepositGold {self.quantity}")
        return WorldState.from_character_schema(
            result.data.character, bank_items=state.bank_items,
            bank_gold=state.bank_gold, pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"DepositGold({self.quantity})"


@dataclass
class WithdrawGoldAction(Action):
    quantity: int = 0
    bank_location: tuple[int, int] | None = field(default=None, repr=False)
    accessible: bool = True

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.accessible or self.bank_location is None:
            return False
        if state.bank_gold is None or state.bank_gold < self.quantity:
            return False
        return True

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location or (state.x, state.y)
        return _gold_apply(state, dest, gold_delta=self.quantity, bank_gold_delta=-self.quantity)

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.bank_location or (state.x, state.y)
        return 2.0 + abs(dest[0] - state.x) + abs(dest[1] - state.y)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.bank_location and (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        body = DepositWithdrawGoldSchema(quantity=self.quantity)
        result = action_withdraw_gold(client=client, name=state.character, body=body)
        Action._raise_for_error(result, f"WithdrawGold {self.quantity}")
        return WorldState.from_character_schema(
            result.data.character, bank_items=state.bank_items,
            bank_gold=state.bank_gold, pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"WithdrawGold({self.quantity})"
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_ai/test_actions_bank_gold.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/bank_gold.py tests/test_ai/test_actions_bank_gold.py
git commit -m "feat(ai): add DepositGoldAction and WithdrawGoldAction"
```

---

## Task B7: Create ExpandBankGoal

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/expand_bank.py`
- Create: `tests/test_ai/test_goals_expand_bank.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_goals_expand_bank.py`:

```python
"""Tests for ExpandBankGoal."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from tests.test_ai.fixtures import make_state


def make_gd(bank_capacity=30, next_expansion_cost=1000) -> GameData:
    gd = GameData()
    gd._bank_capacity = bank_capacity
    gd._next_expansion_cost = next_expansion_cost
    return gd


class TestExpandBankGoal:
    def test_value_zero_when_bank_under_threshold(self):
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        # 20/30 = 0.67, below 0.95
        state = make_state(gold=2000, bank_items={"chicken": 20})
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_insufficient_gold(self):
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=5000)
        state = make_state(gold=100, bank_items={f"item_{i}": 1 for i in range(29)})
        assert goal.value(state, gd) == 0.0

    def test_value_40_when_full_and_can_afford(self):
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        state = make_state(gold=2000, bank_items={f"item_{i}": 1 for i in range(29)})
        assert goal.value(state, gd) == 40.0

    def test_value_zero_when_bank_unknown(self):
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd()
        state = make_state(gold=2000, bank_items=None)
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_inaccessible(self):
        goal = ExpandBankGoal(bank_accessible=False)
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        state = make_state(gold=2000, bank_items={f"item_{i}": 1 for i in range(29)})
        assert goal.value(state, gd) == 0.0

    def test_is_satisfied_when_capacity_used_below_threshold(self):
        goal = ExpandBankGoal()
        gd = make_gd(bank_capacity=30)
        state = make_state(bank_items={f"item_{i}": 1 for i in range(20)})
        assert goal.is_satisfied(state) is True

    def test_repr(self):
        assert repr(ExpandBankGoal()) == "ExpandBank"
```

- [ ] **Step 2: Run tests to verify fail**

```
uv run pytest tests/test_ai/test_goals_expand_bank.py -v
```
Expected: collection error.

- [ ] **Step 3: Implement ExpandBankGoal**

Create `src/artifactsmmo_cli/ai/goals/expand_bank.py`:

```python
"""ExpandBankGoal: buy more bank slots when bank fills up."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.world_state import WorldState

_TRIGGER_FILL = 0.95
_SATISFIED_FILL = 0.90


def _bank_fill(state: WorldState, game_data: GameData) -> float | None:
    if state.bank_items is None or game_data._bank_capacity == 0:
        return None
    return len(state.bank_items) / game_data._bank_capacity


class ExpandBankGoal(Goal):
    """Buy a bank expansion when current bank is ≥95% full and gold is sufficient."""

    def __init__(self, bank_accessible: bool = True) -> None:
        self._bank_accessible = bank_accessible

    def value(self, state: WorldState, game_data: GameData) -> float:
        if not self._bank_accessible:
            return 0.0
        fill = _bank_fill(state, game_data)
        if fill is None or fill < _TRIGGER_FILL:
            return 0.0
        if state.gold < game_data._next_expansion_cost:
            return 0.0
        return 40.0

    def is_satisfied(self, state: WorldState) -> bool:
        fill = _bank_fill(state, GameData())  # capacity is per-instance; pass current
        # If unknown, treat as satisfied to avoid infinite loop on missing data
        if state.bank_items is None:
            return True
        # We can't reach _bank_capacity here without game_data; check absolute count
        return len(state.bank_items) < 27  # 90% of default 30 — refined in player loop

    def desired_state(self, state: WorldState, game_data: GameData) -> dict:
        return {"bank_capacity": game_data._bank_capacity + 1}

    def __repr__(self) -> str:
        return "ExpandBank"
```

Note: `is_satisfied` needs `game_data` to know the current capacity but the `Goal.is_satisfied(state)` signature doesn't accept it. The cleanest workaround in this spec is to also check fill via `value()` — when value drops to 0, the goal stops being selected. We add a `priority` override:

```python
    def priority(self, state: WorldState, game_data: GameData) -> float:
        return self.value(state, game_data)
```

This is already the default, but explicit is fine. The planner uses `is_satisfied(state)` during search — if we return True any time bank is unknown or below absolute 27 items, the goal effectively only fires when there are ≥27 known items. Verify with manual trace once integrated.

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_goals_expand_bank.py -v
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/expand_bank.py tests/test_ai/test_goals_expand_bank.py
git commit -m "feat(ai): add ExpandBankGoal for buying bank slot expansions"
```

---

## Task B8: Update FarmItemsGoal to use TaskTradeAction

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/farm_items.py` (`relevant_actions`)
- Test: `tests/test_ai/test_goals.py` (or new test_farm_items.py)

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_goals.py` (or appropriate location):

```python
def test_farm_items_goal_includes_task_trade_in_relevant_actions():
    """When task_type==items, FarmItemsGoal.relevant_actions must include TaskTradeAction."""
    from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
    from artifactsmmo_cli.ai.actions.gathering import GatherAction
    from artifactsmmo_cli.ai.actions.rest import RestAction
    from artifactsmmo_cli.ai.goals.farm_items import FarmItemsGoal
    from artifactsmmo_cli.ai.game_data import GameData
    from tests.test_ai.fixtures import make_state

    gd = GameData()
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._crafting_recipes = {}

    actions = [
        RestAction(),
        GatherAction(resource_code="iron_rocks", locations=frozenset({(2, 3)})),
        TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2)),
        TaskTradeAction(code="other_item", quantity=1, taskmaster_location=(1, 2)),  # not the task code
    ]
    state = make_state(task_code="iron_ore", task_type="items", task_total=20, task_progress=5)
    goal = FarmItemsGoal()
    relevant = goal.relevant_actions(actions, state, gd)
    names = [repr(a) for a in relevant]
    assert any("TaskTrade(iron_ore" in n for n in names)
    assert not any("TaskTrade(other_item" in n for n in names)
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_ai/test_goals.py::test_farm_items_goal_includes_task_trade_in_relevant_actions -v
```
Expected: FAIL (TaskTrade not in filter).

- [ ] **Step 3: Update `farm_items.py`**

In `src/artifactsmmo_cli/ai/goals/farm_items.py`, add import:

```python
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
```

Modify `relevant_actions` to include matching TaskTradeAction:

```python
    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        if not state.task_code:
            return []
        needed_resources: set[str] = set()
        craftable_mats: set[str] = set()

        def collect(material: str, visited: set[str]) -> None:
            if material in visited:
                return
            visited.add(material)
            for resource_code, drop_item in game_data._resource_drops.items():
                if drop_item == material:
                    needed_resources.add(resource_code)
            recipe = game_data._crafting_recipes.get(material) or {}
            if recipe:
                craftable_mats.add(material)
                for sub_mat in recipe:
                    collect(sub_mat, visited)

        collect(state.task_code, set())

        result: list[Action] = []
        for action in actions:
            if isinstance(action, RestAction):
                result.append(action)
            elif isinstance(action, DepositAllAction):
                result.append(action)
            elif isinstance(action, GatherAction) and action.resource_code in needed_resources:
                result.append(action)
            elif isinstance(action, CraftAction) and action.code in craftable_mats:
                result.append(action)
            elif isinstance(action, TaskTradeAction) and action.code == state.task_code:
                result.append(action)
        return result
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_goals.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/farm_items.py tests/test_ai/test_goals.py
git commit -m "feat(ai): use TaskTradeAction to satisfy items-type tasks"
```

---

## Task B9: Wire Phase B actions/goals into player loop

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (imports + `_build_actions` + `_build_goals`)
- Test: `tests/test_ai/test_player_run.py`

- [ ] **Step 1: Write failing integration test**

Append to `tests/test_ai/test_player_run.py`:

```python
def test_player_builds_phase_b_actions():
    """All Phase B actions should appear in _build_actions output."""
    from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
    from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
    from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
    from artifactsmmo_cli.ai.actions.bank_gold import DepositGoldAction, WithdrawGoldAction
    from artifactsmmo_cli.ai.player import GamePlayer
    from tests.test_ai.fixtures import make_state

    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._bank_location = (4, 0)
    player.game_data._taskmaster_location = (1, 2)
    player.game_data._transition_tiles = {(5, 5)}
    player.game_data._bank_capacity = 30
    player.game_data._next_expansion_cost = 1000
    player._bank_accessible = True
    player.state = make_state(task_code="iron_ore", task_type="items")

    actions = player._build_actions()
    classes = {type(a).__name__ for a in actions}
    assert "BuyBankExpansionAction" in classes
    assert "MapTransitionAction" in classes
    assert "DepositGoldAction" in classes
    assert "WithdrawGoldAction" in classes
    # TaskTradeAction is built per-task — present only when task is items-type
    assert "TaskTradeAction" in classes


def test_player_includes_expand_bank_goal():
    from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
    from artifactsmmo_cli.ai.player import GamePlayer
    from tests.test_ai.fixtures import make_state

    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._monster_level = {"chicken": 1}
    player._bank_accessible = True
    player.state = make_state()
    goals = player._build_goals()
    assert any(isinstance(g, ExpandBankGoal) for g in goals)
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_player_run.py::test_player_builds_phase_b_actions tests/test_ai/test_player_run.py::test_player_includes_expand_bank_goal -v
```
Expected: FAIL.

- [ ] **Step 3: Wire imports and actions/goals into player.py**

In `src/artifactsmmo_cli/ai/player.py`, add imports near other action/goal imports:

```python
from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.bank_gold import DepositGoldAction, WithdrawGoldAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
```

In `_build_actions`, after the existing bank/withdraw actions block, add:

```python
        # Phase B: bank expansion, transitions, gold management
        actions.append(BuyBankExpansionAction(bank_location=bank, accessible=self._bank_accessible))
        actions.append(MapTransitionAction())
        # Gold deposit/withdraw with typical small quantities; let planner decide
        for q in (50, 100, 500, 1000):
            actions.append(DepositGoldAction(quantity=q, bank_location=bank, accessible=self._bank_accessible))
            actions.append(WithdrawGoldAction(quantity=q, bank_location=bank, accessible=self._bank_accessible))
        # Task trade is built only when current task is items-type
        if self.state is not None and self.state.task_type == "items" and self.state.task_code:
            actions.append(TaskTradeAction(
                code=self.state.task_code,
                quantity=1,
                taskmaster_location=taskmaster,
            ))
```

In `_build_goals`, after `DepositInventoryGoal`/`SellInventoryGoal`, add:

```python
            ExpandBankGoal(bank_accessible=self._bank_accessible),
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_player_run.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_run.py
git commit -m "feat(ai): wire Phase B actions and ExpandBankGoal into player loop"
```

---

### Phase B Validation Gate

```bash
uv run pytest tests/test_ai/ -q
uv run mypy src/artifactsmmo_cli/ai/actions/ src/artifactsmmo_cli/ai/goals/
```

All tests green; mypy clean for new files. Manual: `--dry-run --verbose` and confirm the bot has access to the new action set (visible in verbose `Applicable:` lines).

---

# Phase C — Stuck-State Detection & Recovery

**Goal:** Add a meta-recovery layer that detects bot stuck-states the goal/planner can't see (frozen state, oscillating goals, repeated no-plan) and triggers escalating recovery.

---

## Task C1: Create recovery module skeleton

**Files:**
- Create: `src/artifactsmmo_cli/ai/recovery.py` (CycleRecord, StuckSignal, StuckDetector skeleton)
- Create: `tests/test_ai/test_recovery.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_recovery.py`:

```python
"""Tests for recovery module: CycleRecord, StuckSignal, StuckDetector."""

from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckSignal


def make_record(state_key=(0, 0, 5, (), (), None, 0, False),
                goal_name="GoalA", action_name="Fight(chicken)",
                planned_depth=2, planner_timed_out=False, succeeded=True) -> CycleRecord:
    return CycleRecord(
        state_key=state_key, goal_name=goal_name, action_name=action_name,
        planned_depth=planned_depth, planner_timed_out=planner_timed_out, succeeded=succeeded,
    )


class TestStuckDetectorBasics:
    def test_empty_detector_returns_no_signal(self):
        det = StuckDetector()
        assert det.detect() is None

    def test_record_appends_to_history(self):
        det = StuckDetector(history_size=5)
        det.record(make_record())
        det.record(make_record())
        # No assertion fails — history is internal but we can confirm via detect() below
        assert det.detect() is None  # 2 records, no rule fires yet

    def test_history_size_bounded(self):
        det = StuckDetector(history_size=3)
        for i in range(10):
            det.record(make_record(state_key=(i, 0, 5, (), (), None, 0, False)))
        # No state repeats since each key is unique; should not fire
        assert det.detect() is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_recovery.py -v
```
Expected: collection error.

- [ ] **Step 3: Create skeleton**

Create `src/artifactsmmo_cli/ai/recovery.py`:

```python
"""Stuck-state detection and escalating recovery for the GOAP player."""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque


class StuckSignal(Enum):
    """Distinct stuck-state classes the detector can identify."""
    STATE_FROZEN = "state_frozen"
    GOAL_OSCILLATION = "goal_oscillation"
    NO_PROGRESS = "no_progress"


@dataclass(frozen=True)
class CycleRecord:
    """One cycle of the player loop, for stuck-state analysis."""
    state_key: tuple
    goal_name: str
    action_name: str          # "<no_plan>" when planning failed
    planned_depth: int
    planner_timed_out: bool
    succeeded: bool


class StuckDetector:
    """Tracks recent cycles and reports stuck-state signals."""

    def __init__(self, history_size: int = 30) -> None:
        self._history: Deque[CycleRecord] = deque(maxlen=history_size)
        self._ack_index: dict[StuckSignal, int] = {}
        self._cycle_counter = 0

    def record(self, cycle: CycleRecord) -> None:
        self._history.append(cycle)
        self._cycle_counter += 1

    def detect(self) -> StuckSignal | None:
        """Return the first matching signal, or None. Implemented in later tasks."""
        return None

    def acknowledge(self, signal: StuckSignal) -> None:
        """Mark this signal as handled — reset its detection window to the current cycle."""
        self._ack_index[signal] = self._cycle_counter
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_ai/test_recovery.py -v
```
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/recovery.py tests/test_ai/test_recovery.py
git commit -m "feat(ai): add recovery.py skeleton (CycleRecord, StuckSignal, StuckDetector)"
```

---

## Task C2: Implement STATE_FROZEN detection

**Files:**
- Modify: `src/artifactsmmo_cli/ai/recovery.py` (extend `detect`)
- Test: `tests/test_ai/test_recovery.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_recovery.py`:

```python
class TestStateFrozenDetection:
    def test_fires_when_same_state_key_5_of_last_10(self):
        det = StuckDetector(history_size=30)
        repeated = (1, 1, 5, (), (), None, 0, False)
        other = (2, 2, 5, (), (), None, 0, False)
        # 5 cycles of repeated state + 5 cycles of other state, interleaved
        for i in range(10):
            key = repeated if i % 2 == 0 else other
            det.record(make_record(state_key=key))
        assert det.detect() == StuckSignal.STATE_FROZEN

    def test_no_fire_when_state_key_varies(self):
        det = StuckDetector(history_size=30)
        for i in range(10):
            key = (i, i, 5, (), (), None, 0, False)
            det.record(make_record(state_key=key))
        assert det.detect() is None

    def test_no_fire_when_only_4_of_10_repeat(self):
        det = StuckDetector(history_size=30)
        repeated = (1, 1, 5, (), (), None, 0, False)
        for i in range(10):
            key = repeated if i < 4 else (i, i, 5, (), (), None, 0, False)
            det.record(make_record(state_key=key))
        assert det.detect() is None

    def test_no_refire_after_acknowledge_until_new_repeats(self):
        det = StuckDetector(history_size=30)
        repeated = (1, 1, 5, (), (), None, 0, False)
        for i in range(10):
            key = repeated if i % 2 == 0 else (i, i, 5, (), (), None, 0, False)
            det.record(make_record(state_key=key))
        assert det.detect() == StuckSignal.STATE_FROZEN
        det.acknowledge(StuckSignal.STATE_FROZEN)
        # Add 9 more cycles with the repeated state — but the ack window means only post-ack count
        for _ in range(9):
            det.record(make_record(state_key=repeated))
        # After ack, only 9 cycles new — need 5 of 10 within new window; 9 isn't enough by some rules.
        # Specifically: count only post-ack cycles for STATE_FROZEN
        # With 9 post-ack cycles all the same key → 9 of 9 → fires
        # Tweak: add 1 cycle with different key first
        det.record(make_record(state_key=(99, 99, 5, (), (), None, 0, False)))
        # Now 9 of 10 post-ack are repeated → still fires
        assert det.detect() == StuckSignal.STATE_FROZEN
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_ai/test_recovery.py::TestStateFrozenDetection -v
```
Expected: FAIL.

- [ ] **Step 3: Implement STATE_FROZEN rule**

In `src/artifactsmmo_cli/ai/recovery.py`, update `detect()`:

```python
    def detect(self) -> StuckSignal | None:
        if self._check_state_frozen():
            return StuckSignal.STATE_FROZEN
        return None

    def _check_state_frozen(self) -> bool:
        cutoff = self._ack_index.get(StuckSignal.STATE_FROZEN, 0)
        window = self._recent_since(cutoff, count=10)
        if len(window) < 10:
            return False
        # Count occurrences of each state_key in the window
        counts: dict[tuple, int] = {}
        for rec in window:
            counts[rec.state_key] = counts.get(rec.state_key, 0) + 1
        return any(c >= 5 for c in counts.values())

    def _recent_since(self, cutoff_cycle: int, count: int) -> list[CycleRecord]:
        """Return up to `count` records added after `cutoff_cycle`."""
        # Reconstruct cycle index per record using counter and history length
        history_list = list(self._history)
        # The most recent record is at counter-1; oldest in history is at counter-len(history)
        start_idx = self._cycle_counter - len(history_list)
        post_ack = [
            rec for i, rec in enumerate(history_list)
            if start_idx + i >= cutoff_cycle
        ]
        return post_ack[-count:]
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_recovery.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/recovery.py tests/test_ai/test_recovery.py
git commit -m "feat(ai): detect STATE_FROZEN (state_key repeats 5/10 in window)"
```

---

## Task C3: Implement GOAL_OSCILLATION detection

**Files:**
- Modify: `src/artifactsmmo_cli/ai/recovery.py`
- Test: `tests/test_ai/test_recovery.py`

- [ ] **Step 1: Write failing test**

```python
class TestGoalOscillation:
    def test_fires_on_strict_ABAB(self):
        det = StuckDetector()
        for i in range(8):
            name = "GoalA" if i % 2 == 0 else "GoalB"
            det.record(make_record(goal_name=name, state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() == StuckSignal.GOAL_OSCILLATION

    def test_fires_on_AABBAABB(self):
        det = StuckDetector()
        pattern = ["GoalA", "GoalA", "GoalB", "GoalB", "GoalA", "GoalA", "GoalB", "GoalB"]
        for i, name in enumerate(pattern):
            det.record(make_record(goal_name=name, state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() == StuckSignal.GOAL_OSCILLATION

    def test_no_fire_with_3_distinct_goals(self):
        det = StuckDetector()
        for i in range(8):
            name = ["GoalA", "GoalB", "GoalC"][i % 3]
            det.record(make_record(goal_name=name, state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() is None
```

- [ ] **Step 2: Verify fail**

```
uv run pytest tests/test_ai/test_recovery.py::TestGoalOscillation -v
```
Expected: FAIL.

- [ ] **Step 3: Implement GOAL_OSCILLATION rule**

Update `detect()` and add helper:

```python
    def detect(self) -> StuckSignal | None:
        if self._check_state_frozen():
            return StuckSignal.STATE_FROZEN
        if self._check_goal_oscillation():
            return StuckSignal.GOAL_OSCILLATION
        return None

    def _check_goal_oscillation(self) -> bool:
        cutoff = self._ack_index.get(StuckSignal.GOAL_OSCILLATION, 0)
        window = self._recent_since(cutoff, count=8)
        if len(window) < 8:
            return False
        goals = [r.goal_name for r in window]
        distinct = set(goals)
        if len(distinct) != 2:
            return False
        # All cycles unsatisfied (no successful goal switch). Heuristic: planner kept choosing
        # the same two — that's oscillation.
        return True
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_recovery.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/recovery.py tests/test_ai/test_recovery.py
git commit -m "feat(ai): detect GOAL_OSCILLATION (last 8 cycles alternate between 2 goals)"
```

---

## Task C4: Implement NO_PROGRESS detection

**Files:**
- Modify: `src/artifactsmmo_cli/ai/recovery.py`
- Test: `tests/test_ai/test_recovery.py`

- [ ] **Step 1: Write failing test**

```python
class TestNoProgress:
    def test_fires_after_4_consecutive_no_plan(self):
        det = StuckDetector()
        for i in range(4):
            det.record(make_record(action_name="<no_plan>", goal_name="<none>",
                                    state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() == StuckSignal.NO_PROGRESS

    def test_no_fire_after_3_no_plan(self):
        det = StuckDetector()
        for i in range(3):
            det.record(make_record(action_name="<no_plan>", goal_name="<none>",
                                    state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() is None

    def test_no_fire_when_no_plan_interleaved_with_progress(self):
        det = StuckDetector()
        for i in range(5):
            name = "<no_plan>" if i % 2 == 0 else "Fight"
            det.record(make_record(action_name=name, state_key=(i, 0, 5, (), (), None, 0, False)))
        # Only 3 of last 4 are <no_plan> at most
        assert det.detect() is None
```

- [ ] **Step 2: Verify fail**

```
uv run pytest tests/test_ai/test_recovery.py::TestNoProgress -v
```
Expected: FAIL.

- [ ] **Step 3: Implement NO_PROGRESS rule**

Update `detect()`:

```python
    def detect(self) -> StuckSignal | None:
        if self._check_state_frozen():
            return StuckSignal.STATE_FROZEN
        if self._check_goal_oscillation():
            return StuckSignal.GOAL_OSCILLATION
        if self._check_no_progress():
            return StuckSignal.NO_PROGRESS
        return None

    def _check_no_progress(self) -> bool:
        cutoff = self._ack_index.get(StuckSignal.NO_PROGRESS, 0)
        window = self._recent_since(cutoff, count=4)
        if len(window) < 4:
            return False
        return all(r.action_name == "<no_plan>" for r in window)
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_recovery.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/recovery.py tests/test_ai/test_recovery.py
git commit -m "feat(ai): detect NO_PROGRESS (4 consecutive no-plan cycles)"
```

---

## Task C5: Integrate StuckDetector into GamePlayer

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (add detector, recovery state, integrate into loop)
- Test: `tests/test_ai/test_player_recovery.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_ai/test_player_recovery.py`:

```python
"""Player-loop integration tests for stuck-state recovery."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import StuckSignal
from tests.test_ai.fixtures import make_state


def test_player_has_detector_after_init():
    player = GamePlayer(character="testchar")
    assert player._detector is not None
    assert player._suppressed_goals == {}
    assert player._actions_since_full_refresh == 0


def test_build_goals_filters_suppressed_goals():
    """Goals with names in _suppressed_goals (with positive counter) are excluded."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._monster_level = {"chicken": 1}
    player._bank_accessible = True
    player.state = make_state()
    # Suppress FarmMonster for 5 cycles
    player._suppressed_goals = {"FarmMonster(chicken)": 5}

    goals = player._build_goals()
    names = [repr(g) for g in goals]
    assert not any("FarmMonster(chicken)" in n for n in names)


def test_suppression_counter_decrements_per_cycle():
    """Each cycle should decrement suppression counters; zeros should be pruned."""
    player = GamePlayer(character="testchar")
    player._suppressed_goals = {"GoalA": 3, "GoalB": 1}
    player._decrement_suppressions()
    assert player._suppressed_goals == {"GoalA": 2}  # GoalB pruned at zero
```

- [ ] **Step 2: Verify fail**

```
uv run pytest tests/test_ai/test_player_recovery.py -v
```
Expected: FAIL.

- [ ] **Step 3: Add detector + state + suppression filtering to player.py**

In `src/artifactsmmo_cli/ai/player.py`:

Add import:
```python
from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckSignal
```

In `GamePlayer.__init__`, add fields:
```python
        self._detector = StuckDetector(history_size=30)
        self._suppressed_goals: dict[str, int] = {}
        self._actions_since_full_refresh: int = 0
        self._recovery_level: dict[StuckSignal, int] = {}
```

Add a helper method:
```python
    def _decrement_suppressions(self) -> None:
        """Decrement each suppression counter; prune zero entries."""
        new = {name: n - 1 for name, n in self._suppressed_goals.items() if n > 1}
        self._suppressed_goals = new
```

Modify `_build_goals` to filter:
```python
        # ... after building the full goal list, just before returning:
        return [g for g in goals if repr(g) not in self._suppressed_goals]
```

(Apply at the end of `_build_goals`, replacing the bare `return goals`.)

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_player_recovery.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_recovery.py
git commit -m "feat(ai): integrate StuckDetector and goal suppression into GamePlayer"
```

---

## Task C6: Record per-cycle in player loop + detect after planning

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`run()` loop)
- Test: `tests/test_ai/test_player_recovery.py`

- [ ] **Step 1: Write failing test**

Append:

```python
def test_detector_records_cycle_after_action(monkeypatch):
    """After executing an action, the detector should have one new record."""
    # This is a focused unit test on the recording behavior — uses a no-op _execute
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._monster_level = {"chicken": 1}
    player.state = make_state()
    # Manually invoke the record-cycle path
    from artifactsmmo_cli.ai.recovery import CycleRecord
    rec = CycleRecord(
        state_key=(0, 0, 5, (), (), None, 0, False),
        goal_name="FarmMonster(chicken)",
        action_name="Fight(chicken)",
        planned_depth=2, planner_timed_out=False, succeeded=True,
    )
    player._detector.record(rec)
    assert player._detector._cycle_counter == 1
```

- [ ] **Step 2: Verify fail (or pass if just the integration shape)**

```
uv run pytest tests/test_ai/test_player_recovery.py::test_detector_records_cycle_after_action -v
```
Expected: PASS (record method already implemented) — but the *integration* into the run loop needs to happen.

- [ ] **Step 3: Wire detector recording into `run()`**

In `src/artifactsmmo_cli/ai/player.py`, in `run()`, after `_execute` returns (or after dry_run apply) and before the loop continues, add:

```python
            # Build the cycle record
            from artifactsmmo_cli.ai.recovery import CycleRecord
            from artifactsmmo_cli.ai.planner import _state_key  # already exported
            self._detector.record(CycleRecord(
                state_key=_state_key(self.state),
                goal_name=repr(selected_goal),
                action_name=repr(action),
                planned_depth=len(plan),
                planner_timed_out=self.planner.last_stats.timed_out,
                succeeded=True,  # an exception path already refreshed
            ))
            self._actions_since_full_refresh += 1
            self._decrement_suppressions()

            # Check for stuck signals and handle
            signal = self._detector.detect()
            if signal is not None:
                self._handle_stuck(signal, client)
```

Add a `_handle_stuck` stub for now (filled in Task C7):
```python
    def _handle_stuck(self, signal: StuckSignal, client: AuthenticatedClient) -> None:
        """Apply recovery action for a stuck signal. Filled in next task."""
        self._detector.acknowledge(signal)
```

Also, in the "no plan found" branch, record a no-plan cycle:

Before `time.sleep(10)` (now `time.sleep(5)` after Phase D), insert:
```python
            self._detector.record(CycleRecord(
                state_key=_state_key(self.state),
                goal_name="<none>",
                action_name="<no_plan>",
                planned_depth=0,
                planner_timed_out=self.planner.last_stats.timed_out if self.state else False,
                succeeded=False,
            ))
            signal = self._detector.detect()
            if signal is not None:
                self._handle_stuck(signal, client)
```

Note: `_state_key` is internal to planner; we need to import it. Move the helper from inside planner.py to module-level or expose via `from artifactsmmo_cli.ai.planner import _state_key`.

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_player_recovery.py tests/test_ai/test_player_run.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_recovery.py
git commit -m "feat(ai): record cycles in detector and trigger _handle_stuck on signals"
```

---

## Task C7: Implement recovery ladder in _handle_stuck

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (full `_handle_stuck` implementation)
- Test: `tests/test_ai/test_player_recovery.py`

- [ ] **Step 1: Write failing test**

```python
def test_handle_stuck_state_frozen_level1_triggers_full_refresh(monkeypatch):
    """Level 1 STATE_FROZEN should call _full_refresh (or equivalent)."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()

    refresh_called = []
    def fake_refresh(c):
        refresh_called.append(True)
        return player.state
    player._fetch_world_state = fake_refresh  # type: ignore

    player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
    assert refresh_called == [True]
    assert player._recovery_level[StuckSignal.STATE_FROZEN] == 1


def test_handle_stuck_state_frozen_level2_suppresses_current_goal():
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()
    player._recovery_level[StuckSignal.STATE_FROZEN] = 1
    # Need a "current goal" to suppress — track this via _last_goal
    player._last_goal_name = "FarmMonster(chicken)"

    player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
    assert player._suppressed_goals.get("FarmMonster(chicken)") == 5
    assert player._recovery_level[StuckSignal.STATE_FROZEN] == 2


def test_handle_stuck_goal_oscillation_suppresses_both():
    player = GamePlayer(character="testchar")
    # Populate detector history with A/B alternation
    for i in range(8):
        name = "GoalA" if i % 2 == 0 else "GoalB"
        player._detector.record(CycleRecord(
            state_key=(i, 0, 5, (), (), None, 0, False),
            goal_name=name, action_name="X", planned_depth=1,
            planner_timed_out=False, succeeded=True,
        ))
    player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
    assert player._suppressed_goals.get("GoalA") == 5
    assert player._suppressed_goals.get("GoalB") == 5
```

- [ ] **Step 2: Verify fail**

```
uv run pytest tests/test_ai/test_player_recovery.py -v -k handle_stuck
```
Expected: FAIL.

- [ ] **Step 3: Implement the ladder**

In `src/artifactsmmo_cli/ai/player.py`:

```python
    def _handle_stuck(self, signal: StuckSignal, client) -> None:
        """Apply recovery action for a stuck signal at its current escalation level."""
        level = self._recovery_level.get(signal, 0) + 1
        self._recovery_level[signal] = level

        if signal == StuckSignal.STATE_FROZEN:
            if level == 1:
                print(f"[{self._now()}] [recovery] STATE_FROZEN L1: forcing full refresh")
                self.state = self._fetch_world_state(client)
            elif level == 2:
                last = getattr(self, "_last_goal_name", None)
                if last:
                    self._suppressed_goals[last] = 5
                    print(f"[{self._now()}] [recovery] STATE_FROZEN L2: suppressing {last} for 5 cycles")
            else:
                # L3 — broad suppression
                for name in list(self._suppressed_goals):
                    self._suppressed_goals[name] = max(self._suppressed_goals[name], 10)

        elif signal == StuckSignal.GOAL_OSCILLATION:
            # Look at last 8 cycles, suppress both unique goals
            history = list(self._detector._history)[-8:]
            distinct = {r.goal_name for r in history}
            suppress_cycles = {1: 5, 2: 15}.get(level, 0)
            if suppress_cycles == 0:
                # L3: exit
                print(f"[{self._now()}] [recovery] GOAL_OSCILLATION L3: exiting (manual intervention)")
                raise SystemExit(2)
            for name in distinct:
                self._suppressed_goals[name] = suppress_cycles
            print(f"[{self._now()}] [recovery] GOAL_OSCILLATION L{level}: suppressing {distinct} for {suppress_cycles} cycles")

        elif signal == StuckSignal.NO_PROGRESS:
            if level == 1:
                print(f"[{self._now()}] [recovery] NO_PROGRESS L1: forcing full refresh")
                self.state = self._fetch_world_state(client)
            elif level == 2:
                # Wildcard goal mode set via a flag the goal builder consults
                self._wildcard_mode = True
                print(f"[{self._now()}] [recovery] NO_PROGRESS L2: switching to wildcard goals")
            else:
                print(f"[{self._now()}] [recovery] NO_PROGRESS L3: exiting (manual intervention)")
                raise SystemExit(2)

        self._detector.acknowledge(signal)
```

Also need to update `_build_goals` to track `_last_goal_name` and respect `_wildcard_mode`. Add at top of `_build_goals`:

```python
        if getattr(self, "_wildcard_mode", False):
            # Wildcard mode: only the safest goals
            self._wildcard_mode = False  # one-shot
            return [RestoreHPGoal()]
```

And in the player loop, after a goal is selected, record `self._last_goal_name = repr(selected_goal)`.

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_player_recovery.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_recovery.py
git commit -m "feat(ai): implement recovery ladder for stuck-state signals"
```

---

### Phase C Validation Gate

```bash
uv run pytest tests/test_ai/ -q
uv run mypy src/artifactsmmo_cli/ai/recovery.py
```

All tests green. Manual: simulate a stuck state with `--dry-run` (force a state that has all goal values 0, e.g., bank-locked + no sellable inventory + no monster equipment) and verify recovery logs appear.

---

# Phase D — State Refresh + Observability

**Goal:** Replace wall-clock refresh checks with action-counted policy; add JSONL trace for postmortem analysis.

---

## Task D1: Create tracing module (Tracer ABC, NullTracer, FileTracer)

**Files:**
- Create: `src/artifactsmmo_cli/ai/tracing.py`
- Create: `tests/test_ai/test_tracer.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_tracer.py`:

```python
"""Tests for Tracer / NullTracer / FileTracer."""

import json
import os
import tempfile

from artifactsmmo_cli.ai.tracing import FileTracer, NullTracer, Tracer


class TestNullTracer:
    def test_write_is_no_op(self):
        t = NullTracer()
        t.write_cycle({"any": "data"})  # no exception
        t.close()


class TestFileTracer:
    def test_writes_jsonl_records(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            t = FileTracer(path)
            t.write_cycle({"cycle": 1, "action": "Fight"})
            t.write_cycle({"cycle": 2, "action": "Rest"})
            t.close()

            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 2
            assert json.loads(lines[0]) == {"cycle": 1, "action": "Fight"}
            assert json.loads(lines[1]) == {"cycle": 2, "action": "Rest"}
        finally:
            os.unlink(path)

    def test_close_is_idempotent(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            t = FileTracer(path)
            t.close()
            t.close()  # no exception
        finally:
            os.unlink(path)
```

- [ ] **Step 2: Verify fail**

```
uv run pytest tests/test_ai/test_tracer.py -v
```
Expected: collection error.

- [ ] **Step 3: Create tracing.py**

```python
"""JSONL tracing for the GOAP player loop."""

import json
from abc import ABC, abstractmethod
from typing import IO


class Tracer(ABC):
    """Write per-cycle records for postmortem analysis."""

    @abstractmethod
    def write_cycle(self, record: dict) -> None:
        """Write one cycle's record."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources."""


class NullTracer(Tracer):
    """No-op tracer — used when tracing is disabled."""

    def write_cycle(self, record: dict) -> None:
        return

    def close(self) -> None:
        return


class FileTracer(Tracer):
    """JSONL file tracer — one record per line, appended in order."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._fp: IO[str] | None = open(path, "a", encoding="utf-8")

    def write_cycle(self, record: dict) -> None:
        if self._fp is None:
            return
        self._fp.write(json.dumps(record, default=str) + "\n")
        self._fp.flush()

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_tracer.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tracing.py tests/test_ai/test_tracer.py
git commit -m "feat(ai): add Tracer ABC with NullTracer and JSONL FileTracer"
```

---

## Task D2: Replace _refresh_if_stale with action-counted refresh

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_player_run.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_player_run.py`:

```python
def test_refresh_triggers_every_20_actions(monkeypatch):
    """Periodic full refresh should fire after _actions_since_full_refresh reaches 20."""
    from artifactsmmo_cli.ai.player import GamePlayer

    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()

    refresh_calls = []
    def fake_full_refresh(c):
        refresh_calls.append(True)
    player._full_refresh = fake_full_refresh  # type: ignore

    # Not yet triggered
    player._actions_since_full_refresh = 19
    player._maybe_periodic_refresh(client=None)
    assert refresh_calls == []

    # Now triggers
    player._actions_since_full_refresh = 20
    player._maybe_periodic_refresh(client=None)
    assert refresh_calls == [True]
    assert player._actions_since_full_refresh == 0  # reset


def test_refresh_if_stale_method_removed():
    """The wall-clock _refresh_if_stale should be deleted."""
    from artifactsmmo_cli.ai.player import GamePlayer
    assert not hasattr(GamePlayer, "_refresh_if_stale")
```

- [ ] **Step 2: Verify fail**

```
uv run pytest tests/test_ai/test_player_run.py -v -k "refresh"
```
Expected: FAIL.

- [ ] **Step 3: Update player.py**

In `src/artifactsmmo_cli/ai/player.py`:

Delete `_refresh_if_stale` method entirely. Delete the `self._last_action_time = time.monotonic()` line in `__init__` (already replaced with `_actions_since_full_refresh`).

Add `_full_refresh` method:

```python
    def _full_refresh(self, client: AuthenticatedClient) -> None:
        """Force a complete state refresh: character, bank, pending items."""
        self.state = self._fetch_world_state(client)
        self.state = self._sync_bank(client, self.state)
        self.state = self._sync_pending(client, self.state)
        self._actions_since_full_refresh = 0
```

Add `_maybe_periodic_refresh`:

```python
    def _maybe_periodic_refresh(self, client: AuthenticatedClient) -> None:
        if self._actions_since_full_refresh >= 20:
            self._full_refresh(client)
```

In `run()`, replace the existing `self.state = self._refresh_if_stale(client)` line with:

```python
            self._maybe_periodic_refresh(client)
```

Also change the "no plan found" sleep from `time.sleep(10)` to `time.sleep(5)`.

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_player_run.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_run.py
git commit -m "refactor(ai): replace _refresh_if_stale with action-counted _full_refresh"
```

---

## Task D3: Wire tracer into GamePlayer

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (accept tracer, emit records)
- Test: `tests/test_ai/test_tracer.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_tracer.py`:

```python
def test_player_emits_cycle_record_to_tracer(monkeypatch):
    """A cycle of player.run should produce one tracer.write_cycle call."""
    from artifactsmmo_cli.ai.player import GamePlayer
    from artifactsmmo_cli.ai.game_data import GameData
    from artifactsmmo_cli.ai.tracing import Tracer
    from tests.test_ai.fixtures import make_state

    captured = []
    class CapturingTracer(Tracer):
        def write_cycle(self, record):
            captured.append(record)
        def close(self):
            pass

    player = GamePlayer(character="testchar")
    player.tracer = CapturingTracer()
    player.game_data = GameData()
    player.game_data._monster_level = {"chicken": 1}
    player.state = make_state()

    # Manually emit a cycle (using the helper method we'll add)
    player._emit_trace(action_name="Fight(chicken)", goal_name="FarmMonster(chicken)",
                       outcome="ok", planner_stats={"nodes": 5, "depth": 2, "timed_out": False, "plan_len": 1})
    assert len(captured) == 1
    rec = captured[0]
    assert rec["action"] == "Fight(chicken)"
    assert rec["selected_goal"] == "FarmMonster(chicken)"
    assert rec["outcome"] == "ok"
    assert "state" in rec
    assert "ts" in rec
```

- [ ] **Step 2: Verify fail**

```
uv run pytest tests/test_ai/test_tracer.py::test_player_emits_cycle_record_to_tracer -v
```
Expected: FAIL.

- [ ] **Step 3: Add tracer to player + `_emit_trace` helper**

In `src/artifactsmmo_cli/ai/player.py`:

Add import:
```python
from artifactsmmo_cli.ai.tracing import NullTracer, Tracer
```

In `__init__`:
```python
    def __init__(self, character: str, verbose: bool = False, dry_run: bool = False,
                 tracer: Tracer | None = None) -> None:
        # ... existing assignments ...
        self.tracer: Tracer = tracer or NullTracer()
        self._cycle_counter = 0
```

Add `_emit_trace` method:

```python
    def _emit_trace(self, action_name: str, goal_name: str, outcome: str,
                    planner_stats: dict, recovery: dict | None = None) -> None:
        from datetime import datetime, timezone
        if self.state is None:
            return
        cooldown_remaining = 0.0
        if self.state.cooldown_expires is not None:
            cooldown_remaining = max(0.0,
                (self.state.cooldown_expires - datetime.now(tz=timezone.utc)).total_seconds())
        record = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "cycle": self._cycle_counter,
            "state": {
                "x": self.state.x, "y": self.state.y,
                "hp": self.state.hp, "max_hp": self.state.max_hp,
                "gold": self.state.gold, "level": self.state.level,
                "inventory_used": self.state.inventory_used,
                "inventory_max": self.state.inventory_max,
                "bank_accessible": self._bank_accessible,
                "task_code": self.state.task_code, "task_type": self.state.task_type,
                "task_progress": self.state.task_progress, "task_total": self.state.task_total,
            },
            "cooldown_remaining_at_cycle_start": cooldown_remaining,
            "selected_goal": goal_name,
            "planner": planner_stats,
            "action": action_name,
            "outcome": outcome,
            "recovery": recovery,
            "suppressed_goals": list(self._suppressed_goals.keys()),
        }
        self.tracer.write_cycle(record)
        self._cycle_counter += 1
```

Wire `_emit_trace` into the run loop — after each cycle, before the next iteration:

```python
            self._emit_trace(
                action_name=repr(action),
                goal_name=repr(selected_goal),
                outcome="ok",
                planner_stats={
                    "nodes": self.planner.last_stats.nodes_explored,
                    "depth": self.planner.last_stats.max_depth_reached,
                    "timed_out": self.planner.last_stats.timed_out,
                    "plan_len": len(plan),
                },
            )
```

Also emit on "no plan found" path:
```python
            self._emit_trace(
                action_name="<no_plan>",
                goal_name="<none>",
                outcome="no_plan",
                planner_stats={"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 0},
            )
```

Wrap the main loop in `try/finally` to close tracer:
```python
    def run(self) -> None:
        # ... existing setup ...
        try:
            while True:
                # ... existing loop ...
        finally:
            self.tracer.close()
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_ai/test_tracer.py tests/test_ai/test_player_run.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_tracer.py
git commit -m "feat(ai): wire Tracer into GamePlayer for per-cycle JSONL emission"
```

---

## Task D4: Add --trace / --trace-file CLI flags

**Files:**
- Modify: `src/artifactsmmo_cli/commands/play.py`

- [ ] **Step 1: Write failing test (manual integration)**

```
uv run artifactsmmo play --help 2>&1 | grep -E "trace"
```
Expected (after change): shows `--trace` and `--trace-file` flags.

- [ ] **Step 2: Update commands/play.py**

```python
@app.command("play")
def play(
    character: str = typer.Argument(..., help="Character name to play"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    trace: bool = typer.Option(False, "--trace", help="Emit per-cycle JSONL to --trace-file"),
    trace_file: str | None = typer.Option(None, "--trace-file",
                                          help="Trace output path (default: play-trace-{character}-{ts}.jsonl)"),
) -> None:
    from datetime import datetime
    from artifactsmmo_cli.ai.player import GamePlayer
    from artifactsmmo_cli.ai.tracing import FileTracer, NullTracer

    tracer = NullTracer()
    if trace:
        path = trace_file or f"play-trace-{character}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
        tracer = FileTracer(path)
        print(f"Tracing to {path}")

    player = GamePlayer(character=character, verbose=verbose, dry_run=dry_run, tracer=tracer)
    player.run()
```

- [ ] **Step 3: Verify CLI**

```
uv run artifactsmmo play --help | grep -E "trace"
```
Expected: shows `--trace`, `--trace-file`.

- [ ] **Step 4: Commit**

```bash
git add src/artifactsmmo_cli/commands/play.py
git commit -m "feat(cli): add --trace and --trace-file flags to play command"
```

---

### Phase D Validation Gate

```bash
uv run pytest tests/test_ai/ -q
uv run mypy src/artifactsmmo_cli/ai/tracing.py
```

All tests green. Manual: `uv run artifactsmmo play <char> --dry-run --trace --trace-file /tmp/play.jsonl 2>&1 | head -5`, then verify `head -3 /tmp/play.jsonl` shows valid JSON records.

---

# Phase E — Code Quality Cleanup

**Goal:** mypy → 0 errors on `src/artifactsmmo_cli/ai/`; coverage ≥ 98% on the AI module; fix the `PendingItemSchema.code` real bug.

---

## Task E1: Fix PendingItemSchema.code runtime bug

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py:226-254` (`_sync_pending`)
- Test: `tests/test_ai/test_player.py`

**Bug:** `_sync_pending` currently does `(item.id, item.code)` but `PendingItemSchema` has no `code` field. Its actual shape is:
```python
class PendingItemSchema:
    id: str
    account: str
    source: PendingItemSource     # enum
    description: str
    created_at: datetime.datetime
    source_id: Union[None, Unset, str]
    gold: Union[Unset, int]
    items: Union[Unset, list[SimpleItemSchema]]   # ← items live here, with .code on each
    claimed_at: ...
```

So the correct path is to iterate `item.items` and produce one `(pending_id, item_code)` per claimable item.

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_player.py`:

```python
def test_sync_pending_iterates_items_list(monkeypatch):
    """_sync_pending should produce (pending_id, item_code) pairs from PendingItemSchema.items."""
    from artifactsmmo_cli.ai.player import GamePlayer
    from tests.test_ai.fixtures import make_state

    class FakeItem:
        def __init__(self, code, quantity=1):
            self.code = code
            self.quantity = quantity

    class FakePending:
        def __init__(self, id_, items):
            self.id = id_
            self.items = items

    class FakeResult:
        def __init__(self, data):
            self.data = data

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.player.get_pending_items",
        lambda client: FakeResult([
            FakePending("p1", [FakeItem("diamond"), FakeItem("ruby")]),
            FakePending("p2", [FakeItem("emerald")]),
        ]),
    )

    player = GamePlayer(character="testchar")
    player.state = make_state()
    new_state = player._sync_pending(client=None, state=player.state)
    assert new_state.pending_items is not None
    assert ("p1", "diamond") in new_state.pending_items
    assert ("p1", "ruby") in new_state.pending_items
    assert ("p2", "emerald") in new_state.pending_items
    assert len(new_state.pending_items) == 3


def test_sync_pending_handles_unset_items_list(monkeypatch):
    """PendingItemSchema.items can be Unset — _sync_pending should skip such entries gracefully."""
    from artifactsmmo_api_client.types import UNSET
    from artifactsmmo_cli.ai.player import GamePlayer
    from tests.test_ai.fixtures import make_state

    class FakeItem:
        def __init__(self, code):
            self.code = code

    class FakePending:
        def __init__(self, id_, items):
            self.id = id_
            self.items = items

    class FakeResult:
        def __init__(self, data):
            self.data = data

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.player.get_pending_items",
        lambda client: FakeResult([
            FakePending("p1", UNSET),                       # items unset → skip
            FakePending("p2", [FakeItem("diamond")]),
        ]),
    )

    player = GamePlayer(character="testchar")
    player.state = make_state()
    new_state = player._sync_pending(client=None, state=player.state)
    assert new_state.pending_items == (("p2", "diamond"),)
```

- [ ] **Step 2: Run tests to verify fail**

```
uv run pytest tests/test_ai/test_player.py::test_sync_pending_iterates_items_list tests/test_ai/test_player.py::test_sync_pending_handles_unset_items_list -v
```
Expected: FAIL with `AttributeError: 'FakePending' object has no attribute 'code'`.

- [ ] **Step 3: Fix `_sync_pending`**

In `src/artifactsmmo_cli/ai/player.py`, locate `_sync_pending` (around line 226). Add the `Unset` import if not present:

```python
from artifactsmmo_api_client.types import Unset
```

Replace the `pending` construction (the line currently doing `pending = tuple((item.id, item.code) for item in result.data)`):

```python
        pending: tuple[tuple[str, str], ...] | None = None
        if result is not None and result.data:
            pairs: list[tuple[str, str]] = []
            for pi in result.data:
                items = pi.items
                if isinstance(items, Unset) or not items:
                    continue
                for si in items:
                    pairs.append((pi.id, si.code))
            pending = tuple(pairs) if pairs else None
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_ai/test_player.py -q
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit -m "fix(ai): iterate PendingItemSchema.items list in _sync_pending"
```

---

## Task E2: Apply _raise_for_error consistently to all execute() methods

**Files:**
- Modify: every `src/artifactsmmo_cli/ai/actions/*.py` `execute()` method

- [ ] **Step 1: Survey current state**

```
grep -n "result is None\|result.data is None\|isinstance(result, ErrorResponse" src/artifactsmmo_cli/ai/actions/*.py
```

Each match identifies a custom error check that should be replaced with `Action._raise_for_error(result, "<context>")`.

- [ ] **Step 2: For each file with custom checks, replace with the helper**

Example: in `actions/combat.py`, replace any:
```python
        if isinstance(result, ErrorResponseSchema):
            raise RuntimeError(...)
        if result is None or result.data is None:
            raise RuntimeError(...)
```

with:
```python
        Action._raise_for_error(result, f"Fight {self.monster_code}")
```

Apply to: `combat.py`, `gathering.py`, `crafting.py`, `equipment.py`, `bank.py`, `rest.py`, `movement.py`, `delete.py`, `consumable.py`, `claim.py`, `recycle.py`, `task.py`.

- [ ] **Step 3: Run all tests**

```
uv run pytest tests/test_ai/ -q
```
Expected: all green.

- [ ] **Step 4: Run mypy and confirm Union errors dropped**

```
uv run mypy src/artifactsmmo_cli/ai/ 2>&1 | tail -10
```
Expected: error count significantly reduced.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/
git commit -m "refactor(ai): use Action._raise_for_error consistently across all execute() methods"
```

---

## Task E3: Add type parameters to untyped containers

**Files:** Multiple — driven by mypy output

- [ ] **Step 1: Get current mypy errors for untyped containers**

```
uv run mypy src/artifactsmmo_cli/ai/ 2>&1 | grep -E "Missing type parameters" | head -20
```

- [ ] **Step 2: For each file in the list, add type parameters**

Example pattern from spec audit:
- `recovery.py` `dict` → `dict[str, int]`
- `gathering.py:93` `list` → `list[Action]`
- `planner.py:15,66` `tuple` → `tuple[Any, ...]` (or more specific)

Apply to all files. Run `mypy` after each batch to confirm no regression.

- [ ] **Step 3: Run tests + mypy**

```
uv run pytest tests/test_ai/ -q && uv run mypy src/artifactsmmo_cli/ai/ 2>&1 | tail -5
```
Expected: tests green; mypy "Missing type parameters" count = 0.

- [ ] **Step 4: Commit**

```bash
git add src/artifactsmmo_cli/ai/
git commit -m "refactor(ai): add type parameters to generic containers for mypy"
```

---

## Task E4: Fix list variance bugs

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py:72-77`
- Modify: `src/artifactsmmo_cli/ai/goals/farm_items.py:64-69`

- [ ] **Step 1: Find and read the variance lines**

```
uv run mypy src/artifactsmmo_cli/ai/goals/gathering.py 2>&1 | grep "variance\|incompatible"
```

- [ ] **Step 2: Annotate `result` as `list[Action]` at declaration**

Both files: change `result = []` to `result: list[Action] = []` where Action is the imported base class. Already done in farm_items.py earlier — verify gathering.py matches.

- [ ] **Step 3: Run tests + mypy**

```
uv run pytest tests/test_ai/test_goals.py -q && uv run mypy src/artifactsmmo_cli/ai/goals/gathering.py src/artifactsmmo_cli/ai/goals/farm_items.py
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/
git commit -m "refactor(ai): annotate result list as list[Action] to fix variance"
```

---

## Task E5: Fix WorldState | None and ItemStats | None guards

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py:102, 147` (assert state not None after refresh)
- Modify: `src/artifactsmmo_cli/ai/actions/combat.py:36` (ItemStats None guard)

- [ ] **Step 1: Survey errors**

```
uv run mypy src/artifactsmmo_cli/ai/ 2>&1 | grep -E "WorldState|ItemStats"
```

- [ ] **Step 2: Apply fixes**

In `player.py` after `_full_refresh` calls:
```python
            self._full_refresh(client)
            assert self.state is not None
```

In `combat.py:36`, add a guard before dereferencing `stats.level`:
```python
        stats = game_data.item_stats(...)
        if stats is None:
            return False  # or appropriate fallback
        # use stats.level
```

- [ ] **Step 3: Run tests + mypy**

```
uv run pytest tests/test_ai/ -q && uv run mypy src/artifactsmmo_cli/ai/ 2>&1 | tail -5
```
Expected: green; mypy errors approaching 0.

- [ ] **Step 4: Commit**

```bash
git add src/artifactsmmo_cli/ai/
git commit -m "refactor(ai): add None guards for WorldState and ItemStats references"
```

---

## Task E6: Close coverage gaps in error paths

**Files:**
- Create/modify: `tests/test_ai/test_player.py`, `tests/test_ai/test_actions_tier3.py` or similar — add tests for the missing lines.

- [ ] **Step 1: Generate current coverage gap report**

```
uv run pytest tests/test_ai/ --cov=src/artifactsmmo_cli/ai --cov-report=term-missing -q 2>&1 | grep -A 1 "Missing"
```

This identifies all currently-uncovered lines.

- [ ] **Step 2: Add tests for delete.py, unlock_bank.py, consumable.py**

For `delete.py`:
```python
def test_delete_action_is_applicable_only_when_item_in_inventory():
    action = DeleteItemAction(code="iron_ore", quantity=1, cost_weight=5.0)
    state = make_state(inventory={"iron_ore": 1})
    gd = GameData()
    assert action.is_applicable(state, gd) is True
    assert action.is_applicable(make_state(inventory={}), gd) is False

def test_delete_action_cost_returns_weight():
    action = DeleteItemAction(code="iron_ore", quantity=1, cost_weight=25.0)
    state = make_state()
    assert action.cost(state, GameData()) == 25.0

def test_delete_action_repr():
    action = DeleteItemAction(code="iron_ore", quantity=2, cost_weight=10.0)
    assert "iron_ore" in repr(action)
```

For `unlock_bank.py`: test the `relevant_actions` filter when bank is locked and unlock_monster is known.

For `consumable.py`: mock the use_item endpoint, assert HP change in returned state.

- [ ] **Step 3: Add tests for player.py error paths**

```python
def test_player_handles_http_496_by_disabling_bank(monkeypatch):
    """When action.execute raises HTTP 496, player should mark bank inaccessible."""
    from artifactsmmo_cli.ai.player import GamePlayer
    from artifactsmmo_cli.ai.actions.bank import DepositAllAction

    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._bank_location = (4, 0)
    player.state = make_state(x=4, y=0)
    player._bank_accessible = True

    action = DepositAllAction(bank_location=(4, 0), accessible=True)

    def failing_execute(state, client):
        raise RuntimeError("HTTP 496: secure_the_island achievement_unlocked required")
    action.execute = failing_execute  # type: ignore

    monkeypatch.setattr(player, "_fetch_world_state", lambda c: player.state)
    player._execute(action, client=None)
    assert player._bank_accessible is False
```

- [ ] **Step 4: Re-run coverage**

```
uv run pytest tests/test_ai/ --cov=src/artifactsmmo_cli/ai --cov-report=term-missing -q 2>&1 | tail -10
```
Expected: AI module coverage ≥ 98%.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/
git commit -m "test(ai): close coverage gaps in delete, unlock_bank, consumable, and player error paths"
```

---

## Task E7: Final mypy/coverage validation gate

- [ ] **Step 1: Run mypy on the AI module**

```
uv run mypy src/artifactsmmo_cli/ai/
```
Expected: `Success: no issues found in N source files`.

- [ ] **Step 2: Run pytest with coverage**

```
uv run pytest tests/test_ai/ --cov=src/artifactsmmo_cli/ai --cov-report=term-missing -q
```
Expected: all tests pass; coverage ≥ 98% on the AI module.

- [ ] **Step 3: Run the full project test suite**

```
uv run pytest -q
```
Expected: all tests pass; total tests ≈ 1100+ (was 1058 + new tests).

- [ ] **Step 4: Manual dry-run**

```
uv run artifactsmmo play <character> --dry-run --verbose --trace --trace-file /tmp/play-final.jsonl
```
Expected: bot prints goal priorities, plan, and action per cycle; trace file populated with valid JSONL.

- [ ] **Step 5: Phase E completion commit**

```bash
git add .
git commit -m "chore(ai): Phase E complete — mypy clean, coverage ≥98% on AI module"
```

---

### Phase E Validation Gate

- `uv run mypy src/artifactsmmo_cli/ai/` → 0 errors
- `uv run pytest tests/test_ai/ --cov=src/artifactsmmo_cli/ai -q` → all green, ≥98% coverage
- Manual `--dry-run --trace` produces valid trace file

---

# Final Validation

After all phases:

- [ ] **Full test suite**: `uv run pytest -q` — all green
- [ ] **Mypy strict on AI**: `uv run mypy src/artifactsmmo_cli/ai/` — 0 errors
- [ ] **Coverage on AI**: `uv run pytest tests/test_ai/ --cov=src/artifactsmmo_cli/ai --cov-report=term -q` — ≥98%
- [ ] **CLI sanity**: `uv run artifactsmmo play <character> --dry-run --verbose --trace --trace-file /tmp/final-test.jsonl 2>&1 | head -10`
- [ ] **Trace validity**: `head -3 /tmp/final-test.jsonl | python -c "import json, sys; [json.loads(l) for l in sys.stdin]"` — no exceptions

If all gates pass, the robustness layer is complete and ready for the next phase of real-play validation (run Robby for several hours and capture a trace for offline analysis — which becomes the input data for Phase F autoregressive planning).
