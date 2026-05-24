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
from artifactsmmo_cli.ai.planner import GOAPPlanner
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
        assert goal.value(state, _gd_with_weapon_recipes()) == 0.0

    def test_zero_when_gap_too_large(self):
        goal = LevelSkillGoal("weaponcrafting", 1 + MAX_SKILL_GAP + 1)
        state = make_state(skills={"weaponcrafting": 1})
        assert goal.value(state, _gd_with_weapon_recipes()) == 0.0

    def test_fires_with_small_gap_and_craftable(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 1})
        assert goal.value(state, _gd_with_weapon_recipes()) == PRIORITY_WHEN_FIRING

    def test_zero_when_no_craftable_in_skill(self):
        """Skill exists but no recipe at current skill level → grinding impossible."""
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 0})  # below copper_dagger's level 1
        assert goal.value(state, _gd_with_weapon_recipes()) == 0.0


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

    def test_satisfied_by_skill_xp_progress(self):
        """is_satisfied returns True when skill_xp > initial_skill_xp, even if level not reached."""
        goal = LevelSkillGoal("weaponcrafting", 50, initial_skill_xp=0)
        state = make_state(skills={"weaponcrafting": 1}, skill_xp={"weaponcrafting": 5})
        assert goal.is_satisfied(state) is True

    def test_unsatisfied_when_no_xp_progress_and_level_below(self):
        """is_satisfied returns False when skill_xp == initial AND level < target."""
        goal = LevelSkillGoal("weaponcrafting", 50, initial_skill_xp=10)
        state = make_state(skills={"weaponcrafting": 1}, skill_xp={"weaponcrafting": 10})
        assert goal.is_satisfied(state) is False

    def test_satisfied_when_level_at_target_regardless_of_xp(self):
        """is_satisfied returns True when skills[skill] >= target, even if initial_skill_xp set."""
        goal = LevelSkillGoal("weaponcrafting", 5, initial_skill_xp=999)
        state = make_state(skills={"weaponcrafting": 5}, skill_xp={"weaponcrafting": 999})
        assert goal.is_satisfied(state) is True


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


def _gd_with_alchemy_resource() -> GameData:
    """GameData with an alchemy-skill resource so GatherAction bumps alchemy skill_xp."""
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_skill = {"sunflower_field": ("alchemy", 1)}
    gd._resource_locations = {"sunflower_field": [(3, 0)]}
    gd._workshop_locations = {}
    gd._monster_locations = {}
    gd._monster_level = {}
    gd._bank_location = (4, 0)
    return gd


class TestPlannerIntegration:
    """Decisive integration test: proves the skill goal is now plannable (was: 646k nodes / timeout)."""

    def test_gather_alchemy_resource_satisfies_level_skill_goal(self):
        """
        LevelSkillGoal("alchemy", target_level=2, initial_skill_xp=0) must be satisfied
        by a single GatherAction on an alchemy resource (sunflower_field).
        Before the fix: planner explored to 646k-node timeout.
        After the fix: plan has exactly 1 action, no timeout, and < 50 nodes explored.
        """
        gd = _gd_with_alchemy_resource()
        state = make_state(
            skills={"alchemy": 1},
            skill_xp={"alchemy": 0},
            hp=150,
            max_hp=150,
            inventory={},
            inventory_max=20,
            x=0,
            y=0,
        )
        goal = LevelSkillGoal("alchemy", target_level=2, initial_skill_xp=0)
        actions = [GatherAction(resource_code="sunflower_field", locations=frozenset([(3, 0)]))]

        planner = GOAPPlanner()
        plan = planner.plan(state, goal, actions, gd, None)
        stats = planner.last_stats

        assert plan, "planner must return a non-empty plan (was timing out before fix)"
        assert len(plan) == 1, f"expected 1-step plan, got {len(plan)}: {plan}"
        assert isinstance(plan[0], GatherAction), f"expected GatherAction, got {plan[0]!r}"
        assert stats.timed_out is False, "planner must NOT time out"
        assert stats.nodes_explored < 50, (
            f"BLOCKED: expected < 50 nodes, got {stats.nodes_explored} "
            f"(timed_out={stats.timed_out}). The fix is not working."
        )
