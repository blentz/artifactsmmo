"""Tests for CraftAction apply (yield credits) and execute yield-recording."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from artifactsmmo_api_client.models.drop_schema import DropSchema
from artifactsmmo_api_client.models.skill_info_schema import SkillInfoSchema

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema
from tests.test_ai._monster_fixture import fill_monster_stat_defaults


def _make_crafting_game_data(
    code: str,
    recipe: dict[str, int],
    craft_yield_value: int = 1,
    crafting_skill: str = "weaponcrafting",
    crafting_level: int = 1,
) -> GameData:
    """Build a minimal GameData with one craftable item."""
    gd = GameData()
    gd._item_stats = {
        code: ItemStats(
            code=code,
            level=1,
            type_="weapon",
            crafting_skill=crafting_skill,
            crafting_level=crafting_level,
        )
    }
    gd._crafting_recipes = {code: recipe}
    gd._craft_yields = {code: craft_yield_value} if craft_yield_value != 1 else {}
    gd._resource_skill = {}
    gd._monster_level = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


def _make_craft_api_result(char, *, item_code: str, produced: int, xp: int):
    """Build a mock craft API response with SkillInfoSchema details."""
    details = SkillInfoSchema(
        xp=xp,
        items=[DropSchema(code=item_code, quantity=produced)],
    )
    result = MagicMock()
    result.data = MagicMock()
    result.data.character = char
    result.data.details = details
    return result


class TestCraftActionExecuteRecordsYield:
    def test_execute_records_produced_qty_and_xp(self, tmp_path):
        """execute records the observed craft yield and XP into LearningStore."""
        store = LearningStore(db_path=str(tmp_path / "l.db"), character="testchar")
        action = CraftAction(
            code="copper_dagger",
            quantity=1,
            workshop_location=(3, 0),
            history=store,
        )
        state = make_state(x=3, y=0)
        client = MagicMock()
        char = make_char_schema()
        api_result = _make_craft_api_result(char, item_code="copper_dagger", produced=2, xp=15)

        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=api_result):
            action.execute(state, client)

        assert store.observed_craft_yield("copper_dagger") == (2, 15)
        store.close()

    def test_execute_sums_quantity_for_crafted_code(self, tmp_path):
        """Only drops matching self.code contribute to produced quantity."""
        store = LearningStore(db_path=str(tmp_path / "l.db"), character="testchar")
        # Craft response includes a bonus drop with a different code
        details = SkillInfoSchema(
            xp=20,
            items=[
                DropSchema(code="copper_dagger", quantity=1),
                DropSchema(code="copper_ore", quantity=3),  # byproduct — ignored
                DropSchema(code="copper_dagger", quantity=1),  # second drop same code
            ],
        )
        result = MagicMock()
        result.data = MagicMock()
        result.data.character = make_char_schema()
        result.data.details = details

        action = CraftAction(
            code="copper_dagger",
            quantity=1,
            workshop_location=(3, 0),
            history=store,
        )
        state = make_state(x=3, y=0)

        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=result):
            action.execute(state, MagicMock())

        # Quantities of copper_dagger summed: 1 + 1 = 2
        assert store.observed_craft_yield("copper_dagger") == (2, 20)
        store.close()

    def test_execute_without_history_does_not_crash(self):
        """execute with history=None is safe — no recording attempt."""
        action = CraftAction(
            code="copper_dagger",
            quantity=1,
            workshop_location=(3, 0),
        )
        state = make_state(x=3, y=0)
        char = make_char_schema()
        api_result = _make_craft_api_result(char, item_code="copper_dagger", produced=1, xp=5)

        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=api_result):
            new_state = action.execute(state, MagicMock())

        assert new_state is not None

    def test_execute_updates_existing_yield_record(self, tmp_path):
        """Second craft call overwrites the previous observation (last write wins)."""
        store = LearningStore(db_path=str(tmp_path / "l.db"), character="testchar")
        action = CraftAction(
            code="copper_dagger",
            quantity=1,
            workshop_location=(3, 0),
            history=store,
        )
        state = make_state(x=3, y=0)
        char = make_char_schema()

        api_result_1 = _make_craft_api_result(char, item_code="copper_dagger", produced=2, xp=10)
        api_result_2 = _make_craft_api_result(char, item_code="copper_dagger", produced=3, xp=12)

        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=api_result_1):
            action.execute(state, MagicMock())
        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=api_result_2):
            action.execute(state, MagicMock())

        assert store.observed_craft_yield("copper_dagger") == (3, 12)
        store.close()


class TestCraftActionApplyYield:
    """Task 3: apply credits runs×Y for inventory, task_progress, xp-proxy."""

    def test_apply_yield2_credits_runs_times_Y_to_inventory(self):
        """Crafting 3 runs of a yield-2 item credits 6 to inventory."""
        gd = _make_crafting_game_data("potion", {"herb": 1}, craft_yield_value=2)
        state = make_state(inventory={"herb": 10})
        action = CraftAction(code="potion", quantity=3)

        new_state = action.apply(state, gd)

        assert new_state.inventory.get("potion", 0) == 6  # 3 runs × 2 yield

    def test_apply_yield1_unchanged_from_today(self):
        """Y=1 (all live recipes today): credits runs×1, same as before."""
        gd = _make_crafting_game_data("copper_dagger", {"copper_ore": 6}, craft_yield_value=1)
        state = make_state(inventory={"copper_ore": 18})
        action = CraftAction(code="copper_dagger", quantity=3)

        new_state = action.apply(state, gd)

        assert new_state.inventory.get("copper_dagger", 0) == 3  # 3 runs × 1
        assert new_state.inventory.get("copper_ore", 0) == 0     # 18 consumed

    def test_apply_yield2_task_progress_uses_produced(self):
        """task_progress advances by runs×Y when task matches crafted item."""
        gd = _make_crafting_game_data("potion", {"herb": 1}, craft_yield_value=2)
        state = make_state(
            inventory={"herb": 10},
            task_code="potion",
            task_type="crafting",
            task_progress=0,
            task_total=20,
        )
        action = CraftAction(code="potion", quantity=3)

        new_state = action.apply(state, gd)

        assert new_state.task_progress == 6  # 3 runs × 2

    def test_apply_yield1_task_progress_unchanged(self):
        """Y=1: task_progress advances by quantity (same as before)."""
        gd = _make_crafting_game_data("copper_dagger", {"copper_ore": 6}, craft_yield_value=1)
        state = make_state(
            inventory={"copper_ore": 18},
            task_code="copper_dagger",
            task_type="crafting",
            task_progress=0,
            task_total=10,
        )
        action = CraftAction(code="copper_dagger", quantity=3)

        new_state = action.apply(state, gd)

        assert new_state.task_progress == 3  # 3 runs × 1

    def test_apply_ingredient_consumption_unchanged(self):
        """Ingredient consumption is per-run (mat_qty × quantity), unaffected by yield."""
        gd = _make_crafting_game_data("potion", {"herb": 2}, craft_yield_value=2)
        state = make_state(inventory={"herb": 20})
        action = CraftAction(code="potion", quantity=4)

        new_state = action.apply(state, gd)

        # ingredients: 2 herb/run × 4 runs = 8 consumed; 20 - 8 = 12 remaining
        assert new_state.inventory.get("herb", 0) == 12
        # output: 4 runs × 2 yield = 8
        assert new_state.inventory.get("potion", 0) == 8
