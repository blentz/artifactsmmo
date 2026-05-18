"""Tests for inventory_caps + DiscardOverstockGoal."""

from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.discard_overstock import (
    PRIORITY_WHEN_OVERSTOCKED,
    DiscardOverstockGoal,
)
from artifactsmmo_cli.ai.inventory_caps import (
    BATCH_BUFFER,
    overstocked_items,
    useful_quantity_cap,
)
from tests.test_ai.fixtures import make_state


def _gd_with_sap_recipes() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "sap": ItemStats(code="sap", level=1, type_="resource"),
        "small_antidote": ItemStats(
            code="small_antidote", level=1, type_="consumable",
            crafting_skill="alchemy", crafting_level=20,
        ),
    }
    gd._crafting_recipes = {
        "small_antidote": {"sap": 1, "small_health_potion": 1},
        "health_potion": {"sap": 1, "minor_health_potion": 1},
    }
    return gd


class TestUsefulQuantityCap:
    def test_cap_uses_recipe_demand_times_batch_buffer(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1)
        cap = useful_quantity_cap("sap", state, gd)
        # max_recipe_demand("sap") = 1; cap = 1 * BATCH_BUFFER = 5
        assert cap == BATCH_BUFFER

    def test_cap_zero_for_unused_item(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1)
        assert useful_quantity_cap("random_junk", state, gd) == 0

    def test_cap_respects_active_task_demand(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1, task_code="sap", task_type="items",
                            task_total=50, task_progress=10)
        # Task needs 40 more; recipe cap is 5. Max = 40.
        cap = useful_quantity_cap("sap", state, gd)
        assert cap == 40

    def test_equipped_items_have_floor_of_one(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1, equipment={"weapon_slot": "sap"})
        # 'sap' is equipped (silly but valid as test). Cap should be ≥ 1.
        cap = useful_quantity_cap("sap", state, gd)
        assert cap >= 1


class TestOverstockedItems:
    def test_only_returns_items_over_cap(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1, inventory={"sap": 50, "other_thing": 2})
        excess = overstocked_items(state, gd)
        # sap cap is 5; 50 > 5 → excess 45
        assert excess == {"sap": 50 - BATCH_BUFFER, "other_thing": 2}

    def test_empty_when_no_overstock(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1, inventory={"sap": 3})
        assert overstocked_items(state, gd) == {}


class TestDiscardOverstockGoal:
    def test_fires_high_when_overstocked(self):
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50})
        assert goal.priority(state, gd) == PRIORITY_WHEN_OVERSTOCKED

    def test_zero_when_no_overstock(self):
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 3})
        assert goal.priority(state, gd) == 0.0

    def test_satisfied_when_no_overstock(self):
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        assert goal.is_satisfied(make_state(level=1, inventory={"sap": 3})) is True
        assert goal.is_satisfied(make_state(level=1, inventory={"sap": 50})) is False

    def test_relevant_actions_picks_sell_when_buyer_exists(self):
        gd = _gd_with_sap_recipes()
        gd._npc_sell_prices = {"npc1": {"sap": 2}}
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50})
        actions = [
            NpcSellAction(npc_code="npc1", item_code="sap", quantity=1),
            DeleteItemAction(code="sap", quantity=1),
        ]
        relevant = goal.relevant_actions(actions, state, gd)
        # Sell wins (npc1 buys); Delete excluded.
        assert any(isinstance(a, NpcSellAction) for a in relevant)
        assert not any(isinstance(a, DeleteItemAction) for a in relevant)

    def test_relevant_actions_falls_back_to_delete_when_no_buyer(self):
        gd = _gd_with_sap_recipes()
        # No NPC buys sap
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50})
        actions = [DeleteItemAction(code="sap", quantity=1)]
        relevant = goal.relevant_actions(actions, state, gd)
        assert any(isinstance(a, DeleteItemAction) for a in relevant)
