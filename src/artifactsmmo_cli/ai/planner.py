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
    (PlannerAdmissibility.lean); and since gathers/crafts never raise
    state.skills in-search (skill grind is a separate LevelSkill action leg),
    the skills component is constant across every node of a GatherMaterials
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
        self.action_floor_seconds = 0.0
        """Seconds one REQUEST costs when the per-IP rate budget, not the action
        cooldown, is what paces this character. Zero (the default) restores the
        pre-change planner exactly, and is what every single-character run and
        every caller that never wires a `RateGovernor` sees.

        Set via `set_action_floor` from the action bucket's
        `WindowBudget.sustainable_interval()`, i.e. from live `/my/rates` data
        divided by the number of concurrent children — never a constant."""

    def set_action_floor(self, seconds: float) -> None:
        """Wire the request-budget pace. See `action_floor_seconds`.

        Separate from `plan()`'s keyword arguments because it is a property of
        the ENVIRONMENT (this process's share of one per-IP budget), constant
        across every goal and every re-plan, not of an individual search."""
        self.action_floor_seconds = seconds

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
            # h = goal.heuristic(state, game_data): an admissible & CONSISTENT
            # estimate of remaining plan cost (seconds), by contract (see
            # Goal.heuristic's docstring). Every `action.cost(...)` in this
            # codebase returns a non-negative float (see e.g. rest.py's
            # rest_cost_pure ≥ 0.3 — dynamic since 3a4994f4, not the old flat
            # 10.0 —
            # movement.py:58 = max(d*5, 1.0) ≥ 1.0, consumable.py:93 = 2.0,
            # gathering.py:86, combat.py:97, crafting.py:103 — all ≥ 0). With
            # non-negative edge costs and an admissible+consistent h, A*'s
            # "first satisfied node popped is least cost" holds. The default
            # h ≡ 0.0 (trivially admissible & consistent) reduces this to
            # Dijkstra optimality, which holds absolutely for every goal that
            # does not override `heuristic`. A previous version used
            # `goal.value(...)` as h (urgency, not seconds), which was
            # non-admissible and made the planner return strictly suboptimal
            # plans — see formal/Formal/PlannerAdmissibility.lean.
            h0 = goal.heuristic(state, game_data)
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
                    # THE EDGE COST IS max(cooldown, one request slot).
                    #
                    # `action.cost(...)` prices an action at the SECONDS its
                    # cooldown takes. That is the true price only while the
                    # cooldown is what the bot waits on. On a `play --all` fleet
                    # it is not: rate limits are per-IP, every child holds a
                    # fifth of one budget, and the 2026-08-10 five-character run
                    # measured every child pinned at ~52 actions/hour — a mean
                    # 69s between actions against a mean 11.5s cooldown, with
                    # 29-49% of the wall clock spent blocked in
                    # `RateGovernor.acquire`. An action whose cooldown is
                    # cheaper than that pace does not happen any sooner for
                    # being cheap; it still costs one request out of a fixed
                    # hourly supply. Pricing it at its cooldown made a plan of
                    # many cheap actions look better than a plan of few dear
                    # ones, which is backwards whenever requests are what bind.
                    #
                    # A LOWER BOUND, NOT A FLAT RATE. `max` keeps every action
                    # dearer than the floor at its own price, so a long move
                    # still costs more than a short one and distance does not
                    # become free. When the floor binds for both alternatives
                    # the comparison degenerates to "fewer actions wins", which
                    # is the correct objective in exactly that regime.
                    #
                    # APPLIED HERE, NOT INSIDE `Action.cost`, for two reasons
                    # that are both load-bearing:
                    #   * `Goal.heuristic` is NOT `h ≡ 0` — `goals/progression`
                    #     and `goals/gathering` return `LevelSkill(...).cost(...)`
                    #     — and `PlannerAdmissibility.Consistent` is a TIGHT
                    #     equality there (`skillGrind_h_consistent`). Raising
                    #     only the EDGE keeps `h s ≤ cost s s' + h s'` slacker
                    #     on the safe side; raising only the HEURISTIC would
                    #     break consistency and make closed-set pruning discard
                    #     cheaper routes. Admissibility moves the same safe way:
                    #     `trueRemaining` rises while `h` does not.
                    #   * `formal/diff/test_action_cost_nonneg_diff.py` pins
                    #     ~20 EXACT equalities on live `Action.cost(...)` against
                    #     the Lean model, and `ActionCostNonneg` carries two
                    #     UPPER bounds on Rest (`restCost_le_restCostMax`,
                    #     `restCost_lt_consumableCostOverheal`) that keep the
                    #     overheal sentinel dominant. A floor inside the pure
                    #     cost cores would falsify all of them; a floor here
                    #     leaves every published cost formula untouched.
                    # Non-negativity — the seal on the optimality proof — is
                    # preserved trivially: `max(x, y) ≥ x ≥ 0` for `y ≥ 0`.
                    g = node.g_score + max(
                        action.cost(node.state, game_data, history),
                        self.action_floor_seconds,
                    )
                    # h = goal.heuristic(next_state, game_data): see h0 above.
                    # `goal.value` remains used by goal *selection* (StrategyArbiter,
                    # learning) — the planner's heuristic role is a distinct,
                    # admissible+consistent estimate (default 0.0 = Dijkstra).
                    h = goal.heuristic(next_state, game_data)
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
