"""Circuit breaker: surface craftable items toward active goals (task,
target_gear, target_tools) that the bot can craft RIGHT NOW from inventory
AND whose crafting actually RELIEVES inventory pressure.

Used by the CRAFT_RELIEF guard to preempt DEPOSIT_FULL / DISCARD_HIGH when
inventory pressure is rising AND the bot is sitting on raw materials it
could convert into a goal item — banking or deleting those materials
discards progress, crafting them advances it.

Trace 2026-06-05 cycle 71: Robby had 67 ash_wood, task=ash_plank(3/13).
Inventory hit 89/104. Without this circuit breaker the guard ladder routed
to DiscardOverstock (deleted 5 apples) instead of crafting ash_plank
toward the task.

Trace 2026-06-08 cycles 570-632 (the net-relief gate): at ~70% pressure the
guard picked cooked_gudgeon — a 1:1 recipe (1 gudgeon -> 1 cooked_gudgeon)
that frees ZERO inventory units — and crafted x1 thirty-eight times while
flapping CraftRelief<->PursueTask every 1-2 cycles, ping-ponging the gather
spot and the workshop per single item. Relief candidacy therefore requires
net relief (input units consumed > output units produced per craft), and
the candidate quantity batches up to what relieves pressure below the
firing threshold in ONE activation instead of x1 per cycle.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_reservation import consumes_reserved
from artifactsmmo_cli.ai.world_state import WorldState

CRAFT_RELIEF_FRACTION = 0.70
"""When inv pressure crosses this fraction AND a goal-item is craftable
from current inventory with net relief, the CRAFT_RELIEF guard fires AHEAD
of DEPOSIT_FULL. Catches the case where raw materials would otherwise be
banked or deleted while the bot was one Craft action from converting them
into task progress. Defined here (not tiers/guards.py) so the candidate
quantity computation can size batches against the same threshold;
tiers/guards.py re-imports it."""


@dataclass(frozen=True)
class ReliefCandidate:
    """One item the bot can craft from current inventory to relieve pressure.

    `quantity` is the number of crafts for ONE guard activation: the maximum
    simultaneously-craftable units bounded by the smallest recipe input
    stack, by `cap` (e.g. task remaining, BATCH_CAP), and by the crafts
    needed to push inventory pressure back below CRAFT_RELIEF_FRACTION.
    `priority_class` orders candidates: 0=task item, 1=target_gear /
    active-step chain materials, 2=target_tools, 3=other. Lower wins."""
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


def _net_relief_per_craft(recipe: dict[str, int]) -> int:
    """Inventory units freed by ONE craft: total input units consumed minus
    the single output unit produced (game recipes yield 1 unit per craft).
    <= 0 means the craft relieves nothing (1:1 recipes like
    gudgeon -> cooked_gudgeon) and must not be a relief candidate."""
    return sum(recipe.values()) - 1


def _crafts_to_relieve(state: WorldState, net_per_craft: int) -> int | None:
    """Crafts needed to push inventory usage strictly below
    CRAFT_RELIEF_FRACTION, given `net_per_craft` units freed per craft.
    None when usage is already below the threshold (no pressure to relieve,
    so no relief-based cap applies)."""
    excess = state.inventory_used - CRAFT_RELIEF_FRACTION * state.inventory_max
    if excess < 0:
        return None
    return int(excess // net_per_craft) + 1


def craft_relief_candidates(
    state: WorldState, game_data: GameData,
    target_gear: frozenset[str] = frozenset(),
    target_tools: frozenset[str] = frozenset(),
    batch_cap: int = 10,
    step_items: frozenset[str] = frozenset(),
) -> list[ReliefCandidate]:
    """Items the bot can craft from inventory NOW that advance an active goal
    AND free inventory units (net relief gate). Gear/tool candidates whose
    recipe closure would consume reserved task materials (task_reservation)
    are excluded; the task item itself is exempt — producing it IS the
    reserved pipeline.

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
        recipe = game_data.crafting_recipe(item_code) or {}
        net = _net_relief_per_craft(recipe)
        if net <= 0:
            return  # 1:1 (or worse) recipe frees nothing — not relief.
        if priority_class > 0 and consumes_reserved(
                {item_code: 1}, state, game_data):
            return  # would eat the active task's reserved materials.
        # Run-16 trace 2026-06-12 09:09:33 (cycle 90): CraftRelief(copper_dagger)
        # — a target_gear candidate — consumed the 6 copper_bars that completed
        # the helmet grind's material set one action before the craft (the
        # alphabetical tie-break ranked it above copper_helmet at equal
        # priority/quantity). A non-step candidate whose recipe consumes the
        # active step's protected materials destroys chain progress; step
        # items themselves are exempt — producing them IS the chain.
        if (priority_class > 0 and item_code not in step_items
                and any(mat in step_items for mat in recipe)):
            return
        quantity = min(qty, cap, batch_cap)
        relief_cap = _crafts_to_relieve(state, net)
        if relief_cap is not None:
            quantity = min(quantity, relief_cap)
        candidates.append(ReliefCandidate(
            item_code=item_code,
            quantity=quantity,
            priority_class=priority_class,
        ))

    # Active items-task — cap by remaining task units so we don't over-craft.
    if (state.task_type == "items" and state.task_code
            and state.task_total > 0 and state.task_progress < state.task_total):
        consider(state.task_code, 0, state.task_total - state.task_progress)

    # Active step goal's chain materials. Run-13 trace 2026-06-12 cycles
    # 92-95: with 60 ash on hand and the plan already at the plank-craft
    # phase, the ladder took two bank trips (freeing 2 then 1 units) instead
    # of crafting a plank that frees 9 — relief candidacy only saw
    # task/gear/tools. Crafting an in-flight chain intermediate is both
    # pressure relief AND step progress. Sorted for deterministic ordering.
    for code in sorted(step_items):
        consider(code, 1, batch_cap)

    # Target gear / tools — cap at batch_cap; equip layer only needs 1 of each.
    for code in target_gear:
        consider(code, 1, batch_cap)
    for code in target_tools:
        consider(code, 2, batch_cap)

    candidates.sort(key=lambda c: (c.priority_class, -c.quantity, c.item_code))
    return candidates
