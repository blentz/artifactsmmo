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
