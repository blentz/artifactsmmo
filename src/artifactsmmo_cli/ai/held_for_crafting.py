"""Units of an item on hand for crafting: the bag plus the bank.

A leaf module so the potion supply (`potion_supply`) and the utility-craft
ladder (`craft_ladder`) can share it without importing each other."""

from artifactsmmo_cli.ai.world_state import WorldState


def held_for_crafting(code: str, state: WorldState) -> int:
    """Units of `code` on hand for crafting: inventory plus bank."""
    return state.inventory.get(code, 0) + (state.bank_items or {}).get(code, 0)
