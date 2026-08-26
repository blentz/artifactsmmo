"""Quantity of a consumable currently equipped across the utility slots."""

from artifactsmmo_cli.ai.utility_slot import UTILITY_SLOTS, utility_slot_quantity
from artifactsmmo_cli.ai.world_state import WorldState


def equipped_potion_qty(state: WorldState, code: str) -> int:
    """Total quantity of `code` held across the utility slots (0 if not equipped)."""
    total = 0
    for slot in UTILITY_SLOTS:
        if state.equipment.get(slot) == code:
            total += utility_slot_quantity(state, slot)
    return total
