"""Counterexample test pinning the GOAP planner's NON-OPTIMAL plan.

Phase-2 Task 2 finding (REFUTATION). `planner.py:99` claims:

    "A* pops nodes in f-score order; first satisfied node is optimal."

That is the textbook A* result, which requires the heuristic `h` to be
ADMISSIBLE (h <= true remaining cost). The planner uses `h = goal.value(state)`
(planner.py:81,112), an *urgency* score in different units than `g` (seconds);
for RestoreHPGoal it is `(1 - hp_percent) * 100` (restore_hp.py:33), which grossly
overestimates remaining cost. The Lean module `Formal.PlannerAdmissibility` proves
the urgency heuristic is NOT admissible and that the resulting first-popped plan is
strictly costlier than optimal (CE_first_satisfied_not_optimal: 3 < 10).

This test runs the REAL Python planner on the SAME counterexample instance and
asserts it returns the COSTLIER [Rest] plan (cost 10) rather than the optimal
[Move, UseConsumable] plan (cost 3) — the concrete non-optimality the Lean
counterexample predicts. It is a regression PIN on the live bug, not a check that
the planner is correct. When the heuristic is fixed (made admissible / zeroed so
the search is Dijkstra-optimal), this test SHOULD start failing and be updated to
assert optimality.
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
    state = make_state(hp=50, max_hp=100, inventory={"cooked_chicken": 1}, x=0, y=0)
    goal = RestoreHPGoal()
    actions = [
        RestAction(),
        _LabeledMove(x=1, y=0),
        _EatAtTileAction(_item_stats=gd._item_stats, tile_x=1, tile_y=0),
    ]
    return gd, state, goal, actions


def test_urgency_heuristic_is_not_admissible_at_start():
    """value() at HP=50/100 returns 50 (restore_hp.py:33) while the true remaining
    cost to full HP is only 7 (real Move cost 5 + Eat cost 2): h >> remaining, NOT
    admissible. Matches Lean CE_not_admissible / CE_inadmissible_witnessed."""
    gd, state, goal, _ = _instance()
    h_start = goal.value(state, gd, None)
    assert h_start == 50.0  # (1 - 0.5) * 100
    # true remaining cost (least-cost plan) is 7 — proved minimal by brute force below
    assert h_start > 7.0


def test_planner_returns_costlier_plan_than_optimal():
    """The live bug: A* with the inadmissible urgency heuristic pops the satisfied
    Rest-node (f = 10 + 0) before the Move-node (f = 5 + 50) toward the cheaper
    plan, and RETURNS [Rest] (cost 10) — not [Move, Eat] (cost 7).

    Mirrors Lean CE_first_satisfied_not_optimal (7 < 10). REGRESSION PIN: update to
    assert optimality once the heuristic is made admissible (zero h -> Dijkstra)."""
    gd, state, goal, actions = _instance()

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, actions, gd)
    returned_cost = _plan_cost(state, plan, gd)

    bf = _brute_force_min_cost(state, goal, actions, gd, max_depth=goal.max_depth)

    # Optimal is the cheap 2-step plan (cost 7 = real Move 5 + Eat 2); ground truth.
    assert bf["cost"] == 7.0
    assert [repr(a) for a in bf["plan"]] == ["Move(1,0)", "EatAtTile(1,0)"]

    # The planner returns the EXPENSIVE 1-step plan (cost 10) — strictly worse.
    assert [repr(a) for a in plan] == ["Rest"]
    assert returned_cost == 10.0
    assert returned_cost > bf["cost"]  # NON-OPTIMAL: the refuted claim
