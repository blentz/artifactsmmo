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

_SEARCH_BUDGET_SECONDS = 300.0
"""A* wall-clock budget (the MAX / escalation budget). Deep recipe chains explore
thousands of nodes; with learned costs each node issues SQLite queries
(action_cost/success_rate/goal_avg_cycles), making the search I/O-bound under
`--learn`. 300s is a generous ceiling for the escalation pass so a genuinely deep
but reachable goal is found when it is the only option; the tiered arbiter's cheap
pass (CHEAP_BUDGET_SECONDS) plans fast goals first, so this full budget is rarely
hit, and the doomed-goal memo skips known-unreachable goals on later cycles."""

_MAX_SEARCH_NODES = 1_000_000
"""A* node-CREATION cap — the memory bound, independent of the wall clock.
Search memory is proportional to nodes pushed (open heap + visited set +
per-node WorldState copies), not to elapsed seconds: the wall-clock budget
only bounded memory by accident, via slow node evaluation. When the loadout
memo made expansions ~50x cheaper (2026-07-06), an unsatisfiable goal filled
15GB RSS inside 6 minutes while honoring its time budget.

Calibration is in CREATED nodes (pushes), NOT explored (pops): at full
branching (~1800 actions) created runs ~100x explored, so historical
explored-node figures (237K pathological, 52K deep-chain) do NOT transfer.
The first calibration (250K created) truncated a real escalation pass that
succeeded uncapped at ~900K created (RestoreHP live probe 2026-07-06).
1M created ≈ 4GB transient worst case; goals with sane relevant_actions
never approach it."""


def _state_key(state: WorldState) -> tuple[object, ...]:
    """Hashable key over the full WorldState for the visited set.

    Includes `state.skills`: an action whose ONLY effect is a skill-level
    change (LevelSkill's optimistic apply) produces a next_state that is
    otherwise identical to its parent, so without skills in the key that
    child collides with the already-visited parent and is pruned — the
    skill-gated craft it unlocks can then never be reached in-search
    (GatherMaterials(under-skill widget) planned to length 0). Adding skills
    only makes the dedup FINER, so it cannot break Dijkstra optimality
    (PlannerAdmissibility.lean); and since no LIVE action mutates
    state.skills (gathers/crafts accrue projected_skill_xp_delta, never
    levels), the skills component is constant across every node of every live
    search — the in-search partition is unchanged. This key is also compared
    cross-cycle for StuckSignal.STATE_FROZEN (player.py); there the addition is
    strictly MORE precise: a real skill-level gain re-synced between cycles now
    correctly counts as state progress instead of reading as frozen."""
    return (
        state.x, state.y,
        state.hp, state.gold,
        state.xp,
        state.task_code, state.task_type, state.task_progress, state.task_total,
        tuple(sorted(state.inventory.items())),
        tuple(sorted(state.equipment.items())),
        tuple(sorted((state.bank_items or {}).items())),
        tuple(sorted(state.skills.items())),
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
    nodes_created: int = 0
    max_depth_reached: int = 0
    timed_out: bool = False
    node_capped: bool = False
    """True when the search stopped at _MAX_SEARCH_NODES (memory bound).
    Always sets timed_out too: a capped search is inconclusive, not proof of
    unreachability, so it must ride the same doomed-memo-exempt semantics."""


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
        *,
        budget_seconds: float | None = None,
        max_nodes: int | None = None,
    ) -> list[Action]:
        """Return the lowest-cost action plan to satisfy `goal` from `state`, or [] if none found.

        ``budget_seconds`` overrides the module-level ``_SEARCH_BUDGET_SECONDS`` for this
        call only.  Pass ``None`` (the default) to use the full 300s escalation budget;
        the arbiter's cheap first pass passes 10s (strategy_driver.CHEAP_BUDGET_SECONDS).
        ``max_nodes`` likewise overrides ``_MAX_SEARCH_NODES`` (the memory bound).
        """
        max_depth = goal.max_depth
        budget = _SEARCH_BUDGET_SECONDS if budget_seconds is None else budget_seconds
        node_cap = _MAX_SEARCH_NODES if max_nodes is None else max_nodes
        deadline = time.monotonic() + budget
        stats = PlanStats(nodes_created=1)  # the root node below

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
                if stats.nodes_created >= node_cap:
                    # Memory bound hit (checked per pop; overshoot is at most
                    # one expansion's fan-out). Inconclusive like a timeout.
                    stats.node_capped = True
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
                    if getattr(action, "travel_region", "overworld") != \
                            game_data.state_region(node.state):
                        continue
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
                            plan=[*node.plan, action],
                            g_score=g,
                        ),
                    )
                    stats.nodes_created += 1

        self.last_stats = stats
        return []
