"""Quantity of a consumable currently equipped across the utility slots."""

from artifactsmmo_cli.ai.world_state import WorldState

_UTILITY_SLOTS = ("utility1_slot", "utility2_slot")
_QTY_ATTR = {"utility1_slot": "utility1_slot_quantity",
             "utility2_slot": "utility2_slot_quantity"}


def equipped_potion_qty(state: WorldState, code: str) -> int:
    """Total quantity of `code` held across the utility slots (0 if not equipped)."""
    total = 0
    for slot in _UTILITY_SLOTS:
        if state.equipment.get(slot) == code:
            total += getattr(state, _QTY_ATTR[slot])
    return total
