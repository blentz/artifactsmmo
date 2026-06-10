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

Pure — no I/O, no classes. Mirrored by the proved Lean model
formal/Formal/TaskReservation.lean (`reservedDemand` / `consumesReserved`).
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.world_state import WorldState


def task_reserved_demand(state: WorldState, game_data: GameData) -> dict[str, int]:
    """The active items task's reserved demand: {} unless an items task is
    active with remaining > 0, else the closure demand of the task item
    (task item + transitive recipe inputs) scaled by the remaining units."""
    if state.task_type != "items" or not state.task_code:
        return {}
    remaining = state.task_total - state.task_progress
    if remaining <= 0:
        return {}
    demand: dict[str, int] = {}
    closure_demand(state.task_code, remaining, game_data, demand, frozenset())
    return demand


def consumes_reserved(needed: dict[str, int], state: WorldState,
                      game_data: GameData) -> bool:
    """True iff producing `needed` (a goal's item -> qty map) would consume a
    reserved item without surplus: some r in keys(needed) ∪ closure_inputs(
    needed) has r reserved, owned(r) > 0, and owned(r) <= demand[r]."""
    demand = task_reserved_demand(state, game_data)
    if not demand:
        return False
    conflict: dict[str, int] = {}
    for item in needed:
        closure_demand(item, 1, game_data, conflict, frozenset())
    bank = state.bank_items or {}
    for item in conflict:
        if item not in demand:
            continue
        owned = state.inventory.get(item, 0) + bank.get(item, 0)
        if 0 < owned <= demand[item]:
            return True
    return False
