"""Compute per-item "useful quantity cap" — beyond which inventory is overstock.

Caps are pragmatic: max recipe demand × batch buffer, plus task demand, plus a
safety floor for items currently in use. Anything held over the cap is wasted
inventory space.
"""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

BATCH_BUFFER = 5
"""How many craft batches worth of material to keep on hand. With BATCH=5 and
a recipe needing 6 of a mat, the cap is 30."""

SAFETY_FLOOR = 3
"""Always keep at least this many of any item that has any recipe use, so the
bot doesn't immediately re-gather what it just discarded."""

EQUIPPABLE_KEEP = 1
"""Keep at least one of any equippable item Robby can wear — even if not
currently equipped — so the equipment optimizer has it as a swap candidate."""

# Items consumed by API actions (not recipes). Keep enough to use them.
ACTION_CONSUMABLES_CAP = {
    TASKS_COIN_CODE: 9,  # TaskExchange burns 3; keep ~3 batches worth
}


def useful_quantity_cap(
    item_code: str, state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
) -> int:
    """Return the maximum count of `item_code` worth keeping.

    Anything in inventory beyond this is overstock — safe to sell or delete.
    Considers:
      - Largest recipe-demand for this item across all known recipes
      - Current task demand (`state.task_code == item_code` means keep enough
        for completion)
      - Equipped items (always keep at least 1 of each equipped code)
    """
    # Equipped items: never count below 1
    equipped = {code for code in state.equipment.values() if code}
    if item_code in equipped:
        return max(1, useful_quantity_cap_excl_equipped(item_code, state, game_data,
                                                          batch_buffer, safety_floor))
    return useful_quantity_cap_excl_equipped(item_code, state, game_data,
                                              batch_buffer, safety_floor)


def useful_quantity_cap_excl_equipped(
    item_code: str, state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
) -> int:
    """useful_quantity_cap without the equipped-floor adjustment."""
    recipe_max = game_data.max_recipe_demand(item_code)
    recipe_cap = recipe_max * batch_buffer if recipe_max > 0 else 0
    if recipe_max > 0:
        recipe_cap = max(recipe_cap, safety_floor)

    # Active items-task demand: keep enough to finish the task
    task_cap = 0
    if state.task_type == "items" and state.task_code == item_code:
        remaining = max(0, state.task_total - state.task_progress)
        task_cap = remaining

    # Action-consumed items (e.g. tasks_coin for TaskExchange)
    action_cap = ACTION_CONSUMABLES_CAP.get(item_code, 0)

    # Equippable items: keep one of each for the equipment optimizer's
    # candidate pool. Without this, the bot discards weapons/armor it
    # could swap to per-fight.
    equippable_cap = 0
    stats = game_data.item_stats(item_code)
    if stats is not None and ITEM_TYPE_TO_SLOTS.get(stats.type_):
        equippable_cap = EQUIPPABLE_KEEP

    return max(recipe_cap, task_cap, action_cap, equippable_cap)


def overstocked_items(
    state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
) -> dict[str, int]:
    """Return {item_code: excess_quantity} for every overstocked item.

    Items with no recipe use and no task use get a cap of 0 — they're pure
    junk. Items with caps return their `qty - cap` excess.
    """
    excess: dict[str, int] = {}
    for code, qty in state.inventory.items():
        if qty <= 0:
            continue
        cap = useful_quantity_cap(code, state, game_data, batch_buffer, safety_floor)
        if qty > cap:
            excess[code] = qty - cap
    return excess
