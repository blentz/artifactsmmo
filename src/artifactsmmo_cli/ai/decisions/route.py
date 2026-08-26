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

`ObtainItem` is the only variant priced here. `ReachCharLevel` and
`ReachSkillLevel` raise: wave 6 completes them when it moves the level and skill
roots onto the same funnel.
"""

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem
from artifactsmmo_cli.ai.world_state import WorldState


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

    Raises `NotImplementedError` for the variants wave 6 owns. Deliberately not
    a default: a level root priced 0 outranks every gear root and priced high is
    unreachable, so a silent number here would be the graph ranking on a value
    nobody chose. Fail with the variant's name instead.
    """
    if isinstance(goal, ObtainItem):
        return acquisition_actions(goal.code, goal.quantity, state, game_data,
                                   ctx, equip=goal.slot is not None,
                                   store=history)
    raise NotImplementedError(
        f"{type(goal).__name__} is not priced yet — wave 6 completes the "
        f"dispatch; see decisions/route.py's module docstring")
