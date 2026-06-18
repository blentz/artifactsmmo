# tests/test_ai/test_progression_reserve.py
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.progression_reserve import buy_price, gear_targets
from tests.test_ai.fixtures import make_state


def _gd_buyable_armor() -> GameData:
    gd = GameData()
    gd._item_stats = {
        # a body-armor upgrade usable at level<=7, sold by an npc, not craftable
        "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor", hp_bonus=40),
        # currently equipped (worse)
        "rags": ItemStats(code="rags", level=1, type_="body_armor", hp_bonus=5),
    }
    # _npc_stock is what NPCs sell TO the player (feeds npcs_selling_item)
    gd._npc_stock = {"merchant": {"iron_armor": 120}}
    gd._monster_level = {"chicken": 1}
    return gd


def test_buy_price_is_cheapest_seller():
    gd = _gd_buyable_armor()
    assert buy_price("iron_armor", gd) == 120
    assert buy_price("nonexistent", gd) is None


def test_gear_targets_reserves_unmet_buyable_upgrade():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    targets = gear_targets(state, gd)
    assert targets == {"iron_armor": 120}


def test_gear_targets_skips_already_equipped_best():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "iron_armor"})
    assert gear_targets(state, gd) == {}


def test_gear_targets_skips_out_of_horizon():
    gd = _gd_buyable_armor()
    gd._item_stats["iron_armor"].level = 99  # far above level+2
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    assert gear_targets(state, gd) == {}


def test_buy_price_prefers_ge_when_cheaper():
    """GE sell order cheaper than NPC → buy_price returns the GE price."""
    gd = GameData()
    gd._item_stats = {
        "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor", hp_bonus=40),
    }
    gd._npc_stock = {"merchant": {"iron_armor": 200}}
    # GE sell order: (order_id, price, quantity); price 80 < NPC 200
    gd._ge_sell_orders = {"iron_armor": ("order-1", 80, 10)}
    assert buy_price("iron_armor", gd) == 80


def test_buy_price_uses_ge_when_no_npc():
    """Item only available via a GE sell order → buy_price returns the GE price."""
    gd = GameData()
    gd._item_stats = {
        "silver_ring": ItemStats(code="silver_ring", level=3, type_="ring", hp_bonus=5),
    }
    gd._npc_stock = {}
    gd._ge_sell_orders = {"silver_ring": ("order-99", 150, 5)}
    assert buy_price("silver_ring", gd) == 150
