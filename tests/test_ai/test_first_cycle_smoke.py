"""The tiered budget bounds a cycle that has many wide candidates: with a planner
that never plans the wide goals, selection still terminates quickly at Wait and
memoizes them, and a second cycle skips them.

Offline smoke test (scripted planner, no network). Uses a state + action set that
actually drives candidates through the planner (a task-absent state with an
AcceptTask action and a winnable combat target) so the memoization assertion is
non-vacuous: cycle 0 plans the doomed candidates, cycle 1 skips them via the memo.
"""
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx, _FakeDecision, _make_planner_gd
from tests.test_ai.test_strategy_driver_tiered import _ScriptedPlanner


def test_many_doomed_candidates_resolve_to_wait_then_skip():
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())  # nothing ever plans
    a = StrategyArbiter(planner, history=None)
    a.set_cycle(0)
    state = make_state(task_code=None, task_total=0)
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx(combat_monster="chicken")

    g0, plan0, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    assert isinstance(g0, WaitGoal)
    n0 = len(planner.budgets)
    assert n0 >= 1, "cycle 0 must actually try (and fail to plan) the doomed candidates"

    planner.budgets.clear()
    a.set_cycle(1)
    g1, _plan1, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    assert isinstance(g1, WaitGoal)
    assert len(planner.budgets) < n0, "memoized goals must not be re-planned next cycle"
