"""Bid/self-craft mutual exclusion (Task 12): GatherMaterialsGoal must not emit a
Gather or Craft action for an item that currently has an open GE **BUY** order —
the bid and a self-acquisition must never run for the same item (converse of
PostBuyBidGoal's own open_orders suppression, see bid_vs_craft.py). A standing
**SELL** order (surplus disposal) is a different lifecycle and must NOT suppress
acquisition.

Double-acquisition gap fix (review-confirmed): the SAME goal also offers three
OTHER acquisition channels for a needed item — NpcBuyAction, GeFillSellOrderAction
(buy-fill), and FightAction monster-drop farming — which were left unguarded by
the original `bid_items` suppression. A GE BUY bid is only posted when the venue
decider chose POST over NPC/fill (post_price < npc_price); leaving these channels
open let the planner buy the SAME item via NPC (or farm its monster drop) at a
worse price WHILE the cheaper bid was in flight, double-acquiring once the bid
filled. All four channels below share the ONE `bid_items` set and must suppress
on the item's exact code only (a bid on X must not suppress acquiring a
different needed item Y — the CONTROL assertions in each class below)."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd_iron_ore() -> GameData:
    """iron_ore: a raw, non-craftable resource drop of iron_rocks. copper_ore
    (drop of copper_rocks) is the CONTROL sibling — a different non-bid item."""
    gd = GameData()
    gd._item_stats = {
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {}
    gd._resource_drops = {"iron_rocks": "iron_ore", "copper_rocks": "copper_ore"}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    return gd


def _gd_copper_bar() -> GameData:
    """copper_bar: craftable from copper_ore (mining lv1). iron_bar (from
    iron_ore) is the CONTROL sibling — a different non-bid craftable item."""
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
        "iron_bar": ItemStats(
            code="iron_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}, "iron_bar": {"iron_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore", "iron_rocks": "iron_ore"}
    gd._workshop_locations = {"mining": (1, 5)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    return gd


def _gd_npc_buy_items() -> GameData:
    """widget/gadget: non-craftable, gold-sold, no gather/drop source — the ONLY
    acquisition channel is NpcBuy (mirrors the existing must-buy fixtures in
    test_craft_vs_buy_wiring.py)."""
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=1, type_="rune"),
        "gadget": ItemStats(code="gadget", level=1, type_="rune"),
    }
    gd._crafting_recipes = {}
    gd._npc_stock = {"vendor": {"widget": 100, "gadget": 100}}
    gd._npc_buy_currency = {"vendor": {"widget": "gold", "gadget": "gold"}}
    gd._npc_locations = {"vendor": (3, 3)}
    return gd


def _gd_ge_fill_bid() -> GameData:
    """copper_bar: craftable, NPC-sold near, PLUS a standing GE sell order
    cheaper than NPC (choose_buy_venue picks GE, offering GeFillSellOrderAction)."""
    gd = GameData()
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._npc_stock = {"shop": {"copper_bar": 5}}
    gd._npc_locations = {"shop": (1, 0)}
    gd._ge_sell_orders = {"copper_bar": ("ord-3", 2, 4)}
    gd._grand_exchange_location = (7, 7)
    return gd


def _gd_fight_drop_bid() -> GameData:
    """feather_coat needs feather (chicken drop) — the bid item. leather_coat
    needs leather (cow drop) — the CONTROL sibling (a different, non-bid drop
    item), mirroring test_monster_drop_wiring.py's feather_coat/chicken fixture."""
    gd = GameData()
    gd._item_stats = {
        "feather_coat": ItemStats(code="feather_coat", level=1, type_="body_armor",
                                  crafting_skill="gearcrafting", crafting_level=1),
        "leather_coat": ItemStats(code="leather_coat", level=1, type_="body_armor",
                                  crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {
        "feather_coat": {"feather": 2},
        "leather_coat": {"leather": 2},
    }
    gd._monster_level = {"chicken": 1, "cow": 1}
    gd._monster_drops = {
        "chicken": [("feather", 8, 1, 1)],
        "cow": [("leather", 8, 1, 1)],
    }
    gd._monster_locations = {"chicken": [(0, 1)], "cow": [(0, 2)]}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10, "cow": 10}
    return gd


class TestGatherSuppressedByOpenBuyOrder:
    """No GatherAction targeting an item with an open BUY order."""

    def test_no_gather_for_item_with_open_buy_order(self):
        gd = _gd_iron_ore()
        order = OpenOrder("b1", "iron_ore", 5, 9, OrderSide.BUY, 0)
        state = make_state(inventory={}, open_orders=(order,))
        # copper_ore is a DIFFERENT, non-bid needed item (CONTROL).
        goal = GatherMaterialsGoal("iron_ore", {"iron_ore": 5, "copper_ore": 3})
        actions = [
            GatherAction(resource_code="iron_rocks", locations=frozenset([(0, 1)])),
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 2)])),
        ]

        relevant = goal.relevant_actions(actions, state, gd)

        assert not any(
            isinstance(a, GatherAction) and a.resource_code == "iron_rocks"
            for a in relevant
        ), "GatherAction for a bid item must be suppressed"
        # CONTROL: a bid on iron_ore must not suppress gathering the different
        # needed item copper_ore — exact-item-code scoping, not blanket.
        assert any(
            isinstance(a, GatherAction) and a.resource_code == "copper_rocks"
            for a in relevant
        ), "a bid on iron_ore must not suppress acquiring the different item copper_ore"

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
            # iron_ore held too, for the iron_bar CONTROL craft below.
            inventory={"copper_ore": 60, "iron_ore": 60}, inventory_max=100,
            skills={"mining": 5}, open_orders=(order,),
        )
        # iron_bar is a DIFFERENT, non-bid needed item (CONTROL).
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 6, "iron_bar": 4})
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            CraftAction(code="iron_bar", workshop_location=(1, 5)),
        ]

        relevant = goal.relevant_actions(actions, state, gd)

        assert not any(
            isinstance(a, CraftAction) and a.code == "copper_bar"
            for a in relevant
        ), "CraftAction for a bid item must be suppressed"
        # CONTROL: a bid on copper_bar must not suppress crafting the different
        # needed item iron_bar — exact-item-code scoping, not blanket.
        assert any(
            isinstance(a, CraftAction) and a.code == "iron_bar"
            for a in relevant
        ), "a bid on copper_bar must not suppress acquiring the different item iron_bar"

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


