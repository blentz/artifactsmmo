"""Rebatch an intermediate CraftAction or a closure GatherAction to its
inventory-bounded closure demand."""

import dataclasses
from collections.abc import Mapping

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gather_apply_core import gather_batch_size_pure
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_batch import craft_batch_size_pure
from artifactsmmo_cli.ai.world_state import WorldState


def size_intermediate_craft(action: CraftAction, chain: Mapping[str, int],
                            state: WorldState, game_data: GameData) -> CraftAction:
    """Return `action` with its quantity set to the inventory-bounded batch for
    its net closure demand (chain demand minus what is already held in
    inventory+bank). Unchanged when the sized quantity already matches."""
    held = state.inventory.get(action.code, 0) + (state.bank_items or {}).get(action.code, 0)
    demand = max(0, chain.get(action.code, 0) - held)
    qty = craft_batch_size_pure(action.code, demand, state.inventory,
                                state.inventory_free, game_data.crafting_recipes,
                                game_data.resource_drops, game_data.craft_yields)
    return action if action.quantity == qty else dataclasses.replace(action, quantity=qty)


def size_closure_gather(action: GatherAction, chain: Mapping[str, int],
                        state: WorldState, game_data: GameData) -> GatherAction:
    """Return `action` with its quantity set to the inventory-bounded batch for
    its DROP ITEM's net closure demand (chain demand minus inventory+bank
    holdings). Unchanged when the sized quantity already matches.

    The twin of `size_intermediate_craft`, and sized by the goal for the same
    reason: the action factory has no demand context, so a factory-set quantity
    could only ever be a guess.

    Keyed on the drop item, not the resource code — a `drop_item_override`
    gather targets a secondary drop, and it is that item the closure demands.

    `effective_quantity` reads `action.quantity`, so it cannot compute a size
    for a quantity the action does not yet have; this instead reuses
    `GatherAction.inv` (the same inventory-projection helper `is_applicable`,
    `apply`, and `effective_quantity` share, and public precisely because this
    module is outside `GatherAction`) and calls `gather_batch_size_pure`
    directly against the demand.
    """
    drop = action.drop_item(game_data)
    held = state.inventory.get(drop, 0) + (state.bank_items or {}).get(drop, 0)
    demand = max(0, chain.get(drop, 0) - held)
    qty = gather_batch_size_pure(action.inv(state), demand, drop)
    return action if action.quantity == qty else dataclasses.replace(action, quantity=qty)
