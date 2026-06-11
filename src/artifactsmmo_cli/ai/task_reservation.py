"""Task-material reservation: protect an active items task's material pipeline
from step-tier goals that would CONSUME it.

Root cause (trace 2026-06-09): while PursueTask(copper_bar items task 0/11)
pools crafted bars, the skill-grind step GatherMaterials(copper_helmet) becomes
trivially plannable the instant bars exist, wins the step tier, and
Craft(copper_helmet) eats 6 bars — the task restarts from zero, forever.

RULE (reservation-as-step-suppression with surplus carve-out): while an items
task is active with remaining = task_total - task_progress > 0, the closure
demand of the task item x remaining is RESERVED. A step-tier goal is DEFERRED
this cycle iff its craft closure consumes some reserved item r with
owned(r) > 0 and owned(r) <= demand[r] (no surplus), where owned = inventory +
bank (bank None -> treated as 0: conservative-safe). Surplus above the
remaining need is free; remaining == 0 reserves nothing. Re-evaluated every
cycle (defer, not ban).

Pure — no I/O, no classes. PURE CORES (mechanical-extraction P3a):
`task_reserved_demand_pure` / `consumes_reserved_pure` carry the decision over
plain data (state scalars + the `recipes` mapping), calling the shared
`_closure_demand` core directly; they are mechanically extracted to
`formal/Formal/Extracted/TaskReservation.lean` and bridged against the proved
hand model formal/Formal/TaskReservation.lean (`reservedDemand` /
`consumesReserved`). The public wrappers preserve the original
(WorldState, GameData) API exactly and forward.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import _closure_demand
from artifactsmmo_cli.ai.world_state import WorldState


def task_reserved_demand_pure(
    task_type: str | None,
    task_code: str | None,
    task_total: int,
    task_progress: int,
    recipes: Mapping[str, dict[str, int]],
) -> dict[str, int]:
    """The active items task's reserved demand: {} unless an items task is
    active with remaining > 0, else the closure demand of the task item
    (task item + transitive recipe inputs) scaled by the remaining units."""
    if task_code is None:
        return {}
    if task_type != "items" or task_code == "":
        return {}
    remaining = task_total - task_progress
    if remaining <= 0:
        return {}
    no_visited: dict[str, int] = {}
    demand: dict[str, int] = {}
    demand = _closure_demand(len(recipes) + 1, task_code, remaining, recipes,
                             no_visited, demand)
    return demand


def consumes_reserved_pure(
    needed: Mapping[str, int],
    task_type: str | None,
    task_code: str | None,
    task_total: int,
    task_progress: int,
    inventory: Mapping[str, int],
    bank_items: Mapping[str, int] | None,
    recipes: Mapping[str, dict[str, int]],
) -> bool:
    """True iff producing `needed` (a goal's item -> qty map) would consume a
    reserved item without surplus: some r in keys(needed) ∪ closure_inputs(
    needed) has r reserved, owned(r) > 0, and owned(r) <= demand[r].

    Reserved-demand values are always >= 1 (the multiplier starts at
    remaining >= 1 and zero-quantity edges are skipped), so key presence is
    read as `demand.get(r, 0) != 0`."""
    demand = task_reserved_demand_pure(task_type, task_code, task_total,
                                       task_progress, recipes)
    if len(demand) == 0:
        return False
    no_visited: dict[str, int] = {}
    conflict: dict[str, int] = {}
    for item, _qty in needed.items():
        conflict = _closure_demand(len(recipes) + 1, item, 1, recipes,
                                   no_visited, conflict)
    bank: Mapping[str, int] = {}
    if bank_items is not None:
        bank = bank_items
    for item, _conflict_qty in conflict.items():
        if demand.get(item, 0) == 0:
            continue
        owned = inventory.get(item, 0) + bank.get(item, 0)
        if 0 < owned <= demand.get(item, 0):
            return True
    return False


def task_reserved_demand(state: WorldState, game_data: GameData) -> dict[str, int]:
    """The active items task's reserved demand: {} unless an items task is
    active with remaining > 0, else the closure demand of the task item
    (task item + transitive recipe inputs) scaled by the remaining units."""
    return task_reserved_demand_pure(
        state.task_type, state.task_code, state.task_total, state.task_progress,
        game_data.crafting_recipes,
    )


def consumes_reserved(needed: dict[str, int], state: WorldState,
                      game_data: GameData) -> bool:
    """True iff producing `needed` (a goal's item -> qty map) would consume a
    reserved item without surplus: some r in keys(needed) ∪ closure_inputs(
    needed) has r reserved, owned(r) > 0, and owned(r) <= demand[r]."""
    return consumes_reserved_pure(
        needed, state.task_type, state.task_code, state.task_total,
        state.task_progress, state.inventory, state.bank_items,
        game_data.crafting_recipes,
    )
