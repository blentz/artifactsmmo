"""The ONE place a `Decision` may ask what something costs.

Every module under `ai/decisions/` is forbidden to import `acquisition_cost`,
`acquisition_cost_core`, `min_plan_length`, `bid_vs_craft` or
`learning.projections` — except this one. That rule is wave 6's obligation O6,
discharged by an AST census over the package; this module is the single hole it
leaves, so the graph has one cost model rather than one per node.

INERT ON ARRIVAL (wave 4 increment 4.1b). It ships before its first caller
because the alternative is worse: `WhichSlotClosesTheFight` (increment 4.2) needs
a price, and pricing it in `decisions/root.py` would put the first forbidden
import inside the package and make O6 red the day it was written. Landing the
funnel first costs nothing — an unused module with its own tests — and means 4.2
adds a call rather than an exception.

TOTAL over `META_GOAL_KINDS`, with a drift assertion in the same shape as
`prerequisite_graph.prerequisites`: a new root kind cannot silently return an
unpriced 0 — the failure mode `objective_needs` suffered when `ReachSkillLevel`
became reachable at the flip.

EVERY ARM RETURNS PLANNER ACTIONS. Nothing that is not an action count may
enter: no gold price, no level gap, no wall-clock cooldown, no travel distance.
A caller that needs seconds converts ONCE, at the call site, by the published
`ge_order_config.AVG_CYCLE_SECONDS`, and says so.

A LOWER BOUND, never an estimate, and NOT CACHEABLE ACROSS CYCLES —
`UNOBTAINABLE_PER_UNIT` is charged for an item with no route THIS cycle.

THE CALL BUDGET IS PART OF THE CONTRACT. `route_price` is expensive: a live
ranking walk was measured at 33.9 s against a documented 300 ms. A `Decision`
may call it at most once per candidate child, and only when the node has more
than one child that is a genuine alternative. A call that INJECTS a pricing
callback into a helper counts as one call PER CANDIDATE THE HELPER PRICES, not
as one — wave 4's `WhichSlotClosesTheFight` makes one textual call to
`deficit_upgrade_target` which prices 22 candidates behind a closure. It may
never appear inside a `sorted(...)` key over an unbounded list.
"""

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_sources import obtain_sources
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.skill_grind_cost_core import skill_grind_cycles
from artifactsmmo_cli.ai.tiers.meta_goal import (
    META_GOAL_KINDS,
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.world_state import WorldState


def route_exists(code: str, state: WorldState, game_data: GameData,
                 ctx: SelectionContext) -> bool:
    """Can the executor serve ANY route to `code` this cycle?

    A pure forward to `obtain_sources` — the question
    `prerequisite_graph._leafs` already asks, lifted so a root-graph node can
    ask it without importing the prerequisite walk. CHEAP: no cost walk, no
    closure, no learning store.

    A node facing "is this child reachable at all" asks THIS, never
    `route_price(...) < UNOBTAINABLE_PER_UNIT`. The two agree today, and the
    price form spends a full closure walk to learn a boolean.
    """
    return bool(obtain_sources(code, state, game_data, ctx))


def route_price(goal: MetaGoal, state: WorldState, game_data: GameData,
                ctx: SelectionContext,
                history: LearningStore | None) -> int:
    """Lower bound on planner actions to satisfy `goal` by its cheapest route.

    A FORWARDER, not a second cost model. For `ObtainItem` this is
    `acquisition_actions` with the arguments the goal already carries, which is
    the point: the scan that ranks gear candidates and the walk that prices them
    must not be able to disagree, and they cannot if there is one call.

    `equip` IS DERIVED FROM `goal.slot`, AND THAT IS THE ONLY RULE. A slotted
    `ObtainItem` is satisfied by WEARING the code (`ObtainItem.is_satisfied`
    tests `state.equipment.get(self.slot)`), so its price must include the equip
    action; an unslotted one is satisfied by owning. Callers do not pass
    `equip` — the caller that used to (`strategy_driver.py`'s GEAR_REVIEW arm,
    `equip=True` by hand) was asserting a second time a fact the slot already
    carried, and the two could drift.

TOTAL over `META_GOAL_KINDS` since wave 6. The two climbs return
    `UNOBTAINABLE_PER_UNIT` — never 0 and never `inf` — when they cannot be
    priced: 0 would make a level root outrank every gear root, and `inf` would
    break the total order the walk needs. The trailing assertion is the drift
    guard: a new `MetaGoal` kind fails loudly here instead of pricing as 0.
    """
    if isinstance(goal, ObtainItem):
        return acquisition_actions(goal.code, goal.quantity, state, game_data,
                                   ctx, equip=goal.slot is not None,
                                   store=history)
    if isinstance(goal, ReachSkillLevel):
        # Cycles ARE actions — `skill_grind_cost_core`'s own headline. This is
        # the same term `acquisition_cost._gated_craft_option` charges as
        # `unlock_actions`, so a skill-gated `ObtainItem` and a bare
        # `ReachSkillLevel` price the same climb identically.
        #
        # OWN evidence first, the fleet's only in its ABSENCE, and the
        # `is None` test is load-bearing: `rate or fleet` would silently make a
        # stuck character borrow a healthy one's rate. Copied deliberately from
        # `acquisition_cost.py:354-356` rather than re-derived — one rule.
        if history is None:
            return UNOBTAINABLE_PER_UNIT
        rate = history.skill_grind_rate(goal.skill)
        if rate is None:
            rate = history.fleet_skill_grind_rate(goal.skill)
        max_xp = state.skill_max_xp.get(goal.skill, 0)
        if not rate or rate <= 0 or max_xp <= 0:
            # No measured rate is not a free climb. The soundness contract
            # resolves DOWNWARD for pruning, but an unpriceable grind that
            # reads as 0 is exactly the "free-looking grind" that captured R2D2
            # for 4.5 hours (`acquisition_cost.py:310`).
            return UNOBTAINABLE_PER_UNIT
        return skill_grind_cycles(
            state.skills.get(goal.skill, 1), state.skill_xp.get(goal.skill, 0),
            max_xp, goal.level, rate)
    if isinstance(goal, ReachCharLevel):
        # `PathPlan.total_cycles` is "CYCLES — planner actions"
        # (`projections.py:263`) and counts the WHOLE combat loop.
        if history is None:
            return UNOBTAINABLE_PER_UNIT
        plan = cheapest_path_to_level(goal.level, state, history, game_data)
        # `blocked` -> UNOBTAINABLE_PER_UNIT, never `inf`: the walk needs a
        # TOTAL ORDER, which is why UNOBTAINABLE_PER_UNIT is a large number and
        # not infinity. A blocked climb means every beatable monster is grey —
        # the character needs GEAR, not monsters.
        if plan.blocked:
            return UNOBTAINABLE_PER_UNIT
        return int(plan.total_cycles)
    assert not isinstance(goal, META_GOAL_KINDS), (
        f"{goal!r} is in META_GOAL_KINDS but route_price has no arm for it")
    raise AssertionError(f"unhandled MetaGoal kind: {goal!r}")
