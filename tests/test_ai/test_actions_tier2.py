"""Tests for UnequipAction, RecycleAction, NpcBuyAction, and GameData NPC support."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.types import UNSET
from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOT, UnequipAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._monster_locations = {}
    gd._resource_locations = {}
    gd._workshop_locations = kwargs.get("workshop_locs", {})
    gd._bank_location = (4, 0)
    gd._item_stats = kwargs.get("item_stats", {})
    gd._crafting_recipes = kwargs.get("recipes", {})
    gd._resource_skill = {}
    gd._monster_level = {}
    gd._npc_locations = kwargs.get("npc_locations", {})
    gd._npc_stock = kwargs.get("npc_stock", {})
    return gd


def make_full_equipment() -> dict[str, str | None]:
    return {slot: None for slot in ITEM_TYPE_TO_SLOT.values()}


class TestUnequipAction:
    def test_repr(self):
        assert repr(UnequipAction(slot="weapon_slot")) == "Unequip(weapon_slot)"

    def test_not_applicable_when_slot_empty(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        state = make_state(equipment=equipment)
        assert action.is_applicable(state, make_gd()) is False

    def test_applicable_when_slot_occupied(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        equipment["weapon_slot"] = "copper_dagger"
        state = make_state(equipment=equipment)
        assert action.is_applicable(state, make_gd()) is True

    def test_apply_returns_item_to_inventory(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        equipment["weapon_slot"] = "copper_dagger"
        state = make_state(equipment=equipment, inventory={})
        new_state = action.apply(state, make_gd())
        assert new_state.inventory.get("copper_dagger") == 1
        assert new_state.equipment["weapon_slot"] is None

    def test_apply_accumulates_with_existing_inventory(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        equipment["weapon_slot"] = "copper_dagger"
        state = make_state(equipment=equipment, inventory={"copper_dagger": 1})
        new_state = action.apply(state, make_gd())
        assert new_state.inventory["copper_dagger"] == 2

    def test_cost_is_1(self):
        action = UnequipAction(slot="weapon_slot")
        assert action.cost(make_state(), make_gd()) == pytest.approx(1.0)

    def test_execute_calls_api(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        equipment["weapon_slot"] = "copper_dagger"
        char = make_char_schema()
        state = make_state(equipment=equipment)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.equipment.action_unequip", return_value=make_api_result(char)) as mock_api:
            action.execute(state, client)
        mock_api.assert_called_once()


class TestRecycleAction:
    def test_repr(self):
        assert repr(RecycleAction(code="copper_dagger", quantity=2)) == "Recycle(copper_dagger×2)"

    def test_not_applicable_without_workshop(self):
        action = RecycleAction(code="copper_dagger", workshop_location=None)
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon", crafting_skill="weaponcrafting")
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_item_not_in_inventory(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon", crafting_skill="weaponcrafting")
        state = make_state(inventory={})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_without_recipe(self):
        action = RecycleAction(code="wooden_stick", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="wooden_stick", level=1, type_="weapon")
        state = make_state(inventory={"wooden_stick": 1})
        gd = make_gd(item_stats={"wooden_stick": stats}, recipes={})
        assert action.is_applicable(state, gd) is False

    def test_applicable_when_in_inventory_with_recipe(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon", crafting_skill="weaponcrafting")
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is True

    def test_apply_removes_item_and_returns_materials(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        new_state = action.apply(state, gd)
        assert "copper_dagger" not in new_state.inventory
        # 6 // 2 = 3 copper_ore returned
        assert new_state.inventory.get("copper_ore", 0) == 3

    def test_apply_minimum_one_material_returned(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1})
        # Recipe with qty=1: max(1, 1//2) = 1
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 1}})
        new_state = action.apply(state, gd)
        assert new_state.inventory.get("copper_ore", 0) == 1

    def test_cost_includes_distance(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        state = make_state(x=0, y=0)
        gd = make_gd()
        assert action.cost(state, gd) == pytest.approx(3.0 + 5)

    def test_execute_moves_to_workshop_then_recycles(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        char = make_char_schema()
        state = make_state(x=0, y=0, inventory={"copper_dagger": 1})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.recycle.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=5, y=0, inventory={"copper_dagger": 1})
            with patch("artifactsmmo_cli.ai.actions.recycle.action_recycling", return_value=make_api_result(char)) as mock_recycle:
                action.execute(state, client)
        MockMove.assert_called_once_with(x=5, y=0)
        mock_recycle.assert_called_once()


class TestNpcBuyAction:
    def test_repr(self):
        assert repr(NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=3)) == \
            "NpcBuy(cooked_chicken×3@cook)"

    def test_not_applicable_without_npc_location(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=None)
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 10}})
        state = make_state(gold=100)
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_npc_does_not_sell_item(self):
        action = NpcBuyAction(npc_code="cook", item_code="mystery_item", quantity=1, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 10}})
        state = make_state(gold=100)
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_gold(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 50}})
        state = make_state(gold=10)
        assert action.is_applicable(state, gd) is False

    def test_applicable_when_enough_gold(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 10}})
        state = make_state(gold=100)
        assert action.is_applicable(state, gd) is True

    def test_apply_deducts_gold_and_adds_item(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=2, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 10}})
        state = make_state(gold=100, inventory={})
        new_state = action.apply(state, gd)
        assert new_state.gold == 80  # 100 - 2 * 10
        assert new_state.inventory.get("cooked_chicken") == 2

    def test_cost_includes_distance_and_gold(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(4, 0))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 100}})
        state = make_state(x=0, y=0)
        # 2 + dist(4) + 100*1/10 = 2 + 4 + 10 = 16
        assert action.cost(state, gd) == pytest.approx(16.0)

    def test_execute_moves_and_calls_api(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(2, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, gold=100)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.npc.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=2, y=1, gold=100)
            with patch("artifactsmmo_cli.ai.actions.npc.action_npc_buy", return_value=make_api_result(char)) as mock_buy:
                action.execute(state, client)
        MockMove.assert_called_once_with(x=2, y=1)
        mock_buy.assert_called_once()


class TestGameDataNpcSupport:
    def test_npc_location_returns_location(self):
        gd = make_gd(npc_locations={"cook": (2, 1)})
        assert gd.npc_location("cook") == (2, 1)

    def test_npc_location_returns_none_for_unknown(self):
        gd = make_gd()
        assert gd.npc_location("unknown") is None

    def test_npc_sells_item_returns_price(self):
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 42}})
        assert gd.npc_sells_item("cook", "cooked_chicken") == 42

    def test_npc_sells_item_returns_none_when_missing(self):
        gd = make_gd(npc_stock={"cook": {}})
        assert gd.npc_sells_item("cook", "mystery") is None

    def test_npcs_selling_item_sorted_by_price(self):
        gd = make_gd(npc_stock={"cook": {"bread": 20}, "baker": {"bread": 10}})
        result = gd.npcs_selling_item("bread")
        assert result == [("baker", 10), ("cook", 20)]

    def test_npcs_selling_item_empty_when_none_sell(self):
        gd = make_gd(npc_stock={"cook": {"bread": 10}})
        assert gd.npcs_selling_item("mystery") == []

    def test_load_npcs_indexes_stock(self):
        gd = GameData()
        entry = MagicMock()
        entry.code = "cooked_chicken"
        entry.npc = "cook"
        entry.buy_price = 10

        with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items", return_value=MagicMock(data=[entry])):
            gd._load_npcs(MagicMock())

        assert gd._npc_stock["cook"]["cooked_chicken"] == 10

    def test_load_npcs_skips_null_buy_price(self):
        gd = GameData()
        entry = MagicMock()
        entry.code = "mystery_item"
        entry.npc = "cook"
        entry.buy_price = UNSET

        with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items", return_value=MagicMock(data=[entry])):
            gd._load_npcs(MagicMock())

        assert "cook" not in gd._npc_stock

    def test_load_maps_indexes_npc_location(self):
        gd = GameData()
        tile = MagicMock()
        tile.x = 2
        tile.y = 1
        tile.interactions.content.type_ = MapContentType.NPC
        tile.interactions.content.code = "cook"

        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=MagicMock(data=[tile])):
            gd._load_maps(MagicMock())

        assert gd._npc_locations["cook"] == (2, 1)
