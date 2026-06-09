"""task_batch_size: how many task units to produce per PursueTask plan.

Bounded by the units the task still needs, the inventory space available for the
raw materials (counting already-held recipe mats as free-equivalent so K stays
stable as ore accumulates), and a depth cap. Floors at 1 (today's behavior).
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import raw_material_units, recipe_closure
from artifactsmmo_cli.ai.world_state import WorldState

BATCH_CAP = 10
"""Max units per plan — bounds planner search depth and per-trip risk. Tunable."""

_MIN_FREE_SLOTS = 3
"""Mirror GatherAction._MIN_FREE_SLOTS so gathering stays applicable to the end."""


def task_batch_size(state: WorldState, game_data: GameData) -> int:
    """Units to produce/deliver in one PursueTask plan; >= 1."""
    if state.task_type != "items" or not state.task_code or state.task_total <= 0:
        return 1
    remaining = state.task_total - state.task_progress
    if remaining <= 0:
        return 1
    mats_per_unit = raw_material_units(game_data, state.task_code)
    needed_resources, _ = recipe_closure(game_data, [state.task_code])
    held_recipe = sum(
        state.inventory.get(game_data.resource_drops[r], 0) for r in needed_resources
    )
    usable = (state.inventory_free + held_recipe) - _MIN_FREE_SLOTS
    fit = usable // mats_per_unit
    return max(1, min(remaining, fit, BATCH_CAP))
