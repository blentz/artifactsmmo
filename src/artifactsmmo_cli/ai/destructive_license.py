"""The destruction licence: which of the SHARED action pool's destructive actions
the keep authority permits this cycle.

WHY IT EXISTS. `actions/factory.py` emits a quantity=1 `RecycleAction` for every
craftable equippable, a quantity=1 `NpcSellAction` for every (npc, item) pair the
vendor buys, and — when the bank is locked — a quantity=1 `DeleteItemAction` for
every non-equipped held item. Those go into ONE shared pool, and `Goal.relevant_actions`
DEFAULTS to the whole pool (`goals/base.py`): ~10 goals never override it. So a goal
with no business destroying anything (CompleteTask, AcceptTask, ClaimPending, …) could
satisfy `FightAction`'s `inventory_free >= 1` precondition by DELETING an item — and
`player_helpers.delete_cost` prices a SELLABLE item (25) BELOW an ingredient (50), so
the working `copper_axe` was a PREFERRED victim. The factory's old defence was
`protected_codes = protected_gear or (target_gear | target_tools)` — a `frozenset[str]`,
i.e. keep-ALL-copies: the exact type the item-protection-authority epic exists to kill,
and it protected only BiS codes (never the heal stock, never the task's own item, never
the last tool that was not a BiS target).

THE LICENCE IS THE AUTHORITY, ONE PLACE. A pool action that destroys `code` is admitted
only while `min(bankable, destroyable) >= action.quantity`:

  * `destroyable` (`keep_owned`, bag+bank) because destruction is IRREVERSIBLE and
    answers to OWNERSHIP;
  * `bankable` (`keep_in_bag`) because every one of these routes destroys a BAG copy,
    and a copy the bag must keep (the tool the gather re-arm is about to equip) must not
    be eaten when banking it was the correct move.

Exactly the `min` the licensed disposal goals take (`recycle_surplus.recyclable_surplus`,
`accumulation_sell.sellable_surplus`, `discard_surplus.discardable_surplus`).

WHERE IT IS APPLIED: `StrategyArbiter.select`, immediately after `step_profile` is bound
onto the ctx — the ONE point in production where the ctx the authority reads is complete
(the factory runs BEFORE the strategy decision exists, so a factory-side gate would ask
the authority with an empty `step_profile` and no `crafting_target`, and would still
licence deleting an active step's own materials). Filtering there covers EVERY goal's
plan, including the ones that never override `relevant_actions`. The disposal goals
build their OWN batch actions inside `relevant_actions` (already authority-licensed and
quantity-sized), so they neither need nor see this filter.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import bankable, destroyable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def destructive_demand(action: Action) -> tuple[str, int] | None:
    """The `(code, quantity)` `action` would DESTROY, or None when it destroys
    nothing.

    The three routes the factory emits into the shared pool. Deposit is absent on
    purpose: banking retains ownership (it is the reversible route `keep_in_bag` is
    about), so it needs no destruction licence."""
    if isinstance(action, (RecycleAction, DeleteItemAction)):
        return action.code, action.quantity
    if isinstance(action, NpcSellAction):
        return action.item_code, action.quantity
    return None


def licensed_quantity(code: str, state: WorldState, game_data: GameData,
                      ctx: SelectionContext) -> int:
    """Copies of `code` the authority permits a BAG-side destruction to take:
    `min(bankable, destroyable)`.

    A code with none in the BAG short-circuits to 0 — `bankable` is bounded by the
    bag count, so it is already 0, and skipping the keep walk keeps the per-cycle
    filter cheap over a pool whose Recycle/NpcSell arms range over the whole catalog
    (hundreds of codes) while the bag holds at most a couple of dozen."""
    if state.inventory.get(code, 0) <= 0:
        return 0
    return min(bankable(code, state, game_data, ctx),
               destroyable(code, state, game_data, ctx))


def license_destructive_actions(actions: list[Action], state: WorldState,
                                game_data: GameData,
                                ctx: SelectionContext) -> list[Action]:
    """`actions` with every UNLICENSED destructive action removed.

    Non-destructive actions pass through untouched (identity on a pool with no
    Recycle/NpcSell/Delete in it). A destructive action survives only while the
    authority licenses at least its own quantity — so a code the authority protects
    entirely (`min(bankable, destroyable) == 0`) gets NO destructive action at all,
    and no goal can reach for one."""
    licensed: dict[str, int] = {}
    kept: list[Action] = []
    for action in actions:
        demand = destructive_demand(action)
        if demand is None:
            kept.append(action)
            continue
        code, quantity = demand
        if code not in licensed:
            licensed[code] = licensed_quantity(code, state, game_data, ctx)
        if quantity <= licensed[code]:
            kept.append(action)
    return kept
