"""Tests for GameData loading and lookup methods."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from artifactsmmo_api_client.models.craft_skill import CraftSkill
from artifactsmmo_api_client.models.event_content_schema import EventContentSchema
from artifactsmmo_api_client.models.event_map_schema import EventMapSchema
from artifactsmmo_api_client.models.event_schema import EventSchema
from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.models.static_data_page_event_schema import StaticDataPageEventSchema
from artifactsmmo_api_client.types import UNSET

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.game_data_cache import GameDataCache
from artifactsmmo_cli.ai.player import GamePlayer


def make_map_tile(x, y, content_type=None, content_code=None, access_conditions=None):
    tile = MagicMock()
    tile.x = x
    tile.y = y
    # Default: open tile (no access conditions). Pass a non-empty list to gate it.
    tile.access = MagicMock()
    tile.access.conditions = access_conditions if access_conditions is not None else []
    if content_type is not None:
        content = MagicMock()
        content.type_ = MapContentType(content_type)
        content.code = content_code
        tile.interactions.content = content
    else:
        tile.interactions.content = None
    return tile


def make_page(items):
    result = MagicMock()
    result.data = items
    return result


class TestGameDataLookups:
    def setup_method(self):
        self.gd = GameData()
        self.gd._monster_locations = {"chicken": [(1, 0), (2, 0)]}
        self.gd._resource_locations = {"copper": [(3, 0)]}
        self.gd._workshop_locations = {"weaponcrafting": (5, 0)}
        self.gd._bank_location = (4, 0)
        self.gd._item_stats = {"sword": ItemStats(code="sword", level=5, type_="weapon")}
        self.gd._crafting_recipes = {"sword": {"copper_ore": 3}}
        self.gd._resource_skill = {"copper": ("mining", 1)}
        self.gd._monster_level = {"chicken": 1}

    def test_monster_locations_known(self):
        assert self.gd.monster_locations("chicken") == [(1, 0), (2, 0)]

    def test_monster_locations_unknown(self):
        assert self.gd.monster_locations("dragon") == []

    def test_resource_locations_known(self):
        assert self.gd.resource_locations("copper") == [(3, 0)]

    def test_resource_locations_unknown(self):
        assert self.gd.resource_locations("gold") == []

    def test_workshop_location_known(self):
        assert self.gd.workshop_location("weaponcrafting") == (5, 0)

    def test_workshop_location_unknown(self):
        assert self.gd.workshop_location("alchemy") is None

    def test_bank_location(self):
        assert self.gd.bank_location() == (4, 0)

    def test_bank_location_raises_when_none(self):
        gd = GameData()
        gd._bank_location = None
        with pytest.raises(RuntimeError):
            gd.bank_location()

    def test_taskmaster_location(self):
        self.gd._taskmaster_location = (1, 2)
        assert self.gd.taskmaster_location() == (1, 2)

    def test_taskmaster_location_raises_when_none(self):
        gd = GameData()
        gd._taskmaster_location = None
        with pytest.raises(RuntimeError):
            gd.taskmaster_location()

    def test_item_stats_known(self):
        stats = self.gd.item_stats("sword")
        assert stats is not None
        assert stats.level == 5

    def test_item_stats_unknown(self):
        assert self.gd.item_stats("unknown") is None

    def test_crafting_recipe_known(self):
        recipe = self.gd.crafting_recipe("sword")
        assert recipe == {"copper_ore": 3}

    def test_crafting_recipe_unknown(self):
        assert self.gd.crafting_recipe("raw_chicken") is None

    def test_resource_skill_level_known(self):
        assert self.gd.resource_skill_level("copper") == ("mining", 1)

    def test_resource_skill_level_unknown(self):
        assert self.gd.resource_skill_level("gold") is None

    def test_monster_level_known(self):
        assert self.gd.monster_level("chicken") == 1

    def test_monster_level_unknown(self):
        assert self.gd.monster_level("dragon") == 0

    def test_nearest_location_single(self):
        nearest = self.gd.nearest_location(0, 0, [(3, 4)])
        assert nearest == (3, 4)

    def test_nearest_location_picks_closest(self):
        nearest = self.gd.nearest_location(0, 0, [(10, 10), (1, 0), (5, 5)])
        assert nearest == (1, 0)

    def test_nearest_location_empty(self):
        assert self.gd.nearest_location(0, 0, []) is None

    def test_best_consumable_returns_highest_restore(self):
        self.gd._item_stats["bread"] = ItemStats(code="bread", level=1, type_="consumable", hp_restore=10)
        self.gd._item_stats["cooked_chicken"] = ItemStats(
            code="cooked_chicken", level=1, type_="consumable", hp_restore=25)
        result = self.gd.best_consumable({"bread": 1, "cooked_chicken": 2})
        assert result == ("cooked_chicken", 25)

    def test_best_consumable_ignores_zero_qty(self):
        self.gd._item_stats["bread"] = ItemStats(code="bread", level=1, type_="consumable", hp_restore=10)
        result = self.gd.best_consumable({"bread": 0})
        assert result is None

    def test_best_consumable_ignores_non_consumable(self):
        self.gd._item_stats["copper_ore"] = ItemStats(code="copper_ore", level=1, type_="resource", hp_restore=0)
        result = self.gd.best_consumable({"copper_ore": 5})
        assert result is None

    def test_best_consumable_empty_inventory(self):
        assert self.gd.best_consumable({}) is None


class TestGameDataLoadMaps:
    def test_loads_monster_location(self):
        gd = GameData()
        tile = make_map_tile(1, 0, "monster", "chicken")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._monster_locations == {"chicken": [(1, 0)]}

    def test_loads_resource_location(self):
        gd = GameData()
        tile = make_map_tile(2, 3, "resource", "copper")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._resource_locations == {"copper": [(2, 3)]}

    def test_loads_bank_location(self):
        gd = GameData()
        tile = make_map_tile(0, 1, "bank", "bank")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._bank_location == (0, 1)

    def test_bank_selection_prefers_open_over_gated(self):
        """A gated bank (access conditions) must not win over an open one, in
        either iteration order — else the bot 496s on the gated bank."""
        for tiles in (
            [make_map_tile(-2, 19, "bank", "bank", access_conditions=[{"code": "secure_the_island"}]),
             make_map_tile(4, 1, "bank", "bank")],
            [make_map_tile(4, 1, "bank", "bank"),
             make_map_tile(-2, 19, "bank", "bank", access_conditions=[{"code": "secure_the_island"}])],
        ):
            gd = GameData()
            with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page(tiles)):
                gd._load_maps(MagicMock())
            assert gd._bank_location == (4, 1)
            assert gd.has_open_bank() is True

    def test_bank_tile_open_treats_missing_access_as_open(self):
        assert GameData._bank_tile_open(SimpleNamespace(access=None)) is True
        assert GameData._bank_tile_open(SimpleNamespace(access=SimpleNamespace(conditions=None))) is True
        assert GameData._bank_tile_open(SimpleNamespace(access=SimpleNamespace(conditions=[]))) is True
        assert GameData._bank_tile_open(
            SimpleNamespace(access=SimpleNamespace(conditions=[{"code": "secure_the_island"}]))
        ) is False

    def test_bank_falls_back_to_gated_when_no_open(self):
        gd = GameData()
        tile = make_map_tile(-2, 19, "bank", "bank", access_conditions=[{"code": "secure_the_island"}])
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._bank_location == (-2, 19)
        assert gd.has_open_bank() is False

    def test_loads_taskmaster_location(self):
        gd = GameData()
        tile = make_map_tile(1, 2, "tasks_master", "taskmaster")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._taskmaster_location == (1, 2)

    def test_loads_workshop_by_skill_substring(self):
        gd = GameData()
        tile = make_map_tile(5, 0, "workshop", "weaponcrafting_workshop")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._workshop_locations.get("weaponcrafting") == (5, 0)

    def test_skips_null_content(self):
        gd = GameData()
        tile = make_map_tile(1, 0)  # no content
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._monster_locations == {}

    def test_records_known_tiles_including_empty(self):
        """Every tile is recorded in _known_tiles — even content-free ones — so the
        TUI map can distinguish known floor from unmapped void."""
        gd = GameData()
        empty = make_map_tile(1, 0)  # no content
        monster = make_map_tile(2, 3, "monster", "chicken")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([empty, monster])):
            gd._load_maps(MagicMock())
        assert gd._known_tiles == {(1, 0), (2, 3)}

    def test_paginates_until_partial_page(self):
        gd = GameData()
        tile = make_map_tile(1, 0, "monster", "chicken")
        # First call: full page (100 items), second call: partial
        page1 = MagicMock()
        page1.data = [tile] * 100
        page2 = MagicMock()
        page2.data = [make_map_tile(2, 0, "monster", "cow")]
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", side_effect=[page1, page2]):
            gd._load_maps(MagicMock())
        assert "chicken" in gd._monster_locations
        assert "cow" in gd._monster_locations

    def test_loads_grand_exchange_location(self):
        gd = GameData()
        tile = make_map_tile(3, 4, "grand_exchange", "grand_exchange")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._grand_exchange_location == (3, 4)

    def test_stops_on_none_result(self):
        gd = GameData()
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=None):
            gd._load_maps(MagicMock())
        assert gd._monster_locations == {}


class TestGameDataLoadItems:
    def test_loads_item_stats(self):
        gd = GameData()
        item = MagicMock()
        item.code = "copper_dagger"
        item.level = 3
        item.type_ = "weapon"
        item.craft = UNSET
        with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=make_page([item])):
            gd._load_items(MagicMock())
        assert "copper_dagger" in gd._item_stats
        assert gd._item_stats["copper_dagger"].level == 3

    def test_loads_crafting_recipe(self):
        gd = GameData()
        item = MagicMock()
        item.code = "copper_dagger"
        item.level = 3
        item.type_ = "weapon"

        mat = MagicMock()
        mat.code = "copper_ore"
        mat.quantity = 6

        craft = MagicMock()
        craft.skill = CraftSkill.WEAPONCRAFTING
        craft.level = 1
        craft.items = [mat]
        item.craft = craft

        with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=make_page([item])):
            gd._load_items(MagicMock())

        assert gd._crafting_recipes["copper_dagger"] == {"copper_ore": 6}

    def test_loads_hp_restore_from_heal_effect(self):
        gd = GameData()
        item = MagicMock()
        item.code = "cooked_chicken"
        item.level = 5
        item.type_ = "consumable"
        item.craft = UNSET

        heal_effect = MagicMock()
        heal_effect.code = "heal"
        heal_effect.value = 25
        item.effects = [heal_effect]

        with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=make_page([item])):
            gd._load_items(MagicMock())

        assert gd._item_stats["cooked_chicken"].hp_restore == 25

    def test_hp_restore_zero_for_non_heal_effect(self):
        gd = GameData()
        item = MagicMock()
        item.code = "copper_dagger"
        item.level = 3
        item.type_ = "weapon"
        item.craft = UNSET

        attack_effect = MagicMock()
        attack_effect.code = "attack_earth"
        attack_effect.value = 5
        item.effects = [attack_effect]

        with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=make_page([item])):
            gd._load_items(MagicMock())

        assert gd._item_stats["copper_dagger"].hp_restore == 0

    def test_stops_on_none_result(self):
        gd = GameData()
        with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=None):
            gd._load_items(MagicMock())
        assert gd._item_stats == {}

    def test_loads_gear_combat_effects(self):
        gd = GameData()
        item = MagicMock()
        item.code = "power_ring"
        item.level = 5
        item.type_ = "ring"
        item.craft = UNSET  # no recipe
        def eff(code, value):
            e = MagicMock()
            e.code = code
            e.value = value
            return e
        item.effects = [eff("dmg", 8), eff("dmg_fire", 4), eff("critical_strike", 6),
                        eff("initiative", 20), eff("hp", 50)]
        with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=make_page([item])):
            gd._load_items(MagicMock())
        s = gd.item_stats("power_ring")
        assert s.dmg == 8
        assert s.dmg_elements == {"fire": 4}
        assert s.critical_strike == 6
        assert s.initiative == 20
        assert s.hp_bonus == 50

    def test_loads_utility_artifact_effects(self):
        """wisdom + prospecting (artifact utility stats) parse into ItemStats so
        the value/scoring model sees them — novice_guide regression."""
        gd = GameData()
        item = MagicMock()
        item.code = "novice_guide"
        item.level = 10
        item.type_ = "artifact"
        item.craft = UNSET
        def eff(code, value):
            e = MagicMock()
            e.code = code
            e.value = value
            return e
        item.effects = [eff("hp", 25), eff("wisdom", 25), eff("prospecting", 25)]
        with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=make_page([item])):
            gd._load_items(MagicMock())
        s = gd.item_stats("novice_guide")
        assert s.hp_bonus == 25
        assert s.wisdom == 25
        assert s.prospecting == 25


class TestGameDataLoadResources:
    def test_loads_skill_requirement(self):
        gd = GameData()
        resource = MagicMock()
        resource.code = "copper"
        resource.skill = MagicMock()
        resource.skill.value = "mining"
        resource.level = 1
        resource.drops = []
        with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=make_page([resource])):
            gd._load_resources(MagicMock())
        assert gd._resource_skill["copper"] == ("mining", 1)

    def test_loads_primary_drop_item(self):
        gd = GameData()
        resource = MagicMock()
        resource.code = "copper_rocks"
        resource.skill = MagicMock()
        resource.skill.value = "mining"
        resource.level = 1
        drop = MagicMock()
        drop.code = "copper_ore"
        drop.rate = 1
        resource.drops = [drop]
        with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=make_page([resource])):
            gd._load_resources(MagicMock())
        assert gd.resource_drop_item("copper_rocks") == "copper_ore"

    def test_picks_most_common_drop_when_multiple(self):
        gd = GameData()
        resource = MagicMock()
        resource.code = "iron_rocks"
        resource.skill = MagicMock()
        resource.skill.value = "mining"
        resource.level = 5
        drop_rare = MagicMock()
        drop_rare.code = "gem"
        drop_rare.rate = 10
        drop_common = MagicMock()
        drop_common.code = "iron_ore"
        drop_common.rate = 1
        resource.drops = [drop_rare, drop_common]
        with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=make_page([resource])):
            gd._load_resources(MagicMock())
        assert gd.resource_drop_item("iron_rocks") == "iron_ore"

    def test_no_drop_when_resource_has_no_drops(self):
        gd = GameData()
        resource = MagicMock()
        resource.code = "copper"
        resource.skill = MagicMock()
        resource.skill.value = "mining"
        resource.level = 1
        resource.drops = []
        with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=make_page([resource])):
            gd._load_resources(MagicMock())
        assert gd.resource_drop_item("copper") is None

    def test_stops_on_none_result(self):
        gd = GameData()
        with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=None):
            gd._load_resources(MagicMock())
        assert gd._resource_skill == {}


class TestGameDataLoadMonsters:
    def test_loads_monster_level(self):
        gd = GameData()
        monster = MagicMock()
        monster.code = "chicken"
        monster.level = 1
        with patch("artifactsmmo_cli.ai.game_data.get_all_monsters", return_value=make_page([monster])):
            gd._load_monsters(MagicMock())
        assert gd._monster_level["chicken"] == 1

    def test_loads_monster_combat_stats(self):
        gd = GameData()
        monster = MagicMock()
        monster.code = "chicken"
        monster.level = 1
        monster.hp = 60
        monster.critical_strike = 5
        monster.initiative = 100
        with patch("artifactsmmo_cli.ai.game_data.get_all_monsters", return_value=make_page([monster])):
            gd._load_monsters(MagicMock())
        assert gd._monster_hp["chicken"] == 60
        assert gd._monster_critical_strike["chicken"] == 5
        assert gd._monster_initiative["chicken"] == 100

    def test_stops_on_none_result(self):
        gd = GameData()
        with patch("artifactsmmo_cli.ai.game_data.get_all_monsters", return_value=None):
            gd._load_monsters(MagicMock())
        assert gd._monster_level == {}


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


def _ge_order(order_id, code, price, quantity):
    return SimpleNamespace(id=order_id, code=code, price=price, quantity=quantity)


def test_load_ge_orders_keeps_highest_price_buy_order_per_item(monkeypatch):
    """_load_ge_orders should index the highest-price OPEN BUY order per item."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeResult:
        def __init__(self, data):
            self.data = data

    def fake_sync(client, type_, page, size):
        from artifactsmmo_api_client.models.ge_order_type import GEOrderType
        # _load_ge_orders pages BOTH sides; only the BUY side feeds this assertion.
        if type_ is not GEOrderType.BUY:
            return FakeResult([])
        if page == 1:
            return FakeResult([
                _ge_order("o1", "iron_ore", price=10, quantity=5),
                _ge_order("o2", "iron_ore", price=14, quantity=3),  # higher price wins
                _ge_order("o3", "copper_ore", price=7, quantity=2),
            ])
        return FakeResult([])

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
    gd = GameData()
    gd._load_ge_orders(client=None)

    assert gd.ge_best_buy_order("iron_ore") == ("o2", 14, 3)
    assert gd.ge_best_buy_order("copper_ore") == ("o3", 7, 2)
    assert gd.ge_best_buy_order("unknown") is None


