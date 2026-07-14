# disposal_route

"""Overstock disposal-route decision: recycle > deposit > delete.

When `DiscardOverstockGoal` cannot liquidate an overstocked item (no fillable
GE order, no executable NPC sell), the item is ROUTED instead of blindly
deleted (live Robby trace 2026-07-04: copper_helmet×33, copper_ring×14,
wooden_shield×8 recyclable gear plus 40 bankable gems destroyed):

    RECYCLE  iff  an applicable RecycleAction exists this cycle
    DEPOSIT  iff  no recycle, the bank can take it, and the item has future value
    DELETE   otherwise (true junk only)

Inputs are EXECUTABILITY-NOW facts so every route yields an action executable
this cycle and overstock always clears — preserving the 2026-06-24 liveness
fix (the Withdraw↔Deposit bag-full livelock). `future_value` is generic over
the API taxonomy (recipe demand or equippability), never a hardcoded item
list; items with neither (sap over cap, slimeballs) still delete, preserving
the anti-hoard rationale on the discard guards.

The pure `disposal_route` is the differential target proved in
formal/Formal/DisposalRoute.lean over `Bool` (exhaustive 8-case diff).
"""

from enum import Enum

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import keep_owned
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

RECYCLING_SKILLS = frozenset({"weaponcrafting", "gearcrafting", "jewelrycrafting"})
"""Server rule: the /action/recycling endpoint accepts ONLY items crafted with
these skills. Cooking and alchemy products (potions, food) cannot be recycled,
so the recycle probe must never offer them (the server would 4xx)."""


class Route(Enum):
    RECYCLE = "recycle"
    DEPOSIT = "deposit"
    DELETE = "delete"


def disposal_route(recyclable: bool, bank_ok: bool, future_value: bool) -> Route:
    """Recycle when executable now; else deposit when the bank can take it AND
    the item has future value; else delete. Proved in
    formal/Formal/DisposalRoute.lean (`disposalRoute`): delete fires ONLY when
    the item can be neither recycled nor usefully banked."""
    if recyclable:
        return Route.RECYCLE
    if bank_ok and future_value:
        return Route.DEPOSIT
    return Route.DELETE


def _applicable_recycle(code: str, excess_qty: int, state: WorldState,
                        game_data: GameData,
                        ctx: SelectionContext) -> RecycleAction | None:
    """The largest-quantity applicable RecycleAction for `code`, or None.

    Same eligibility as `ai/recycle_surplus.recyclable_surplus` (craftable
    equipment at a known workshop) restricted to `RECYCLING_SKILLS`, with the
    descending-quantity probe of `RecycleSurplusGoal.relevant_actions`:
    recycling MINTS recovered materials into the bag, so the quantity descends
    until `RecycleAction.is_applicable` accepts the net space (HTTP 497).

    This BATCH action is built outside `destructive_license`, so it stamps its
    own `owned_floor = keep_owned(code)` — the per-application bound that keeps a
    plan from applying the same recycle twice and destroying past `destroyable`
    (whole-branch review, CRITICAL 1). `excess_qty` already comes from the same
    authority (`discard_surplus.discardable_surplus` = `min(bankable,
    destroyable)`), so the floor never blocks the FIRST application — only the
    repeat."""
    stats = game_data.item_stats(code)
    if stats is None or stats.crafting_skill not in RECYCLING_SKILLS:
        return None
    if not ITEM_TYPE_TO_SLOTS.get(stats.type_):
        return None
    workshop = game_data.workshop_location(stats.crafting_skill)
    if workshop is None:
        return None
    floor = keep_owned(code, state, game_data, ctx)
    for qty in range(excess_qty, 0, -1):
        action = RecycleAction(code=code, quantity=qty, workshop_location=workshop,
                               owned_floor=floor)
        if action.is_applicable(state, game_data):
            return action
    return None


def _future_value(code: str, game_data: GameData) -> bool:
    """Generic over the API taxonomy: an item has future value when some known
    recipe consumes it (including far-future skill-gated recipes — those are
    exactly the deposit-eligible materials per `reachable_recipe_demand`'s
    contract) or it is equippable gear/utility."""
    if game_data.max_recipe_demand(code) > 0:
        return True
    stats = game_data.item_stats(code)
    return stats is not None and bool(ITEM_TYPE_TO_SLOTS.get(stats.type_))


def overstock_disposal(code: str, excess_qty: int, state: WorldState,
                       game_data: GameData, bank_accessible: bool,
                       ctx: SelectionContext) -> Action:
    """Impure adapter (like `liquidation_venue`): assemble the executability
    facts from state/GameData and delegate to the proved `disposal_route`,
    returning the routed action for one overstocked code.

    `ctx` is the per-cycle SelectionContext the keep authority reads — the RECYCLE
    arm stamps `owned_floor = keep_owned(code)` onto its batch action from it."""
    recycle = _applicable_recycle(code, excess_qty, state, game_data, ctx)
    bank_location = game_data.bank_location_or_none
    bank_ok = bank_location is not None and bank_has_room(
        bank_accessible, state.bank_items, game_data.bank_capacity)
    route = disposal_route(recycle is not None, bank_ok, _future_value(code, game_data))
    if route is Route.RECYCLE:
        assert recycle is not None  # disposal_route: RECYCLE ⇒ recyclable
        return recycle
    if route is Route.DEPOSIT:
        assert bank_location is not None  # disposal_route: DEPOSIT ⇒ bank_ok
        return DepositItemAction(code=code, quantity=excess_qty,
                                 bank_location=bank_location,
                                 accessible=bank_accessible)
    return DeleteItemAction(code=code, quantity=excess_qty)
