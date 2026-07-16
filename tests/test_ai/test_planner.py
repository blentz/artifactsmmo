"""Tests for the GOAP planner A* search."""

import os
import tempfile
from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai import planner as planner_mod
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


@pytest.fixture
def tmp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


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


def _insert_cycles(store: LearningStore, action_repr: str, cooldowns: list[float]) -> None:
    """Seed Cycle rows for a given action_repr."""
    for i, cd in enumerate(cooldowns):
        store.record_cycle(Cycle(
            ts=f"2026-05-17T00:00:{i:02d}+00:00",
            session_id="x", cycle_index=i, character="x", outcome="ok",
            action_repr=action_repr,
            actual_cooldown_seconds=cd,
        ))


def test_plan_caches_learned_queries(tmp_db_path):
    """plan() wraps the search loop in search_cache, so learned-stat queries are
    issued at most once per distinct (repr, window) key, not per A* node."""
    store = LearningStore(db_path=tmp_db_path, character="testchar")
    store.start_session()
    # Seed enough cycles so success_rate returns a real value (not the default)
    _insert_cycles(store, str(RestAction()), [12.0] * 10)

    calls: list[int] = []
    original = store._success_rate_uncached

    def counting_uncached(action_repr: str, window: int) -> float:
        calls.append(1)
        return original(action_repr, window)

    store._success_rate_uncached = counting_uncached  # type: ignore[method-assign]

    planner = GOAPPlanner()
    state = make_state(hp=50, max_hp=100)
    goal = RestoreHPGoal()
    actions = [RestAction()]
    gd = make_game_data()

    plan_with_store = planner.plan(state, goal, actions, gd, history=store)
    nodes_explored = planner.last_stats.nodes_explored

    # The plan should be correct (RestAction satisfies RestoreHPGoal)
    assert len(plan_with_store) == 1
    assert isinstance(plan_with_store[0], RestAction)

    # With caching, uncached was called at most once per (repr, window),
    # NOT once per node explored
    assert len(calls) <= nodes_explored
    # Specifically: success_rate for RestAction should be cached — at most 1 real call
    assert len(calls) <= 1

    # Verify the plan is the same as without history (correctness regression)
    plan_no_store = planner.plan(state, goal, actions, gd, history=None)
    assert len(plan_no_store) == len(plan_with_store)

    store.close()


class _RecordingHeuristicGoal(RestoreHPGoal):
    """Records the states the planner asks a heuristic for; returns 0.0 so the
    plan is byte-identical to Dijkstra (this proves the SEAM, not a bias)."""

    def __init__(self) -> None:
        super().__init__()
        self.asked: list = []

    def heuristic(self, state, game_data) -> float:
        self.asked.append(state)
        return 0.0


def test_planner_invokes_goal_heuristic_on_root_and_children():
    goal = _RecordingHeuristicGoal()
    state = make_state(hp=50, max_hp=150)
    plan = GOAPPlanner().plan(state, goal, [RestAction()], GameData())
    assert goal.asked, "planner never called goal.heuristic"
    assert state in goal.asked, "planner did not ask h for the ROOT state"
    assert plan  # a rest plan still forms — h=0.0 leaves behavior unchanged
