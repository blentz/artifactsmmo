"""GOAPPlanner.plan honors an explicit per-call time budget and a node cap."""

import dataclasses
import inspect
import time

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.planner import _MAX_SEARCH_NODES, _SEARCH_BUDGET_SECONDS, GOAPPlanner
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
    assert _SEARCH_BUDGET_SECONDS == 300.0


class _ExplodingAction(Action):
    """Always applicable, every apply() yields a NEW state (gold+1): the
    reachable state space is infinite, so only the node cap can stop the
    search before the wall clock does."""

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return True

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        return dataclasses.replace(state, gold=state.gold + 1)

    def cost(self, state: WorldState, game_data: GameData, history=None) -> float:
        return 1.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        raise NotImplementedError("planner-only test action")

    def __repr__(self) -> str:
        return "Exploding"


class _DeepNeverSatisfiedGoal(_NeverSatisfiedGoal):
    """Unbounded depth: without a node cap the frontier grows until the
    wall-clock budget expires (live 2026-07-06: 15GB RSS in 6 minutes once
    the loadout memo made node expansion cheap)."""

    @property
    def max_depth(self) -> int:
        return 10_000


def test_node_cap_bounds_search_memory(make_planner_gd: GameData) -> None:
    """An unsatisfiable goal over an infinite state space must stop at the
    node cap — well before the time budget — and report it."""
    planner = GOAPPlanner()
    t0 = time.monotonic()
    plan = planner.plan(
        make_state(), _DeepNeverSatisfiedGoal(), [_ExplodingAction()],
        make_planner_gd, budget_seconds=30.0, max_nodes=100,
    )
    elapsed = time.monotonic() - t0
    assert plan == []
    assert planner.last_stats.node_capped is True
    # Node-capped searches are inconclusive, exactly like timed-out ones —
    # they must ride the same "don't memo as doomed" semantics.
    assert planner.last_stats.timed_out is True
    assert planner.last_stats.nodes_explored <= 100
    # The cap bounds CREATED nodes (memory), which at branching-1 tracks
    # explored closely; the stat must be recorded for live diagnosis.
    assert planner.last_stats.nodes_created >= 100
    assert planner.last_stats.nodes_created <= 100 + 1  # ≤ one fan-out overshoot
    assert elapsed < 5.0, f"cap=100 must stop far under the 30s budget, took {elapsed:.1f}s"


def test_node_cap_default_uses_module_constant() -> None:
    """250K was the first calibration and it TRUNCATED real escalation passes:
    node counts in past incident reports are EXPLORED (pops), but memory —
    and this cap — follow CREATED (pushes), ~100x explored at full branching
    (live probe 2026-07-06: RestoreHP found [Rest] at ~900K created; the 250K
    cap killed that search at 21s). 1M created ≈ 4GB transient worst case."""
    sig = inspect.signature(GOAPPlanner.plan)
    assert sig.parameters["max_nodes"].default is None
    assert _MAX_SEARCH_NODES == 1_000_000


def test_node_cap_does_not_block_reachable_plans(make_planner_gd: GameData) -> None:
    """A goal satisfiable within the cap still plans normally."""

    start = make_state()
    target = start.gold + 3

    class _GoldGoal(_DeepNeverSatisfiedGoal):
        def is_satisfied(self, state: WorldState) -> bool:
            return state.gold >= target

    planner = GOAPPlanner()
    plan = planner.plan(
        start, _GoldGoal(), [_ExplodingAction()],
        make_planner_gd, budget_seconds=30.0, max_nodes=100,
    )
    assert len(plan) == 3
    assert planner.last_stats.node_capped is False