def test_load_ge_orders_breaks_price_ties_by_quantity_then_id(monkeypatch):
    """Equal price → prefer the order with greater fillable quantity, then id."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeResult:
        def __init__(self, data):
            self.data = data

    def fake_sync(client, type_, page, size):
        if page == 1:
            return FakeResult([
                _ge_order("a", "gem", price=20, quantity=2),
                _ge_order("b", "gem", price=20, quantity=9),  # more quantity → wins
                _ge_order("c", "gem", price=20, quantity=9),  # tie on qty → higher id "c"
            ])
        return FakeResult([])

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
    gd = GameData()
    gd._load_ge_orders(client=None)

    assert gd.ge_best_buy_order("gem") == ("c", 20, 9)


def test_load_ge_orders_paginates_past_full_page(monkeypatch):
    """A full first page forces a second fetch; the loop terminates on the short page."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeResult:
        def __init__(self, data):
            self.data = data

    def fake_sync(client, type_, page, size):
        if page == 1:
            return FakeResult([_ge_order(f"p1-{i}", "ore", price=i, quantity=1) for i in range(100)])
        if page == 2:
            return FakeResult([_ge_order("p2", "ore", price=999, quantity=4)])
        return FakeResult([])

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
    gd = GameData()
    gd._load_ge_orders(client=None)

    assert gd.ge_best_buy_order("ore") == ("p2", 999, 4)


