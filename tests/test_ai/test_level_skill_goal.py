"""Tests for LevelSkillGoal (Phase G-E)."""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.level_skill import (
    MAX_SKILL_GAP,
    PRIORITY_WHEN_FIRING,
    LevelSkillGoal,
)
from tests.test_ai.fixtures import make_state


def _gd_with_weapon_recipes() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        ),
        "iron_dagger": ItemStats(
            code="iron_dagger", level=10, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=10,
        ),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "iron_dagger": {"iron_bar": 6},
    }
    return gd


class TestPriority:
    def test_zero_when_already_at_target(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 3})
        assert goal.priority(state, _gd_with_weapon_recipes()) == 0.0

    def test_zero_when_gap_too_large(self):
        goal = LevelSkillGoal("weaponcrafting", 1 + MAX_SKILL_GAP + 1)
        state = make_state(skills={"weaponcrafting": 1})
        assert goal.priority(state, _gd_with_weapon_recipes()) == 0.0

    def test_fires_with_small_gap_and_craftable(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 1})
        assert goal.priority(state, _gd_with_weapon_recipes()) == PRIORITY_WHEN_FIRING

    def test_zero_when_no_craftable_in_skill(self):
        """Skill exists but no recipe at current skill level → grinding impossible."""
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 0})  # below copper_dagger's level 1
        assert goal.priority(state, _gd_with_weapon_recipes()) == 0.0


class TestSatisfaction:
    def test_satisfied_at_target(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        assert goal.is_satisfied(make_state(skills={"weaponcrafting": 3})) is True

    def test_satisfied_above_target(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        assert goal.is_satisfied(make_state(skills={"weaponcrafting": 5})) is True

    def test_unsatisfied_below_target(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        assert goal.is_satisfied(make_state(skills={"weaponcrafting": 2})) is False


class TestRelevantActions:
    def test_includes_craft_in_skill_family(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        gd = _gd_with_weapon_recipes()
        actions = [
            RestAction(),
            CraftAction(code="copper_dagger", quantity=1),
            CraftAction(code="ash_plank", quantity=1),  # different skill
            GatherAction(resource_code="copper_rocks"),
        ]
        relevant = goal.relevant_actions(actions, make_state(), gd)
        codes = [a.code if isinstance(a, CraftAction) else None for a in relevant]
        assert "copper_dagger" in codes
        assert "ash_plank" not in codes
        assert any(isinstance(a, RestAction) for a in relevant)
        assert any(isinstance(a, GatherAction) for a in relevant)


class TestRepr:
    def test_repr_includes_skill_and_target(self):
        assert repr(LevelSkillGoal("woodcutting", 5)) == "LevelSkill(woodcutting->5)"
