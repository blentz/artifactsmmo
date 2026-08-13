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

_SEARCH_BUDGET_SECONDS = 15.0
"""A* wall-clock budget — ONE budget for every goal.

Was 300s behind a 10s "cheap" first pass. That two-pass scheme is deleted: its
escalation ran only when NOTHING planned, and a fallback combat grind always
plans in 2-3 nodes, so the escalation was unreachable in practice and the cheap
10s timeout was the real budget for every objective (live traces 2026-08-12,
5 characters, 31 hours).

15s is generous for a healthy search now that gather edges carry a quantity —
the searches that were spending 10s to reach 3873 nodes and no plan were
enumerating a singleton-gather chain that no longer exists. A goal that still
cannot be planned costs 15s once per DoomedMemo re-probe window instead of every
cycle, because any no-plan — TIMEOUT INCLUDED — now marks the goal doomed.

THE SEARCH IS NOT I/O-BOUND UNDER `--learn`. This paragraph used to claim it was
("each node issues LearningStore SQLite queries, at roughly 7.5s") and that claim
is measured false — it is corrected here rather than deleted because it sent two
separate investigations at the learning store. cProfile over the from-scratch
`greater_wooden_staff` search (bank holds no `spruce_plank`) with a real
`LearningStore` over the live 45087-cycle DB, 310s wall, 100080 nodes explored:
the ENTIRE store contribution is 98985 memoised `action_cost` calls (0.089s),
98985 `success_rate` (0.056s), and **two** `sqlite3.Cursor.execute` calls
(0.009s). `LearningStore.search_cache()` keys are state-INDEPENDENT, so one
decision queries each distinct statistic once no matter how many nodes read it.
A cross-cycle learned-stat cache would save 0.145s of 310s.

What `--learn` actually costs is NODES, not node latency: 100080 explored against
23214 for the same search with `history=None` (4.31x), at 1.06 vs 0.93 ms/node
(1.15x). One edge changes price — `Gather(spruce_tree×60)` is 900.0 cold and
2030.66 learned (60 gathers at the observed median instead of the flat 15.0s) —
and it is the edge the optimal plan must take, while
`UpgradeEquipmentGoal.heuristic` stays at 50.0 because it prices only the forced
craft-skill grind and nothing of the material acquisition that is 97% of that
plan. With h that weak against a doubled g, A* degenerates toward breadth. The
lever on this residual is an acquisition-aware admissible heuristic, which
carries a proof obligation against `formal/Formal/PlannerAdmissibility.lean`.

What the profile DID indict, identically in both configurations: `LevelSkill.
is_applicable` -> `tiers/skill_grind_target.build_selectable_grind_candidates`.
Cold, `is_applicable` is 48.2s of a 67.3s search (72%), of which the producer is
47.0s (70%); learned, the producer alone is 219.3s of 310.4s (71%). It priced
every in-skill craftable when the selection core can only ever pick the in-level
ones (69 vs 10 for R2D2 at weaponcrafting 9). Fixed 2026-08-13: 21.47s -> ~10.2s
cold (four runs of the fixed code: 9.68 / 10.20 / 10.23 / 10.28 — quote the
spread, not the fast one), 106.28s -> 49.53s learned, identical node counts and
plans both ways. An independent reviewer on ~8% slower hardware measured
22.22s -> 10.45s, so the ratio is ~2.1-2.2x and reproduces off this machine.

PER-NODE COST IS SUPERLINEAR IN HOLDINGS, and that — not SQLite — is why a live
search is several times dearer per node than any offline harness with an empty
bag. Same search, varying only the number of banked codes: 0.434 ms/node at 1,
0.618 at 21, 0.950 at 61, 11.29 at 121. At 121 codes
`obtain_sources._recycle_sources` is 94% of the search: it walks
`set(inventory) | set(bank)` on EVERY `obtain_sources` call (~1.2M per search)
and calls `destroyable` -> `inventory_caps._is_equippable_dominated` per held
code, so the cost is O(holdings x holdings) in the innermost loop. Live R2D2 at
`inv=65/130` with a stocked bank measured 1.99 ms/node (7537 nodes in 15s) where
this harness measured 0.495. UNFIXED.

Orthogonal to `_MAX_SEARCH_NODES`, which is the memory bound."""

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
        call only.  Pass ``None`` (the default) to use the one 15s budget — which is
        what the arbiter passes for every candidate, guards included.
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
                    g = node.g_score + action.cost(node.state, game_data, history)
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
