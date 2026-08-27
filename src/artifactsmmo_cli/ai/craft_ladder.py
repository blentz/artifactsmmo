"""Shared craft-a-utility ladder for CraftPotionsGoal and CraftUnlockBoostGoal.

craft_utility_ladder builds the gather/buy/withdraw/craft/move/equip action
filter for ONE utility target, batched to `runs` and equipping `equip_qty`
into the utility slot `utility_slot_for` picks for the target code.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.buy_source_venue import BuyVenue, choose_buy_venue
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.recipe_closure import gather_serves_closure
from artifactsmmo_cli.ai.requirement_projections import (
    demand_set,
    requirement_craftables,
)
from artifactsmmo_cli.ai.utility_slot import utility_slot_for
from artifactsmmo_cli.ai.world_state import WorldState


def _held(code: str, state: WorldState) -> int:
    """Units of `code` on hand for crafting: inventory plus bank."""
    return state.inventory.get(code, 0) + (state.bank_items or {}).get(code, 0)


def _ge_fill_for(item: str, qty: int,
                 game_data: GameData) -> GeFillSellOrderAction | None:
    """A `GeFillSellOrderAction` for `qty` of `item`, or None.

    Extracted rather than inlined because the same three conditions are checked
    by `GatherMaterialsGoal` and by `UpgradeEquipmentGoal`, and a fourth
    hand-written copy is how the three would drift. None when the GE has no
    location, no standing sell order, an order too small to fill the whole
    quantity in one go, or a price the NPC beats.

    THE WHOLE-QUANTITY RULE IS NOT AN OPTIMISATION. A partial fill leaves the
    remainder unsourced inside a plan the planner already costed as complete.
    """
    ge_loc = game_data.grand_exchange_location()
    order = game_data.ge_best_sell_order(item)
    if ge_loc is None or order is None or order[2] < qty:
        return None
    sellers = game_data.npcs_selling_item(item)
    if not sellers:
        # No NPC sells it, so there is no buy edge for this fill to be the DUAL
        # of. The ladder offers GE only as the cheaper of two buy venues; with
        # one venue there is nothing to choose between, and admitting it here
        # would be a new sourcing rule rather than the restoration of an old
        # one. Same guard `GatherMaterialsGoal` applies by reaching this code
        # only after `if not sellers: continue`.
        return None
    npc_price = min(p for _n, p in sellers)
    order_id, price, _order_qty = order
    if choose_buy_venue(npc_price, price) is not BuyVenue.GE:
        return None
    return GeFillSellOrderAction(order_id=order_id, item_code=item, price=price,
                                 quantity=qty, ge_location=ge_loc)


def craft_utility_ladder(
    target_code: str,
    runs: int,
    equip_qty: int,
    actions: list[Action],
    state: WorldState,
    game_data: GameData,
) -> list[Action]:
    """Gather/buy/withdraw/craft/move/equip action filter for ONE utility target.

    Builds the closure of actions needed to craft `runs` batches of
    `target_code` and equip `equip_qty` into the utility slot
    `utility_slot_for` picks (the slot already holding the code, else a FREE
    slot, else the smaller stack).  Mirrors the recipe-closure action filter
    from CraftPotionsGoal.relevant_actions, parameterised for reuse by
    CraftUnlockBoostGoal and other utility-slot craft goals.
    """
    craftable_mats = requirement_craftables(
        game_data.requirement_graph.graph(), [target_code])
    # Withdraw-eligible codes: craftable intermediates + target; every leaf
    # material arrives via the closure-demand union below (the historical
    # per-resource primary-drop loop was redundant, and with GAP-7's widened
    # needed_resources it would admit junk withdraws — the primary drop of a
    # secondarily-needed resource is not a closure material).
    withdrawable: set[str] = set(craftable_mats) | {target_code}
    chain = dict(demand_set(game_data.requirement_graph.graph(), [target_code]).quantities)
    withdrawable |= set(chain)

    buy_chain = dict(demand_set(
        game_data.requirement_graph.graph(), [target_code], {target_code: runs}).quantities)

    result: list[Action] = []
    have_craft = False
    for a in actions:
        if isinstance(a, CraftAction) and a.code == target_code:
            if not have_craft:
                have_craft = True
                result.append(a if a.quantity == runs
                              else dataclasses.replace(a, quantity=runs))
        elif isinstance(a, CraftAction) and a.code in craftable_mats:
            result.append(size_intermediate_craft(a, buy_chain, state, game_data))
        elif isinstance(a, GatherAction) and gather_serves_closure(
                a.resource_code, a.drop_item_override,
                game_data.resource_drops, chain):
            # GAP-7 admission precision: the gather's EFFECTIVE drop
            # (override or primary) must be a closure material — resource
            # membership alone fans every drop-variant into the search.
            result.append(a)
        elif isinstance(a, NpcBuyAction) and a.item_code in chain:
            buy_qty = max(1, buy_chain.get(a.item_code, 0)
                          - _held(a.item_code, state))
            result.append(a if a.quantity == buy_qty
                          else dataclasses.replace(a, quantity=buy_qty))
            # THE GE FILL, the DUAL of the NPC buy above and the route this
            # ladder lost at the wave-3a flip. Pre-flip the potion root was an
            # `UpgradeEquipmentGoal`, which carries this widening
            # (`goals/gathering.py:600-610`, `goals/progression.py`); the
            # CRAFT_POTIONS guard's goal does not, and 289 live GE fills went
            # with it.
            #
            # Same rule as its sibling, not a new one: fill only an EXISTING
            # sell order, only when it can supply the whole quantity in one
            # fill, and only when `choose_buy_venue` prefers GE over the NPC
            # price — the decision proved in `formal/Formal/BuySourceVenue.lean`.
            # The least-cost planner then picks between the two edges. We never
            # POST an order here.
            _ge_fill = _ge_fill_for(a.item_code, buy_qty, game_data)
            if _ge_fill is not None:
                result.append(_ge_fill)
        elif (isinstance(a, WithdrawItemAction) and a.code in withdrawable) or isinstance(a, MoveAction):
            result.append(a)
    result.append(EquipAction(code=target_code, slot=utility_slot_for(target_code, state),
                              quantity=equip_qty))
    return result
