"""Tests for CraftAction execute yield-recording (Task 2)."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from artifactsmmo_api_client.models.drop_schema import DropSchema
from artifactsmmo_api_client.models.skill_info_schema import SkillInfoSchema

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema


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
