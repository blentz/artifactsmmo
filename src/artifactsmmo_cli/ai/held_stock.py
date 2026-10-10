"""The units of a consumable a character holds (USER 2026-10-09: held stock is
free until used up)."""

from artifactsmmo_cli.ai.bank_drain import owned_total
from artifactsmmo_cli.ai.utility_slot import UTILITY_SLOTS, utility_slot_quantity
from artifactsmmo_cli.ai.world_state import WorldState


def held_count(code: str, state: WorldState) -> int:
    """Units of `code` held: bag + bank + every utility slot wearing it."""
    worn = sum(utility_slot_quantity(state, slot) for slot in UTILITY_SLOTS
               if state.equipment.get(slot) == code)
    return owned_total(state, frozenset({code})) + worn
