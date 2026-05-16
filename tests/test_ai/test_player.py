"""Tests for GamePlayer."""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

import pytest

from artifactsmmo_api_client.models.achievement_type import AchievementType
from artifactsmmo_api_client.types import UNSET

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.farm_items import FarmItemsGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.survival import RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.player import GamePlayer, _format_plan
from artifactsmmo_cli.ai.recovery import StuckSignal
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_game_data_mock() -> GameData:
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)], "cow": [(2, 0)]}
    gd._resource_locations = {"copper": [(3, 0)]}
    gd._workshop_locations = {"weaponcrafting": (5, 0)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._monster_level = {"chicken": 1, "cow": 2}
    return gd


class TestGamePlayerInit:
    def test_default_flags(self):
        player = GamePlayer(character="hero")
        assert player.character == "hero"
        assert player.verbose is False
        assert player.dry_run is False

    def test_verbose_and_dry_run(self):
        player = GamePlayer(character="hero", verbose=True, dry_run=True)
        assert player.verbose is True
        assert player.dry_run is True


class TestBuildActions:
    def test_includes_rest_and_deposit(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        actions = player._build_actions()
        from artifactsmmo_cli.ai.actions.rest import RestAction
        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        assert any(isinstance(a, RestAction) for a in actions)
        assert any(isinstance(a, DepositAllAction) for a in actions)

    def test_includes_fight_actions_for_all_monsters(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        actions = player._build_actions()
        from artifactsmmo_cli.ai.actions.combat import FightAction
        monster_codes = {a.monster_code for a in actions if isinstance(a, FightAction)}
        assert "chicken" in monster_codes
        assert "cow" in monster_codes

    def test_fight_actions_carry_locations(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        actions = player._build_actions()
        from artifactsmmo_cli.ai.actions.combat import FightAction
        fight_locs = {a.monster_code: a.locations for a in actions if isinstance(a, FightAction)}
        assert "chicken" in fight_locs
        assert (1, 0) in fight_locs["chicken"]


class TestBuildGoals:
    def test_returns_base_goals(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        player.state = make_state(level=3)
        goals = player._build_goals()
        # RestoreHP, DepositInventory, CompleteTask, AcceptTask, TaskExchange, FarmMonster, UpgradeEquipment
        assert len(goals) >= 7

    def test_farm_target_respects_character_level(self):
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)], "dragon": [(10, 0)]}
        gd._monster_level = {"chicken": 1, "dragon": 100}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._item_stats = {}
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        player.game_data = gd
        player.state = make_state(level=5)
        goals = player._build_goals()
        from artifactsmmo_cli.ai.goals.combat import FarmMonsterGoal
        farm_goals = [g for g in goals if isinstance(g, FarmMonsterGoal)]
        assert len(farm_goals) == 1
        assert farm_goals[0].monster_code != "dragon"

    def test_adds_gather_goal_when_upgrade_needs_materials(self):
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._item_stats = {
            "copper_dagger": ItemStats(
                code="copper_dagger", level=1, type_="weapon",
                crafting_skill="weaponcrafting", crafting_level=1,
            )
        }
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        gd._resource_skill = {}
        player.game_data = gd
        # Skilled enough to craft but no materials
        player.state = make_state(level=5, skills={"weaponcrafting": 1},
                                  inventory={}, bank_items={})
        goals = player._build_goals()
        gather_goals = [g for g in goals if isinstance(g, GatherMaterialsGoal)]
        assert len(gather_goals) == 1
        assert gather_goals[0]._target_item == "copper_dagger"
        assert gather_goals[0]._needed == {"copper_ore": 6}

    def test_no_gather_goal_when_materials_available(self):
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._item_stats = {
            "copper_dagger": ItemStats(
                code="copper_dagger", level=1, type_="weapon",
                crafting_skill="weaponcrafting", crafting_level=1,
            )
        }
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        gd._resource_skill = {}
        player.game_data = gd
        # Materials already in bank — no gather needed
        player.state = make_state(level=5, skills={"weaponcrafting": 1},
                                  inventory={}, bank_items={"copper_ore": 6})
        goals = player._build_goals()
        gather_goals = [g for g in goals if isinstance(g, GatherMaterialsGoal)]
        assert len(gather_goals) == 0

    def test_gather_goal_uses_full_recipe_qty_not_remaining(self):
        """Regression: GatherMaterials must use the full recipe quantity so it aligns
        with UpgradeEquipment's material check (both threshold on inventory+bank >= recipe_qty).
        Using remaining=(recipe-already_have) caused GatherMaterials to satisfy early when
        DepositAll moved existing items to bank during gathering."""
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._item_stats = {
            "copper_dagger": ItemStats(
                code="copper_dagger", level=1, type_="weapon",
                crafting_skill="weaponcrafting", crafting_level=1,
            )
        }
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
        gd._resource_skill = {}
        player.game_data = gd
        # Partial materials in bank: old code would set needed=4, new code must use 6
        player.state = make_state(level=5, skills={"weaponcrafting": 1},
                                  inventory={}, bank_items={"copper_ore": 2})
        goals = player._build_goals()
        gather_goals = [g for g in goals if isinstance(g, GatherMaterialsGoal)]
        assert len(gather_goals) == 1
        # Must be the full recipe quantity — not (6 - 2 = 4)
        assert gather_goals[0]._needed == {"copper_ore": 6}


class TestWaitForCooldown:
    def test_no_wait_when_state_is_none(self):
        player = GamePlayer(character="hero")
        player.state = None
        player._wait_for_cooldown()  # should not raise or sleep

    def test_no_wait_when_cooldown_none(self):
        player = GamePlayer(character="hero")
        player.state = make_state(cooldown_expires=None)
        player._wait_for_cooldown()

    def test_sleeps_for_remaining_cooldown(self):
        player = GamePlayer(character="hero")
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=2.5)
        player.state = make_state(cooldown_expires=future)
        with patch("artifactsmmo_cli.ai.player.time.sleep") as mock_sleep:
            player._wait_for_cooldown()
            mock_sleep.assert_called_once()
            sleep_arg = mock_sleep.call_args[0][0]
            assert 2.0 < sleep_arg < 3.5

    def test_logs_cooldown_duration(self):
        player = GamePlayer(character="hero")
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=3.0)
        player.state = make_state(cooldown_expires=future)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("artifactsmmo_cli.ai.player.time.sleep"):
            with redirect_stdout(buf):
                player._wait_for_cooldown()
        assert "Cooldown:" in buf.getvalue()

    def test_no_sleep_when_cooldown_expired(self):
        player = GamePlayer(character="hero")
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=5)
        player.state = make_state(cooldown_expires=past)
        with patch("artifactsmmo_cli.ai.player.time.sleep") as mock_sleep:
            player._wait_for_cooldown()
            mock_sleep.assert_not_called()


