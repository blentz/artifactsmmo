"""Bid/self-craft mutual exclusion (Task 12): GatherMaterialsGoal must not emit a
Gather or Craft action for an item that currently has an open GE **BUY** order —
the bid and a self-acquisition must never run for the same item (converse of
PostBuyBidGoal's own open_orders suppression, see bid_vs_craft.py). A standing
**SELL** order (surplus disposal) is a different lifecycle and must NOT suppress
acquisition.
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state


def _gd_iron_ore() -> GameData:
    """iron_ore: a raw, non-craftable resource drop of iron_rocks."""
    gd = GameData()
    gd._item_stats = {
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    return gd


def _gd_copper_bar() -> GameData:
    """copper_bar: craftable from copper_ore (mining lv1)."""
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._workshop_locations = {"mining": (1, 5)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    return gd


class TestGatherSuppressedByOpenBuyOrder:
    """No GatherAction targeting an item with an open BUY order."""

    def test_no_gather_for_item_with_open_buy_order(self):
        gd = _gd_iron_ore()
        order = OpenOrder("b1", "iron_ore", 5, 9, OrderSide.BUY, 0)
        state = make_state(inventory={}, open_orders=(order,))
        goal = GatherMaterialsGoal("iron_ore", {"iron_ore": 5})
        actions = [GatherAction(resource_code="iron_rocks",
                                locations=frozenset([(0, 1)]))]

        relevant = goal.relevant_actions(actions, state, gd)

        assert not any(
            isinstance(a, GatherAction) and a.resource_code == "iron_rocks"
            for a in relevant
        ), "GatherAction for a bid item must be suppressed"

    def test_open_sell_order_does_not_suppress_gather(self):
        """A SELL order (surplus disposal) is a different lifecycle and must NOT
        block acquisition of the same code."""
        gd = _gd_iron_ore()
        order = OpenOrder("s1", "iron_ore", 5, 9, OrderSide.SELL, 0)
        state = make_state(inventory={}, open_orders=(order,))
        goal = GatherMaterialsGoal("iron_ore", {"iron_ore": 5})
        actions = [GatherAction(resource_code="iron_rocks",
                                locations=frozenset([(0, 1)]))]

        relevant = goal.relevant_actions(actions, state, gd)

        assert any(
            isinstance(a, GatherAction) and a.resource_code == "iron_rocks"
            for a in relevant
        ), "a SELL order must not suppress acquisition"


class TestCraftSuppressedByOpenBuyOrder:
    """No CraftAction targeting an item with an open BUY order."""

    def test_no_craft_for_item_with_open_buy_order(self):
        gd = _gd_copper_bar()
        order = OpenOrder("b2", "copper_bar", 6, 20, OrderSide.BUY, 0)
        state = make_state(
            inventory={"copper_ore": 60}, inventory_max=100,
            skills={"mining": 5}, open_orders=(order,),
        )
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 6})
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
        ]

        relevant = goal.relevant_actions(actions, state, gd)

        assert not any(
            isinstance(a, CraftAction) and a.code == "copper_bar"
            for a in relevant
        ), "CraftAction for a bid item must be suppressed"

    def test_open_sell_order_does_not_suppress_craft(self):
        gd = _gd_copper_bar()
        order = OpenOrder("s2", "copper_bar", 6, 20, OrderSide.SELL, 0)
        state = make_state(
            inventory={"copper_ore": 60}, inventory_max=100,
            skills={"mining": 5}, open_orders=(order,),
        )
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 6})
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
        ]

        relevant = goal.relevant_actions(actions, state, gd)

        assert any(
            isinstance(a, CraftAction) and a.code == "copper_bar"
            for a in relevant
        ), "a SELL order must not suppress acquisition"
