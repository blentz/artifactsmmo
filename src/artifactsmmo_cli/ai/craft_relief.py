"""Circuit breaker: surface craftable INTERMEDIATE items toward active goals
(the items-task deliverable and the active step's chain materials) that the
bot can craft RIGHT NOW from inventory AND whose crafting actually RELIEVES
inventory pressure.

End-stage equippables (target gear / tools) are deliberately NOT relief
candidates: relief is for inventory management — converting raw materials
into intermediates — while assembling the final equippable is left to its
own goal. Trace 2026-06-13: with the committed root ObtainItem(copper_boots)
(8 copper_bar), relief crafted an off-objective copper_dagger (6 copper_bar)
every time copper_bar reached 6, permanently starving the boots root.

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

Inventory census 2026-07-12 (the SLOT gate — `_slot_delta`): net QUANTITY
relief is not relief at all when the bag's binding constraint is SLOTS. With
16 ash_wood in ONE stack, crafting 1 ash_plank frees 9 units but leaves 6
ash_wood + 1 ash_plank — slots 1 -> 2, strictly WORSE — and because
CRAFT_RELIEF out-ranks DEPOSIT_FULL ("craft before deposit") it PREEMPTED the
deposit that would actually have freed the bag, while eating the ash_wood the
keep authority reserves for the active goal (KeepReason.GOAL_MATERIALS). This
is the same quantity-vs-slot confusion as the HTTP-497 livelock. A craft is
relief only when it does not INCREASE the stack count, measured at the batch
it will actually perform — the ordering ("craft before deposit") is right once
the gate is honest, so GUARD_ORDER and CRAFT_RELIEF_FRACTION are unchanged.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_reservation import consumes_reserved
from artifactsmmo_cli.ai.thresholds import CRAFT_RELIEF_FRACTION as CRAFT_RELIEF_FRACTION
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class ReliefCandidate:
    """One item the bot can craft from current inventory to relieve pressure.

    `quantity` is the number of crafts for ONE guard activation: the crafts
    needed to push inventory pressure back below CRAFT_RELIEF_FRACTION, raised
    to the smallest SLOT-HONEST batch (`_slot_honest_batch`) and bounded above
    by the simultaneously-craftable units, by `cap` (e.g. task remaining) and
    by BATCH_CAP. `priority_class` orders candidates: 0=task item, 1=active-step
    chain materials. Lower wins."""
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


def _slot_delta(item_code: str, recipe: dict[str, int], quantity: int,
                state: WorldState) -> int:
    """Change in occupied inventory SLOTS from crafting `quantity` units of
    `item_code` out of the current bag. Negative/zero = the craft consolidates.

    The bag is SLOT-limited (20 stacks) long before it is QUANTITY-limited
    (~124 units) — `guards._used_fraction` already models pressure as
    `max(quantity_fraction, slot_fraction)` for exactly that reason. A craft
    that frees units can still ADD a stack:

        hold 16 ash_wood (1 stack) -> craft 1 ash_plank (consumes 10)
        leaves 6 ash_wood + 1 ash_plank  ->  SLOTS 1 -> 2  (WORSE)

    * a source stack is FREED iff the batch consumes it to zero (a remainder
      keeps its slot, however small);
    * the product costs a NEW slot unless a stack of that code is already held
      (then it merges and costs nothing).
    """
    freed = sum(1 for mat, per_craft in recipe.items()
                if state.inventory.get(mat, 0) - per_craft * quantity <= 0)
    gained = 0 if state.inventory.get(item_code, 0) > 0 else 1
    return gained - freed


def _slot_honest_batch(item_code: str, recipe: dict[str, int], floor_qty: int,
                       max_qty: int, state: WorldState) -> int | None:
    """The SMALLEST batch in `[floor_qty, max_qty]` that does not increase the
    slot count, or None when no batch in range is slot-honest.

    `floor_qty` is the pressure-relief batch (`_crafts_to_relieve`); the search
    walks UP from it because a craft only frees a slot by consuming its source
    stack WHOLE, so under-crafting is what leaves the remainder that adds a
    stack: with 20 ash_wood, x1 frees nothing (10 left + a plank = 2 stacks)
    while x2 clears the stack (1 -> 1). Nothing above `max_qty` is reachable
    (it is bounded by the on-hand inputs, the task remainder and BATCH_CAP), so
    a range with no slot-honest batch means the item is not relief AT ALL."""
    for quantity in range(floor_qty, max_qty + 1):
        if _slot_delta(item_code, recipe, quantity, state) <= 0:
            return quantity
    return None


def craft_relief_candidates(
    state: WorldState, game_data: GameData,
    batch_cap: int = 10,
    step_items: frozenset[str] = frozenset(),
) -> list[ReliefCandidate]:
    """Intermediate items the bot can craft from inventory NOW that advance an
    active goal AND relieve the bag on BOTH axes — it frees QUANTITY units (the
    net-relief gate) and does not ADD a stack (the SLOT gate, `_slot_delta`):
    the items-task deliverable and the active step's chain materials. End-stage
    gear/tools are NOT considered — relief is inventory management, not final
    assembly.
    A step candidate whose recipe would consume reserved task materials
    (task_reservation) is excluded; the task item itself is exempt — producing
    it IS the reserved pipeline.

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
        max_qty = min(qty, cap, batch_cap)
        relief_cap = _crafts_to_relieve(state, net)
        floor_qty = 1 if relief_cap is None else min(relief_cap, max_qty)
        quantity = _slot_honest_batch(item_code, recipe, floor_qty, max_qty, state)
        if quantity is None:
            return  # every reachable batch ADDS a stack — not relief.
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

    # Sole-output materials: for each held material m, if every recipe that
    # consumes m produces only ONE distinct output code, that sole output is a
    # relief candidate when craftable ≥1 AND net relief > 0.  This catches the
    # copper_ore -> copper_bar pattern where the material itself isn't on the
    # goal chain but its only craftable use advances a goal.
    # End-stage gear (equippable type) and tools (subtype=="tool") are excluded
    # — relief is inventory management, not final assembly (docstring guarantee).
    for mat_code, mat_qty in state.inventory.items():
        if mat_qty <= 0:
            continue
        outputs = {
            code for code, rec in game_data.crafting_recipes.items()
            if mat_code in rec
        }
        if len(outputs) != 1:
            continue
        (output_code,) = outputs
        out_stats = game_data.item_stats(output_code)
        if out_stats is not None and (
            out_stats.type_ in ITEM_TYPE_TO_SLOTS
            or out_stats.subtype == "tool"
        ):
            continue  # end-stage gear or tool — not a relief candidate
        consider(output_code, 1, batch_cap)

    candidates.sort(key=lambda c: (c.priority_class, -c.quantity, c.item_code))
    return candidates