class TestNpcBuySuppressedByOpenBuyOrder:
    """No NpcBuyAction targeting an item with an open BUY order (double-acquisition
    gap fix): the venue decider already chose POST over NPC for this item, so
    also offering an NpcBuy would let the planner buy it twice."""

    def test_no_npcbuy_for_item_with_open_buy_order(self):
        gd = _gd_npc_buy_items()
        order = OpenOrder("b3", "widget", 5, 100, OrderSide.BUY, 0)
        state = make_state(gold=100000, x=0, y=0, open_orders=(order,))
        # gadget is a DIFFERENT, non-bid needed item (CONTROL).
        goal = GatherMaterialsGoal("widget", {"widget": 1, "gadget": 1})

        relevant = goal.relevant_actions([], state, gd)

        assert not any(
            isinstance(a, NpcBuyAction) and a.item_code == "widget"
            for a in relevant
        ), "NpcBuyAction for a bid item must be suppressed"
        # CONTROL: a bid on widget must not suppress buying the different
        # needed item gadget — exact-item-code scoping, not blanket.
        assert any(
            isinstance(a, NpcBuyAction) and a.item_code == "gadget"
            for a in relevant
        ), "a bid on widget must not suppress acquiring the different item gadget"

    def test_open_sell_order_does_not_suppress_npcbuy(self):
        """A SELL order (surplus disposal) is a different lifecycle and must NOT
        block acquisition of the same code."""
        gd = _gd_npc_buy_items()
        order = OpenOrder("s3", "widget", 5, 100, OrderSide.SELL, 0)
        state = make_state(gold=100000, x=0, y=0, open_orders=(order,))
        goal = GatherMaterialsGoal("widget", {"widget": 1})

        relevant = goal.relevant_actions([], state, gd)

        assert any(
            isinstance(a, NpcBuyAction) and a.item_code == "widget"
            for a in relevant
        ), "a SELL order must not suppress acquisition"


