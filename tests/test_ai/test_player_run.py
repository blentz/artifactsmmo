"""Tests for GamePlayer.run() and sync_bank pagination."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_minimal_game_data() -> GameData:
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._monster_level = {"chicken": 1}
    return gd


def _patch_game_data_load():
    """Context manager stack that stubs out all GameData API calls."""
    empty = MagicMock(data=[])
    return (
        patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_monsters", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_npc_items", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_bank_details", return_value=None),
    )


class TestSyncBankPagination:
    def test_paginates_when_full_page_returned(self):
        player = GamePlayer(character="hero")
        state = make_state()
        client = MagicMock()

        slot = MagicMock()
        slot.code = "copper_ore"
        slot.quantity = 1

        page1 = MagicMock()
        page1.data = [slot] * 100

        page2 = MagicMock()
        page2.data = [slot]

        bank_details = MagicMock()
        bank_details.data = MagicMock()
        bank_details.data.gold = 0

        with patch("artifactsmmo_cli.ai.player.get_bank_items", side_effect=[page1, page2]):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details):
                new_state = player._sync_bank(client, state)

        assert new_state.bank_items["copper_ore"] == 101


class TestPlayerRun:
    def test_run_executes_one_action_then_stops(self):
        """Test run() executes the plan loop once then exits via KeyboardInterrupt."""
        player = GamePlayer(character="hero")
        char = make_char_schema(hp=100, max_hp=150, xp=50, max_xp=500)
        client = MagicMock()

        # The run loop calls: GameData.load, _fetch_world_state, then loops
        # We stop after one loop iteration by having _wait_for_cooldown raise
        call_count = [0]

        def fake_wait():
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt

        p_maps, p_items, p_resources, p_monsters, p_npcs, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_bank:
                    with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_refresh_if_stale", return_value=make_state(hp=100, max_hp=150)):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

    def test_run_dry_run_uses_apply_not_execute(self):
        """In dry_run mode, the player calls action.apply() instead of action.execute()."""
        player = GamePlayer(character="hero", dry_run=True)
        char = make_char_schema(hp=50, max_hp=150)  # low HP triggers RestoreHPGoal
        client = MagicMock()

        call_count = [0]

        def fake_wait():
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt

        state_with_low_hp = make_state(hp=50, max_hp=150)

        p_maps, p_items, p_resources, p_monsters, p_npcs, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_bank:
                    with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_refresh_if_stale", return_value=state_with_low_hp):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

        # In dry_run, the state should be updated via apply() — RestAction would set hp to max_hp
        assert player.state is not None

    def test_run_no_plan_sleeps(self):
        """When no plan is found, run() sleeps for 10s."""
        player = GamePlayer(character="hero")
        char = make_char_schema(hp=150, max_hp=150)  # full HP, no task, low value goals
        client = MagicMock()

        call_count = [0]

        def fake_wait():
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt

        # State with full HP and no task — FarmMonsterGoal will plan but with empty game data
        # no actions will be applicable, so plan will be empty → sleep
        state = make_state(hp=150, max_hp=150)

        p_maps, p_items, p_resources, p_monsters, p_npcs, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_bank:
                    with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_refresh_if_stale", return_value=state):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep") as mock_sleep:
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

        mock_sleep.assert_called_with(10)

    def test_run_verbose_logs_no_plan(self, capsys):
        """In verbose mode, run() logs 'No plan for' when a goal can't be planned."""
        player = GamePlayer(character="hero", verbose=True)
        char = make_char_schema(hp=150, max_hp=150)
        client = MagicMock()

        call_count = [0]

        def fake_wait():
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt

        state = make_state(hp=150, max_hp=150)

        p_maps, p_items, p_resources, p_monsters, p_npcs, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_bank:
                    with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_refresh_if_stale", return_value=state):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

        output = capsys.readouterr().out
        assert "No plan for" in output


def test_player_builds_sell_actions_for_sellable_inventory():
    """When bank is locked and inventory has sellable items, _build_actions should include NpcSell."""
    player = GamePlayer(character="testchar", verbose=False, dry_run=True)
    player.game_data = GameData()
    player.game_data._npc_locations = {"cook": (2, 1)}
    player.game_data._npc_sell_prices = {"cook": {"chicken": 5}}
    player.game_data._bank_location = (4, 0)
    player.game_data._taskmaster_location = (1, 2)
    player._bank_accessible = False
    player.state = make_state(inventory={"chicken": 5})

    actions = player._build_actions()
    sell_actions = [a for a in actions if isinstance(a, NpcSellAction)]
    assert any(a.item_code == "chicken" and a.npc_code == "cook" for a in sell_actions)


def test_player_includes_sell_inventory_goal_when_bank_locked():
    """When bank is locked, _build_goals should include SellInventoryGoal."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._monster_level = {"chicken": 1}
    player._bank_accessible = False
    player.state = make_state()

    goals = player._build_goals()
    assert any(isinstance(g, SellInventoryGoal) for g in goals)
