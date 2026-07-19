"""Tests for GOAP actions — pure apply() functions, no mocking needed."""

import dataclasses
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import (
    TASK_COMPLETE_XP_ESTIMATE,
    CompleteTaskAction,
)
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.cost_core import OVERHEAL_CONSUMABLE_COST, REST_COST_MAX
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.movement_semantic import MoveTo
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import _delete_cost
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
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
    fill_monster_stat_defaults(gd)
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
            inventory={}, inventory_max=100, inventory_slots_max=0, equipment={},
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

    def test_apply_preserves_skill_xp(self):
        """RestAction.apply must carry skill_xp forward (not reset to {})."""
        action = RestAction()
        state = make_state(hp=50, max_hp=100, skill_xp={"alchemy": 200})
        new_state = action.apply(state, make_game_data())
        assert new_state.skill_xp == {"alchemy": 200}

    def test_cost_delegates_to_rest_cost_pure(self):
        # The action holds no constant of its own: it is rest_cost_pure(hp, max_hp).
        # make_state defaults are hp=100/max_hp=150 -> missing 50 -> ceil(5000/150)
        # = 34% -> max(3, 34)/10 = 3.4. The regimes themselves (min-3s floor, ceil,
        # full deficit) are pinned in tests/test_ai/test_cost_core.py.
        action = RestAction()
        state = make_state()
        gd = make_game_data()
        assert action.cost(state, gd) == pytest.approx(3.4)

    def test_cost_exceeds_consumable_only_at_deep_deficit(self):
        # Rest always refills to full; its cooldown is the only price, and it
        # scales with the deficit. So a consumable is worth its own cooldown only
        # when it removes more rest-seconds than it costs -- true at a deep
        # deficit, false at a shallow one. The old blanket "rest is dearer than a
        # consumable" assertion held only by accident of the fixture defaults.
        stats = {"chicken": ItemStats(code="chicken", level=1, type_="consumable", hp_restore=80)}
        rest = RestAction()
        use = UseConsumableAction(_item_stats=stats)
        gd = make_game_data()

        deep = make_state(hp=10, max_hp=150)      # 94% missing -> 9.4
        assert rest.cost(deep, gd) > use.cost(deep, gd)

        shallow = make_state(hp=149, max_hp=150)  # 1% missing -> min-3s floor -> 0.3
        assert rest.cost(shallow, gd) < use.cost(shallow, gd)


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

    def test_applicable_below_old_window_when_xp_positive(self):
        """P0 regression (2026-06-09): the old hard lower window
        `monster_level >= max(1, level-1)` rejected chicken (L1) at level 3
        and deadlocked combat when nothing in-window was winnable. The
        lower gate is now `xp_per_kill > 0` — chicken grants XP at level 3,
        so the fight is applicable."""
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100, level=3)
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        assert gd.xp_per_kill("chicken", 3) > 0
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_monster_grants_zero_xp(self):
        """The honest lower bound: the documented XP curve zeroes out at
        char_level - monster_level >= 10, so a far-below monster serves no
        leveling objective and is excluded — naturally level-tracking."""
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100, level=11)
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        assert gd.xp_per_kill("chicken", 11) == 0
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

    def test_apply_adds_monster_drops_to_inventory(self):
        """Fight must model the loot drop so the planner can plan
        "fight chicken -> feather" (GatherMaterials over a monster-drop material).
        Without it, GatherMaterials(feather) explored 21868 nodes / plan_len 0 and
        the bot fell to char-grind forever (trace 2026-06-14 230824)."""
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100, level=1,
                           inventory={}, inventory_max=20)
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        gd._monster_drops = {"chicken": [("feather", 5, 1, 1), ("raw_chicken", 3, 1, 1)]}
        new_state = action.apply(state, gd)
        assert new_state.inventory.get("feather") == 1
        assert new_state.inventory.get("raw_chicken") == 1

    def test_apply_does_not_overflow_inventory_with_drops(self):
        """Drops past capacity are not minted (used never exceeds max)."""
        action = FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100, level=1,
                           inventory={"junk": 19}, inventory_max=20)
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        gd._monster_drops = {"chicken": [("feather", 5, 1, 1), ("raw_chicken", 3, 1, 1)]}
        new_state = action.apply(state, gd)
        assert new_state.inventory_used <= new_state.inventory_max

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

    def test_apply_preserves_skill_xp_baseline(self):
        """GatherAction.apply must NOT mutate skill_xp — it is a server-snapshot
        baseline field (see ApplyBaseline contract / WorldState docstring)."""
        action = GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))
        gd = make_game_data(resource_skills={"copper_rocks": ("mining", 1)})
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        state = make_state(x=0, y=0, inventory={}, skill_xp={"mining": 5})
        new_state = action.apply(state, gd)
        assert new_state.skill_xp == state.skill_xp

    def test_apply_preserves_other_skill_xp_entries(self):
        """GatherAction.apply must not wipe unrelated skill_xp entries."""
        action = GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))
        gd = make_game_data(resource_skills={"copper_rocks": ("mining", 1)})
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        state = make_state(x=0, y=0, inventory={}, skill_xp={"mining": 0, "alchemy": 200})
        new_state = action.apply(state, gd)
        assert new_state.skill_xp == state.skill_xp

    def test_apply_falls_back_to_resource_code_when_no_drop_mapping(self):
        action = GatherAction(resource_code="copper", locations=frozenset([(2, 0)]))
        state = make_state(x=0, y=0, inventory={})
        gd = make_game_data(resource_locs={"copper": [(2, 0)]})
        new_state = action.apply(state, gd)
        assert new_state.inventory.get("copper", 0) == 1


