"""`_producible` currency-buy leg: a vendor currency the character can GATHER
counts as producible (P3 engagement expansion — tailor leathers @ hides)."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.strategy import _producible
from tests.test_ai.fixtures import make_state


def test_producible_recognizes_currency_buy_with_gatherable_currency() -> None:
    """leather_boots sold by a permanent tailor for cowhide; cowhide is a
    resource drop (gatherable) → producible, no recipe/fight needed."""
    gd = GameData()
    gd._npc_stock = {"tailor": {"leather_boots": 4}}
    gd._npc_buy_currency = {"tailor": {"leather_boots": "cowhide"}}
    gd._npc_locations = {"tailor": (2, 7)}
    gd._resource_drops = {"cow_field": "cowhide"}
    gd._item_stats = {
        "leather_boots": ItemStats(code="leather_boots", level=1, type_="boots"),
        "cowhide": ItemStats(code="cowhide", level=1, type_="resource"),
    }
    assert _producible("leather_boots", make_state(), gd) is True


def _vendor_only_gd() -> GameData:
    """Recipe-less bag sold for a currency whose droppers are UNWINNABLE:
    the sandwhisper_bag shape at low level."""
    gd = GameData()
    gd._npc_stock = {"trader": {"dune_bag": 230}}
    gd._npc_buy_currency = {"trader": {"dune_bag": "dune_coin"}}
    gd._npc_locations = {"trader": (2, 7)}
    gd._item_stats = {
        "dune_bag": ItemStats(code="dune_bag", level=50, type_="bag"),
        "dune_coin": ItemStats(code="dune_coin", level=1, type_="currency"),
    }
    gd._monster_level = {"titan": 60}
    gd._monster_hp = {"titan": 99999}
    gd._monster_attack = {"titan": {"fire": 9999}}
    gd._monster_resistance = {"titan": {}}
    gd._monster_locations = {"titan": (9, 9)}
    gd._monster_critical_strike = {"titan": 0}
    gd._monster_initiative = {"titan": 0}
    gd._monster_drops = {"titan": [("dune_coin", 50, 1, 1)]}
    return gd


def test_producible_credits_held_stock() -> None:
    """An item already IN HAND is trivially producible — there is nothing
    left to produce; the obtain step is served by withdraw/equip. Live gap
    2026-07-06: a HELD sandwhisper_bag still read not-producible (recipe-less,
    droppers of its purchase currency unwinnable), so actionable_step
    returned None and the equip leg never fired."""
    gd = _vendor_only_gd()
    assert _producible("dune_bag", make_state(inventory={"dune_bag": 1}), gd) is True
    assert _producible("dune_bag", make_state(bank_items={"dune_bag": 1}), gd) is True
    assert _producible("dune_bag", make_state(), gd) is False


def test_producible_credits_held_currency_covering_price() -> None:
    """Currency ON HAND >= price makes the vendor purchase producible even
    when the currency's droppers are unwinnable (the coins are already
    earned — live gap: 230 held sandwhisper_coin still read not-producible
    and the buy leg never fired)."""
    gd = _vendor_only_gd()
    assert _producible("dune_bag",
                       make_state(inventory={"dune_coin": 230}), gd) is True
    assert _producible("dune_bag",
                       make_state(inventory={"dune_coin": 229}), gd) is False
