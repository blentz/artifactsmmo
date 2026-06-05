"""Circuit breaker: surface craftable items toward active goals (task,
target_gear, target_tools) that the bot can craft RIGHT NOW from inventory.

Used by the CRAFT_RELIEF guard to preempt DEPOSIT_FULL / DISCARD_HIGH when
inventory pressure is rising AND the bot is sitting on raw materials it
could convert into a goal item — banking or deleting those materials
discards progress, crafting them advances it.

Trace 2026-06-05 cycle 71: Robby had 67 ash_wood, task=ash_plank(3/13)
with a 1:1 ash_wood->ash_plank recipe. Inventory hit 89/104. Without this
circuit breaker the guard ladder routed to DiscardOverstock (deleted 5
apples, would have deleted ash_wood next on cap=5) instead of crafting
10 ash_plank to complete the task. The fix offers a 'craft first' branch
when inv pressure forces a decision and a goal item is craftable from
inventory.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class ReliefCandidate:
    """One item the bot can craft from current inventory to relieve pressure.

    `quantity` is the maximum simultaneously-craftable units bounded by the
    smallest recipe input stack and by `cap` (e.g. task remaining, BATCH_CAP).
    `priority_class` orders candidates: 0=task item, 1=target_gear,
    2=target_tools, 3=other. Lower wins."""
    item_code: str
    quantity: int
    priority_class: int


def _can_craft_qty(item_code: str, state: WorldState, game_data: GameData) -> int:
    """Max quantity craftable from current inventory + skill check. 0 means
    not craftable (missing materials, missing skill, no recipe, unknown stats)."""
    stats = game_data.item_stats(item_code)
    if stats is None or stats.crafting_skill is None:
        return 0
    if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
        return 0
    recipe = game_data.crafting_recipe(item_code)
    if not recipe:
        return 0
    # Bound by the smallest stack-to-mat ratio across recipe inputs.
    return min(
        state.inventory.get(mat, 0) // qty_per
        for mat, qty_per in recipe.items()
    )


def craft_relief_candidates(
    state: WorldState, game_data: GameData,
    target_gear: frozenset[str] = frozenset(),
    target_tools: frozenset[str] = frozenset(),
    batch_cap: int = 10,
) -> list[ReliefCandidate]:
    """Items the bot can craft from inventory NOW that advance an active goal.

    Sorted by priority_class asc, then quantity desc, then code asc — so the
    task item with the most craftable units wins. Empty list when nothing
    qualifies (callers treat as 'circuit breaker doesn't fire')."""
    seen: set[str] = set()
    candidates: list[ReliefCandidate] = []

    def consider(item_code: str, priority_class: int, cap: int) -> None:
        if item_code in seen or cap <= 0:
            return
        seen.add(item_code)
        qty = _can_craft_qty(item_code, state, game_data)
        if qty <= 0:
            return
        candidates.append(ReliefCandidate(
            item_code=item_code,
            quantity=min(qty, cap, batch_cap),
            priority_class=priority_class,
        ))

    # Active items-task — cap by remaining task units so we don't over-craft.
    if (state.task_type == "items" and state.task_code
            and state.task_total > 0 and state.task_progress < state.task_total):
        consider(state.task_code, 0, state.task_total - state.task_progress)

    # Target gear / tools — cap at batch_cap; equip layer only needs 1 of each.
    for code in target_gear:
        consider(code, 1, batch_cap)
    for code in target_tools:
        consider(code, 2, batch_cap)

    candidates.sort(key=lambda c: (c.priority_class, -c.quantity, c.item_code))
    return candidates