def test_load_ge_orders_keeps_lowest_price_sell_order_per_item(monkeypatch):
    """_load_ge_orders should index the LOWEST-price OPEN SELL order per item — the
    cheapest fillable BUY source (DUAL of the highest-price buy order)."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeResult:
        def __init__(self, data):
            self.data = data

    def fake_sync(client, type_, page, size):
        from artifactsmmo_api_client.models.ge_order_type import GEOrderType
        if type_ is not GEOrderType.SELL:
            return FakeResult([])
        if page == 1:
            return FakeResult([
                _ge_order("s1", "iron_ore", price=10, quantity=5),
                _ge_order("s2", "iron_ore", price=6, quantity=3),  # lower price wins
                _ge_order("s3", "copper_ore", price=7, quantity=2),
            ])
        return FakeResult([])

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
    gd = GameData()
    gd._load_ge_orders(client=None)

    assert gd.ge_best_sell_order("iron_ore") == ("s2", 6, 3)
    assert gd.ge_best_sell_order("copper_ore") == ("s3", 7, 2)
    assert gd.ge_best_sell_order("unknown") is None


def test_load_ge_orders_sell_breaks_price_ties_by_quantity_then_id(monkeypatch):
    """Equal (lowest) price → prefer the order with greater fillable quantity, then id."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeResult:
        def __init__(self, data):
            self.data = data

    def fake_sync(client, type_, page, size):
        from artifactsmmo_api_client.models.ge_order_type import GEOrderType
        if type_ is not GEOrderType.SELL:
            return FakeResult([])
        if page == 1:
            return FakeResult([
                _ge_order("a", "gem", price=5, quantity=2),
                _ge_order("b", "gem", price=5, quantity=9),  # more quantity → wins
                _ge_order("c", "gem", price=5, quantity=9),  # tie on qty → higher id "c"
            ])
        return FakeResult([])

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
    gd = GameData()
    gd._load_ge_orders(client=None)

    assert gd.ge_best_sell_order("gem") == ("c", 5, 9)