class TestDepositAllAction:
    def test_applicable_with_items(self):
        gd = make_game_data(bank_loc=(4, 0))
        action = DepositAllAction(bank_location=(4, 0), game_data=gd)
        state = make_state(x=0, y=0, inventory={"copper_ore": 5})  # no task → bankable
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_empty_inventory(self):
        gd = make_game_data(bank_loc=(4, 0))
        action = DepositAllAction(bank_location=(4, 0), game_data=gd)
        state = make_state(x=0, y=0, inventory={})
        assert action.is_applicable(state, gd) is False

    def test_apply_moves_to_bank_clears_bankable_inventory(self):
        gd = make_game_data(bank_loc=(4, 0))
        action = DepositAllAction(bank_location=(4, 0), game_data=gd)
        state = make_state(x=0, y=0, inventory={"copper_ore": 5}, bank_items={"iron_ore": 2})
        new_state = action.apply(state, gd)
        assert new_state.inventory == {}  # copper_ore (no keep rule) banked
        assert new_state.bank_items["copper_ore"] == 5
        assert new_state.bank_items["iron_ore"] == 2
        assert (new_state.x, new_state.y) == (4, 0)

    def test_apply_preserves_skill_xp(self):
        """DepositAllAction.apply must carry skill_xp forward (not reset to {})."""
        gd = make_game_data(bank_loc=(4, 0))
        action = DepositAllAction(bank_location=(4, 0), game_data=gd)
        state = make_state(x=0, y=0, inventory={"copper_ore": 5}, bank_items={},
                           skill_xp={"alchemy": 200})
        new_state = action.apply(state, gd)
        assert new_state.skill_xp == {"alchemy": 200}


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

    def test_not_applicable_new_code_blocked_when_no_free_slot(self):
        """Withdrawing a code NOT held into a full bag needs a slot -> blocked,
        even with quantity headroom."""
        action = WithdrawItemAction(code="iron_ore", quantity=3, bank_location=(4, 0))
        inv = {f"j{n}": 1 for n in range(20)}
        state = make_state(x=0, y=0, inventory=inv, inventory_max=100,
                           inventory_slots_max=20, bank_items={"iron_ore": 10})
        gd = make_game_data(bank_loc=(4, 0))
        assert action.is_applicable(state, gd) is False

    def test_applicable_held_code_grows_stack_when_no_free_slot(self):
        """Withdrawing MORE of a held code grows its stack -> no new slot
        needed, so quantity headroom alone decides."""
        action = WithdrawItemAction(code="iron_ore", quantity=3, bank_location=(4, 0))
        inv = {"iron_ore": 2, **{f"j{n}": 1 for n in range(19)}}
        state = make_state(x=0, y=0, inventory=inv, inventory_max=100,
                           inventory_slots_max=20, bank_items={"iron_ore": 10})
        gd = make_game_data(bank_loc=(4, 0))
        assert action.is_applicable(state, gd) is True


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

    def test_applicable_when_partial_batch_affordable(self):
        """A batch craft whose inputs cover only SOME of the requested quantity
        is applicable — partial (>=1) counts, full satisfaction is not required."""
        action = CraftAction(code="copper_dagger", quantity=3, workshop_location=(3, 0))
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        # 12 ore covers 2 daggers (needs 18 for the full 3)
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5}, inventory={"copper_ore": 12})
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_when_not_even_one_unit_affordable(self):
        """Inputs below one unit's recipe => cannot contribute => not applicable."""
        action = CraftAction(code="copper_dagger", quantity=3, workshop_location=(3, 0))
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5}, inventory={"copper_ore": 5})
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        assert action.is_applicable(state, gd) is False

    def test_apply_crafts_largest_feasible_batch_when_partial(self):
        """apply produces the largest feasible batch (<= requested), not zero and
        not the full requested amount when inputs fall short."""
        action = CraftAction(code="copper_dagger", quantity=3, workshop_location=(3, 0))
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5}, inventory={"copper_ore": 12})
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        new_state = action.apply(state, gd)
        assert new_state.inventory["copper_dagger"] == 2
        assert new_state.inventory.get("copper_ore", 0) == 0

    def test_not_applicable_when_skill_below_recipe_gate(self):
        """Skill below the recipe's crafting_level blocks the craft even with
        materials on hand (partial applicability must NOT bypass the skill gate)."""
        action = CraftAction(code="steel_sword", quantity=1, workshop_location=(3, 0))
        stats = ItemStats(
            code="steel_sword", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=10,
        )
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5}, inventory={"steel": 6})
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"steel_sword": stats},
            recipes={"steel_sword": {"steel": 6}},
        )
        assert action.is_applicable(state, gd) is False

    def test_effective_quantity_zero_when_no_recipe(self):
        """No recipe for the item => nothing craftable => effective 0."""
        action = CraftAction(code="mystery_item", quantity=3, workshop_location=(0, 0))
        state = make_state(x=0, y=0, skills={"weaponcrafting": 5})
        gd = make_game_data(workshop_locs={"weaponcrafting": (0, 0)}, recipes={})
        assert action.effective_quantity(state, gd) == 0

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

    def test_apply_preserves_skill_xp_baseline(self):
        """CraftAction.apply must NOT mutate skill_xp — it is a server-snapshot
        baseline field (see ApplyBaseline contract / WorldState docstring)."""
        action = CraftAction(code="copper_dagger", quantity=3, workshop_location=(3, 0))
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        state = make_state(
            x=0, y=0, skills={"weaponcrafting": 5},
            inventory={"copper_ore": 18},
            skill_xp={"weaponcrafting": 10},
        )
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        new_state = action.apply(state, gd)
        assert new_state.skill_xp == state.skill_xp

    def test_apply_preserves_other_skill_xp_entries(self):
        """CraftAction.apply must carry forward unrelated skill_xp entries."""
        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0))
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        state = make_state(
            x=0, y=0, skills={"weaponcrafting": 5},
            inventory={"copper_ore": 6},
            skill_xp={"weaponcrafting": 0, "alchemy": 777},
        )
        gd = make_game_data(
            workshop_locs={"weaponcrafting": (3, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        new_state = action.apply(state, gd)
        assert new_state.skill_xp["alchemy"] == 777


def _gd_with_utility_heal(code: str, hp_restore: int) -> GameData:
    stats = ItemStats(code=code, level=1, type_="utility", hp_restore=hp_restore)
    return make_game_data(item_stats={code: stats})


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

    def test_not_applicable_when_slot_mismatches_item_type(self):
        """A weapon code targeted at a helmet slot is non-executable on the
        server, so is_applicable rejects it (slot/type gate, line 63-64)."""
        action = EquipAction(code="copper_dagger", slot="helmet_slot")
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1}, level=5)
        gd = make_game_data(item_stats={"copper_dagger": stats})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_code_already_equipped_in_sibling_slot(self):
        """The server forbids a single item code occupying two slots at once
        (HTTP 485 "This item is already equipped"). With small_health_potion
        already in utility1, equipping a second copy into the empty utility2
        is non-executable; is_applicable must reject it so the planner never
        emits the doomed equip (the Robby utility2 livelock, trace 20260610)."""
        action = EquipAction(code="small_health_potion", slot="utility2_slot")
        stats = ItemStats(code="small_health_potion", level=1, type_="utility")
        state = make_state(
            inventory={"small_health_potion": 1},
            equipment={**make_state().equipment, "utility1_slot": "small_health_potion"},
            level=5,
        )
        gd = make_game_data(item_stats={"small_health_potion": stats})
        assert action.is_applicable(state, gd) is False

    def test_applicable_when_different_code_in_sibling_slot(self):
        """Two DIFFERENT consumables across the utility slots is legal, so a
        distinct code into the empty sibling slot stays applicable (the guard
        keys on item code, not slot-group occupancy)."""
        action = EquipAction(code="small_health_potion", slot="utility2_slot")
        stats = ItemStats(code="small_health_potion", level=1, type_="utility")
        state = make_state(
            inventory={"small_health_potion": 1},
            equipment={**make_state().equipment, "utility1_slot": "antidote"},
            level=5,
        )
        gd = make_game_data(item_stats={"small_health_potion": stats})
        assert action.is_applicable(state, gd) is True

    def test_applicable_when_same_code_in_its_own_target_slot(self):
        """Equipping a code into the slot ALREADY holding that code (utility
        re-stock / stacking) is exempt from the already-worn guard (`slot !=
        self.slot` in equip.py); it stays governed by the pre-existing
        inventory/level gates, so with a spare copy held it is applicable."""
        action = EquipAction(code="small_health_potion", slot="utility1_slot")
        stats = ItemStats(code="small_health_potion", level=1, type_="utility")
        state = make_state(
            inventory={"small_health_potion": 1},
            equipment={**make_state().equipment, "utility1_slot": "small_health_potion"},
            level=5,
        )
        gd = make_game_data(item_stats={"small_health_potion": stats})
        assert action.is_applicable(state, gd) is True

    def test_equip_action_quantity_requires_enough_inventory(self):
        state = make_state(inventory={"small_health_potion": 1})
        stats = ItemStats(code="small_health_potion", level=1, type_="utility")
        gd = make_game_data(item_stats={"small_health_potion": stats})
        action = EquipAction(code="small_health_potion", slot="utility1_slot", quantity=2)
        assert action.is_applicable(state, gd) is False  # only 1 held, want 2

    def test_equip_action_quantity_decrements_by_quantity(self):
        state = make_state(inventory={"small_health_potion": 5}, level=1)
        stats = ItemStats(code="small_health_potion", level=1, type_="utility")
        gd = make_game_data(item_stats={"small_health_potion": stats})
        action = EquipAction(code="small_health_potion", slot="utility1_slot", quantity=2)
        result = action.apply(state, gd)
        assert result.inventory.get("small_health_potion", 0) == 3
        assert result.equipment["utility1_slot"] == "small_health_potion"

    def test_repr_with_quantity(self):
        action = EquipAction(code="small_health_potion", slot="utility1_slot", quantity=10)
        assert repr(action) == "Equip(small_health_potionx10->utility1_slot)"

    def test_repr_default_quantity(self):
        action = EquipAction(code="copper_dagger", slot="weapon_slot")
        assert repr(action) == "Equip(copper_dagger->weapon_slot)"

    def test_equip_utility_sets_quantity_on_empty_slot(self):
        state = make_state(inventory={"small_health_potion": 50}, level=1,
                           equipment={"utility1_slot": None})
        gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
        out = EquipAction("small_health_potion", "utility1_slot", quantity=30).apply(state, gd)
        assert out.equipment["utility1_slot"] == "small_health_potion"
        assert out.utility1_slot_quantity == 30

    def test_equip_utility_adds_to_existing_same_code_stack(self):
        state = make_state(inventory={"small_health_potion": 50}, level=1,
                           equipment={"utility1_slot": "small_health_potion"})
        state = dataclasses.replace(state, utility1_slot_quantity=20)
        gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
        out = EquipAction("small_health_potion", "utility1_slot", quantity=30).apply(state, gd)
        assert out.utility1_slot_quantity == 50  # 20 + 30

    def test_equip_utility2_sets_quantity_on_empty_slot(self):
        """Equipping into an empty utility2_slot SETS the slot quantity to the
        equipped amount (covers the utility2 apply branch, equip.py:108)."""
        state = make_state(inventory={"small_health_potion": 50}, level=1,
                           equipment={"utility2_slot": None})
        gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
        out = EquipAction("small_health_potion", "utility2_slot", quantity=30).apply(state, gd)
        assert out.equipment["utility2_slot"] == "small_health_potion"
        assert out.utility2_slot_quantity == 30

    def test_equip_utility2_adds_to_existing_same_code_stack(self):
        """Equipping the SAME code into utility2_slot ADDS to the existing stack
        (additive same-code branch through equip.py:108)."""
        state = make_state(inventory={"small_health_potion": 50}, level=1,
                           equipment={"utility2_slot": "small_health_potion"})
        state = dataclasses.replace(state, utility2_slot_quantity=20)
        gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
        out = EquipAction("small_health_potion", "utility2_slot", quantity=30).apply(state, gd)
        assert out.utility2_slot_quantity == 50  # 20 + 30

    def test_equip_blocked_when_displaced_item_needs_slot_and_bag_full(self):
        """Full bag (0 slots free), equipping C displaces a NEW item O not held
        and C's stack does NOT empty (qty=2 held, equipping 1) -> O needs a
        slot -> not applicable (net-slot room guard, equip.py)."""
        stats = ItemStats(code="C", level=1, type_="body_armor")
        inv = {"C": 2, **{f"j{n}": 1 for n in range(19)}}
        state = make_state(
            inventory=inv, inventory_slots_max=20, inventory_max=999, level=5,
            equipment={**make_state().equipment, "body_armor_slot": "O"},
        )
        gd = make_game_data(item_stats={"C": stats})
        action = EquipAction(code="C", slot="body_armor_slot")
        assert action.is_applicable(state, gd) is False

    def test_equip_allowed_when_equipped_stack_frees_slot_for_displaced(self):
        """C has qty 1 -> equipping empties C's slot, which absorbs displaced
        O -> net zero new slots -> applicable even at 0 free slots."""
        stats = ItemStats(code="C", level=1, type_="body_armor")
        inv = {"C": 1, **{f"j{n}": 1 for n in range(19)}}
        state = make_state(
            inventory=inv, inventory_slots_max=20, inventory_max=999, level=5,
            equipment={**make_state().equipment, "body_armor_slot": "O"},
        )
        gd = make_game_data(item_stats={"C": stats})
        action = EquipAction(code="C", slot="body_armor_slot")
        assert action.is_applicable(state, gd) is True

    def test_equip_allowed_when_displaced_item_already_held(self):
        """Displaced O already a held stack -> returning it grows that stack,
        no new slot -> applicable at 0 free slots."""
        stats = ItemStats(code="C", level=1, type_="body_armor")
        inv = {"C": 2, "O": 3, **{f"j{n}": 1 for n in range(18)}}
        state = make_state(
            inventory=inv, inventory_slots_max=20, inventory_max=999, level=5,
            equipment={**make_state().equipment, "body_armor_slot": "O"},
        )
        gd = make_game_data(item_stats={"C": stats})
        action = EquipAction(code="C", slot="body_armor_slot")
        assert action.is_applicable(state, gd) is True


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

    def test_not_applicable_for_utility_potion(self):
        """A type='utility' heal (small_health_potion, subtype potion) has
        hp_restore>0 but is NOT use-able via the action/use endpoint — it heals
        by being EQUIPPED into a utility slot and consumed in combat. Selecting
        it made execute() spin on HTTP 476 'Invalid consumable item' (live
        deadlock 2026-07-02: Robby held 10 small_health_potion with empty utility
        slots and looped UseConsumable forever). Only type='consumable' food is
        use-able, so a bag full of potions must NOT make UseConsumable applicable."""
        stats = {"small_health_potion": ItemStats(code="small_health_potion",
                                                  level=5, type_="utility", hp_restore=30)}
        action = UseConsumableAction(_item_stats=stats)
        state = make_state(hp=73, max_hp=235, inventory={"small_health_potion": 10})
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

    def test_apply_preserves_skill_xp(self):
        """UseConsumableAction.apply must carry skill_xp forward (not reset to {})."""
        action = UseConsumableAction(_item_stats=_consumable_stats())
        state = make_state(hp=50, max_hp=150, inventory={"cooked_chicken": 1},
                           skill_xp={"alchemy": 200})
        new_state = action.apply(state, make_game_data())
        assert new_state.skill_xp == {"alchemy": 200}

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

    def test_consumable_cheap_when_deficit_justifies_it(self):
        # deficit 60 >= potion restore 50 -> cheap (2.0, beats Rest 10.0)
        item_stats = {"potion": ItemStats(code="potion", level=1, type_="consumable", hp_restore=50)}
        action = UseConsumableAction(_item_stats=item_stats)
        state = make_state(hp=40, max_hp=100, inventory={"potion": 3})
        assert action.cost(state, make_game_data()) == 2.0

    def test_consumable_expensive_when_overheal(self):
        # deficit 10 < potion restore 50 -> overheal -> the Rest-forcing sentinel,
        # which must outrank the dearest possible Rest rather than a literal 10.0.
        item_stats = {"potion": ItemStats(code="potion", level=1, type_="consumable", hp_restore=50)}
        action = UseConsumableAction(_item_stats=item_stats)
        state = make_state(hp=90, max_hp=100, inventory={"potion": 3})
        assert action.cost(state, make_game_data()) == OVERHEAL_CONSUMABLE_COST
        assert action.cost(state, make_game_data()) > REST_COST_MAX


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
        gd = make_game_data()
        gd._task_coin_rewards = {"chicken": 1}
        new_state = action.apply(state, gd)
        assert new_state.task_code == ""
        assert new_state.task_total == 0
        assert new_state.task_progress == 0
        assert (new_state.x, new_state.y) == (1, 2)
        # Server reward is items + gold only (RewardsSchema has no XP field);
        # planner XP projection is 0 (TASK_COMPLETE_XP_ESTIMATE).
        assert new_state.xp == state.xp + TASK_COMPLETE_XP_ESTIMATE
        assert TASK_COMPLETE_XP_ESTIMATE == 0

    def test_apply_does_not_grant_xp(self):
        """Server task completion grants items+gold only (RewardsSchema has
        no XP field). The planner-side apply must mirror this — XP unchanged
        on CompleteTaskAction. Lean ``taskCompleteXpEstimate`` def matches."""
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(
            x=0, y=0, xp=12345, task_code="chicken", task_total=10, task_progress=10
        )
        gd = make_game_data()
        gd._task_coin_rewards = {"chicken": 1}
        new_state = action.apply(state, gd)
        assert new_state.xp == state.xp

    def test_cost_includes_distance(self):
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(x=0, y=0)
        assert action.cost(state, make_game_data()) == 1.0 + 3  # dist=3

    def test_repr(self):
        assert repr(CompleteTaskAction(taskmaster_location=(1, 2))) == "CompleteTask"

    def test_apply_mints_tasks_coin_reward(self):
        """CompleteTaskAction.apply mints the task's tasks_coin reward into
        inventory via complete_task_apply_pure + GameData.task_coin_reward.
        The delta must equal the seeded reward (3) and the existing task-clearing
        behaviour must be preserved (task_code=="" / task_total==0)."""
        action = CompleteTaskAction(taskmaster_location=(1, 2))
        state = make_state(
            x=0, y=0,
            task_code="chicken", task_progress=1, task_total=1,
            inventory={"tasks_coin": 2},
        )
        gd = make_game_data()
        gd._task_coin_rewards = {"chicken": 3}
        before = state.inventory.get("tasks_coin", 0)
        new_state = action.apply(state, gd)
        # coin reward minted
        assert new_state.inventory.get("tasks_coin", 0) == before + 3
        # task state still cleared (no regression)
        assert new_state.task_code == ""
        assert new_state.task_total == 0
        assert new_state.task_progress == 0


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

    # Ingredient (regardless of sellable status) → 50
    gd_ingredient = GameData()
    gd_ingredient._crafting_recipes = {"sword": {"iron_ore": 5}}
    assert _delete_cost("iron_ore", gd_ingredient) == 50.0

    gd_ingredient_also_sellable = GameData()
    gd_ingredient_also_sellable._crafting_recipes = {"sword": {"iron_ore": 5}}
    gd_ingredient_also_sellable._npc_sell_prices = {"smith": {"iron_ore": 8}}
    assert _delete_cost("iron_ore", gd_ingredient_also_sellable) == 50.0

    # Sellable but not ingredient → 25
    gd_sellable_only = GameData()
    gd_sellable_only._npc_sell_prices = {"cook": {"raw_meat": 3}}
    assert _delete_cost("raw_meat", gd_sellable_only) == 25.0

    # Neither → 5
    gd_worthless = GameData()
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
        gd._monster_level = {"yellow_slime": 2}
        fill_monster_stat_defaults(gd)
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
        gd = GameData()
        gd._monster_level = {"z": 1}
        fill_monster_stat_defaults(gd)
        # learned cost = 10.0 (only ok cycles counted in action_cost)
        # success_rate = 0.5 (5 ok / 10 total)
        # cost = 10.0 / 0.5 = 20.0
        assert action.cost(state, gd, history=store) == 20.0
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


class TestDepositAllSelective:
    def _gd(self):
        gd = make_game_data()
        gd._npc_sell_prices = {"m": {"gold_ore": 50, "sap": 3}}
        gd._item_stats = {
            "gold_ore": ItemStats(code="gold_ore", level=1, type_="resource"),
            "sap": ItemStats(code="sap", level=1, type_="resource"),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        return gd

    def test_apply_deposits_only_selected_keeps_task_item(self):
        gd = self._gd()
        action = DepositAllAction(bank_location=(4, 1), accessible=True, game_data=gd)
        state = make_state(x=0, y=0, inventory={"gold_ore": 1, "copper_ore": 5},
                           task_code="copper_ore", task_type="items", task_total=5,
                           bank_items={})
        new_state = action.apply(state, gd)
        assert new_state.inventory == {"copper_ore": 5}   # task item kept (5 still owed)
        assert new_state.bank_items == {"gold_ore": 1}    # junk banked
        assert (new_state.x, new_state.y) == (4, 1)

    def test_not_applicable_when_nothing_bankable(self):
        gd = self._gd()
        action = DepositAllAction(bank_location=(4, 1), accessible=True, game_data=gd)
        state = make_state(inventory={"copper_ore": 5}, task_code="copper_ore",
                           task_type="items", task_total=5)
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_without_game_data(self):
        action = DepositAllAction(bank_location=(4, 1), accessible=True)
        state = make_state(inventory={"sap": 1})
        assert action.is_applicable(state, make_game_data()) is False

    def test_not_applicable_when_inaccessible(self):
        gd = self._gd()
        action = DepositAllAction(bank_location=(4, 1), accessible=False, game_data=gd)
        state = make_state(inventory={"sap": 1})
        assert action.is_applicable(state, gd) is False


class TestGatherRareDropTargeting:
    """P1 (engagement expansion): rare multi-drop targeting."""

    def test_override_apply_credits_secondary_drop(self):
        from artifactsmmo_cli.ai.actions.gathering import GatherAction
        gd = GameData()
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._resource_drops_full = {
            "copper_rocks": [("copper_ore", 1, 1, 1), ("emerald_stone", 200, 1, 1)],
        }
        gd._resource_skill = {"copper_rocks": ("mining", 1)}
        action = GatherAction(resource_code="copper_rocks",
                              locations=frozenset({(0, 0)}),
                              drop_item_override="emerald_stone")
        state = make_state(x=0, y=0, inventory={}, inventory_max=20)
        post = action.apply(state, gd)
        assert post.inventory.get("emerald_stone") == 1
        assert repr(action) == "Gather(copper_rocks->emerald_stone)"

    def test_factory_emits_targeted_gathers_for_secondary_drops(self):
        from artifactsmmo_cli.ai.actions.factory import build_actions
        gd = GameData()
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._resource_drops_full = {
            "copper_rocks": [("copper_ore", 1, 1, 1), ("emerald_stone", 200, 1, 1)],
        }
        gd._resource_skill = {"copper_rocks": ("mining", 1)}
        gd._resource_locations = {"copper_rocks": [(0, 0)]}
        gd.world.bank_tile = (1, 1)
        gd.world.taskmaster_tile = (2, 2)
        actions = build_actions(gd, None, None, bank_accessible=False,
                                task_exchange_min_coins=0)
        names = {repr(a) for a in actions}
        assert "Gather(copper_rocks)" in names
        assert "Gather(copper_rocks->emerald_stone)" in names


def test_factory_emits_equip_for_owned_recipeless_equippable():
    """A recipe-less, NPC-bought equippable (sandwhisper_bag) got NO
    EquipAction — the factory only enumerated equips for items with crafting
    recipes, so even with the bag IN HAND UpgradeEquipment's closure-locked
    search died at 0 plans (probe 2026-07-06 @L50). Owned (inventory or
    bank) equippables must get their EquipAction (+ Withdraw for banked)."""
    from artifactsmmo_cli.ai.actions.factory import build_actions
    from tests.test_ai.fixtures import make_state
    gd = GameData()
    gd._item_stats = {
        "dune_bag": ItemStats(code="dune_bag", level=1, type_="bag",
                              inventory_space=10),
    }
    gd.world.bank_tile = (1, 1)
    gd.world.taskmaster_tile = (2, 2)
    held = make_state(inventory={"dune_bag": 1})
    names = {repr(a) for a in build_actions(gd, held, None, bank_accessible=True,
                                            task_exchange_min_coins=0)}
    assert "Equip(dune_bag->bag_slot)" in names, sorted(
        n for n in names if "dune" in n)
    banked = make_state(bank_items={"dune_bag": 1})
    names_b = {repr(a) for a in build_actions(gd, banked, None, bank_accessible=True,
                                              task_exchange_min_coins=0)}
    assert "Equip(dune_bag->bag_slot)" in names_b
    assert any(n.startswith("Withdraw(dune_bag") for n in names_b), sorted(
        n for n in names_b if "dune" in n)