class TestMaybePeriodicRefresh:
    def test_does_not_refresh_below_threshold(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player._actions_since_full_refresh = 19
        refresh_calls = []
        player._full_refresh = lambda c: refresh_calls.append(True)  # type: ignore
        player._maybe_periodic_refresh(client=None)
        assert refresh_calls == []

    def test_refreshes_at_threshold(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player._actions_since_full_refresh = 20
        refresh_calls = []

        def fake_full_refresh(c):
            refresh_calls.append(True)
            player._actions_since_full_refresh = 0

        player._full_refresh = fake_full_refresh  # type: ignore
        player._maybe_periodic_refresh(client=None)
        assert refresh_calls == [True]


class TestFetchWorldState:
    def test_returns_world_state(self):
        player = GamePlayer(character="hero")
        player.state = None
        char = make_char_schema()
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
            state = player._fetch_world_state(client)
        assert isinstance(state, WorldState)

    def test_preserves_bank_state_from_current_state(self):
        player = GamePlayer(character="hero")
        player.state = make_state(bank_items={"gold": 100}, bank_gold=50)
        char = make_char_schema()
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
            state = player._fetch_world_state(client)
        assert state.bank_items == {"gold": 100}

    def test_raises_on_none_response(self):
        player = GamePlayer(character="hero")
        player.state = None
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=None):
            with pytest.raises(RuntimeError):
                player._fetch_world_state(client)


class TestSyncBank:
    def test_syncs_bank_items_and_gold(self):
        player = GamePlayer(character="hero")
        state = make_state()
        client = MagicMock()

        bank_slot = MagicMock()
        bank_slot.code = "copper_ore"
        bank_slot.quantity = 10

        bank_items_result = MagicMock()
        bank_items_result.data = [bank_slot]

        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 200

        with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=bank_items_result):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details_result):
                new_state = player._sync_bank(client, state)

        assert new_state.bank_items == {"copper_ore": 10}
        assert new_state.bank_gold == 200

    def test_empty_bank(self):
        player = GamePlayer(character="hero")
        state = make_state()
        client = MagicMock()

        empty_result = MagicMock()
        empty_result.data = []

        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 0

        with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=empty_result):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details_result):
                new_state = player._sync_bank(client, state)

        assert new_state.bank_items == {}