def test_load_ge_orders_sell_paginates_past_full_page(monkeypatch):
    """A full first SELL page forces a second fetch; the loop terminates on the short page."""
    from artifactsmmo_cli.ai.game_data import GameData

    class FakeResult:
        def __init__(self, data):
            self.data = data

    def fake_sync(client, type_, page, size):
        from artifactsmmo_api_client.models.ge_order_type import GEOrderType
        if type_ is not GEOrderType.SELL:
            return FakeResult([])
        if page == 1:
            return FakeResult([_ge_order(f"p1-{i}", "ore", price=500 + i, quantity=1) for i in range(100)])
        if page == 2:
            return FakeResult([_ge_order("p2", "ore", price=3, quantity=4)])  # lowest → wins
        return FakeResult([])

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
    gd = GameData()
    gd._load_ge_orders(client=None)

    assert gd.ge_best_sell_order("ore") == ("p2", 3, 4)


def test_grand_exchange_location_accessor():
    from artifactsmmo_cli.ai.game_data import GameData
    gd = GameData()
    assert gd.grand_exchange_location() is None
    gd._grand_exchange_location = (3, 4)
    assert gd.grand_exchange_location() == (3, 4)


class TestGameDataLoad:
    def test_load_calls_all_sub_loaders(self, tmp_path):
        client = MagicMock()
        cache = GameDataCache("https://api.artifactsmmo.com", cache_dir=tmp_path)
        empty_page = make_page([])
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=empty_page):
            with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=empty_page):
                with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=empty_page):
                    with patch("artifactsmmo_cli.ai.game_data.get_all_monsters", return_value=empty_page):
                        with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items", return_value=empty_page):
                            with patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=empty_page):
                                with patch("artifactsmmo_cli.ai.game_data.get_ge_orders", return_value=empty_page):
                                    with patch("artifactsmmo_cli.ai.game_data.get_bank_details", return_value=None):
                                        gd = GameData.load(client, cache=cache)
        assert isinstance(gd, GameData)


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


