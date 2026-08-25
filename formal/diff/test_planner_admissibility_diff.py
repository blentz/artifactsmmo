"""Differential test asserting the GOAP planner returns the OPTIMAL plan.

Phase-2 finding (FIX). `planner.py` used to use `h = goal.value(state)` (urgency)
as the A* heuristic; that heuristic is inadmissible (it overestimates the true
remaining cost in seconds), so the planner returned strictly suboptimal plans.
The fix sets `h = 0.0` (planner.py:81,112), making the search Dijkstra /
uniform-cost over non-negative `action.cost(...)` — so the textbook A* optimality
result applies absolutely. Proved in `Formal.PlannerAdmissibility`:
`RHP_first_satisfied_is_optimal` (7 ≤ 9) via the general
`firstSatisfied_least_cost_of_admissible` applied with the admissible `h ≡ 0`.

Rest cost is DYNAMIC and denominated in SECONDS (rest_cost_pure =
max(3, ceil(missing%))); the instance is anchored at HP 364/400 (missing 9%) so
Rest = 9.0 stays the expensive single-step and the multi-step optimum (8) is
preserved. It was HP 10/100 while Rest carried a phantom /10 — at true seconds
that shape costs 90.0 and no longer contests anything.

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
    Cost 3.0 — the published flat consumable cooldown, mirroring
    `cost_core.CONSUMABLE_COOLDOWN_SECONDS` as consumable.py returns it."""

    tile_x: int = 1
    tile_y: int = 0

    def is_applicable(self, state, game_data) -> bool:
        if state.x != self.tile_x or state.y != self.tile_y:
            return False
        return super().is_applicable(state, game_data)

    def cost(self, state, game_data, history=None) -> float:
        return 3.0

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
            rec(action.apply(s, gd), [*plan, action], cost + action.cost(s, gd, None), depth + 1)

    rec(state, [], 0.0, 0)
    return best


def _instance():
    gd = _make_game_data()
    gd._item_stats = {
        "cooked_chicken": ItemStats(
            code="cooked_chicken", level=1, type_="consumable", hp_restore=30
        )
    }
    # HP 364/400 (missing 36 = 9%) anchors the demo for the DYNAMIC Rest cost
    # (rest_cost_pure = max(3, ceil(missing%)) = 9.0 seconds here), keeping Rest
    # the expensive single-step. cooked_chicken restores 30 ≤ 36 deficit, so
    # EatAtTile FITS (cost 3.0, not the 200.0 overheal sentinel) and full-heals
    # in-model. A big bar is what buys both properties at once: a 9% deficit that
    # still exceeds one chicken.
    state = make_state(hp=364, max_hp=400, inventory={"cooked_chicken": 1}, x=0, y=0)
    goal = RestoreHPGoal()
    actions = [
        RestAction(),
        _LabeledMove(x=1, y=0),
        _EatAtTileAction(_item_stats=gd._item_stats, tile_x=1, tile_y=0),
    ]
    return gd, state, goal, actions


def test_planner_returns_optimal_plan_after_fix():
    """With h ≡ 0 the search is Dijkstra over non-negative `action.cost`. On the
    RestoreHP instance (HP 364/400) the Move-prefix node (f = g = 5) pops before
    the Rest-node (f = g = 9); the planner expands UseConsumable from there and
    returns the optimal `[Move, EatAtTile]` plan (cost 5 + 3 = 8), strictly
    cheaper than the `[Rest]` plan (cost 9). Mirrors Lean
    `RHP_first_satisfied_is_optimal`."""
    gd, state, goal, actions = _instance()

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, actions, gd)
    returned_cost = _plan_cost(state, plan, gd)

    bf = _brute_force_min_cost(state, goal, actions, gd, max_depth=goal.max_depth)

    # Ground-truth optimum from brute force.
    assert bf["cost"] == 8.0
    assert [repr(a) for a in bf["plan"]] == ["Move(1,0)", "EatAtTile(1,0)"]

    # The planner returns the brute-force optimum (the previously-buggy
    # `[Rest]` cost-9 plan is no longer chosen).
    assert [repr(a) for a in plan] == ["Move(1,0)", "EatAtTile(1,0)"]
    assert returned_cost == bf["cost"] == 8.0


