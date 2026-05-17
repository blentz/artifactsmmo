"""GOAP planner: forward A* search over the action space."""

import heapq
import time
from dataclasses import dataclass, field

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

_SEARCH_BUDGET_SECONDS = 2.0


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

        h0 = goal.value(state, game_data, history)
        heap: list[_Node] = [_Node(f_score=h0, depth=0, state=state, plan=[], g_score=0.0)]
        visited: set[tuple[object, ...]] = set()
        relevant = goal.relevant_actions(actions, state, game_data)

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
                # A* pops nodes in f-score order; first satisfied node is optimal.
                self.last_stats = stats
                return node.plan

            if node.depth >= max_depth:
                continue

            for action in relevant:
                if not action.is_applicable(node.state, game_data):
                    continue

                next_state = action.apply(node.state, game_data)
                g = node.g_score + action.cost(node.state, game_data, history)
                h = goal.value(next_state, game_data, history)
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