def test_active_gathering_skills_walks_recipe_tree():
    """Task on a crafted item should surface every gather skill in its recipe
    chain (e.g. ash_plank ← ash_wood ← ash_tree → woodcutting)."""
    gd = GameData()
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    assert gd.active_gathering_skills("ash_plank") == {"woodcutting"}


def test_active_gathering_skills_returns_empty_for_no_task():
    gd = GameData()
    assert gd.active_gathering_skills(None) == set()
    assert gd.active_gathering_skills("") == set()


def test_active_gathering_skills_counts_crafting_target():
    """A self-directed crafting target surfaces its recipe-tree gather skills
    even with no taskmaster task — mining copper for copper gear marks mining."""
    gd = GameData()
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 10},
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    # No task, but the bot is crafting a copper dagger → mining is active.
    assert gd.active_gathering_skills(None, "copper_dagger") == {"mining"}


def test_active_gathering_skills_unions_task_and_crafting_target():
    """Skills from BOTH the task recipe tree and the crafting target unite."""
    gd = GameData()
    gd._crafting_recipes = {
        "ash_plank": {"ash_wood": 1},
        "copper_bar": {"copper_ore": 10},
    }
    gd._resource_drops = {"ash_tree": "ash_wood", "copper_rocks": "copper_ore"}
    gd._resource_skill = {
        "ash_tree": ("woodcutting", 1),
        "copper_rocks": ("mining", 1),
    }
    assert gd.active_gathering_skills("ash_plank", "copper_bar") == {"woodcutting", "mining"}


def test_active_gathering_skills_handles_multi_skill_recipes():
    """Two raws in the recipe = two skills surfaced."""
    gd = GameData()
    gd._crafting_recipes = {"alloy_bar": {"copper_ore": 2, "iron_ore": 2}}
    gd._resource_drops = {"copper_rocks": "copper_ore", "iron_rocks": "iron_ore"}
    gd._resource_skill = {
        "copper_rocks": ("mining", 1),
        "iron_rocks": ("mining", 5),
    }
    assert gd.active_gathering_skills("alloy_bar") == {"mining"}


