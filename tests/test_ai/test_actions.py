"""Tests for GOAP actions — pure apply() functions, no mocking needed."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.bank import DepositAllAction, WithdrawItemAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equipment import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.movement_semantic import MoveTo
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task import AcceptTaskAction, CompleteTaskAction, TaskExchangeAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import _delete_cost
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state


def make_game_data(
    monster_locs=None,
    resource_locs=None,
    workshop_locs=None,
    bank_loc=(4, 0),
    taskmaster_loc=(1, 2),
    item_stats=None,
    recipes=None,
    resource_skills=None,
    monster_levels=None,
) -> GameData:
    gd = GameData()
    gd._monster_locations = monster_locs or {}
    gd._resource_locations = resource_locs or {}
    gd._workshop_locations = workshop_locs or {}
    gd._bank_location = bank_loc
    gd._taskmaster_location = taskmaster_loc
    gd._item_stats = item_stats or {}
    gd._crafting_recipes = recipes or {}
    gd._resource_skill = resource_skills or {}
    gd._monster_level = monster_levels or {}
    return gd


class TestMoveAction:
    def test_is_applicable_when_not_at_target(self):
        action = MoveAction(x=3, y=5)
        state = make_state(x=0, y=0)
        gd = make_game_data()
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_when_already_at_target(self):
        action = MoveAction(x=3, y=5)
        state = make_state(x=3, y=5)
        gd = make_game_data()
        assert action.is_applicable(state, gd) is False

    def test_apply_updates_position(self):
        action = MoveAction(x=3, y=5)
        state = make_state(x=0, y=0)
        gd = make_game_data()
        new_state = action.apply(state, gd)
        assert new_state.x == 3
        assert new_state.y == 5

    def test_cost_proportional_to_distance(self):
        action = MoveAction(x=4, y=3)
        state = make_state(x=0, y=0)
        gd = make_game_data()
        assert action.cost(state, gd) == pytest.approx((4 + 3) * 5.0)

    def test_cost_minimum_is_one(self):
        action = MoveAction(x=1, y=0)
        state = make_state(x=0, y=0)
        gd = make_game_data()
        assert action.cost(state, gd) >= 1.0

    def test_repr(self):
        assert repr(MoveAction(x=3, y=5)) == "Move(3,5)"

    def test_execute_blocks_until_returned_cooldown_expires(self):
        """MoveAction.execute must sleep until the server's post-move cooldown
        clears, so composite callers (Gather/Fight/TaskTrade) don't HTTP 499
        on the secondary call. Verifies time.sleep was invoked with
        approximately the cooldown duration."""
        action = MoveAction(x=4, y=13)
        state = make_state(x=0, y=0)
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=2.0)
        post_state = WorldState(
            character=state.character, level=1, xp=0, max_xp=100,
            hp=100, max_hp=100, gold=0, skills={}, x=4, y=13,
            inventory={}, inventory_max=100, equipment={},
            cooldown_expires=future,
            task_code=None, task_type=None, task_progress=0, task_total=0,
            bank_items={}, bank_gold=0, pending_items=(),
        )
        client = MagicMock()
        with patch(
            "artifactsmmo_cli.ai.actions.movement.action_move",
            return_value=MagicMock(data=MagicMock(character=MagicMock())),
        ), patch(
            "artifactsmmo_cli.ai.actions.movement.WorldState.from_character_schema",
            return_value=post_state,
        ), patch(
            "artifactsmmo_cli.ai.actions.movement.time.sleep"
        ) as sleep:
            action.execute(state, client)
        assert sleep.called
        slept = sleep.call_args[0][0]
        assert 1.5 < slept < 3.0, f"expected ~2s sleep, got {slept}"


class TestMoveToAction:
    def test_not_applicable_when_already_at_destination(self):
        action = MoveTo(name="monster:chicken", destinations=frozenset([(1, 0), (2, 0)]))
        state = make_state(x=1, y=0)
        assert action.is_applicable(state, make_game_data()) is False

    def test_applicable_when_not_at_any_destination(self):
        action = MoveTo(name="monster:chicken", destinations=frozenset([(1, 0), (2, 0)]))
        state = make_state(x=0, y=0)
        assert action.is_applicable(state, make_game_data()) is True

    def test_apply_moves_to_deterministic_destination(self):
        action = MoveTo(name="monster:chicken", destinations=frozenset([(2, 0), (1, 0)]))
        state = make_state(x=0, y=0)
        new_state = action.apply(state, make_game_data())
        assert (new_state.x, new_state.y) in [(1, 0), (2, 0)]

    def test_cost_is_fixed(self):
        action = MoveTo(name="bank", destinations=frozenset([(4, 0)]))
        state = make_state(x=0, y=0)
        assert action.cost(state, make_game_data()) == 1.0

    def test_repr(self):
        action = MoveTo(name="workshop:cooking", destinations=frozenset([(1, 1)]))
        assert repr(action) == "MoveTo(workshop:cooking)"


class TestRestAction:
    def test_applicable_when_hp_below_max(self):
        action = RestAction()
        state = make_state(hp=50, max_hp=100)
        gd = make_game_data()
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_when_full_hp(self):
        action = RestAction()
        state = make_state(hp=100, max_hp=100)
        gd = make_game_data()
        assert action.is_applicable(state, gd) is False

    def test_apply_restores_hp(self):
        action = RestAction()
        state = make_state(hp=50, max_hp=100)
        gd = make_game_data()
        new_state = action.apply(state, gd)
        assert new_state.hp == 100

    def test_cost(self):
        action = RestAction()
        state = make_state()
        gd = make_game_data()
        assert action.cost(state, gd) == pytest.approx(10.0)

    def test_cost_higher_than_consumable(self):
        from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
        from artifactsmmo_cli.ai.game_data import ItemStats
        stats = {"chicken": ItemStats(code="chicken", level=1, type_="consumable", hp_restore=80)}
        rest = RestAction()
        use = UseConsumableAction(_item_stats=stats)
        state = make_state()
        gd = make_game_data()
        assert rest.cost(state, gd) > use.cost(state, gd)


class TestFightAction:
    def test_applicable_with_hp_and_locations(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100, level=1)
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_empty_locations(self):
        action = FightAction(monster_code="chicken", locations=frozenset())
        state = make_state(x=1, y=0, hp=100, max_hp=100, level=1)
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_low_hp(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(x=0, y=0, hp=20, max_hp=100, level=1)
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_monster_too_low_level(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        # level 3 → min_level = max(1, 3-1) = 2; chicken is level 1 → excluded
        state = make_state(x=0, y=0, hp=100, max_hp=100, level=3)
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_monster_too_high_level(self):
        action = FightAction(monster_code="dragon", locations=frozenset([(1, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100, level=1)
        gd = make_game_data(monster_locs={"dragon": [(1, 0)]}, monster_levels={"dragon": 50})
        assert action.is_applicable(state, gd) is False

    def test_apply_moves_to_nearest_and_reduces_hp(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(3, 0), (1, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100, xp=0, level=1)
        gd = make_game_data(monster_locs={"chicken": [(1, 0), (3, 0)]}, monster_levels={"chicken": 1})
        new_state = action.apply(state, gd)
        assert new_state.xp > state.xp
        assert new_state.hp < state.hp
        assert (new_state.x, new_state.y) == (1, 0)  # nearest

    def test_apply_increments_task_progress_for_task_monster(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(
            x=0, y=0, hp=100, max_hp=100, level=1,
            task_code="chicken", task_type="monsters", task_progress=2, task_total=10,
        )
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        new_state = action.apply(state, gd)
        assert new_state.task_progress == 3

    def test_execute_raises_on_fight_loss(self):
        """FightAction.execute must surface API-reported loss as a RuntimeError.

        Regression: the API returns 200 OK on a loss but with fight.result == LOSS.
        Without this raise, the player loop would record outcome=ok and learn that
        Fight(monster) is a "successful" 0-xp 0-gold near-death action — polluting
        action_cost/success_rate and trapping the bot in a loss loop.
        """
        from unittest.mock import MagicMock, patch

        from artifactsmmo_api_client.models.fight_result import FightResult

        from tests.test_ai.test_actions_execute import make_char_schema

        action = FightAction(monster_code="yellow_slime", locations=frozenset([(1, 0)]))
        state = make_state(x=1, y=0, hp=100, max_hp=100, level=1)

        char = make_char_schema(x=1, y=0)
        fight_data = MagicMock()
        fight_data.characters = [char]
        fight_data.fight = MagicMock()
        fight_data.fight.result = FightResult.LOSS
        fight_data.fight.turns = 3
        api_result = MagicMock()
        api_result.data = fight_data

        with patch("artifactsmmo_cli.ai.actions.combat.action_fight", return_value=api_result):
            with pytest.raises(RuntimeError, match="fight_lost"):
                action.execute(state, client=MagicMock())


class TestGatherAction:
    def test_applicable_with_skill_and_locations(self):
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        state = make_state(x=0, y=0, skills={"mining": 5}, inventory={}, inventory_max=10)
        gd = make_game_data(resource_locs={"copper": [(2, 0)]}, resource_skills={"copper": ("mining", 1)})
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_insufficient_skill(self):
        action = GatherAction(resource_code="iron", locations=frozenset([(2, 0)]))
        state = make_state(x=0, y=0, skills={"mining": 1}, inventory={}, inventory_max=10)
        gd = make_game_data(resource_locs={"iron": [(2, 0)]}, resource_skills={"iron": ("mining", 10)})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_full_inventory(self):
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        inventory = {f"item_{i}": 1 for i in range(10)}
        state = make_state(x=0, y=0, skills={"mining": 5}, inventory=inventory, inventory_max=10)
        gd = make_game_data(resource_locs={"copper": [(2, 0)]}, resource_skills={"copper": ("mining", 1)})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_near_full_inventory(self):
        # Requires at least 3 free slots to handle multi-drop scenarios
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        inventory = {f"item_{i}": 1 for i in range(8)}  # 8/10 used = 2 free slots < 3
        state = make_state(x=0, y=0, skills={"mining": 5}, inventory=inventory, inventory_max=10)
        gd = make_game_data(resource_locs={"copper": [(2, 0)]}, resource_skills={"copper": ("mining", 1)})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_empty_locations(self):
        action = GatherAction(resource_code="copper", locations=frozenset())
        state = make_state(x=0, y=0, skills={"mining": 5}, inventory={}, inventory_max=10)
        gd = make_game_data(resource_locs={"copper": [(2, 0)]}, resource_skills={"copper": ("mining", 1)})
        assert action.is_applicable(state, gd) is False

    def test_apply_moves_to_nearest_and_adds_drop_item(self):
        action = GatherAction(resource_code="copper_rocks", locations=frozenset([(5, 0), (2, 0)]))
        state = make_state(x=0, y=0, inventory={})
        gd = make_game_data(resource_locs={"copper_rocks": [(2, 0), (5, 0)]})
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        new_state = action.apply(state, gd)
        assert new_state.inventory.get("copper_ore", 0) == 1
        assert (new_state.x, new_state.y) == (2, 0)  # nearest

    def test_apply_falls_back_to_resource_code_when_no_drop_mapping(self):
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        state = make_state(x=0, y=0, inventory={})
        gd = make_game_data(resource_locs={"copper": [(2, 0)]})
        new_state = action.apply(state, gd)
        assert new_state.inventory.get("copper", 0) == 1


class TestDepositAllAction:
    def test_applicable_with_items(self):
        action = DepositAllAction(bank_location=(4, 0))
        state = make_state(x=0, y=0, inventory={"copper_ore": 5})
        gd = make_game_data(bank_loc=(4, 0))
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_empty_inventory(self):
        action = DepositAllAction(bank_location=(4, 0))
        state = make_state(x=0, y=0, inventory={})
        gd = make_game_data(bank_loc=(4, 0))
        assert action.is_applicable(state, gd) is False

    def test_apply_moves_to_bank_clears_inventory(self):
        action = DepositAllAction(bank_location=(4, 0))
        state = make_state(x=0, y=0, inventory={"copper_ore": 5}, bank_items={"iron_ore": 2})
        gd = make_game_data(bank_loc=(4, 0))
        new_state = action.apply(state, gd)
        assert new_state.inventory == {}
        assert new_state.bank_items["copper_ore"] == 5
        assert new_state.bank_items["iron_ore"] == 2
        assert (new_state.x, new_state.y) == (4, 0)


class TestWithdrawItemAction:
    def test_applicable_with_item_in_bank(self):
        action = WithdrawItemAction(code="copper_ore", quantity=3, bank_location=(4, 0))
        state = make_state(x=0, y=0, inventory={}, inventory_max=10, bank_items={"copper_ore": 5})
        gd = make_game_data(bank_loc=(4, 0))
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_insufficient_bank_quantity(self):
        action = WithdrawItemAction(code="copper_ore", quantity=10, bank_location=(4, 0))
        state = make_state(x=0, y=0, inventory={}, bank_items={"copper_ore": 5})
        gd = make_game_data(bank_loc=(4, 0))
        assert action.is_applicable(state, gd) is False

    def test_apply_moves_to_bank_and_item_to_inventory(self):
        action = WithdrawItemAction(code="copper_ore", quantity=3, bank_location=(4, 0))
        state = make_state(x=0, y=0, inventory={}, bank_items={"copper_ore": 5})
        gd = make_game_data(bank_loc=(4, 0))
        new_state = action.apply(state, gd)
        assert new_state.inventory["copper_ore"] == 3
        assert new_state.bank_items["copper_ore"] == 2
        assert (new_state.x, new_state.y) == (4, 0)


class TestCraftAction:
    def test_applicable_with_workshop_location_and_materials(self):
        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0))
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5}, inventory={"copper_ore": 6})
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_no_workshop_location(self):
        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=None)
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5}, inventory={"copper_ore": 6})
        gd = make_game_data(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_missing_materials(self):
        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0))
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5}, inventory={"copper_ore": 2})
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        assert action.is_applicable(state, gd) is False

    def test_apply_moves_to_workshop_and_produces_item(self):
        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0))
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5}, inventory={"copper_ore": 6})
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        new_state = action.apply(state, gd)
        assert new_state.inventory.get("copper_ore", 0) == 0
        assert new_state.inventory["copper_dagger"] == 1
        assert (new_state.x, new_state.y) == (3, 0)


class TestEquipAction:
    def test_applicable_with_item_in_inventory(self):
        action = EquipAction(code="copper_dagger", slot="weapon_slot")
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1}, level=5)
        gd = make_game_data(item_stats={"copper_dagger": stats})
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_level_too_low(self):
        action = EquipAction(code="epic_sword", slot="weapon_slot")
        stats = ItemStats(code="epic_sword", level=20, type_="weapon")
        state = make_state(inventory={"epic_sword": 1}, level=5)
        gd = make_game_data(item_stats={"epic_sword": stats})
        assert action.is_applicable(state, gd) is False

    def test_apply_moves_item_to_equipment(self):
        action = EquipAction(code="copper_dagger", slot="weapon_slot")
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1}, level=5)
        gd = make_game_data(item_stats={"copper_dagger": stats})
        new_state = action.apply(state, gd)
        assert new_state.equipment["weapon_slot"] == "copper_dagger"
        assert new_state.inventory.get("copper_dagger", 0) == 0


def _consumable_stats(code: str = "cooked_chicken", hp_restore: int = 80) -> dict[str, ItemStats]:
    return {code: ItemStats(code=code, level=1, type_="consumable", hp_restore=hp_restore)}


class TestUseConsumableAction:
    def test_applicable_when_hurt_and_has_food(self):
        action = UseConsumableAction(_item_stats=_consumable_stats())
        state = make_state(hp=50, max_hp=150, inventory={"cooked_chicken": 2})
        assert action.is_applicable(state, make_game_data()) is True

    def test_not_applicable_at_full_hp(self):
        action = UseConsumableAction(_item_stats=_consumable_stats())
        state = make_state(hp=150, max_hp=150, inventory={"cooked_chicken": 2})
        assert action.is_applicable(state, make_game_data()) is False

    def test_not_applicable_when_no_food(self):
        action = UseConsumableAction(_item_stats=_consumable_stats())
        state = make_state(hp=50, max_hp=150, inventory={})
        assert action.is_applicable(state, make_game_data()) is False

    def test_not_applicable_when_item_not_consumable(self):
        stats = {"copper_ore": ItemStats(code="copper_ore", level=1, type_="resource", hp_restore=0)}
        action = UseConsumableAction(_item_stats=stats)
        state = make_state(hp=50, max_hp=150, inventory={"copper_ore": 10})
        assert action.is_applicable(state, make_game_data()) is False

    def test_apply_sets_hp_to_max(self):
        action = UseConsumableAction(_item_stats=_consumable_stats())
        state = make_state(hp=50, max_hp=150, inventory={"cooked_chicken": 2})
        new_state = action.apply(state, make_game_data())
        assert new_state.hp == 150

    def test_apply_removes_one_food_from_inventory(self):
        action = UseConsumableAction(_item_stats=_consumable_stats())
        state = make_state(hp=50, max_hp=150, inventory={"cooked_chicken": 2})
        new_state = action.apply(state, make_game_data())
        assert new_state.inventory["cooked_chicken"] == 1

    def test_apply_removes_key_when_last_food_used(self):
        action = UseConsumableAction(_item_stats=_consumable_stats())
        state = make_state(hp=50, max_hp=150, inventory={"cooked_chicken": 1})
        new_state = action.apply(state, make_game_data())
        assert "cooked_chicken" not in new_state.inventory

    def test_apply_picks_highest_restore_food(self):
        stats = {
            "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=50),
            "cooked_beef": ItemStats(code="cooked_beef", level=5, type_="consumable", hp_restore=150),
        }
        action = UseConsumableAction(_item_stats=stats)
        state = make_state(hp=50, max_hp=200, inventory={"apple": 3, "cooked_beef": 1})
        new_state = action.apply(state, make_game_data())
        assert "cooked_beef" not in new_state.inventory
        assert new_state.inventory["apple"] == 3

    def test_cost_is_2(self):
        action = UseConsumableAction(_item_stats=_consumable_stats())
        state = make_state()
        assert action.cost(state, make_game_data()) == 2.0

    def test_repr(self):
        assert repr(UseConsumableAction(_item_stats={})) == "UseConsumable"


class TestAcceptTaskAction:
    def test_applicable_when_no_task(self):
        action = AcceptTaskAction(taskmaster_location=(1, 2))
        state = make_state(task_code="", task_total=0)
        assert action.is_applicable(state, make_game_data()) is True

    def test_not_applicable_when_task_active(self):
        action = AcceptTaskAction(taskmaster_location=(1, 2))
        state = make_state(task_code="chicken", task_total=10)
        assert action.is_applicable(state, make_game_data()) is False

    def test_apply_sets_pending_task_and_moves(self):
        action = AcceptTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=0, y=0, task_code="", task_total=0)
        new_state = action.apply(state, make_game_data())
        assert new_state.task_code == "__pending__"
        assert new_state.task_total == 1
        assert new_state.task_progress == 0
        assert (new_state.x, new_state.y) == (1, 2)

    def test_cost_includes_distance(self):
        action = AcceptTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=0, y=0)
        assert action.cost(state, make_game_data()) == 1.0 + 3  # dist=3

    def test_repr(self):
        assert repr(AcceptTaskAction(taskmaster_location=(1, 2))) == "AcceptTask"


class TestCompleteTaskAction:
    def test_applicable_when_task_done(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(task_code="chicken", task_total=10, task_progress=10)
        assert action.is_applicable(state, make_game_data()) is True

    def test_not_applicable_when_in_progress(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(task_code="chicken", task_total=10, task_progress=5)
        assert action.is_applicable(state, make_game_data()) is False

    def test_not_applicable_when_no_task(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(task_code="", task_total=0, task_progress=0)
        assert action.is_applicable(state, make_game_data()) is False

    def test_apply_clears_task_and_moves(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=0, y=0, task_code="chicken", task_total=10, task_progress=10)
        new_state = action.apply(state, make_game_data())
        assert new_state.task_code == ""
        assert new_state.task_total == 0
        assert new_state.task_progress == 0
        assert (new_state.x, new_state.y) == (1, 2)

    def test_cost_includes_distance(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=0, y=0)
        assert action.cost(state, make_game_data()) == 1.0 + 3  # dist=3

    def test_repr(self):
        assert repr(CompleteTaskAction(taskmaster_location=(1, 2))) == "CompleteTask"


class TestTaskExchangeAction:
    def test_applicable_when_coins_meet_learned_minimum(self):
        # The minimum is injected (learned empirically); not a hardcoded cost.
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(inventory={"tasks_coin": 6})
        assert action.is_applicable(state, make_game_data()) is True

    def test_not_applicable_below_learned_minimum(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(inventory={"tasks_coin": 5})
        assert action.is_applicable(state, make_game_data()) is False

    def test_default_minimum_is_one(self):
        # Optimistic default before anything is learned.
        action = TaskExchangeAction(taskmaster_location=(1, 2))
        assert action.is_applicable(make_state(inventory={"tasks_coin": 1}), make_game_data()) is True
        assert action.is_applicable(make_state(inventory={}), make_game_data()) is False

    def test_not_applicable_when_coins_only_in_bank(self):
        # Bank coins must be withdrawn first; goal logic includes them in its
        # heuristic but the action itself requires them in inventory.
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(bank_items={"tasks_coin": 8})
        assert action.is_applicable(state, make_game_data()) is False

    def test_not_applicable_when_no_coins(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(inventory={}, bank_items={})
        assert action.is_applicable(state, make_game_data()) is False

    def test_apply_removes_min_coins_from_inventory(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(inventory={"tasks_coin": 6, "copper_ore": 2}, bank_items={})
        new_state = action.apply(state, make_game_data())
        assert "tasks_coin" not in new_state.inventory
        assert new_state.inventory.get("copper_ore") == 2

    def test_apply_keeps_leftover_coins(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(inventory={"tasks_coin": 8}, bank_items={})
        new_state = action.apply(state, make_game_data())
        assert new_state.inventory.get("tasks_coin") == 2

    def test_apply_moves_character_to_taskmaster(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2), min_coins=6)
        state = make_state(x=0, y=0, inventory={"tasks_coin": 6}, bank_items={})
        new_state = action.apply(state, make_game_data())
        assert new_state.x == 1
        assert new_state.y == 2

    def test_cost_at_taskmaster(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2))
        state = make_state(x=1, y=2)
        assert action.cost(state, make_game_data()) == 1.0

    def test_cost_distant(self):
        action = TaskExchangeAction(taskmaster_location=(1, 2))
        state = make_state(x=0, y=0)
        assert action.cost(state, make_game_data()) == 1.0 + 3  # dist=3

    def test_repr(self):
        assert repr(TaskExchangeAction(taskmaster_location=(1, 2))) == "TaskExchange"


class TestGatherActionTaskProgress:
    """Gathering NEVER advances an items-task — the server only counts items on
    delivery to the taskmaster (TaskTradeAction). Modelling gather as +progress
    made the bot gather the task item forever without delivering, fill its
    inventory, and deadlock."""

    def test_gather_does_not_advance_items_task_even_when_drop_matches(self):
        gd = make_game_data(resource_locs={"copper_rocks": [(2, 0)]})
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        action = GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))
        state = make_state(task_code="copper_ore", task_type="items", task_progress=3, task_total=10)
        new_state = action.apply(state, gd)
        assert new_state.task_progress == 3                # unchanged
        assert new_state.inventory.get("copper_ore", 0) == 1  # item still gathered

    def test_no_change_when_task_type_wrong(self):
        gd = make_game_data(resource_locs={"copper_rocks": [(2, 0)]})
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        action = GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))
        state = make_state(task_code="copper_ore", task_type="monsters", task_progress=3, task_total=10)
        new_state = action.apply(state, gd)
        assert new_state.task_progress == 3

    def test_no_change_when_drop_doesnt_match_task(self):
        gd = make_game_data(resource_locs={"ash_tree": [(2, 0)]})
        gd._resource_drops = {"ash_tree": "ash_wood"}
        action = GatherAction(resource_code="ash_tree", locations=frozenset([(2, 0)]))
        state = make_state(task_code="copper_ore", task_type="items", task_progress=3, task_total=10)
        new_state = action.apply(state, gd)
        assert new_state.task_progress == 3


class TestRaiseForError:
    def test_raises_on_error_response_schema(self):
        from artifactsmmo_api_client.models.error_response_schema import ErrorResponseSchema
        from artifactsmmo_api_client.models.error_schema import ErrorSchema
        err = ErrorResponseSchema(error=ErrorSchema(code=499, message="Character in cooldown"))
        with pytest.raises(RuntimeError, match="HTTP 499"):
            Action._raise_for_error(err, "Test")

    def test_raises_on_none_result(self):
        with pytest.raises(RuntimeError, match="no response data"):
            Action._raise_for_error(None, "Test")

    def test_no_raise_on_valid_result(self):
        from unittest.mock import MagicMock
        result = MagicMock()
        result.data = MagicMock()
        Action._raise_for_error(result, "Test")  # should not raise


def test_delete_cost_weight_rule():
    """Verify cost: ingredient first (50), then sellable (25), else worthless (5)."""

    class FakeGD:
        def __init__(self, recipes=None, sell_prices=None):
            self._crafting_recipes = recipes or {}
            self._npc_sell_prices = sell_prices or {}
        def npcs_buying_item(self, code):
            return [(npc, prices[code]) for npc, prices in self._npc_sell_prices.items() if code in prices]

    # Ingredient (regardless of sellable status) → 50
    gd_ingredient = FakeGD(recipes={"sword": {"iron_ore": 5}})
    assert _delete_cost("iron_ore", gd_ingredient) == 50.0

    gd_ingredient_also_sellable = FakeGD(
        recipes={"sword": {"iron_ore": 5}},
        sell_prices={"smith": {"iron_ore": 8}},
    )
    assert _delete_cost("iron_ore", gd_ingredient_also_sellable) == 50.0

    # Sellable but not ingredient → 25
    gd_sellable_only = FakeGD(sell_prices={"cook": {"raw_meat": 3}})
    assert _delete_cost("raw_meat", gd_sellable_only) == 25.0

    # Neither → 5
    gd_worthless = FakeGD()
    assert _delete_cost("garbage", gd_worthless) == 5.0


def test_fight_action_cost_uses_history_when_provided():
    """When LearningStore has >=5 ok samples, FightAction.cost returns the learned median."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr="Fight(yellow_slime)", actual_cooldown_seconds=25.0,
            ))
        action = FightAction(monster_code="yellow_slime", locations=frozenset({(1, 1)}))
        state = make_state(x=1, y=1, hp=100, max_hp=100)
        gd = GameData()
        assert repr(action) == "Fight(yellow_slime)"
        assert action.cost(state, gd, history=store) == 25.0
        static_cost = action.cost(state, gd, history=None)
        assert static_cost != 25.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_fight_action_cost_penalises_low_success_rate():
    """Low success rate adds penalty: cost = learned / rate."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr="Fight(z)", actual_cooldown_seconds=10.0,
            ))
        for i in range(5, 10):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="error:X",
                action_repr="Fight(z)", actual_cooldown_seconds=99.0,
            ))
        action = FightAction(monster_code="z", locations=frozenset({(1, 1)}))
        state = make_state(x=1, y=1, hp=100, max_hp=100)
        # learned cost = 10.0 (only ok cycles counted in action_cost)
        # success_rate = 0.5 (5 ok / 10 total)
        # cost = 10.0 / 0.5 = 20.0
        assert action.cost(state, GameData(), history=store) == 20.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_gather_action_cost_uses_history_when_provided():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        action = GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 2)}))
        repr_str = repr(action)
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr=repr_str, actual_cooldown_seconds=18.0,
            ))
        state = make_state(x=2, y=2, hp=100, max_hp=100, inventory={}, inventory_max=20)
        assert action.cost(state, GameData(), history=store) == 18.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_move_action_cost_uses_history_when_provided():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        action = MoveAction(x=3, y=4)
        repr_str = repr(action)
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr=repr_str, actual_cooldown_seconds=8.0,
            ))
        state = make_state(x=0, y=0)
        assert action.cost(state, GameData(), history=store) == 8.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)


class TestActionTags:
    """R-1: Every concrete Action class declares its semantic tags so goals
    can filter via `action.tags & {"combat"}` instead of isinstance chains."""

    def test_base_action_default_tags_empty(self):
        assert Action.tags == frozenset()

    def test_fight_action_tagged_combat_and_xp(self):
        assert "combat" in FightAction.tags
        assert "produces_char_xp" in FightAction.tags

    def test_gather_action_tagged_gather_and_skill_xp(self):
        assert "gather" in GatherAction.tags
        assert "produces_skill_xp" in GatherAction.tags

    def test_craft_action_tagged_craft(self):
        assert "craft" in CraftAction.tags
        assert "produces_skill_xp" in CraftAction.tags

    def test_recovery_actions_tagged(self):
        assert "recovery" in RestAction.tags
        assert "recovery" in UseConsumableAction.tags

    def test_movement_tagged(self):
        assert "movement" in MoveAction.tags

    def test_bank_actions_tagged_bank(self):
        assert "bank" in DepositAllAction.tags
        assert "bank" in WithdrawItemAction.tags

    def test_task_actions_tagged_task(self):
        assert "task" in AcceptTaskAction.tags
        assert "task" in CompleteTaskAction.tags
        assert "task" in TaskExchangeAction.tags

    def test_equip_actions_tagged_equip(self):
        assert "equip" in EquipAction.tags

    def test_tags_are_class_attributes_not_instance(self):
        """Class attribute on ClassVar — instances share the same frozenset."""
        a = MoveAction(x=1, y=2)
        b = MoveAction(x=3, y=4)
        assert a.tags is b.tags is MoveAction.tags