class TestExecute:
    def test_execute_success_updates_state(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=0, y=0)
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=3, y=5)
        char = make_char_schema(x=3, y=5)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(char)):
            new_state = player._execute(action, client)

        assert new_state.x == 3

    def test_execute_api_error_refreshes_state(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=3, y=5)
        char = make_char_schema()

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", side_effect=RuntimeError("fail")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                new_state = player._execute(action, client)

        assert isinstance(new_state, WorldState)

    def test_execute_http_499_logs_server_cooldown(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=3, y=5)
        char = make_char_schema()

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            with patch("artifactsmmo_cli.ai.actions.movement.action_move", side_effect=RuntimeError("HTTP 499: Character in cooldown")):
                with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                    new_state = player._execute(action, client)

        assert isinstance(new_state, WorldState)
        assert "Server cooldown (HTTP 499)" in buf.getvalue()

    def test_execute_bank_action_syncs_bank(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 5})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0))
        char = make_char_schema()
        bank_slot = MagicMock()
        bank_slot.code = "copper_ore"
        bank_slot.quantity = 5
        bank_result = MagicMock()
        bank_result.data = [bank_slot]
        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 0

        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item", return_value=make_api_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=bank_result):
                with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details_result):
                    new_state = player._execute(action, client)

        assert new_state.bank_items is not None


class TestNow:
    def test_returns_time_string(self):
        result = GamePlayer._now()
        assert len(result) == 8
        assert result[2] == ":"


class TestFormatPlan:
    def test_empty_plan(self):
        assert _format_plan([]) == ""

    def test_single_action(self):
        from artifactsmmo_cli.ai.actions.rest import RestAction
        assert _format_plan([RestAction()]) == "Rest"

    def test_consecutive_repeats_collapsed(self):
        from artifactsmmo_cli.ai.actions.gathering import GatherAction
        actions = [GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))] * 3
        assert _format_plan(actions) == "Gather(copper_rocks)×3"

    def test_mixed_plan_collapsed(self):
        from artifactsmmo_cli.ai.actions.gathering import GatherAction
        from artifactsmmo_cli.ai.actions.crafting import CraftAction
        gathers = [GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))] * 80
        crafts = [CraftAction(code="copper_bar", quantity=1, workshop_location=(1, 5))] * 8
        result = _format_plan(gathers + crafts)
        assert "×80" in result
        assert "×8" in result
        assert "…" not in result  # only 2 distinct segments — no truncation needed

    def test_truncates_after_five_segments(self):
        from artifactsmmo_cli.ai.actions.rest import RestAction
        from artifactsmmo_cli.ai.actions.movement import MoveAction
        plan = [RestAction(), MoveAction(1, 0), MoveAction(2, 0), MoveAction(3, 0),
                MoveAction(4, 0), MoveAction(5, 0), RestAction()]
        result = _format_plan(plan)
        assert "…" in result