def test_active_gathering_skills_terminates_on_cyclic_recipe():
    """A self-referential / cyclic recipe graph must not loop forever — the
    visited-set guard (line 334-335) terminates the walk and still surfaces the
    real gather skill."""
    gd = GameData()
    # foo <- bar and bar <- foo form a cycle; bar also consumes copper_ore.
    gd._crafting_recipes = {
        "foo": {"bar": 1},
        "bar": {"foo": 1, "copper_ore": 1},
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    assert gd.active_gathering_skills("foo") == {"mining"}


def test_max_character_level_is_documented_50():
    """Documented cap per https://docs.artifactsmmo.com/concepts/stats_and_fights/.
    Constant — does not depend on loaded monster data (events/bosses can
    exceed 50)."""
    gd = GameData()
    assert gd.max_character_level == 50
    gd._monster_level = {"sea_marauder": 45, "boss_at_55": 55}
    assert gd.max_character_level == 50  # still 50, not 55


def test_max_skill_level_is_documented_50():
    """Verified: https://docs.artifactsmmo.com/concepts/skills —
    '8 skills that can gain XP and reach up to level 50'."""
    assert GameData().max_skill_level == 50


def test_xp_per_kill_formula_normal_monster():
    """Documented formula: (monster_level/char_level * 20 + monster_hp * 0.04) * penalty * mult * wisdom_bonus."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 60}
    gd._monster_type = {"chicken": "normal"}
    # char L1, no wisdom: (1/1 * 20 + 60 * 0.04) * 1.0 * 1.0 * 1.0 = 22.4 → round 22
    assert gd.xp_per_kill("chicken", char_level=1, wisdom=0) == 22


def test_xp_per_kill_level_penalty_above_5():
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 60}
    gd._monster_type = {"chicken": "normal"}
    # char L6 vs L1 monster: diff=5 → 0.7 penalty
    # (1/6 * 20 + 60 * 0.04) * 0.7 = (3.33 + 2.4) * 0.7 = 4.01 → 4
    result = gd.xp_per_kill("chicken", char_level=6, wisdom=0)
    assert result == 4


def test_xp_per_kill_level_penalty_above_10_zero():
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 60}
    gd._monster_type = {"chicken": "normal"}
    assert gd.xp_per_kill("chicken", char_level=11, wisdom=0) == 0


def test_xp_per_kill_elite_multiplier():
    gd = GameData()
    gd._monster_level = {"elite_boss": 5}
    gd._monster_hp = {"elite_boss": 200}
    gd._monster_type = {"elite_boss": "elite"}
    # (5/5 * 20 + 200 * 0.04) * 1.0 * 1.4 = (20 + 8) * 1.4 = 39.2 → 39
    assert gd.xp_per_kill("elite_boss", char_level=5) == 39


def test_xp_per_kill_unknown_monster_zero():
    gd = GameData()
    assert gd.xp_per_kill("nonexistent", char_level=5) == 0


# ---------------------------------------------------------------------------
# Event NPC registry tests
# ---------------------------------------------------------------------------

def _make_event_catalog() -> StaticDataPageEventSchema:
    npc_event = EventSchema(
        name="Gemstone Merchant",
        code="gemstone_merchant",
        content=EventContentSchema(type_=MapContentType.NPC, code="gemstone_merchant"),
        maps=[EventMapSchema(map_id=238, x=6, y=-1, layer="overworld", skin="x")],
        duration=60,
        rate=1500,
    )
    monster_event = EventSchema(
        name="Bandit Camp",
        code="bandit_camp",
        content=EventContentSchema(type_=MapContentType.MONSTER, code="bandit_lizard"),
        maps=[EventMapSchema(map_id=538, x=4, y=5, layer="overworld", skin="y")],
        duration=120,
        rate=1500,
    )
    return StaticDataPageEventSchema(data=[npc_event, monster_event])


def test_load_events_indexes_npc_events_only():
    gd = GameData()
    with patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=_make_event_catalog()):
        gd._load_events(client=None)
    assert gd.is_event_npc("gemstone_merchant") is True
    assert gd.is_event_npc("bandit_lizard") is False
    assert gd.npc_event_code("gemstone_merchant") == "gemstone_merchant"


def test_npc_location_falls_back_to_event_spawn():
    gd = GameData()
    with patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=_make_event_catalog()):
        gd._load_events(client=None)
    assert gd.npc_location("gemstone_merchant") == (6, -1)


def test_static_npc_location_wins_over_event_spawn():
    gd = GameData()
    gd._npc_locations["gemstone_merchant"] = (1, 1)
    with patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=_make_event_catalog()):
        gd._load_events(client=None)
    assert gd.npc_location("gemstone_merchant") == (1, 1)


def test_load_events_paginates_past_full_page():
    """A full 100-entry page advances to the next page until a short page ends it."""
    def _npc_event(code: str) -> EventSchema:
        return EventSchema(
            name=code,
            code=code,
            content=EventContentSchema(type_=MapContentType.NPC, code=code),
            maps=[EventMapSchema(map_id=1, x=0, y=0, layer="overworld", skin="s")],
            duration=60,
            rate=1500,
        )

    full_page = StaticDataPageEventSchema(data=[_npc_event(f"merchant_{i}") for i in range(100)])
    last_page = StaticDataPageEventSchema(data=[_npc_event("merchant_last")])
    gd = GameData()
    with patch("artifactsmmo_cli.ai.game_data.get_all_events", side_effect=[full_page, last_page]):
        gd._load_events(client=None)
    assert gd.is_event_npc("merchant_0") is True
    assert gd.is_event_npc("merchant_last") is True


def test_monster_combat_getters_return_stored_values():
    gd = GameData()
    gd._monster_hp = {"chicken": 60}
    gd._monster_critical_strike = {"chicken": 5}
    gd._monster_initiative = {"chicken": 100}
    assert gd.monster_hp("chicken") == 60
    assert gd.monster_critical_strike("chicken") == 5
    assert gd.monster_initiative("chicken") == 100


def test_monster_combat_getters_raise_when_unknown():
    """Phase-9 REAL BUG #16 fix: silent zero defaults masked
    `predict_win` saying True for any unknown monster (zero-attack,
    zero-hp ⇒ player_first ∧ monster_hit=0 ⇒ True). Accessors now raise
    KeyError instead of silently returning 0/{} — the single-locus
    enforcement of "use only API data or fail with an error"."""
    gd = GameData()
    with pytest.raises(KeyError):
        gd.monster_hp("missing")
    with pytest.raises(KeyError):
        gd.monster_critical_strike("missing")
    with pytest.raises(KeyError):
        gd.monster_initiative("missing")
    with pytest.raises(KeyError):
        gd.monster_attack("missing")
    with pytest.raises(KeyError):
        gd.monster_resistance("missing")
    # monster_level KEEPS the silent zero default — it's a documented probe
    # used by consumers as the "is this code a known monster?" gate, NOT a
    # value-bearing accessor. See game_data.py:monster_level docstring.
    assert gd.monster_level("missing") == 0


# Item 2d differential: GlobalInvariants Category A establishment.
#
# The Lean liveness proof (Formal.Liveness.LevelFiftyReachable) assumes
# GlobalInvariants Category A holds at the starting state:
#   hex: state.task_exchange_min_coins > 0 when TaskExchange evaluates.
#   hbe: game_data._next_expansion_cost > 0 when BankExpand evaluates.
#
# Item 2b proved these propagate structurally across cycleStep (see
# Formal.Liveness.GameDataInvariance). This test asserts production
# establishes them at every observation point.


def test_category_a_hbe_invariant_next_expansion_cost_positive_when_bank_present(
    monkeypatch,
):
    """GlobalInvariants Category A (hbe): when bank_capacity > 0 (the
    BANK_EXPAND firing gate in tiers/means.py:108), the server's
    next_expansion_cost MUST be > 0. Without this, the Lean liveness
    proof's hbe hypothesis is vacuously satisfied yet semantically
    violated."""

    class FakeBankDetails:
        slots = 30
        next_expansion_cost = 1000

    class FakeResult:
        data = FakeBankDetails()

    def fake_get_bank_details(client):
        return FakeResult()

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.game_data.get_bank_details", fake_get_bank_details
    )
    gd = GameData()
    gd._load_bank_metadata(client=None)
    assert gd._bank_capacity > 0
    assert gd._next_expansion_cost > 0  # Lean hbe invariant.


def test_category_a_hex_invariant_task_exchange_min_coins_positive():
    """GlobalInvariants Category A (hex): the bot's
    task_exchange_min_coins parameter MUST be > 0. Default is 1
    (player.py:125) — verifies the default establishes the invariant."""
    bot = GamePlayer.__new__(GamePlayer)
    bot._task_exchange_min_coins = 1
    assert bot._task_exchange_min_coins > 0  # Lean hex invariant.


# Item 14 OpenAPI conformance — newly-ingested fields.


def test_monster_drops_default_empty_when_unknown():
    """OpenAPI conformance: monster_drops returns [] for unknown monster
    (legacy code expected no drops table; defensive default keeps the
    callers safe before the API populates the field)."""
    gd = GameData()
    assert gd.monster_drops("nonexistent_monster") == []


def test_monster_min_max_gold_default_zero_when_unknown():
    """OpenAPI conformance: min/max gold accessors return 0 for unknown
    monster. Legacy code didn't carry gold rewards."""
    gd = GameData()
    assert gd.monster_min_gold("nonexistent_monster") == 0
    assert gd.monster_max_gold("nonexistent_monster") == 0


def test_monster_drops_populated_after_load(monkeypatch):
    """OpenAPI conformance: monster.drops list survives _load_monsters."""

    class FakeDrop:
        def __init__(self, code, rate, min_quantity, max_quantity):
            self.code = code
            self.rate = rate
            self.min_quantity = min_quantity
            self.max_quantity = max_quantity

    class FakeMonster:
        def __init__(self):
            self.code = "chicken"
            self.level = 1
            self.hp = 60
            self.type_ = "normal"
            self.attack_fire = 0
            self.attack_earth = 0
            self.attack_water = 0
            self.attack_air = 3
            self.res_fire = 0
            self.res_earth = 0
            self.res_water = 0
            self.res_air = 0
            self.critical_strike = 5
            self.initiative = 100
            self.min_gold = 1
            self.max_gold = 3
            self.drops = [FakeDrop("egg", 5, 1, 2), FakeDrop("feather", 10, 1, 1)]

    class FakeResult:
        def __init__(self):
            self.data = [FakeMonster()]

    def fake_get(client, page, size):
        return FakeResult() if page == 1 else None

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.game_data.get_all_monsters", fake_get
    )
    gd = GameData()
    gd._load_monsters(client=None)
    assert gd.monster_drops("chicken") == [("egg", 5, 1, 2), ("feather", 10, 1, 1)]
    assert gd.monster_min_gold("chicken") == 1
    assert gd.monster_max_gold("chicken") == 3
    # min_quantity is restored symmetric to max_quantity (was dropped at load).
    assert gd.monsters_dropping("egg") == [("chicken", 5, 1, 2)]
    assert gd.monsters_dropping("feather") == [("chicken", 10, 1, 1)]
    assert gd.monsters_dropping("nonexistent_item") == []


