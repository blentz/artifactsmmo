"""The arbiter's ONE-BUDGET walk, asked afresh every cycle.

This module used to test a cheap/full TWO-PASS budget scheme and then a
doomed-memo that aged no-plans over a 20-160-cycle window. Both are deleted: the
walk runs at one budget (`planner._SEARCH_BUDGET_SECONDS`, passed as None), and
since Phase 3-1 nothing is remembered between cycles. A walk-served goal's
answer is decomposition's plan or its named decline, read from live state, so a
no-plan goal is asked again next cycle and becomes eligible exactly when the
state that blocked it changes.

A scripted planner returns a plan only for the goal reprs it is told to, letting
us assert walk behaviour deterministically."""
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx, _FakeDecision, _make_planner_gd


class _ScriptedPlanner:
    """Plans `[WaitAction()]` for goal reprs in `plannable`; everything else gets
    no plan, reported as a budget TIMEOUT when the repr is in `timing_out` and as
    an exhausted search otherwise. Records the budget it was handed per goal."""
    def __init__(self, plannable=(), timing_out=()):
        self.plannable = set(plannable)
        self.timing_out = set(timing_out)
        self.budgets = []
        self.last_stats = GOAPPlanner().last_stats

    def plan(self, state, goal, actions, game_data, history=None, *, budget_seconds=None):
        r = repr(goal)
        self.budgets.append((r, budget_seconds))
        if r in self.plannable:
            self.last_stats.timed_out = False
            return [WaitAction()]
        self.last_stats.timed_out = r in self.timing_out
        return []


def _arbiter_with(planner):
    return StrategyArbiter(planner, history=None)


def test_every_candidate_is_planned_at_the_one_budget():
    """The walk selects the plannable candidate, and the planner is handed None —
    the one budget — for it. A resurrected cheap first pass would show up here as
    a numeric budget."""
    planner = _ScriptedPlanner(plannable={"AcceptTask"})
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    decision = _FakeDecision(chosen_step=None)
    goal, _plan, _ = a.select(decision, state, _make_planner_gd(),
                              [AcceptTaskAction(taskmaster_location=(2, 1))],
                              _ctx(combat_monster="chicken"))
    assert repr(goal) == "AcceptTask"
    assert planner.budgets, "the planner must actually have been consulted"
    assert all(b is None for (_r, b) in planner.budgets), planner.budgets


def test_a_no_plan_goal_is_asked_again_next_cycle():
    """Nothing is remembered between cycles (Phase 3-1). A goal that produced no
    plan, timed out or exhausted, is planned again on the next cycle with the
    same state: there is no doomed-memo to skip it, so a goal becomes eligible
    again as soon as its blocker clears rather than after an aging window."""
    planner = _ScriptedPlanner(timing_out={"AcceptTask"})
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    ctx = _ctx(combat_monster="chicken")
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    goal0, _, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    calls_cycle0 = len([1 for (r, _) in planner.budgets if r == "AcceptTask"])
    planner.budgets.clear()
    goal1, _, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    calls_cycle1 = len([1 for (r, _) in planner.budgets if r == "AcceptTask"])
    assert isinstance(goal0, WaitGoal) and isinstance(goal1, WaitGoal)
    assert calls_cycle0 >= 1
    assert calls_cycle1 == calls_cycle0, "a no-plan goal must be asked again next cycle"


def test_wait_selected_when_nothing_plans():
    planner = _ScriptedPlanner()
    a = _arbiter_with(planner)
    state = make_state(task_code="chicken", task_type="monsters", task_progress=0, task_total=5)
    goal, plan, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), [], _ctx())
    assert isinstance(goal, WaitGoal)
    assert len(plan) == 1 and isinstance(plan[0], WaitAction)


def test_plans_short_circuits_wait_goal_without_invoking_planner():
    """_plans special-cases WaitGoal: it returns a single-WaitAction plan and
    records a zero-node goals_tried entry WITHOUT calling the planner (which
    would never terminate on the no-op WaitAction)."""
    planner = _ScriptedPlanner()
    a = _arbiter_with(planner)
    state = make_state()
    plan = a._plans(WaitGoal(), state, _make_planner_gd(), [], _ctx())
    assert len(plan) == 1 and isinstance(plan[0], WaitAction)
    # Planner was never consulted for the Wait goal.
    assert planner.budgets == []
    # A diagnostic goals_tried entry was recorded for the Wait attempt.
    assert any(entry["goal"] == repr(WaitGoal()) and entry["nodes"] == 0
               for entry in a.goals_tried)
