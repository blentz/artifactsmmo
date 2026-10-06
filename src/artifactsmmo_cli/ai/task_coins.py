"""The character's task-coin holding — a leaf, so the root walk can read it
without importing the exchange goal (which pulls in the action layer)."""

from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


def tasks_coin_total(state: WorldState) -> int:
    """Inventory + bank tasks_coin total (bank-unknown counts as zero)."""
    bank = state.bank_items or {}
    return state.inventory.get(TASKS_COIN_CODE, 0) + bank.get(TASKS_COIN_CODE, 0)
