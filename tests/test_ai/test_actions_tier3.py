"""Tests for TaskCancelAction, ClaimPendingItemAction, TaskCancelGoal, ClaimPendingGoal,
DeleteItemAction, and UseConsumableAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._monster_locations = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._monster_level = kwargs.get("monster_level", {})
    gd._npc_locations = {}
    gd._npc_stock = {}
    return gd


class TestTaskCancelAction:
    def test_repr(self):
        assert repr(TaskCancelAction(taskmaster_location=(1, 2))) == "TaskCancel"

    def test_applicable_when_task_active(self):
        action = TaskCancelAction(taskmaster_location=(1, 2))
        state = make_state(task_code="chicken", task_total=10, task_progress=3)
        assert action.is_applicable(state, make_gd()) is True

    def test_not_applicable_without_task(self):
        action = TaskCancelAction(taskmaster_location=(1, 2))
        state = make_state(task_code=None, task_total=0)
        assert action.is_applicable(state, make_gd()) is False

    def test_not_applicable_when_task_total_zero(self):
        action = TaskCancelAction(taskmaster_location=(1, 2))
        state = make_state(task_code="chicken", task_total=0)
        assert action.is_applicable(state, make_gd()) is False

    def test_apply_clears_task(self):
        action = TaskCancelAction(taskmaster_location=(1, 2))
        state = make_state(task_code="chicken", task_total=10, task_progress=5)
        new_state = action.apply(state, make_gd())
        assert new_state.task_code is None
        assert new_state.task_total == 0
        assert new_state.task_progress == 0

    def test_apply_moves_to_taskmaster(self):
        action = TaskCancelAction(taskmaster_location=(3, 4))
        state = make_state(x=0, y=0, task_code="wolf", task_total=5)
        new_state = action.apply(state, make_gd())
        assert new_state.x == 3
        assert new_state.y == 4

    def test_apply_preserves_pending_items(self):
        action = TaskCancelAction(taskmaster_location=(1, 2))
        state = make_state(task_code="wolf", task_total=5, pending_items=(("id1", "copper_ore"),))
        new_state = action.apply(state, make_gd())
        assert new_state.pending_items == (("id1", "copper_ore"),)

    def test_cost_includes_distance(self):
        action = TaskCancelAction(taskmaster_location=(3, 0))
        state = make_state(x=0, y=0)
        assert action.cost(state, make_gd()) == pytest.approx(4.0)

    def test_execute_moves_and_calls_api(self):
        action = TaskCancelAction(taskmaster_location=(1, 2))
        char = make_char_schema()
        state = make_state(x=0, y=0, task_code="wolf", task_total=5)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.task_cancel.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=1, y=2)
            with patch("artifactsmmo_cli.ai.actions.task_cancel.action_task_cancel",
                       return_value=make_api_result(char)) as mock_api:
                action.execute(state, client)
        MockMove.assert_called_once_with(x=1, y=2)
        mock_api.assert_called_once()


class TestClaimPendingItemAction:
    def test_repr(self):
        assert repr(ClaimPendingItemAction()) == "ClaimPendingItem"

    def test_not_applicable_when_no_pending_items(self):
        action = ClaimPendingItemAction()
        state = make_state(pending_items=None)
        assert action.is_applicable(state, make_gd()) is False

    def test_not_applicable_when_empty_tuple(self):
        action = ClaimPendingItemAction()
        state = make_state(pending_items=())
        assert action.is_applicable(state, make_gd()) is False

    def test_applicable_when_pending_items_exist(self):
        action = ClaimPendingItemAction()
        state = make_state(pending_items=(("id1", "copper_ore"),))
        assert action.is_applicable(state, make_gd()) is True

    def test_apply_adds_item_to_inventory(self):
        action = ClaimPendingItemAction()
        state = make_state(pending_items=(("id1", "copper_ore"),), inventory={})
        new_state = action.apply(state, make_gd())
        assert new_state.inventory.get("copper_ore") == 1
        assert new_state.pending_items is None

    def test_apply_returns_state_when_pending_items_is_none(self):
        """Defensive guard: apply() returns state unchanged if pending_items is None."""
        action = ClaimPendingItemAction()
        state = make_state(pending_items=None)
        result = action.apply(state, make_gd())
        assert result is state

    def test_apply_removes_claimed_item_from_pending(self):
        action = ClaimPendingItemAction()
        state = make_state(pending_items=(("id1", "copper_ore"), ("id2", "iron_ore")), inventory={})
        new_state = action.apply(state, make_gd())
        assert new_state.inventory["copper_ore"] == 1
        assert new_state.pending_items == (("id2", "iron_ore"),)

    def test_apply_sets_pending_to_none_when_last_item(self):
        action = ClaimPendingItemAction()
        state = make_state(pending_items=(("id1", "copper_ore"),))
        new_state = action.apply(state, make_gd())
        assert new_state.pending_items is None

    def test_cost_is_1(self):
        action = ClaimPendingItemAction()
        assert action.cost(make_state(), make_gd()) == pytest.approx(1.0)

    def test_execute_fetches_and_claims(self):
        action = ClaimPendingItemAction()
        char = make_char_schema()
        state = make_state(pending_items=(("id1", "copper_ore"),))
        client = MagicMock()

        pending_item = MagicMock()
        pending_item.id = "id1"
        pending_item.code = "copper_ore"
        pending_result = MagicMock()
        pending_result.data = [pending_item]

        with patch("artifactsmmo_cli.ai.actions.claim.get_pending_items", return_value=pending_result):
            with patch("artifactsmmo_cli.ai.actions.claim.action_claim_item",
                       return_value=make_api_result(char)) as mock_claim:
                new_state = action.execute(state, client)

        mock_claim.assert_called_once()
        assert new_state is not None

    def test_execute_returns_state_when_no_pending(self):
        action = ClaimPendingItemAction()
        state = make_state(pending_items=(("id1", "copper_ore"),))
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.claim.get_pending_items", return_value=MagicMock(data=[])):
            result = action.execute(state, client)

        assert result is state


class TestTaskCancelGoal:
    def test_repr(self):
        assert repr(TaskCancelGoal()) == "TaskCancel"

    def test_value_zero_when_no_task(self):
        goal = TaskCancelGoal()
        state = make_state(task_code=None, task_total=0)
        assert goal.value(state, make_gd()) == pytest.approx(0.0)

    def test_value_zero_when_task_not_too_hard(self):
        goal = TaskCancelGoal()
        state = make_state(level=10, task_code="chicken", task_type="monsters", task_total=10)
        gd = make_gd(monster_level={"chicken": 5})
        assert goal.value(state, gd) == pytest.approx(0.0)

    def test_value_nonzero_when_monster_too_strong(self):
        goal = TaskCancelGoal()
        state = make_state(level=5, task_code="dragon", task_type="monsters", task_total=10)
        gd = make_gd(monster_level={"dragon": 20})
        assert goal.value(state, gd) > 0.0

    def test_value_zero_for_non_monster_task(self):
        goal = TaskCancelGoal()
        state = make_state(level=1, task_code="copper_ore", task_type="resources", task_total=10)
        gd = make_gd(monster_level={})
        assert goal.value(state, gd) == pytest.approx(0.0)

    def test_satisfied_when_no_task(self):
        goal = TaskCancelGoal()
        assert goal.is_satisfied(make_state(task_code=None, task_total=0)) is True

    def test_not_satisfied_when_task_active(self):
        goal = TaskCancelGoal()
        assert goal.is_satisfied(make_state(task_code="chicken", task_total=10)) is False

    def test_desired_state(self):
        goal = TaskCancelGoal()
        ds = goal.desired_state(make_state(), make_gd())
        assert ds == {"task_code": None, "task_total": 0}


class TestClaimPendingGoal:
    def test_repr(self):
        assert repr(ClaimPendingGoal()) == "ClaimPending"

    def test_value_zero_when_no_pending(self):
        goal = ClaimPendingGoal()
        state = make_state(pending_items=None)
        assert goal.value(state, make_gd()) == pytest.approx(0.0)

    def test_value_nonzero_when_pending_items_exist(self):
        goal = ClaimPendingGoal()
        state = make_state(pending_items=(("id1", "copper_ore"),))
        assert goal.value(state, make_gd()) > 0.0

    def test_satisfied_when_no_pending(self):
        goal = ClaimPendingGoal()
        assert goal.is_satisfied(make_state(pending_items=None)) is True

    def test_not_satisfied_when_pending_exist(self):
        goal = ClaimPendingGoal()
        assert goal.is_satisfied(make_state(pending_items=(("id1", "copper_ore"),))) is False

    def test_desired_state(self):
        goal = ClaimPendingGoal()
        ds = goal.desired_state(make_state(), make_gd())
        assert ds == {"pending_items": None}


class TestDeleteItemAction:
    def test_repr(self):
        assert repr(DeleteItemAction(code="iron_ore", quantity=2)) == "Delete(iron_ore×2)"

    def test_is_applicable_when_item_in_inventory(self):
        action = DeleteItemAction(code="iron_ore", quantity=1)
        state = make_state(inventory={"iron_ore": 1})
        assert action.is_applicable(state, make_gd()) is True

    def test_is_applicable_when_inventory_meets_quantity(self):
        action = DeleteItemAction(code="iron_ore", quantity=3)
        state = make_state(inventory={"iron_ore": 3})
        assert action.is_applicable(state, make_gd()) is True

    def test_not_applicable_when_insufficient_quantity(self):
        action = DeleteItemAction(code="iron_ore", quantity=2)
        state = make_state(inventory={"iron_ore": 1})
        assert action.is_applicable(state, make_gd()) is False

    def test_not_applicable_when_item_absent(self):
        action = DeleteItemAction(code="iron_ore", quantity=1)
        state = make_state(inventory={})
        assert action.is_applicable(state, make_gd()) is False

    def test_apply_removes_item_from_inventory(self):
        action = DeleteItemAction(code="iron_ore", quantity=1)
        state = make_state(inventory={"iron_ore": 3, "copper_ore": 2})
        new_state = action.apply(state, make_gd())
        assert new_state.inventory["iron_ore"] == 2
        assert new_state.inventory["copper_ore"] == 2

    def test_apply_removes_key_when_quantity_reaches_zero(self):
        action = DeleteItemAction(code="iron_ore", quantity=1)
        state = make_state(inventory={"iron_ore": 1})
        new_state = action.apply(state, make_gd())
        assert "iron_ore" not in new_state.inventory

    def test_apply_removes_key_when_quantity_goes_below_zero(self):
        # Should not happen in practice, but apply defensively removes the key
        action = DeleteItemAction(code="iron_ore", quantity=2)
        state = make_state(inventory={"iron_ore": 1})
        new_state = action.apply(state, make_gd())
        assert "iron_ore" not in new_state.inventory

    def test_apply_preserves_other_state_fields(self):
        action = DeleteItemAction(code="iron_ore", quantity=1)
        state = make_state(inventory={"iron_ore": 1}, gold=500, hp=80, x=3, y=4)
        new_state = action.apply(state, make_gd())
        assert new_state.gold == 500
        assert new_state.hp == 80
        assert new_state.x == 3
        assert new_state.y == 4

    def test_cost_returns_cost_weight(self):
        action = DeleteItemAction(code="iron_ore", quantity=1, cost_weight=25.0)
        state = make_state()
        assert action.cost(state, make_gd()) == pytest.approx(25.0)

    def test_cost_default_weight(self):
        action = DeleteItemAction(code="iron_ore", quantity=1)
        state = make_state()
        assert action.cost(state, make_gd()) == pytest.approx(2.0)

    def test_execute_calls_api_and_returns_updated_state(self):
        action = DeleteItemAction(code="iron_ore", quantity=1)
        char = make_char_schema()
        state = make_state(inventory={"iron_ore": 1}, bank_items={"gold": 5}, bank_gold=100)
        client = MagicMock()
        api_result = make_api_result(char)
        with patch("artifactsmmo_cli.ai.actions.delete.action_delete", return_value=api_result) as mock_delete:
            new_state = action.execute(state, client)
        mock_delete.assert_called_once()
        assert new_state is not None

    def test_execute_preserves_bank_items(self):
        action = DeleteItemAction(code="iron_ore", quantity=1)
        char = make_char_schema()
        state = make_state(inventory={"iron_ore": 1}, bank_items={"gold": 5}, bank_gold=100)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.delete.action_delete", return_value=make_api_result(char)):
            new_state = action.execute(state, client)
        assert new_state.bank_items == {"gold": 5}
        assert new_state.bank_gold == 100


class TestBestConsumableHelper:
    """Tests for the _best_consumable module-level helper in consumable.py."""

    def test_skips_items_with_zero_quantity(self):
        from artifactsmmo_cli.ai.actions.consumable import _best_consumable
        item_stats = {"bread": ItemStats(code="bread", level=1, type_="consumable", hp_restore=30)}
        # Inventory has bread with qty=0 — must be skipped
        result = _best_consumable({"bread": 0}, item_stats)
        assert result is None

    def test_returns_best_consumable_when_multiple_available(self):
        from artifactsmmo_cli.ai.actions.consumable import _best_consumable
        item_stats = {
            "bread": ItemStats(code="bread", level=1, type_="consumable", hp_restore=20),
            "chicken": ItemStats(code="chicken", level=1, type_="consumable", hp_restore=50),
        }
        result = _best_consumable({"bread": 1, "chicken": 1}, item_stats)
        assert result == ("chicken", 50)


class TestUseConsumableAction:
    def _make_item_stats_with_food(self, code: str, hp: int) -> dict[str, ItemStats]:
        return {code: ItemStats(code=code, level=1, type_="consumable", hp_restore=hp)}

    def test_repr(self):
        action = UseConsumableAction(_item_stats={})
        assert repr(action) == "UseConsumable"

    def test_execute_calls_api_and_returns_updated_state(self):
        item_stats = self._make_item_stats_with_food("cooked_chicken", 50)
        action = UseConsumableAction(_item_stats=item_stats)
        char = make_char_schema(hp=150, max_hp=150)
        state = make_state(hp=80, max_hp=150, inventory={"cooked_chicken": 2})
        client = MagicMock()
        api_result = make_api_result(char)
        with patch("artifactsmmo_cli.ai.actions.consumable.action_use_item", return_value=api_result) as mock_use:
            new_state = action.execute(state, client)
        mock_use.assert_called_once()
        assert new_state is not None

    def test_execute_raises_when_no_consumable_at_execute_time(self):
        action = UseConsumableAction(_item_stats={})
        state = make_state(hp=80, max_hp=150, inventory={})
        client = MagicMock()
        with pytest.raises(RuntimeError, match="no consumable"):
            action.execute(state, client)

    def test_execute_preserves_bank_items(self):
        item_stats = self._make_item_stats_with_food("bread", 30)
        action = UseConsumableAction(_item_stats=item_stats)
        char = make_char_schema(hp=150, max_hp=150)
        state = make_state(hp=50, max_hp=150, inventory={"bread": 1},
                           bank_items={"iron_ore": 10}, bank_gold=200)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.consumable.action_use_item", return_value=make_api_result(char)):
            new_state = action.execute(state, client)
        assert new_state.bank_items == {"iron_ore": 10}
        assert new_state.bank_gold == 200
