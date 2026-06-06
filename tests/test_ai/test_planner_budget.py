"""GOAPPlanner.plan honors an explicit per-call time budget."""

import inspect
import time

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.planner import GOAPPlanner, _SEARCH_BUDGET_SECONDS
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state


class _NeverSatisfiedGoal(Goal):
    """A goal the planner can never satisfy, so it runs until the deadline."""

    def value(self, state: WorldState, game_data: GameData, history=None) -> float:
        return 1.0

    def is_satisfied(self, state: WorldState) -> bool:
        return False

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"_unreachable": True}

    @property
    def max_depth(self) -> int:
        return 1

    def __repr__(self) -> str:
        return "NeverSatisfied"


def test_explicit_budget_caps_wall_clock(make_planner_gd: GameData) -> None:
    planner = GOAPPlanner()
    t0 = time.monotonic()
    plan = planner.plan(make_state(), _NeverSatisfiedGoal(), [], make_planner_gd, budget_seconds=0.2)
    elapsed = time.monotonic() - t0
    assert plan == []
    assert elapsed < 2.0, f"0.2s budget should return fast, took {elapsed:.1f}s"


def test_default_budget_uses_module_constant() -> None:
    sig = inspect.signature(GOAPPlanner.plan)
    assert sig.parameters["budget_seconds"].default is None
    assert _SEARCH_BUDGET_SECONDS == 90.0
