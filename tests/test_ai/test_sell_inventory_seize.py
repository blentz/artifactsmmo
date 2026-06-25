"""Tests for SellInventoryGoal event-window seize behavior (Task 9)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.sell_inventory import SEIZE_WINDOW_VALUE, SellInventoryGoal
from tests.test_ai.fixtures import make_state

FIXED_NOW = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)


def _gd() -> GameData:
    gd = GameData()
    gd._npc_event_code["gemstone_merchant"] = "gemstone_merchant"
    gd._event_npc_spawns["gemstone_merchant"] = (6, -1)
    gd._npc_sell_prices["gemstone_merchant"] = {"copper_ore": 1}
    return gd


class TestSellInventorySeize:
    def test_value_boosted_when_window_live_even_if_bank_accessible(self):
        """Bank accessible but event window live -> value >= SEIZE_WINDOW_VALUE."""
        gd = _gd()
        # 101 used out of 104 max -> free=3 < MIN_FREE_SLOTS(5) -> NOT satisfied
        state = make_state(
            x=6,
            y=-1,
            inventory={"copper_ore": 101},
            inventory_max=104,
            active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)},
        )
        with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            goal = SellInventoryGoal(bank_accessible=True)
            assert goal.value(state, gd) >= SEIZE_WINDOW_VALUE

    def test_zero_quantity_items_are_skipped(self):
        """An inventory entry with qty <= 0 is skipped; a real sellable item still boosts."""
        gd = _gd()
        state = make_state(
            x=6,
            y=-1,
            inventory={"empty_stack": 0, "copper_ore": 101},
            inventory_max=104,
            active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)},
        )
        with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            goal = SellInventoryGoal(bank_accessible=True)
            assert goal.value(state, gd) >= SEIZE_WINDOW_VALUE

    def test_no_boost_when_no_window_and_bank_accessible(self):
        """Bank accessible, no active event, and no accumulation -> value == 0."""
        gd = _gd()
        # 4 copper_ore < ACCUM_MULT * eff_cap (5*1=5) -> no accumulation
        # inventory_max=7, free=3 < MIN_FREE_SLOTS(5) -> NOT satisfied
        state = make_state(
            x=6,
            y=-1,
            inventory={"copper_ore": 4},
            inventory_max=7,
            active_events={},
        )
        with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            goal = SellInventoryGoal(bank_accessible=True)
            assert goal.value(state, gd) == 0.0

    def test_bank_locked_no_window_uses_fraction(self):
        """Bank locked + sellable + NO active window -> used_fraction * 100."""
        gd = _gd()
        # 80 used / 100 max = 0.8; 0.8 * 100 = 80; inventory_free = 20 >= MIN_FREE_SLOTS(5)
        # need to be NOT satisfied: use 96 used / 100 max => 4 free < 5
        state = make_state(
            x=6,
            y=-1,
            inventory={"copper_ore": 96},
            inventory_max=100,
            active_events={},
        )
        with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            goal = SellInventoryGoal(bank_accessible=False)
            expected = 96 / 100 * 100.0
            assert goal.value(state, gd) == expected

    def test_satisfied_returns_zero_when_no_accumulation_even_with_window(self):
        """When satisfied and no accumulation, value is 0 regardless of window."""
        gd = _gd()
        # 4 copper_ore < ACCUM_MULT * eff_cap (5*1=5) -> no accumulation
        # inventory_max=104, free=100 >= MIN_FREE_SLOTS(5) -> satisfied
        state = make_state(
            x=6,
            y=-1,
            inventory={"copper_ore": 4},
            inventory_max=104,
            active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)},
        )
        with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            goal = SellInventoryGoal(bank_accessible=True)
            assert goal.value(state, gd) == 0.0

    def test_no_sellable_items_returns_zero_even_with_window(self):
        """If no held item is sellable by any NPC, value is 0."""
        gd = _gd()
        # item not in merchant buy list; 96 used / 100 max -> free=4 < MIN_FREE_SLOTS -> NOT satisfied
        state = make_state(
            x=6,
            y=-1,
            inventory={"useless_rock": 96},
            inventory_max=100,
            active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)},
        )
        with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            goal = SellInventoryGoal(bank_accessible=True)
            assert goal.value(state, gd) == 0.0

    def test_bank_locked_with_window_returns_max(self):
        """Bank locked AND event window live -> max(fraction*100, SEIZE_WINDOW_VALUE)."""
        gd = _gd()
        # 96 used / 100 max -> 96.0 > SEIZE_WINDOW_VALUE(60), so expect 96.0
        state = make_state(
            x=6,
            y=-1,
            inventory={"copper_ore": 96},
            inventory_max=100,
            active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)},
        )
        with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            goal = SellInventoryGoal(bank_accessible=False)
            result = goal.value(state, gd)
            assert result == max(96.0, SEIZE_WINDOW_VALUE)

    def test_expired_event_no_boost(self):
        """Expired event (expiry in the past) -> no boost when bank accessible and no accumulation."""
        gd = _gd()
        # 4 copper_ore < ACCUM_MULT * eff_cap (5*1=5) -> no accumulation
        # inventory_max=7, free=3 < MIN_FREE_SLOTS(5) -> NOT satisfied
        state = make_state(
            x=6,
            y=-1,
            inventory={"copper_ore": 4},
            inventory_max=7,
            active_events={"gemstone_merchant": FIXED_NOW - timedelta(minutes=5)},
        )
        with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
            dt.now.return_value = FIXED_NOW
            goal = SellInventoryGoal(bank_accessible=True)
            assert goal.value(state, gd) == 0.0
