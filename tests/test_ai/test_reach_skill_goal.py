"""Tests for ReachSkillGoal (P3a Task 2): a thin goal that aims the planner-native
LevelSkill action so the PURSUE_TASK skill grind routes through LevelSkill instead
of the old LevelSkillGoal (retired in P3b)."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from tests.test_ai.fixtures import make_state


def _gd_with_alchemy_resource() -> GameData:
    """GameData with an alchemy-skill resource so LevelSkill(alchemy).is_applicable
    is True (best_gather_resource_drop returns a drop usable at level 1)."""
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


class TestSatisfaction:
    def test_unsatisfied_below_target(self):
        goal = ReachSkillGoal("alchemy", 5)
        assert goal.is_satisfied(make_state(skills={"alchemy": 1})) is False

    def test_satisfied_at_target(self):
        goal = ReachSkillGoal("alchemy", 5)
        assert goal.is_satisfied(make_state(skills={"alchemy": 5})) is True

    def test_satisfied_above_target(self):
        goal = ReachSkillGoal("alchemy", 5)
        assert goal.is_satisfied(make_state(skills={"alchemy": 7})) is True

    def test_unsatisfied_when_skill_absent_defaults_to_one(self):
        goal = ReachSkillGoal("alchemy", 5)
        assert goal.is_satisfied(make_state(skills={})) is False


class TestValue:
    def test_fires_at_55_when_unsatisfied(self):
        goal = ReachSkillGoal("alchemy", 5)
        gd = _gd_with_alchemy_resource()
        assert goal.value(make_state(skills={"alchemy": 1}), gd) == 55.0

    def test_zero_when_satisfied(self):
        goal = ReachSkillGoal("alchemy", 5)
        gd = _gd_with_alchemy_resource()
        assert goal.value(make_state(skills={"alchemy": 5}), gd) == 0.0




class TestDesiredStateAndDepth:
    def test_desired_state_targets_skill(self):
        goal = ReachSkillGoal("alchemy", 5)
        assert goal.desired_state(make_state(), _gd_with_alchemy_resource()) == {
            "skills": {"alchemy": 5}}

    def test_max_depth_matches_level_skill_goal(self):
        assert ReachSkillGoal("alchemy", 5).max_depth == 100


class TestRepr:
    def test_repr(self):
        assert repr(ReachSkillGoal("alchemy", 5)) == "ReachSkill(alchemy->5)"


class TestSerialize:
    def test_round_trips(self):
        goal = ReachSkillGoal("alchemy", 5)
        d = goal.serialize()
        assert d == {"type": "ReachSkillGoal", "skill_name": "alchemy",
                     "target_level": 5}