def test_zero_heuristic_is_admissible_and_planner_is_dijkstra():
    """h ≡ 0 is admissible w.r.t. ANY true-remaining function, so the planner
    is uniform-cost. Behavioural witness: a cheap-prefix multi-step plan
    (Move 5 + Eat 3 = 8) beats an expensive single-step plan (Rest 9), even
    though the multi-step plan is longer. Under the old urgency heuristic (at
    HP 364/400, urgency = (1 − 0.91)·100 = 9) the single-step satisfied node was
    popped first (f = 9 + 0 = 9) before the Move-prefix node (f = 5 + 9 = 14),
    and the planner returned [Rest]. With h = 0 the Move node (f = 5) pops first
    and the optimal plan wins."""
    gd, state, goal, actions = _instance()

    # Brute-force confirms the multi-step prefix is genuinely the cheaper route.
    bf = _brute_force_min_cost(state, goal, actions, gd, max_depth=goal.max_depth)
    assert bf["cost"] == 8.0
    assert len(bf["plan"]) == 2  # multi-step

    # Rest alone is shorter (1 step) but strictly costlier (9 > 8). At HP 364/400
    # the dynamic rest cost is max(3, ceil(9%)) = 9.0 seconds.
    rest_only = [RestAction()]
    rest_cost = _plan_cost(state, rest_only, gd)
    assert rest_cost == 9.0
    assert rest_cost > bf["cost"]

    # The planner picks the cheaper multi-step plan — Dijkstra ordering by g.
    plan = GOAPPlanner().plan(state, goal, actions, gd)
    assert len(plan) == 2
    assert _plan_cost(state, plan, gd) == bf["cost"]


def _plan_under_floor(floor: float | None) -> list[str]:
    gd, state, goal, actions = _instance()
    planner = GOAPPlanner()
    if floor is not None:
        planner.set_action_floor(floor)
    return [repr(a) for a in planner.plan(state, goal, actions, gd)]


def test_request_budget_floor_flips_this_instance_to_the_single_step_plan():
    """The SAME instance, priced in REQUESTS instead of seconds.

    `[Move, EatAtTile]` costs 8 seconds across TWO requests; `[Rest]` costs 9
    seconds in ONE. Seconds say the two-step plan wins, and above
    (`test_planner_returns_optimal_plan_after_fix`) it does. But on a
    `play --all` fleet seconds are not what the bot waits on: rate limits are
    per-IP, each of five children holds a fifth of one budget, and the
    2026-08-10 five-character run measured every child pinned at ~52
    actions/hour — a mean 69s between actions against a mean 11.5s cooldown,
    with 29-49% of the wall clock spent blocked in `RateGovernor.acquire`. At
    that pace the two-step plan does not take 8 seconds, it takes two slots out
    of a fixed hourly supply, and `[Rest]` buys the same full-HP state for one.

    At a 5s floor: 5 + 5 = 10 against max(9, 5) = 9, so `[Rest]` wins.

    The optimality theorem is untouched — the planner still returns the
    least-cost plan under the cost function it is given; this test pins WHICH
    cost function a request-bound fleet should give it."""
    assert _plan_under_floor(None) == ["Move(1,0)", "EatAtTile(1,0)"]
    assert _plan_under_floor(5.0) == ["Rest"]


def test_request_budget_floor_is_a_lower_bound_not_a_flat_rate():
    """The property that stops the floor from erasing every price difference.

    Under a flat per-action rate the one-action plan would win for EVERY
    positive floor, since it is always one action against two. It does not: at
    a 3s floor the two-step plan costs max(5,3) + max(3,3) = 8, still under
    `[Rest]`'s max(9,3) = 9, and the multi-step plan is still returned. Only at
    5s — where the floor genuinely binds on both steps — does the choice flip.
    Rest keeps its own 9 throughout rather than being flattened to the floor."""
    assert _plan_under_floor(3.0) == ["Move(1,0)", "EatAtTile(1,0)"]
    assert _plan_under_floor(5.0) == ["Rest"]


def test_an_unset_request_budget_floor_leaves_the_search_identical():
    """The single-character path and the no-governor path: the floor defaults to
    0.0, `max(cost, 0.0)` is the identity on non-negative costs, and every
    assertion in this file's optimality tests holds unchanged."""
    assert GOAPPlanner().action_floor_seconds == 0.0
    assert _plan_under_floor(0.0) == _plan_under_floor(None)
