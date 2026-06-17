"""Unit tests for TeleportAction (PLAN #6b: fast-travel consumable)."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.teleport import TELEPORT_COST, TeleportAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    return GameData()


def _char_schema(x=0, y=0):
    from artifactsmmo_api_client.types import UNSET
    char = MagicMock()
    char.name = "testchar"
    char.level = 5
    char.xp = 0
    char.max_xp = 500
    char.hp = 100
    char.max_hp = 150
    char.gold = 50
    char.x = x
    char.y = y
    char.inventory_max_items = 20
    char.inventory = UNSET
    char.cooldown_expiration = UNSET
    char.task = ""
    char.task_type = ""
    char.task_progress = 0
    char.task_total = 0
    for slot in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                 "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                 "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                 "utility1_slot", "utility2_slot", "bag_slot", "rune_slot",
                 "mining_level", "woodcutting_level", "fishing_level", "weaponcrafting_level",
                 "gearcrafting_level", "jewelrycrafting_level", "cooking_level", "alchemy_level"]:
        setattr(char, slot, 1 if "_level" in slot else "")
    return char


def _api_result(char):
    result = MagicMock()
    result.data = MagicMock()
    result.data.character = char
    return result


class TestTeleportApplicable:
    def test_applicable_when_holding_potion_and_elsewhere(self):
        action = TeleportAction(item_code="recall_potion", dest_x=0, dest_y=0)
        state = make_state(x=5, y=5, inventory={"recall_potion": 1})
        assert action.is_applicable(state, _gd()) is True

    def test_not_applicable_without_potion(self):
        action = TeleportAction(item_code="recall_potion", dest_x=0, dest_y=0)
        state = make_state(x=5, y=5, inventory={})
        assert action.is_applicable(state, _gd()) is False

    def test_not_applicable_when_already_at_destination(self):
        action = TeleportAction(item_code="recall_potion", dest_x=0, dest_y=0)
        state = make_state(x=0, y=0, inventory={"recall_potion": 1})
        assert action.is_applicable(state, _gd()) is False


class TestTeleportApply:
    def test_warps_and_decrements_keeping_potion(self):
        action = TeleportAction(item_code="recall_potion", dest_x=0, dest_y=0)
        state = make_state(x=5, y=5, inventory={"recall_potion": 2})
        after = action.apply(state, _gd())
        assert (after.x, after.y) == (0, 0)
        assert after.inventory["recall_potion"] == 1
        assert after.cooldown_expires is None

    def test_warps_and_removes_last_potion(self):
        action = TeleportAction(item_code="recall_potion", dest_x=7, dest_y=13)
        state = make_state(x=1, y=1, inventory={"recall_potion": 1, "keep": 3})
        after = action.apply(state, _gd())
        assert (after.x, after.y) == (7, 13)
        assert "recall_potion" not in after.inventory  # consumed the last one
        assert after.inventory["keep"] == 3


class TestTeleportCostAndRepr:
    def test_cost_is_flat_constant(self):
        action = TeleportAction(item_code="recall_potion", dest_x=0, dest_y=0)
        state = make_state(x=20, y=20, inventory={"recall_potion": 1})
        assert action.cost(state, _gd()) == TELEPORT_COST == 20.0

    def test_repr(self):
        assert repr(TeleportAction(item_code="recall_potion", dest_x=0, dest_y=0)) == \
            "Teleport(recall_potion->0,0)"


class TestTeleportExecute:
    def test_calls_use_item_and_returns_server_state(self):
        action = TeleportAction(item_code="recall_potion", dest_x=0, dest_y=0)
        state = make_state(x=5, y=5, inventory={"recall_potion": 1})
        client = MagicMock()
        char = _char_schema(x=0, y=0)
        with patch("artifactsmmo_cli.ai.actions.teleport.action_use_item",
                   return_value=_api_result(char)) as use:
            new_state = action.execute(state, client)
        assert (new_state.x, new_state.y) == (0, 0)
        # used exactly the teleport item, quantity 1.
        body = use.call_args.kwargs["body"]
        assert body.code == "recall_potion" and body.quantity == 1

    def test_raises_on_missing_response(self):
        action = TeleportAction(item_code="recall_potion", dest_x=0, dest_y=0)
        state = make_state(x=5, y=5, inventory={"recall_potion": 1})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.teleport.action_use_item", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestTeleportInFactory:
    def test_factory_builds_teleport_for_resolvable_item(self):
        from artifactsmmo_cli.ai.actions.factory import build_actions
        gd = GameData()
        gd._item_stats = {
            "recall_potion": ItemStats(code="recall_potion", level=1, type_="utility",
                                       teleport_map_id=271),
            "unmapped_potion": ItemStats(code="unmapped_potion", level=1, type_="utility",
                                         teleport_map_id=88888),
            "plain": ItemStats(code="plain", level=1, type_="weapon"),
        }
        gd.world.map_id_to_loc = {271: (0, 0)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 0)
        gd._next_expansion_cost = 1000
        actions = build_actions(gd, make_state(), None, bank_accessible=True,
                                task_exchange_min_coins=1)
        teleports = [a for a in actions if isinstance(a, TeleportAction)]
        # only the resolvable teleport item yields an action.
        assert len(teleports) == 1
        assert teleports[0].item_code == "recall_potion"
        assert (teleports[0].dest_x, teleports[0].dest_y) == (0, 0)