class TestBuildGoalsTier1:
    def _make_player_with_gd(self, extra_stats=None, extra_recipes=None) -> GamePlayer:
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = extra_stats or {}
        gd._crafting_recipes = extra_recipes or {}
        gd._resource_skill = {}
        player.game_data = gd
        return player

    def test_farm_items_goal_added_for_items_task(self):
        player = self._make_player_with_gd()
        player.state = make_state(task_type="items", task_code="ash_wood", task_total=5, task_progress=0)
        goals = player._build_goals()
        farm_goals = [g for g in goals if isinstance(g, FarmItemsGoal)]
        assert len(farm_goals) == 1

    def test_farm_items_goal_not_added_for_monsters_task(self):
        player = self._make_player_with_gd()
        player.state = make_state(task_type="monsters", task_code="chicken", task_total=10, task_progress=0)
        goals = player._build_goals()
        farm_goals = [g for g in goals if isinstance(g, FarmItemsGoal)]
        assert len(farm_goals) == 0

    def test_farm_items_goal_not_added_when_no_task(self):
        player = self._make_player_with_gd()
        player.state = make_state(task_code="", task_total=0, task_progress=0)
        goals = player._build_goals()
        farm_goals = [g for g in goals if isinstance(g, FarmItemsGoal)]
        assert len(farm_goals) == 0

    def test_task_exchange_goal_always_in_goals(self):
        player = self._make_player_with_gd()
        player.state = make_state()
        goals = player._build_goals()
        exchange_goals = [g for g in goals if isinstance(g, TaskExchangeGoal)]
        assert len(exchange_goals) == 1

    def test_build_actions_includes_task_exchange(self):
        player = self._make_player_with_gd()
        player.state = make_state()
        from artifactsmmo_cli.ai.actions.task import TaskExchangeAction
        actions = player._build_actions()
        exchange_actions = [a for a in actions if isinstance(a, TaskExchangeAction)]
        assert len(exchange_actions) == 1

    def test_build_actions_adds_withdraw_for_equippable_craftable_items(self):
        """Regression: crafted items deposited to bank must be withdrawable for equipping."""
        weapon_stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=1)
        player = self._make_player_with_gd(
            extra_stats={"copper_dagger": weapon_stats},
            extra_recipes={"copper_dagger": {"copper_ore": 2}},
        )
        player.state = make_state(skills={"weaponcrafting": 1})
        from artifactsmmo_cli.ai.actions.bank import WithdrawItemAction
        actions = player._build_actions()
        withdraw_codes = {a.code for a in actions if isinstance(a, WithdrawItemAction)}
        assert "copper_dagger" in withdraw_codes

    def test_build_actions_multi_slot_ring_creates_two_equip(self):
        ring_stats = ItemStats(code="copper_ring", level=1, type_="ring",
                               crafting_skill="jewelrycrafting", crafting_level=1)
        player = self._make_player_with_gd(
            extra_stats={"copper_ring": ring_stats},
            extra_recipes={"copper_ring": {"copper_ore": 2}},
        )
        player.state = make_state(skills={"jewelrycrafting": 1})
        from artifactsmmo_cli.ai.actions.equipment import EquipAction
        actions = player._build_actions()
        equip_actions = [a for a in actions if isinstance(a, EquipAction) and a.code == "copper_ring"]
        slots = {a.slot for a in equip_actions}
        assert "ring1_slot" in slots
        assert "ring2_slot" in slots


class TestLogAction:
    def test_log_with_single_action(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        from artifactsmmo_cli.ai.actions.rest import RestAction
        from artifactsmmo_cli.ai.goals.survival import RestoreHPGoal
        action = RestAction()
        goal = RestoreHPGoal()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            player._log_action(action, goal, [action])
        assert "Rest" in buf.getvalue()


def test_sync_pending_iterates_items_list(monkeypatch):
    """_sync_pending should produce (pending_id, item_code) pairs from PendingItemSchema.items."""

    class FakeItem:
        def __init__(self, code, quantity=1):
            self.code = code
            self.quantity = quantity

    class FakePending:
        def __init__(self, id_, items):
            self.id = id_
            self.items = items

    class FakeResult:
        def __init__(self, data):
            self.data = data

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.player.get_pending_items",
        lambda client: FakeResult([
            FakePending("p1", [FakeItem("diamond"), FakeItem("ruby")]),
            FakePending("p2", [FakeItem("emerald")]),
        ]),
    )

    player = GamePlayer(character="testchar")
    player.state = make_state()
    new_state = player._sync_pending(client=None, state=player.state)
    assert new_state.pending_items is not None
    assert ("p1", "diamond") in new_state.pending_items
    assert ("p1", "ruby") in new_state.pending_items
    assert ("p2", "emerald") in new_state.pending_items
    assert len(new_state.pending_items) == 3


