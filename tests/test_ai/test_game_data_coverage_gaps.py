"""Behavior tests closing coverage gaps in GameData API-loading parsers."""

from unittest.mock import MagicMock, patch

from artifactsmmo_api_client.types import UNSET

from artifactsmmo_cli.ai.game_data import GameData


def _make_page(items):
    result = MagicMock()
    result.data = items
    return result


def _eff(code, value):
    e = MagicMock()
    e.code = code
    e.value = value
    return e


class TestLoadItemEffects:
    def test_resistance_effect_parsed(self):
        """A `res_<element>` effect populates ItemStats.resistance (lines
        441-442)."""
        gd = GameData()
        item = MagicMock()
        item.code = "earth_shield"
        item.level = 3
        item.type_ = "shield"
        item.craft = UNSET
        item.effects = [_eff("res_earth", 15)]
        with patch("artifactsmmo_cli.ai.game_data.get_all_items",
                   return_value=_make_page([item])):
            gd._load_items(MagicMock())
        assert gd.item_stats("earth_shield").resistance == {"earth": 15}

    def test_gather_skill_tool_effect_parsed(self):
        """An effect whose code is a gathering skill (e.g. `woodcutting`) is a
        tool bonus stored in skill_effects (lines 453-457)."""
        gd = GameData()
        item = MagicMock()
        item.code = "copper_axe"
        item.level = 1
        item.type_ = "weapon"
        item.craft = UNSET
        # negative value = cooldown reduction (faster woodcutting)
        item.effects = [_eff("woodcutting", -10)]
        with patch("artifactsmmo_cli.ai.game_data.get_all_items",
                   return_value=_make_page([item])):
            gd._load_items(MagicMock())
        assert gd.item_stats("copper_axe").skill_effects == {"woodcutting": -10}


class TestLoadNpcsPaginates:
    def test_paginates_across_full_then_partial_page(self):
        """A full 100-entry page forces page+=1 (line 510); the next partial
        page ends the loop. Entries from BOTH pages are indexed."""
        class FakeEntry:
            def __init__(self, npc, code, sell_price):
                self.npc = npc
                self.code = code
                self.buy_price = None
                self.sell_price = sell_price

        class FakeResult:
            def __init__(self, data):
                self.data = data

        page1 = [FakeEntry("cook", f"item_{i}", sell_price=i + 1) for i in range(100)]
        page2 = [FakeEntry("smith", "iron_ore", sell_price=8)]

        def fake_sync(client, page, size):
            if page == 1:
                return FakeResult(page1)
            if page == 2:
                return FakeResult(page2)
            return FakeResult([])

        gd = GameData()
        with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items",
                   side_effect=fake_sync):
            gd._load_npcs(MagicMock())
        # Page-1 and page-2 entries both present -> the page+=1 branch ran.
        assert gd._npc_sell_prices["cook"]["item_0"] == 1
        assert gd._npc_sell_prices["smith"]["iron_ore"] == 8
