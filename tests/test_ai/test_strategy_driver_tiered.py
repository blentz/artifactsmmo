"""Tiered selection: cheap pass, escalate only when cheap empty, memoize timeouts.

A scripted planner returns a plan for a goal only when given >= its required
budget, letting us assert pass behavior deterministically."""
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import CHEAP_BUDGET_SECONDS as CHEAP


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