def test_sync_pending_handles_unset_items_list(monkeypatch):
    """PendingItemSchema.items can be Unset — _sync_pending should skip such entries."""

    class FakeItem:
        def __init__(self, code):
            self.code = code

    class FakePending:
        def __init__(self, id_, items):
            self.id = id_
            self.items = items

    class FakeResult:
        def __init__(self, data):
            self.data = data

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.player.get_pending_items",
        lambda client: FakeResult([
            FakePending("p1", UNSET),
            FakePending("p2", [FakeItem("diamond")]),
        ]),
    )

    player = GamePlayer(character="testchar")
    player.state = make_state()
    new_state = player._sync_pending(client=None, state=player.state)
    assert new_state.pending_items == (("p2", "diamond"),)


class TestExecuteHttp496BankLock:
    """Tests for HTTP 496 bank-lock path in _execute."""

    def test_http496_on_deposit_sets_bank_inaccessible(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 5})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0))
        char = make_char_schema()

        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item",
                   side_effect=RuntimeError("HTTP 496 (locked bank_deposit achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=None):
                    player._execute(action, client)

        assert player._bank_accessible is False
        assert player._bank_blocked_since is not None

    def test_http496_without_achievement_code_leaves_unlock_monster_none(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0))
        char = make_char_schema()

        # No achievement code in error message — no match for the regex
        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item",
                   side_effect=RuntimeError("HTTP 496 bank access denied")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                player._execute(action, client)

        assert player._bank_accessible is False
        assert player._bank_unlock_monster is None

    def test_http496_does_not_mark_inaccessible_for_non_bank_action(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=1, y=0)
        char = make_char_schema()

        # HTTP 496 on a non-bank action — bank_accessible must NOT be changed
        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   side_effect=RuntimeError("HTTP 496 some unrelated error")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                player._execute(action, client)

        assert player._bank_accessible is True  # unchanged

    def test_http496_with_achievement_code_calls_resolve(self):
        """When achievement code is in the 496 error, _resolve_bank_unlock_monster is called."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0))
        char = make_char_schema()

        resolve_calls = []

        def fake_resolve(c, code):
            resolve_calls.append(code)
            return "skeleton"

        player._resolve_bank_unlock_monster = fake_resolve  # type: ignore

        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item",
                   side_effect=RuntimeError("HTTP 496 (myach achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                player._execute(action, client)

        assert resolve_calls == ["myach"]
        assert player._bank_unlock_monster == "skeleton"

    def test_http496_skips_resolve_when_monster_already_set(self):
        """Once bank_unlock_monster is set, _resolve_bank_unlock_monster is not called again."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        player._bank_unlock_monster = "chicken"  # already resolved
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0))
        char = make_char_schema()

        resolve_calls = []

        def fake_resolve(c, code):
            resolve_calls.append(code)
            return "wolf"

        player._resolve_bank_unlock_monster = fake_resolve  # type: ignore

        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item",
                   side_effect=RuntimeError("HTTP 496 (newach achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                player._execute(action, client)

        # resolve should NOT be called since monster is already set
        assert resolve_calls == []
        assert player._bank_unlock_monster == "chicken"


class TestExecuteClaimPendingSync:
    """Test that ClaimPendingItemAction triggers _sync_pending in _execute."""

    def test_execute_claim_pending_calls_sync_pending(self):
        from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
        player = GamePlayer(character="hero")
        player.state = make_state(pending_items=(("id1", "copper_ore"),))
        player.game_data = make_game_data_mock()
        client = MagicMock()

        char = make_char_schema()
        pending_item = MagicMock()
        pending_item.id = "id1"
        pending_item.code = "copper_ore"
        pending_result = MagicMock()
        pending_result.data = [pending_item]
        final_pending = MagicMock()
        final_pending.data = []

        sync_calls = []
        original_sync = player._sync_pending

        def fake_sync(c, s):
            sync_calls.append(True)
            return s

        player._sync_pending = fake_sync  # type: ignore

        with patch("artifactsmmo_cli.ai.actions.claim.get_pending_items", return_value=pending_result):
            with patch("artifactsmmo_cli.ai.actions.claim.action_claim_item", return_value=make_api_result(char)):
                player._execute(ClaimPendingItemAction(), client)

        assert sync_calls == [True]


class TestResolveBankUnlockMonster:
    """Tests for _resolve_bank_unlock_monster."""

    def test_returns_none_when_api_returns_none(self):
        player = GamePlayer(character="hero")
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=None):
            result = player._resolve_bank_unlock_monster(client, "some_achievement")
        assert result is None

    def test_returns_combat_kill_target(self):
        player = GamePlayer(character="hero")
        client = MagicMock()

        obj = MagicMock()
        obj.type_ = AchievementType.COMBAT_KILL
        obj.target = "skeleton"

        result_obj = MagicMock()
        result_obj.data = MagicMock()
        result_obj.data.objectives = [obj]

        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=result_obj):
            result = player._resolve_bank_unlock_monster(client, "some_achievement")

        assert result == "skeleton"

    def test_returns_none_when_no_combat_kill_objective(self):
        player = GamePlayer(character="hero")
        client = MagicMock()

        obj = MagicMock()
        obj.type_ = MagicMock()  # some other achievement type, not COMBAT_KILL
        obj.type_ = "craft"  # not AchievementType.COMBAT_KILL
        obj.target = "some_item"

        result_obj = MagicMock()
        result_obj.data = MagicMock()
        result_obj.data.objectives = [obj]

        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=result_obj):
            result = player._resolve_bank_unlock_monster(client, "some_achievement")

        assert result is None

    def test_returns_none_when_result_has_no_data(self):
        player = GamePlayer(character="hero")
        client = MagicMock()

        result_obj = MagicMock()
        result_obj.data = None

        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=result_obj):
            result = player._resolve_bank_unlock_monster(client, "some_achievement")

        assert result is None


