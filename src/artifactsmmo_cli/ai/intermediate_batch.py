"""Rebatch an intermediate CraftAction to its inventory-bounded closure demand."""

import dataclasses
from collections.abc import Mapping

from artifactsmmo_cli.ai.actions.crafting import CraftAction
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
