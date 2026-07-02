"""task_batch_size: how many task units to produce per PursueTask plan.

Bounded by the units the task still needs, the inventory space available for the
raw materials (counting already-held recipe mats as free-equivalent so K stays
stable as ore accumulates), and a depth cap. Floors at 1 (today's behavior).

PURE CORE (mechanical-extraction P3a): the code-agnostic `craft_batch_size_pure`
carries the whole clamp over plain data (a `demand` plus `recipes`/`drops`
mappings), calling the recipe_closure pure cores directly.
`task_batch_size_pure` is the thin items-task wrapper delegating with
`demand = remaining`. Both are mechanically extracted to
`formal/Formal/Extracted/TaskBatch.lean` and bridged against the hand model
`formal/Formal/TaskBatch.lean` (`batchSize` — demand-generic). The public
`task_batch_size` preserves the original (WorldState, GameData) API exactly and
forwards.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import _closure_visited, _raw_units
from artifactsmmo_cli.ai.world_state import WorldState

BATCH_CAP = 10
"""Max units per plan — bounds planner search depth and per-trip risk. Tunable."""

_MIN_FREE_SLOTS = 3
"""Mirror GatherAction._MIN_FREE_SLOTS so gathering stays applicable to the end."""


def craft_batch_size_pure(
    code: str | None,
    demand: int,
    inventory: Mapping[str, int],
    inventory_free: int,
    recipes: Mapping[str, dict[str, int]],
    drops: Mapping[str, str],
    yields: Mapping[str, int],
) -> int:
    """Runs to craft of `code` in one plan; >= 1 (pure core).

    Bounded by `demand` (units still needed), the inventory space the raws
    require (already-held closure drops count as free-equivalent so the batch
    stays stable as raws accumulate), and BATCH_CAP. `code` with no raw inputs
    (mats_per_unit == 0) is bounded by demand and the cap only.

    `yields` maps item code to output quantity per craft run (default 1 when
    absent) and is threaded into `_raw_units`, so the per-unit raw footprint is
    yield-aware (ceil-batch) — matching the yield-aware closure demand fed in as
    `demand`. All-`Y=1` data (today's) leaves the fit unchanged."""
    if code is None:
        return 1
    if demand <= 0:
        return 1
    no_visited: dict[str, int] = {}
    mats_per_unit = _raw_units(len(recipes) + 1, code, recipes, yields, no_visited)
    if mats_per_unit == 0:
        return max(1, min(demand, BATCH_CAP))
    closure: dict[str, int] = {}
    closure = _closure_visited(len(recipes) + 1, code, recipes, closure)
    held_recipe = 0
    for _res, drop_item in drops.items():
        if closure.get(drop_item, 0) == 1:
            held_recipe = held_recipe + inventory.get(drop_item, 0)
    usable = (inventory_free + held_recipe) - _MIN_FREE_SLOTS
    fit = usable // mats_per_unit
    return max(1, min(demand, fit, BATCH_CAP))


def task_batch_size_pure(
    task_type: str | None,
    task_code: str | None,
    task_total: int,
    task_progress: int,
    inventory: Mapping[str, int],
    inventory_free: int,
    recipes: Mapping[str, dict[str, int]],
    drops: Mapping[str, str],
    yields: Mapping[str, int],
) -> int:
    """Units to produce/deliver in one PursueTask plan; >= 1 (pure core).

    The items-task branch delegates to `craft_batch_size_pure` with
    `demand = remaining` (task_total - task_progress); the code-agnostic core
    carries the identical inventory-bounded clamp. A None `task_code` yields 1
    via `craft_batch_size_pure`'s own None guard (the gate below keeps
    `task_code` Optional so it forwards without unwrapping). `yields` is
    forwarded so the raw footprint is yield-aware (see `craft_batch_size_pure`)."""
    if task_type != "items" or task_code == "" or task_total <= 0:
        return 1
    remaining = task_total - task_progress
    if remaining <= 0:
        return 1
    return craft_batch_size_pure(task_code, remaining, inventory,
                                 inventory_free, recipes, drops, yields)


def task_batch_size(state: WorldState, game_data: GameData) -> int:
    """Units to produce/deliver in one PursueTask plan; >= 1."""
    return task_batch_size_pure(
        state.task_type, state.task_code, state.task_total, state.task_progress,
        state.inventory, state.inventory_free,
        game_data.crafting_recipes, game_data.resource_drops,
        game_data.craft_yields,
    )
