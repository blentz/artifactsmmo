"""Tiered selection: cheap pass, escalate only when cheap empty, memoize timeouts.

A scripted planner returns a plan for a goal only when given >= its required
budget, letting us assert pass behavior deterministically."""
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import CHEAP_BUDGET_SECONDS as CHEAP
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx, _FakeDecision, _make_planner_gd


class _ScriptedPlanner:
    """Plans `[WaitAction()]` for goal reprs in `cheap_ok` at any budget; for reprs
    in `full_only` only when budget is None (full). Records budgets per goal."""
    def __init__(self, cheap_ok, full_only):
        self.cheap_ok = set(cheap_ok)
        self.full_only = set(full_only)
        self.budgets = []
        self.last_stats = GOAPPlanner().last_stats

    def plan(self, state, goal, actions, game_data, history=None, *, budget_seconds=None):
        r = repr(goal)
        self.budgets.append((r, budget_seconds))
        if r in self.cheap_ok:
            return [WaitAction()]
        if r in self.full_only and budget_seconds is None:
            return [WaitAction()]
        return []


def test_cheap_budget_constant_is_one_second():
    assert CHEAP == 1.0


def _arbiter_with(planner):
    a = StrategyArbiter(planner, history=None)
    a.set_cycle(0)
    return a


def test_cheap_pass_selects_cheaply_plannable_and_skips_escalation():
    # A discretionary goal that plans cheap is selected; planner never asked for full budget.
    planner = _ScriptedPlanner(cheap_ok={"AcceptTask"}, full_only=set())
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    decision = _FakeDecision(chosen_step=None)
    goal, _plan, _ = a.select(decision, state, _make_planner_gd(),
                              [AcceptTaskAction(taskmaster_location=(2, 1))], _ctx(combat_monster="chicken"))
    assert repr(goal) == "AcceptTask"
    assert all(b == CHEAP for (r, b) in planner.budgets if r == "AcceptTask")


def test_escalates_to_full_when_nothing_cheap():
    # AcceptTask only plans at full budget → cheap pass empty → escalation selects it.
    planner = _ScriptedPlanner(cheap_ok=set(), full_only={"AcceptTask"})
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    goal, _plan, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(),
                              [AcceptTaskAction(taskmaster_location=(2, 1))], _ctx(combat_monster="chicken"))
    assert repr(goal) == "AcceptTask"
    assert any(b is None for (r, b) in planner.budgets if r == "AcceptTask")


def test_timed_out_goal_is_memoized_and_skipped_next_cycle():
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())  # nothing ever plans
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    ctx = _ctx(combat_monster="chicken")
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    calls_cycle0 = len([1 for (r, _) in planner.budgets if r == "AcceptTask"])
    planner.budgets.clear()
    a.set_cycle(1)
    a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    calls_cycle1 = len([1 for (r, _) in planner.budgets if r == "AcceptTask"])
    assert calls_cycle0 >= 1
    assert calls_cycle1 == 0, "memoized goal must be skipped on the next cycle"


def test_wait_selected_when_nothing_plans():
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())
    a = _arbiter_with(planner)
    state = make_state(task_code="chicken", task_type="monsters", task_progress=0, task_total=5)
    goal, plan, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), [], _ctx())
    assert isinstance(goal, WaitGoal)
    assert len(plan) == 1 and isinstance(plan[0], WaitAction)


def test_plans_short_circuits_wait_goal_without_invoking_planner():
    """_plans special-cases WaitGoal: it returns a single-WaitAction plan and
    records a zero-node goals_tried entry WITHOUT calling the planner (which
    would never terminate on the no-op WaitAction) — lines 308-317."""
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())
    a = _arbiter_with(planner)
    state = make_state()
    plan = a._plans(WaitGoal(), state, _make_planner_gd(), [])
    assert len(plan) == 1 and isinstance(plan[0], WaitAction)
    # Planner was never consulted for the Wait goal.
    assert planner.budgets == []
    # A diagnostic goals_tried entry was recorded for the Wait attempt.
    assert any(entry["goal"] == repr(WaitGoal()) and entry["nodes"] == 0
               for entry in a.goals_tried)
