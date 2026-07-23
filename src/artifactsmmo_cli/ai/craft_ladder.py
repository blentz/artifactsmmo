"""Shared craft-a-utility ladder for CraftPotionsGoal and CraftUnlockBoostGoal.

craft_utility_ladder builds the gather/buy/withdraw/craft/move/equip action
filter for ONE utility target, batched to `runs` and equipping `equip_qty`
into utility1_slot.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.recipe_closure import (
    closure_demand,
    gather_serves_closure,
)
from artifactsmmo_cli.ai.requirement_projections import requirement_craftables
from artifactsmmo_cli.ai.world_state import WorldState

_TARGET_SLOT = "utility1_slot"


def _held(code: str, state: WorldState) -> int:
    """Units of `code` on hand for crafting: inventory plus bank."""
    return state.inventory.get(code, 0) + (state.bank_items or {}).get(code, 0)


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
    `target_code` and equip `equip_qty` into utility1_slot.  Mirrors the
    recipe-closure action filter from CraftPotionsGoal.relevant_actions,
    parameterised for reuse by CraftUnlockBoostGoal and other utility-slot
    craft goals.
    """
    craftable_mats = requirement_craftables(
        game_data.requirement_graph.graph(), [target_code])
    # Withdraw-eligible codes: craftable intermediates + target; every leaf
    # material arrives via the closure-demand union below (the historical
    # per-resource primary-drop loop was redundant, and with GAP-7's widened
    # needed_resources it would admit junk withdraws — the primary drop of a
    # secondarily-needed resource is not a closure material).
    withdrawable: set[str] = set(craftable_mats) | {target_code}
    chain: dict[str, int] = {}
    closure_demand(target_code, 1, game_data, chain, frozenset())
    withdrawable |= set(chain)

    buy_chain: dict[str, int] = {}
    closure_demand(target_code, runs, game_data, buy_chain, frozenset())

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
        elif (isinstance(a, WithdrawItemAction) and a.code in withdrawable) or isinstance(a, MoveAction):
            result.append(a)
    result.append(EquipAction(code=target_code, slot=_TARGET_SLOT, quantity=equip_qty))
    return result