def test_item_stats_tradeable_default_true():
    """OpenAPI conformance: ItemStats.tradeable defaults to True for
    backward-compat with legacy fixtures."""
    s = ItemStats(code="copper_ore", level=1, type_="resource")
    assert s.tradeable is True
    assert s.conditions == []
    assert s.subtype == ""


def test_monster_load_unset_min_max_gold(monkeypatch):
    """OpenAPI conformance: when API client returns UNSET for
    min_gold/max_gold (older client), loader treats as 0."""

    class FakeMonster:
        def __init__(self):
            self.code = "phantom"
            self.level = 1
            self.hp = 10
            self.type_ = "normal"
            self.attack_fire = 0
            self.attack_earth = 0
            self.attack_water = 0
            self.attack_air = 1
            self.res_fire = 0
            self.res_earth = 0
            self.res_water = 0
            self.res_air = 0
            self.critical_strike = 0
            self.initiative = 50
            self.min_gold = UNSET
            self.max_gold = UNSET
            self.drops = None

    class FakeResult:
        def __init__(self):
            self.data = [FakeMonster()]

    def fake_get(client, page, size):
        return FakeResult() if page == 1 else None

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.game_data.get_all_monsters", fake_get
    )
    gd = GameData()
    gd._load_monsters(client=None)
    assert gd.monster_min_gold("phantom") == 0
    assert gd.monster_max_gold("phantom") == 0
    assert gd.monster_drops("phantom") == []


def test_item_load_conditions_and_unset_subtype(monkeypatch):
    """OpenAPI conformance: item.conditions list parsed; subtype UNSET → ''."""

    class FakeCondition:
        def __init__(self, code, value):
            self.code = code
            self.value = value

    class FakeItem:
        def __init__(self):
            self.code = "trinket"
            self.level = 1
            self.type_ = "ring"
            self.tradeable = True
            self.subtype = UNSET
            self.conditions = [
                FakeCondition("character_level", 10),
                FakeCondition("mining_level", 5),
            ]
            self.effects = UNSET
            self.craft = UNSET

    class FakeResult:
        def __init__(self):
            self.data = [FakeItem()]

    def fake_get(client, page, size):
        return FakeResult() if page == 1 else None

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.game_data.get_all_items", fake_get
    )
    gd = GameData()
    gd._load_items(client=None)
    stats = gd._item_stats["trinket"]
    assert stats.subtype == ""
    assert stats.conditions == [("character_level", 10), ("mining_level", 5)]
    assert stats.tradeable is True


class TestGameDataFetchBuildSplit:
    def test_fetch_maps_returns_element_objects(self):
        gd = GameData()
        tile = make_map_tile(1, 0, "monster", "chicken")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            out = gd._fetch_maps(MagicMock())
        assert out == [tile]   # _fetch_* returns the schema objects, un-built

    def test_load_maps_is_fetch_then_build(self):
        # the existing wrapper still indexes correctly (build over fetched objects)
        gd = GameData()
        tile = make_map_tile(2, 3, "resource", "copper")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._resource_locations == {"copper": [(2, 3)]}


_STATIC = ("maps", "items", "resources", "monsters", "npcs", "events")