class TestEmitTrace:
    """Tests for _emit_trace."""

    def test_returns_early_when_state_is_none(self):
        player = GamePlayer(character="hero")
        player.state = None
        tracer = MagicMock()
        player.tracer = tracer
        # Should not raise and should not call tracer.write_cycle
        player._emit_trace("Rest", "RestoreHP", "ok", {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1})
        tracer.write_cycle.assert_not_called()

    def test_computes_cooldown_remaining_when_cooldown_set(self):
        from datetime import datetime, timezone, timedelta
        player = GamePlayer(character="hero")
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=5.0)
        player.state = make_state(cooldown_expires=future)
        tracer = MagicMock()
        player.tracer = tracer
        player._emit_trace("Rest", "RestoreHP", "ok", {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1})
        tracer.write_cycle.assert_called_once()
        record = tracer.write_cycle.call_args[0][0]
        assert record["cooldown_remaining_at_cycle_start"] > 0.0


class TestHandleStuckExtended:
    """Tests for additional _handle_stuck escalation levels."""

    def test_state_frozen_level3_broadens_suppression(self):
        player = GamePlayer(character="hero")
        player._recovery_level[StuckSignal.STATE_FROZEN] = 2
        player._suppressed_goals = {"GoalA": 3}

        player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)

        # Should broaden GoalA from 3 to max(3, 10) = 10
        assert player._suppressed_goals["GoalA"] == 10
        assert player._recovery_level[StuckSignal.STATE_FROZEN] == 3

    def test_goal_oscillation_level2_suppresses_for_15_cycles(self):
        player = GamePlayer(character="hero")
        from artifactsmmo_cli.ai.recovery import CycleRecord
        for i in range(8):
            name = "GoalA" if i % 2 == 0 else "GoalB"
            player._detector.record(CycleRecord(
                state_key=(i, 0, 5, (), (), None, 0, False),
                goal_name=name, action_name="X", planned_depth=1,
                planner_timed_out=False, succeeded=True,
            ))
        player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 1

        player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)

        assert player._suppressed_goals.get("GoalA") == 15
        assert player._suppressed_goals.get("GoalB") == 15
        assert player._recovery_level[StuckSignal.GOAL_OSCILLATION] == 2

    def test_no_progress_level2_sets_wildcard_mode(self):
        player = GamePlayer(character="hero")
        player._recovery_level[StuckSignal.NO_PROGRESS] = 1

        player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)

        assert player._wildcard_mode is True
        assert player._recovery_level[StuckSignal.NO_PROGRESS] == 2

    def test_no_progress_level3_exits(self):
        player = GamePlayer(character="hero")
        player._recovery_level[StuckSignal.NO_PROGRESS] = 2

        with pytest.raises(SystemExit) as exc_info:
            player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)

        assert exc_info.value.code == 2


