"""GOAP planner: forward A* search over the action space."""

import heapq
import time
from contextlib import nullcontext
from dataclasses import dataclass, field

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

_SEARCH_BUDGET_SECONDS = 90.0
"""A* wall-clock budget. Set to span a game action cooldown (typically 60s+) so
the bot can plan the next action during the current one's cooldown. Deep recipe
chains (e.g. 6 ash_plank = 60 ash_wood) explore ~2800 nodes; with learned costs
each node issues SQLite queries (action_cost/success_rate/goal_avg_cycles), making
the search I/O-bound at ~7.5s — far past the old 2s budget, which abandoned such
reachable goals as false no_plan stalls. 90s is a generous ceiling rarely hit
(normal plans resolve in <0.1s); the cost is that a genuinely unplannable goal
now burns up to 90s before the planner gives up."""


def _state_key(state: WorldState) -> tuple[object, ...]:
    """Hashable key over the full WorldState for the visited set."""
    return (
        state.x, state.y,
        state.hp, state.gold,
        state.xp,
        state.task_code, state.task_type, state.task_progress, state.task_total,
        tuple(sorted(state.inventory.items())),
        tuple(sorted(state.equipment.items())),
        tuple(sorted((state.bank_items or {}).items())),
    )


@dataclass(order=True)
class _Node:
    """Priority queue node for A* search."""

    f_score: float
    depth: int
    state: WorldState = field(compare=False)
    plan: list[Action] = field(compare=False)
    g_score: float = field(compare=False)


@dataclass
class PlanStats:
    """Diagnostics from the last planner run."""
    nodes_explored: int = 0
    max_depth_reached: int = 0
    timed_out: bool = False


class GOAPPlanner:
    """Forward A* planner. Finds the minimum-cost action sequence to satisfy a goal."""

    def __init__(self) -> None:
        self.last_stats = PlanStats()

    def plan(
        self,
        state: WorldState,
        goal: Goal,
        actions: list[Action],
        game_data: GameData,
        history: LearningStore | None = None,
    ) -> list[Action]:
        """Return the lowest-cost action plan to satisfy `goal` from `state`, or [] if none found."""
        max_depth = goal.max_depth
        deadline = time.monotonic() + _SEARCH_BUDGET_SECONDS
        stats = PlanStats()

        visited: set[tuple[object, ...]] = set()
        relevant = goal.relevant_actions(actions, state, game_data)

        cache_ctx = history.search_cache() if history is not None else nullcontext()
        with cache_ctx:
            # Heuristic h = 0 makes this Dijkstra / uniform-cost search.  Every
            # `action.cost(...)` in this codebase returns a non-negative float
            # (see e.g. rest.py:51 = 10.0, movement.py:58 = max(d*5, 1.0) ≥ 1.0,
            # consumable.py:93 = 2.0, gathering.py:86, combat.py:97, crafting.py:103
            # — all ≥ 0).  With h ≡ 0 (trivially admissible & consistent) and
            # non-negative edge costs, A*'s "first satisfied node popped is least
            # cost" reduces to Dijkstra optimality, which holds absolutely. A
            # previous version used `goal.value(...)` as h (urgency, not seconds),
            # which was non-admissible and made the planner return strictly
            # suboptimal plans — see formal/Formal/PlannerAdmissibility.lean.
            h0 = 0.0
            heap: list[_Node] = [_Node(f_score=h0, depth=0, state=state, plan=[], g_score=0.0)]
            while heap:
                if time.monotonic() >= deadline:
                    stats.timed_out = True
                    break

                node = heapq.heappop(heap)

                key = _state_key(node.state)
                if key in visited:
                    continue
                visited.add(key)
                stats.nodes_explored += 1
                if node.depth > stats.max_depth_reached:
                    stats.max_depth_reached = node.depth

                if goal.is_satisfied(node.state):
                    # Dijkstra / uniform-cost search: with h ≡ 0 and non-negative
                    # `action.cost(...)` (verified across all Action subclasses),
                    # f-score equals g-score, so the first satisfied node popped
                    # is provably least-cost.  Proven in
                    # formal/Formal/PlannerAdmissibility.lean
                    # (`firstSatisfied_least_cost_of_admissible` applied with h=0).
                    self.last_stats = stats
                    return node.plan

                if node.depth >= max_depth:
                    continue

                for action in relevant:
                    if not action.is_applicable(node.state, game_data):
                        continue

                    next_state = action.apply(node.state, game_data)
                    g = node.g_score + action.cost(node.state, game_data, history)
                    # h ≡ 0 (Dijkstra): see h0 above.  `goal.value` remains used
                    # by goal *selection* (StrategyArbiter, learning) — only the
                    # planner's heuristic role is zeroed for provable optimality.
                    h = 0.0
                    heapq.heappush(
                        heap,
                        _Node(
                            f_score=g + h,
                            depth=node.depth + 1,
                            state=next_state,
                            plan=node.plan + [action],
                            g_score=g,
                        ),
                    )

        self.last_stats = stats
        return []
