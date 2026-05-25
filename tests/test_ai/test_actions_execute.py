"""Integration tests for Action.execute() — API client mocked."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.movement_semantic import MoveTo
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state


def make_char_schema(x=0, y=0, hp=100, max_hp=150, xp=0, max_xp=500, level=5, gold=50,
                     task_progress=0, task_total=0):
    """Return a minimal mock CharacterSchema."""
    from artifactsmmo_api_client.types import UNSET
    char = MagicMock()
    char.name = "testchar"
    char.level = level
    char.xp = xp
    char.max_xp = max_xp
    char.hp = hp
    char.max_hp = max_hp
    char.gold = gold
    char.x = x
    char.y = y
    char.inventory_max_items = 20
    char.inventory = UNSET
    char.cooldown_expiration = UNSET
    char.task = ""
    char.task_type = ""
    char.task_progress = task_progress
    char.task_total = task_total
    for slot in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                 "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                 "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                 "utility1_slot", "utility2_slot", "bag_slot", "rune_slot",
                 "mining_level", "woodcutting_level", "fishing_level", "weaponcrafting_level",
                 "gearcrafting_level", "jewelrycrafting_level", "cooking_level", "alchemy_level"]:
        setattr(char, slot, 1 if "_level" in slot else "")
    return char


def make_api_result(char):
    result = MagicMock()
    result.data = MagicMock()
    result.data.character = char
    return result


def make_fight_api_result(char):
    result = MagicMock()
    result.data = MagicMock()
    result.data.characters = [char]
    return result


class TestMoveActionExecute:
    def test_calls_api_and_returns_new_state(self):
        action = MoveAction(x=3, y=5)
        state = make_state(x=0, y=0)
        client = MagicMock()
        char = make_char_schema(x=3, y=5)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(char)):
            new_state = action.execute(state, client)

        assert new_state.x == 3
        assert new_state.y == 5

    def test_raises_on_missing_response(self):
        action = MoveAction(x=3, y=5)
        state = make_state()
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestRestActionExecute:
    def test_calls_api_and_returns_new_state(self):
        action = RestAction()
        state = make_state(hp=50, max_hp=150)
        client = MagicMock()
        char = make_char_schema(hp=150, max_hp=150)

        with patch("artifactsmmo_cli.ai.actions.rest.action_rest", return_value=make_api_result(char)):
            new_state = action.execute(state, client)

        assert new_state.hp == 150

    def test_raises_on_missing_response(self):
        action = RestAction()
        state = make_state()
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.rest.action_rest", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestFightActionExecute:
    def test_calls_api_and_returns_new_state(self):
        # Already at monster location — no move needed
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(x=1, y=0, hp=100, max_hp=150)
        client = MagicMock()
        char = make_char_schema(hp=80, xp=15)

        with patch("artifactsmmo_cli.ai.actions.combat.action_fight", return_value=make_fight_api_result(char)):
            new_state = action.execute(state, client)

        assert new_state.xp == 15

    def test_moves_to_nearest_before_fighting(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(5, 0), (1, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=150)
        client = MagicMock()
        char = make_char_schema(x=1, y=0, hp=80, xp=15)
        move_char = make_char_schema(x=1, y=0)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.combat.action_fight", return_value=make_fight_api_result(char)):
                new_state = action.execute(state, client)

        assert new_state.xp == 15

    def test_raises_on_missing_response(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(x=1, y=0)
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.combat.action_fight", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestGatherActionExecute:
    def test_calls_api_and_returns_new_state(self):
        # Already at resource location — no move needed
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        state = make_state(x=2, y=0)
        client = MagicMock()
        char = make_char_schema()

        with patch("artifactsmmo_cli.ai.actions.gathering.action_gathering", return_value=make_api_result(char)):
            new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_moves_to_nearest_before_gathering(self):
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        state = make_state(x=0, y=0)
        client = MagicMock()
        char = make_char_schema()
        move_char = make_char_schema(x=2, y=0)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.gathering.action_gathering", return_value=make_api_result(char)):
                new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_raises_on_missing_response(self):
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        state = make_state(x=2, y=0)
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.gathering.action_gathering", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestDepositAllActionExecute:
    def test_deposits_each_item_type(self):
        # Already at bank location — no move needed
        action = DepositAllAction(bank_location=(4, 0))
        state = make_state(x=4, y=0, inventory={"copper_ore": 5, "iron_ore": 2})
        client = MagicMock()
        char = make_char_schema()

        with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item", return_value=make_api_result(char)):
            new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_moves_to_bank_before_depositing(self):
        action = DepositAllAction(bank_location=(4, 0))
        state = make_state(x=0, y=0, inventory={"copper_ore": 5})
        client = MagicMock()
        char = make_char_schema()
        move_char = make_char_schema(x=4, y=0)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item", return_value=make_api_result(char)):
                new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_skips_api_when_inventory_empty_in_loop(self):
        action = DepositAllAction(bank_location=(4, 0))
        state = make_state(x=4, y=0, inventory={})
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item") as mock_api:
            action.execute(state, client)
            mock_api.assert_not_called()


class TestWithdrawItemActionExecute:
    def test_calls_api_and_returns_new_state(self):
        # Already at bank location — no move needed
        action = WithdrawItemAction(code="copper_ore", quantity=3, bank_location=(4, 0))
        state = make_state(x=4, y=0, bank_items={"copper_ore": 5})
        client = MagicMock()
        char = make_char_schema()

        with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item", return_value=make_api_result(char)):
            new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_moves_to_bank_before_withdrawing(self):
        action = WithdrawItemAction(code="copper_ore", quantity=3, bank_location=(4, 0))
        state = make_state(x=0, y=0, bank_items={"copper_ore": 5})
        client = MagicMock()
        char = make_char_schema()
        move_char = make_char_schema(x=4, y=0)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item", return_value=make_api_result(char)):
                new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_raises_on_missing_response(self):
        action = WithdrawItemAction(code="copper_ore", quantity=3, bank_location=(4, 0))
        state = make_state(x=4, y=0, bank_items={"copper_ore": 5})
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestCraftActionExecute:
    def test_calls_api_and_returns_new_state(self):
        # Already at workshop — no move needed
        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0))
        state = make_state(x=3, y=0)
        client = MagicMock()
        char = make_char_schema()

        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=make_api_result(char)):
            new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_moves_to_workshop_before_crafting(self):
        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0))
        state = make_state(x=0, y=0)
        client = MagicMock()
        char = make_char_schema()
        move_char = make_char_schema(x=3, y=0)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=make_api_result(char)):
                new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_raises_on_missing_response(self):
        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0))
        state = make_state(x=3, y=0)
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestEquipActionExecute:
    def test_calls_api_and_returns_new_state(self):
        action = EquipAction(code="copper_dagger", slot="weapon_slot")
        state = make_state(inventory={"copper_dagger": 1}, level=5)
        client = MagicMock()
        char = make_char_schema()

        with patch("artifactsmmo_cli.ai.actions.equip.action_equip", return_value=make_api_result(char)):
            new_state = action.execute(state, client)

        assert isinstance(new_state, WorldState)

    def test_raises_on_missing_response(self):
        action = EquipAction(code="copper_dagger", slot="weapon_slot")
        state = make_state()
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.equip.action_equip", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestAcceptTaskActionExecute:
    def test_moves_then_accepts_and_returns_task_from_server(self):
        action = AcceptTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=0, y=0, task_code=None, task_total=0)
        client = MagicMock()
        # Server hands back a fresh items task.
        char = make_char_schema(x=1, y=2, task_progress=0, task_total=6)
        char.task = "copper_ore"
        char.task_type = "items"
        move_char = make_char_schema(x=1, y=2)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.accept_task.action_task_new",
                       return_value=make_api_result(char)) as mock_new:
                new_state = action.execute(state, client)

        mock_new.assert_called_once()
        assert new_state.task_code == "copper_ore"
        assert new_state.task_type == "items"
        assert new_state.task_total == 6

    def test_skips_move_when_already_at_taskmaster(self):
        action = AcceptTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=1, y=2, task_code=None, task_total=0)
        client = MagicMock()
        char = make_char_schema(x=1, y=2, task_total=6)
        char.task = "copper_ore"
        char.task_type = "items"

        with patch("artifactsmmo_cli.ai.actions.movement.action_move") as mock_move:
            with patch("artifactsmmo_cli.ai.actions.accept_task.action_task_new",
                       return_value=make_api_result(char)):
                new_state = action.execute(state, client)

        mock_move.assert_not_called()
        assert new_state.task_code == "copper_ore"

    def test_raises_on_missing_response(self):
        action = AcceptTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=1, y=2)
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.accept_task.action_task_new",
                   return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestCompleteTaskActionExecute:
    def test_moves_then_completes_and_clears_task(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=0, y=0, task_code="copper_ore", task_type="items",
                           task_progress=6, task_total=6)
        client = MagicMock()
        # Server clears the task after turn-in.
        char = make_char_schema(x=1, y=2, task_progress=0, task_total=0)
        move_char = make_char_schema(x=1, y=2, task_progress=6, task_total=6)
        move_char.task = "copper_ore"

        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.complete_task.action_task_complete",
                       return_value=make_api_result(char)) as mock_complete:
                new_state = action.execute(state, client)

        mock_complete.assert_called_once()
        assert new_state.task_code is None
        assert new_state.task_total == 0

    def test_skips_move_when_already_at_taskmaster(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=1, y=2, task_code="copper_ore", task_type="items",
                           task_progress=6, task_total=6)
        client = MagicMock()
        char = make_char_schema(x=1, y=2, task_progress=0, task_total=0)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move") as mock_move:
            with patch("artifactsmmo_cli.ai.actions.complete_task.action_task_complete",
                       return_value=make_api_result(char)):
                new_state = action.execute(state, client)

        mock_move.assert_not_called()
        assert new_state.task_total == 0

    def test_raises_on_missing_response(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=1, y=2, task_code="copper_ore", task_type="items",
                           task_progress=6, task_total=6)
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.complete_task.action_task_complete",
                   return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestTaskExchangeActionExecute:
    def test_moves_then_exchanges_and_returns_server_state(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(x=0, y=0, inventory={"tasks_coin": 6})
        client = MagicMock()
        # Server consumed the coins; inventory empty on return.
        char = make_char_schema(x=1, y=2)
        move_char = make_char_schema(x=1, y=2)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.task_exchange.action_task_exchange",
                       return_value=make_api_result(char)) as mock_exch:
                new_state = action.execute(state, client)

        mock_exch.assert_called_once()
        assert (new_state.x, new_state.y) == (1, 2)
        assert new_state.inventory.get("tasks_coin", 0) == 0

    def test_skips_move_when_already_at_taskmaster(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(x=1, y=2, inventory={"tasks_coin": 6})
        client = MagicMock()
        char = make_char_schema(x=1, y=2)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move") as mock_move:
            with patch("artifactsmmo_cli.ai.actions.task_exchange.action_task_exchange",
                       return_value=make_api_result(char)):
                action.execute(state, client)

        mock_move.assert_not_called()

    def test_raises_on_missing_response(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(x=1, y=2, inventory={"tasks_coin": 6})
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.task_exchange.action_task_exchange",
                   return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client)


class TestMoveToExecute:
    def test_execute_moves_to_nearest_destination(self):
        action = MoveTo(name="monster:chicken", destinations=frozenset([(1, 0), (5, 0)]))
        state = make_state(x=0, y=0)
        client = MagicMock()
        char = make_char_schema(x=1, y=0)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(char)):
            new_state = action.execute(state, client)

        assert new_state.x == 1
        assert new_state.y == 0