class TestBuildGoalsExtended:
    def _make_minimal_player(self) -> GamePlayer:
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = {}
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        player.game_data = gd
        player.state = make_state()
        return player

    def test_wildcard_mode_returns_only_restore_hp(self):
        player = self._make_minimal_player()
        player._wildcard_mode = True
        goals = player._build_goals()
        assert len(goals) == 1
        assert isinstance(goals[0], RestoreHPGoal)
        # wildcard mode is one-shot: should be reset after call
        assert player._wildcard_mode is False

    def test_bank_retry_timer_resets_bank_accessible(self):
        player = self._make_minimal_player()
        player._bank_accessible = False
        # Simulate that the block started more than _BANK_RETRY_SECONDS ago
        player._bank_blocked_since = time.monotonic() - 61.0  # > 60s threshold

        player._build_goals()

        assert player._bank_accessible is True
        assert player._bank_blocked_since is None

    def test_bank_retry_timer_does_not_reset_before_timeout(self):
        player = self._make_minimal_player()
        player._bank_accessible = False
        player._bank_blocked_since = time.monotonic() - 10.0  # only 10s ago

        player._build_goals()

        assert player._bank_accessible is False  # still locked


class TestBuildActionsExtended:
    def test_delete_actions_skip_equipped_items(self):
        """Items in equipment slots must not get delete actions."""
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = {}
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        gd._monster_level = {}
        player.game_data = gd
        player._bank_accessible = False

        equipment = {slot: None for slot in [
            "weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
            "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
            "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
            "utility1_slot", "utility2_slot", "bag_slot", "rune_slot",
        ]}
        equipment["weapon_slot"] = "copper_dagger"
        player.state = make_state(
            inventory={"copper_dagger": 1, "iron_ore": 3},
            equipment=equipment,
        )

        from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
        actions = player._build_actions()
        delete_codes = {a.code for a in actions if isinstance(a, DeleteItemAction)}

        assert "iron_ore" in delete_codes
        assert "copper_dagger" not in delete_codes  # equipped — must be skipped

    def test_npc_buy_actions_include_consumables_only(self):
        """NPC buy actions are only built for items with hp_restore > 0."""
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = {
            "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable", hp_restore=50),
            "raw_iron": ItemStats(code="raw_iron", level=1, type_="resource"),
        }
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        gd._monster_level = {}
        gd._npc_locations = {"cook": (5, 0)}
        gd._npc_stock = {"cook": ["cooked_chicken", "raw_iron"]}
        player.game_data = gd
        player.state = make_state()

        from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
        actions = player._build_actions()
        npc_buy_items = {a.item_code for a in actions if isinstance(a, NpcBuyAction)}

        assert "cooked_chicken" in npc_buy_items
        assert "raw_iron" not in npc_buy_items  # no hp_restore
