"""Differential test asserting the GOAP planner returns the OPTIMAL plan.

Phase-2 finding (FIX). `planner.py` used to use `h = goal.value(state)` (urgency)
as the A* heuristic; that heuristic is inadmissible (it overestimates the true
remaining cost in seconds), so the planner returned strictly suboptimal plans.
The fix sets `h = 0.0` (planner.py:81,112), making the search Dijkstra /
uniform-cost over non-negative `action.cost(...)` — so the textbook A* optimality
result applies absolutely. Proved in `Formal.PlannerAdmissibility`:
`RHP_first_satisfied_is_optimal` (7 ≤ 9) via the general
`firstSatisfied_least_cost_of_admissible` applied with the admissible `h ≡ 0`.

Rest cost is DYNAMIC (rest_cost_pure = max(3, ceil(missing%))/10); the instance
is re-anchored to HP 10/100 (missing 90%) so Rest = 9.0 stays the expensive
single-step and the multi-step optimum (7) is preserved.

This test runs the real Python planner on the SAME instance the Lean module
models and asserts:
* it returns the optimal `[Move, EatAtTile]` plan (cost 7), NOT the rest plan
  (cost 9) — the now-true optimality;
* the planner's ordering by `g` alone (h = 0) lets a cheap-prefix multi-step
  beat an expensive single-step — the behavioural consequence of Dijkstra.
"""
from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


@dataclass
class _EatAtTileAction(UseConsumableAction):
    """UseConsumable gated to a specific tile (models 'eat at the cooking tile').
    Cost 2.0 — a fitting heal that beats Rest, mirroring consumable.py:93."""

    tile_x: int = 1
    tile_y: int = 0

    def is_applicable(self, state, game_data) -> bool:
        if state.x != self.tile_x or state.y != self.tile_y:
            return False
        return super().is_applicable(state, game_data)

    def cost(self, state, game_data, history=None) -> float:
        return 2.0

    def __repr__(self) -> str:
        return f"EatAtTile({self.tile_x},{self.tile_y})"


class _LabeledMove(MoveAction):
    """Real MoveAction (no cost override) with a deterministic repr for the assertion.
    Real cost: `max(distance*5, 1.0)` (movement.py:58-59) -> 5.0 for one tile."""

    def __repr__(self) -> str:
        return f"Move({self.x},{self.y})"


def _make_game_data() -> GameData:
    gd = GameData()
    gd._monster_locations = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._monster_level = {}
    return gd


def _plan_cost(state, plan, gd):
    total, s = 0.0, state
    for action in plan:
        total += action.cost(s, gd, None)
        s = action.apply(s, gd)
    return total


def _brute_force_min_cost(state, goal, actions, gd, max_depth):
    best = {"cost": float("inf"), "plan": None}

    def rec(s, plan, cost, depth):
        if goal.is_satisfied(s):
            if cost < best["cost"]:
                best["cost"], best["plan"] = cost, plan
            return
        if depth >= max_depth:
            return
        for action in actions:
            if not action.is_applicable(s, gd):
                continue
            rec(action.apply(s, gd), plan + [action], cost + action.cost(s, gd, None), depth + 1)

    rec(state, [], 0.0, 0)
    return best


def _instance():
    gd = _make_game_data()
    gd._item_stats = {
        "cooked_chicken": ItemStats(
            code="cooked_chicken", level=1, type_="consumable", hp_restore=30
        )
    }
    # HP 10/100 (missing 90%) re-anchors the demo for the DYNAMIC Rest cost
    # (rest_cost_pure = max(3, ceil(missing%))/10 = 9.0 here), keeping Rest the
    # expensive single-step. cooked_chicken restores 30 ≤ 90 deficit, so EatAtTile
    # FITS (cost 2.0, not the 100.0 overheal sentinel) and full-heals in-model.
    state = make_state(hp=10, max_hp=100, inventory={"cooked_chicken": 1}, x=0, y=0)
    goal = RestoreHPGoal()
    actions = [
        RestAction(),
        _LabeledMove(x=1, y=0),
        _EatAtTileAction(_item_stats=gd._item_stats, tile_x=1, tile_y=0),
    ]
    return gd, state, goal, actions


def test_planner_returns_optimal_plan_after_fix():
    """With h ≡ 0 the search is Dijkstra over non-negative `action.cost`. On the
    RestoreHP instance (HP 10/100) the Move-prefix node (f = g = 5) pops before
    the Rest-node (f = g = 9); the planner expands UseConsumable from there and
    returns the optimal `[Move, EatAtTile]` plan (cost 5 + 2 = 7), strictly
    cheaper than the `[Rest]` plan (cost 9). Mirrors Lean
    `RHP_first_satisfied_is_optimal`."""
    gd, state, goal, actions = _instance()

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, actions, gd)
    returned_cost = _plan_cost(state, plan, gd)

    bf = _brute_force_min_cost(state, goal, actions, gd, max_depth=goal.max_depth)

    # Ground-truth optimum from brute force.
    assert bf["cost"] == 7.0
    assert [repr(a) for a in bf["plan"]] == ["Move(1,0)", "EatAtTile(1,0)"]

    # The planner returns the brute-force optimum (the previously-buggy
    # `[Rest]` cost-9 plan is no longer chosen).
    assert [repr(a) for a in plan] == ["Move(1,0)", "EatAtTile(1,0)"]
    assert returned_cost == bf["cost"] == 7.0


def test_zero_heuristic_is_admissible_and_planner_is_dijkstra():
    """h ≡ 0 is admissible w.r.t. ANY true-remaining function, so the planner
    is uniform-cost. Behavioural witness: a cheap-prefix multi-step plan
    (Move 5 + Eat 2 = 7) beats an expensive single-step plan (Rest 9), even
    though the multi-step plan is longer. Under the old urgency heuristic (at
    HP 10/100, urgency = (1 − 0.1)·100 = 90) the single-step satisfied node was
    popped first (f = 9 + 0 = 9) before the Move-prefix node (f = 5 + 90 = 95),
    and the planner returned [Rest]. With h = 0 the Move node (f = 5) pops first
    and the optimal plan wins."""
    gd, state, goal, actions = _instance()

    # Brute-force confirms the multi-step prefix is genuinely the cheaper route.
    bf = _brute_force_min_cost(state, goal, actions, gd, max_depth=goal.max_depth)
    assert bf["cost"] == 7.0
    assert len(bf["plan"]) == 2  # multi-step

    # Rest alone is shorter (1 step) but strictly costlier (9 > 7). At HP 10/100
    # the dynamic rest cost is max(3, ceil(90%))/10 = 9.0.
    rest_only = [RestAction()]
    rest_cost = _plan_cost(state, rest_only, gd)
    assert rest_cost == 9.0
    assert rest_cost > bf["cost"]

    # The planner picks the cheaper multi-step plan — Dijkstra ordering by g.
    plan = GOAPPlanner().plan(state, goal, actions, gd)
    assert len(plan) == 2
    assert _plan_cost(state, plan, gd) == bf["cost"]