class TestGeFillSuppressedByOpenBuyOrder:
    """No GeFillSellOrderAction (buy-fill) targeting an item with an open BUY
    order — same mutual-exclusion invariant as NpcBuy, for the OTHER buy-venue
    channel (choose_buy_venue == GE)."""

    def test_no_gefill_for_item_with_open_buy_order(self):
        gd = _gd_ge_fill_bid()
        order = OpenOrder("b4", "copper_bar", 6, 20, OrderSide.BUY, 0)
        state = make_state(gold=100000, inventory={}, x=0, y=0,
                           skills={"mining": 5}, open_orders=(order,))
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 1})

        relevant = goal.relevant_actions([], state, gd)

        assert not any(
            isinstance(a, GeFillSellOrderAction) for a in relevant
        ), "GeFillSellOrderAction for a bid item must be suppressed"
        # The NpcBuy alternative for the SAME item must also be suppressed —
        # both are the same buy-venue channel, guarded by the same continue.
        assert not any(
            isinstance(a, NpcBuyAction) for a in relevant
        ), "NpcBuyAction for a bid item must also be suppressed"

    def test_open_sell_order_does_not_suppress_gefill(self):
        """A SELL order (surplus disposal) is a different lifecycle and must NOT
        block acquisition of the same code."""
        gd = _gd_ge_fill_bid()
        order = OpenOrder("s4", "copper_bar", 6, 20, OrderSide.SELL, 0)
        state = make_state(gold=100000, inventory={}, x=0, y=0,
                           skills={"mining": 5}, open_orders=(order,))
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 1})

        relevant = goal.relevant_actions([], state, gd)

        assert any(
            isinstance(a, GeFillSellOrderAction) for a in relevant
        ), "a SELL order must not suppress acquisition"


class TestFightDropFarmSuppressedByOpenBuyOrder:
    """No FightAction drop-farm targeting a bid DROP item — same mutual-exclusion
    invariant applied to the monster-drop acquisition channel; a fight whose drop
    item is NOT bid on must still be emitted."""

    def test_no_fight_for_bid_drop_item(self):
        gd = _gd_fight_drop_bid()
        order = OpenOrder("b5", "feather", 4, 9, OrderSide.BUY, 0)
        state = make_state(
            level=1, x=0, y=0, max_hp=100, hp=100,
            attack={"fire": 30}, initiative=50,
            inventory={}, inventory_max=50, open_orders=(order,),
        )
        actions = [
            FightAction(monster_code="chicken", locations=frozenset({(0, 1)})),
            FightAction(monster_code="cow", locations=frozenset({(0, 2)})),
        ]
        # leather_coat/leather/cow is a DIFFERENT, non-bid drop chain (CONTROL).
        goal = GatherMaterialsGoal(
            "feather_coat", {"feather_coat": 1, "leather_coat": 1})

        relevant = goal.relevant_actions(actions, state, gd)

        assert not any(
            isinstance(a, FightAction) and a.monster_code == "chicken"
            for a in relevant
        ), "Fight(chicken) drop-farm for the bid drop-item feather must be suppressed"
        # CONTROL: a bid on feather must not suppress farming the different
        # drop item leather — exact-item-code scoping, not blanket.
        assert any(
            isinstance(a, FightAction) and a.monster_code == "cow"
            for a in relevant
        ), "a bid on feather must not suppress acquiring the different item leather"

    def test_open_sell_order_does_not_suppress_fight_drop_farm(self):
        """A SELL order (surplus disposal) is a different lifecycle and must NOT
        block acquisition of the same code."""
        gd = _gd_fight_drop_bid()
        order = OpenOrder("s5", "feather", 4, 9, OrderSide.SELL, 0)
        state = make_state(
            level=1, x=0, y=0, max_hp=100, hp=100,
            attack={"fire": 30}, initiative=50,
            inventory={}, inventory_max=50, open_orders=(order,),
        )
        actions = [FightAction(monster_code="chicken", locations=frozenset({(0, 1)}))]
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})

        relevant = goal.relevant_actions(actions, state, gd)

        assert any(
            isinstance(a, FightAction) and a.monster_code == "chicken"
            for a in relevant
        ), "a SELL order must not suppress acquisition"
