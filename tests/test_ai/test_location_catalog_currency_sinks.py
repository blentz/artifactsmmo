"""Direct coverage for `LocationCatalog.currency_sinks` (Task residuals 1 & 3
of the fleet-currency-turn-in review): the tuple contract `_resolve_turn_in`
now depends on, and the API-data-or-fail guard on a missing price.
"""
import pytest

from artifactsmmo_cli.ai.game_data_error import GameDataCoverageError
from artifactsmmo_cli.ai.location_catalog import LocationCatalog


def test_currency_sinks_raises_when_the_priced_npc_has_no_stock_entry():
    """`npc_buy_currency` and `npc_stock` are populated together from the
    same NPC-item payload (`GameData._build_npcs`), so an NPC that names a
    currency for an item but carries no price for it in `npc_stock` means
    the upstream data shape changed in a way this repo must fail loudly on
    (CLAUDE.md: "Use only API data or fail with an error") rather than
    silently price the sink at 0."""
    catalog = LocationCatalog()
    catalog.npc_buy_currency = {
        "archaeologist": {"lich_race_trophy": "lich_race_medal"},
    }
    # Deliberately no `npc_stock["archaeologist"]` entry at all.

    with pytest.raises(GameDataCoverageError):
        catalog.currency_sinks("lich_race_medal")


def test_currency_sinks_returns_item_npc_price_tuples_cheapest_first():
    """The tuple SHAPE `_resolve_turn_in` reads — (item_code, npc_code,
    price) — and the cheapest-first ORDERING it relies on for rule 5's
    max-price pick to be meaningful."""
    catalog = LocationCatalog()
    catalog.npc_buy_currency = {
        "vendor_a": {"item_a": "gold_coin"},
        "vendor_b": {"item_b": "gold_coin"},
    }
    catalog.npc_stock = {
        "vendor_a": {"item_a": 50},
        "vendor_b": {"item_b": 10},
    }

    result = catalog.currency_sinks("gold_coin")

    assert result == [
        ("item_b", "vendor_b", 10),
        ("item_a", "vendor_a", 50),
    ]
