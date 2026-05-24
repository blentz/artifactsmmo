"""Tests for the GOAP planner A* search."""

from unittest.mock import patch

from artifactsmmo_cli.ai import planner as planner_mod
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task import AcceptTaskAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.survival import RestoreHPGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def test_search_budget_spans_a_game_cooldown():
    """Deep recipe chains (e.g. 6 ash_plank = 60 ash_wood, ~2800 search nodes)
    become I/O-bound when learned costs query SQLite per node — such a search
    needs ~7.5s. The budget must comfortably exceed that while staying within the
    game's 60s+ action cooldown (we plan during the prior action's cooldown), so
    a deep-but-reachable goal is never abandoned as a false no_plan."""
    assert planner_mod._SEARCH_BUDGET_SECONDS >= 90.0


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

    def test_accept_task_plan_single_step(self):
        planner = GOAPPlanner()
        state = make_state(x=0, y=0, task_code="")
        goal = AcceptTaskGoal()
        actions = [AcceptTaskAction(taskmaster_location=(1, 2))]
        gd = make_game_data()
        gd._taskmaster_location = (1, 2)
        plan = planner.plan(state, goal, actions, gd)
        # AcceptTaskAction handles movement itself — plan is a single step
        assert len(plan) == 1
        assert isinstance(plan[0], AcceptTaskAction)

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

    def test_accept_task_picks_single_step_when_already_at_taskmaster(self):
        """Regression: _state_key must include task_code so the AcceptTask child
        is not treated as a duplicate of the root state when position is
        unchanged. Otherwise the planner is forced into longer detours."""
        planner = GOAPPlanner()
        state = make_state(x=2, y=13, task_code=None, task_total=0, gold=100)
        goal = AcceptTaskGoal()
        gd = make_game_data()
        gd._npc_sell_prices = {}
        # NpcBuy at a different tile is the detour the planner used to pick.
        npc = NpcBuyAction(
            npc_code="cultist_wizard",
            item_code="corrupted_fruit",
            quantity=1,
            npc_location=(4, 13),
        )
        gd_with_npc = make_game_data()
        gd_with_npc._npc_stock = {"cultist_wizard": {"corrupted_fruit": 10}}
        actions = [AcceptTaskAction(taskmaster_location=(2, 13)), npc]
        plan = planner.plan(state, goal, actions, gd_with_npc)
        assert len(plan) == 1
        assert isinstance(plan[0], AcceptTaskAction)

    def test_plan_accepts_history_parameter(self):
        """GOAPPlanner.plan should accept history (and ignore None gracefully)."""
        planner = GOAPPlanner()
        state = make_state(hp=50, max_hp=100)
        goal = RestoreHPGoal()
        actions = [RestAction()]
        plan = planner.plan(state, goal, actions, GameData(), history=None)
        assert len(plan) == 1
        assert isinstance(plan[0], RestAction)