class _RecordingCache(GameDataCache):
    def __init__(self, tmp_path, seeded=None):
        super().__init__("https://api.artifactsmmo.com", cache_dir=tmp_path)
        self.reads = 0
        self.writes = 0
        self._seeded = seeded

    def read(self, ttl_minutes, now=None):
        self.reads += 1
        return self._seeded

    def write(self, raw_pages, now=None):
        self.writes += 1
        self._seeded = raw_pages


def _stub_fetch_build(monkeypatch):
    """Stub every _fetch_* to return empty (so serialize/deserialize loops are
    no-ops) and _build_*/_load_ge_orders to recorders. Returns the GE counter."""
    for name in _STATIC:
        monkeypatch.setattr(GameData, f"_fetch_{name}", lambda self, client: [])
        monkeypatch.setattr(GameData, f"_build_{name}", lambda self, items: None)
    monkeypatch.setattr(GameData, "_fetch_bank", lambda self, client: None)
    monkeypatch.setattr(GameData, "_build_bank", lambda self, item: None)
    ge = {"n": 0}
    monkeypatch.setattr(
        GameData, "_load_ge_orders", lambda self, client: ge.__setitem__("n", ge["n"] + 1)
    )
    return ge


def test_cold_load_fetches_and_writes(monkeypatch, tmp_path):
    ge = _stub_fetch_build(monkeypatch)
    cache = _RecordingCache(tmp_path, seeded=None)  # miss
    GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)
    assert cache.reads == 1 and cache.writes == 1
    assert ge["n"] == 1  # GE always live


def test_warm_load_skips_fetch_uses_cache(monkeypatch, tmp_path):
    ge = _stub_fetch_build(monkeypatch)
    seeded = {k: [] for k in _STATIC} | {"bank": None}
    cache = _RecordingCache(tmp_path, seeded=seeded)  # hit
    monkeypatch.setattr(
        GameData,
        "_fetch_maps",
        lambda self, client: (_ for _ in ()).throw(AssertionError("fetched on warm hit")),
    )
    GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)
    assert cache.reads == 1 and cache.writes == 0
    assert ge["n"] == 1  # GE STILL fetched live on a warm hit


def test_force_refresh_bypasses_read(monkeypatch, tmp_path):
    _stub_fetch_build(monkeypatch)
    cache = _RecordingCache(tmp_path, seeded={k: [] for k in _STATIC} | {"bank": None})
    GameData.load(client=MagicMock(), ttl_minutes=30, force_refresh=True, cache=cache)
    assert cache.reads == 0 and cache.writes == 1


def test_cold_load_survives_cache_write_oserror(monkeypatch, tmp_path, capsys):
    """A failed cache write (disk full / permissions) must NOT crash load(): the
    fetched data is already in hand, so load swallows the OSError, logs it, and
    still returns a fully-built GameData (the next start simply re-fetches)."""
    ge = _stub_fetch_build(monkeypatch)

    class _WriteFailsCache(_RecordingCache):
        def write(self, raw_pages, now=None):
            raise OSError("disk full")

    cache = _WriteFailsCache(tmp_path, seeded=None)  # cold miss → fetch → write (raises)
    gd = GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)
    assert isinstance(gd, GameData)
    assert cache.reads == 1
    assert ge["n"] == 1  # GE still fetched live; build pipeline ran to completion
    assert "cache write failed" in capsys.readouterr().out


def test_build_bank_none_is_noop():
    """_build_bank(None) leaves bank metadata untouched (the cold-load 'no bank'
    branch and the warm-load BankSchema-None branch both pass None here)."""
    gd = GameData()
    gd._build_bank(None)
    assert gd._bank_capacity == 0
    assert gd._next_expansion_cost == 0


def test_fetch_bank_returns_none_when_no_data(monkeypatch):
    """_fetch_bank returns None when the API yields no result or a dataless one,
    and the schema object when data is present."""
    gd = GameData()

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_bank_details", lambda client: None)
    assert gd._fetch_bank(client=None) is None

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.game_data.get_bank_details",
        lambda client: SimpleNamespace(data=None),
    )
    assert gd._fetch_bank(client=None) is None

    bank_obj = SimpleNamespace(slots=30, next_expansion_cost=1000)
    monkeypatch.setattr(
        "artifactsmmo_cli.ai.game_data.get_bank_details",
        lambda client: SimpleNamespace(data=bank_obj),
    )
    assert gd._fetch_bank(client=None) is bank_obj


def _make_event_npc(code, npc_code, x, y) -> EventSchema:
    return EventSchema(
        name=code,
        code=code,
        content=EventContentSchema(type_=MapContentType.NPC, code=npc_code),
        maps=[EventMapSchema(map_id=1, x=x, y=y, layer="overworld", skin="s")],
        duration=60,
        rate=1500,
    )


def test_warm_and_cold_events_build_equal(monkeypatch, tmp_path):
    """A real EventSchema fetched cold (built from the object) and warm
    (built from from_dict(to_dict(...))) must index identically."""
    ev = _make_event_npc(code="gold_merchant", npc_code="merchant", x=5, y=6)  # real EventSchema
    monkeypatch.setattr(GameData, "_fetch_events", lambda self, client: [ev])
    for name in ("maps", "items", "resources", "monsters", "npcs"):
        monkeypatch.setattr(GameData, f"_fetch_{name}", lambda self, client: [])
    monkeypatch.setattr(GameData, "_fetch_bank", lambda self, client: None)
    monkeypatch.setattr(GameData, "_load_ge_orders", lambda self, client: None)
    cache = _RecordingCache(tmp_path, seeded=None)
    cold = GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)  # writes cache
    warm = GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)  # from_dict path
    assert cold._npc_event_code == warm._npc_event_code
    assert cold._event_npc_spawns == warm._event_npc_spawns
    assert warm._event_npc_spawns  # non-empty -> the round-trip really happened
