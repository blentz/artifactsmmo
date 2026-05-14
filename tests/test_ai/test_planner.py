"""Tests for the GOAP planner A* search."""

from unittest.mock import patch

from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.survival import RestoreHPGoal
from artifactsmmo_cli.ai.goals.combat import FarmMonsterGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def make_game_data(monster_locs=None, monster_levels=None) -> GameData:
    gd = GameData()
    gd._monster_locations = monster_locs or {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._monster_level = monster_levels or {}
    return gd


class _ShallowGoal(RestoreHPGoal):
    """RestoreHP goal with max_depth=1 for testing depth cutoff."""

    @property
    def max_depth(self) -> int:
        return 1


class TestGOAPPlanner:
    def test_rest_plan_when_hp_low(self):
        planner = GOAPPlanner()
        state = make_state(hp=50, max_hp=150)
        goal = RestoreHPGoal()
        actions = [RestAction()]
        gd = make_game_data()
        plan = planner.plan(state, goal, actions, gd)
        assert len(plan) == 1
        assert isinstance(plan[0], RestAction)

    def test_empty_plan_when_goal_already_satisfied(self):
        planner = GOAPPlanner()
        state = make_state(hp=150, max_hp=150)
        goal = RestoreHPGoal()
        actions = [RestAction()]
        gd = make_game_data()
        plan = planner.plan(state, goal, actions, gd)
        assert plan == []

    def test_fight_plan_without_explicit_move(self):
        planner = GOAPPlanner()
        state = make_state(x=0, y=0, hp=150, max_hp=150, xp=0, max_xp=500, level=1)
        goal = FarmMonsterGoal(monster_code="chicken", initial_xp=0)
        actions = [FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))]
        gd = make_game_data(monster_locs={"chicken": [(1, 0)]}, monster_levels={"chicken": 1})
        plan = planner.plan(state, goal, actions, gd)
        # FightAction handles movement itself — plan is a single step
        assert len(plan) == 1
        assert isinstance(plan[0], FightAction)

    def test_stops_at_max_depth(self):
        planner = GOAPPlanner()
        state = make_state(hp=50, max_hp=150)
        goal = _ShallowGoal()
        actions = [MoveAction(x=1, y=0)]  # no action can satisfy RestoreHP
        gd = make_game_data()
        plan = planner.plan(state, goal, actions, gd)
        assert plan == []
        assert planner.last_stats.max_depth_reached <= 1

    def test_returns_empty_list_when_no_plan_possible(self):
        planner = GOAPPlanner()
        state = make_state(hp=50, max_hp=150)
        goal = RestoreHPGoal()
        actions = [MoveAction(x=5, y=5)]  # can't satisfy RestoreHP with only Move
        gd = make_game_data()
        plan = planner.plan(state, goal, actions, gd)
        assert plan == []

    def test_plan_within_depth_limit(self):
        planner = GOAPPlanner()
        state = make_state(hp=50, max_hp=150)
        goal = _ShallowGoal()
        actions = [RestAction()]
        gd = make_game_data()
        plan = planner.plan(state, goal, actions, gd)
        assert len(plan) <= 1

    def test_timeout_sets_timed_out_flag(self):
        planner = GOAPPlanner()
        state = make_state(hp=50, max_hp=150)
        goal = RestoreHPGoal()
        # Deadline already past — planner times out on first iteration
        with patch("artifactsmmo_cli.ai.planner.time.monotonic", side_effect=[0.0, float("inf")]):
            plan = planner.plan(state, goal, [RestAction()], make_game_data())
        assert plan == []
        assert planner.last_stats.timed_out is True

    def test_last_stats_populated_on_success(self):
        planner = GOAPPlanner()
        state = make_state(hp=50, max_hp=150)
        goal = RestoreHPGoal()
        plan = planner.plan(state, goal, [RestAction()], make_game_data())
        assert plan != []
        assert planner.last_stats.nodes_explored > 0
