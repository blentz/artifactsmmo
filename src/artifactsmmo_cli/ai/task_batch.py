"""task_batch_size: how many task units to produce per PursueTask plan.

Bounded by the units the task still needs, the inventory space available for the
raw materials (counting already-held recipe mats as free-equivalent so K stays
stable as ore accumulates), and a depth cap. Floors at 1 (today's behavior).

PURE CORE (mechanical-extraction P3a): `task_batch_size_pure` carries the whole
decision over plain data (state scalars + `recipes`/`drops` mappings), calling
the recipe_closure pure cores directly; it is mechanically extracted to
`formal/Formal/Extracted/TaskBatch.lean` and bridged against the hand model
`formal/Formal/TaskBatch.lean` (`batchSize`). The public `task_batch_size`
preserves the original (WorldState, GameData) API exactly and forwards.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import _closure_visited, _raw_units
from artifactsmmo_cli.ai.world_state import WorldState

BATCH_CAP = 10
"""Max units per plan — bounds planner search depth and per-trip risk. Tunable."""

_MIN_FREE_SLOTS = 3
"""Mirror GatherAction._MIN_FREE_SLOTS so gathering stays applicable to the end."""


def task_batch_size_pure(
    task_type: str | None,
    task_code: str | None,
    task_total: int,
    task_progress: int,
    inventory: Mapping[str, int],
    inventory_free: int,
    recipes: Mapping[str, dict[str, int]],
    drops: Mapping[str, str],
) -> int:
    """Units to produce/deliver in one PursueTask plan; >= 1 (pure core).

    `held_recipe` counts already-held drop items of every resource in the task
    item's recipe closure: each resource whose drop is in the closure
    contributes the inventory count of its drop item (per resource, exactly as
    the original needed_resources sum)."""
    if task_code is None:
        return 1
    if task_type != "items" or task_code == "" or task_total <= 0:
        return 1
    remaining = task_total - task_progress
    if remaining <= 0:
        return 1
    no_visited: dict[str, int] = {}
    mats_per_unit = _raw_units(len(recipes) + 1, task_code, recipes, {}, no_visited)
    closure: dict[str, int] = {}
    closure = _closure_visited(len(recipes) + 1, task_code, recipes, closure)
    held_recipe = 0
    for _res, drop_item in drops.items():
        if closure.get(drop_item, 0) == 1:
            held_recipe = held_recipe + inventory.get(drop_item, 0)
    usable = (inventory_free + held_recipe) - _MIN_FREE_SLOTS
    fit = usable // mats_per_unit
    return max(1, min(remaining, fit, BATCH_CAP))


def task_batch_size(state: WorldState, game_data: GameData) -> int:
    """Units to produce/deliver in one PursueTask plan; >= 1."""
    return task_batch_size_pure(
        state.task_type, state.task_code, state.task_total, state.task_progress,
        state.inventory, state.inventory_free,
        game_data.crafting_recipes, game_data.resource_drops,
    )
