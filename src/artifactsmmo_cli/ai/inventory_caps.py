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
currently equipped — so the equipment optimizer has it as a swap candidate.
DROPS TO ZERO when the item is DOMINATED by another owned item that fills
the same equipment slot AND has strictly higher equip_value AND covers
every skill_effect of the dominated item with equal-or-better magnitude.
Without this dominance gate, the bot keeps `wooden_stick` (starter, attack
0) forever even after crafting `copper_dagger` (attack 12) — both occupy
weapon_slot and `EQUIPPABLE_KEEP=1` protects each individually. The
dominated stick should be the FIRST thing the discard ladder picks when
inventory pressure forces a delete."""

CONSUMABLE_KEEP = 999
"""Keep effectively unlimited HP-restoring consumables (apple,
cooked_chicken, potion, etc.). Consumables STACK in a single inventory
slot regardless of quantity — capping low frees zero slots while
throwing away healing stock with real survival value. Trace 2026-06-05
16:13: bot deleted 19 apples in one Delete(apple×19) action because the
prior cap of 10 declared excess=19; 19 apples is 19 RestAction-class
heals worth of insurance lost for zero slot benefit. Same fix pattern
as tasks_coin (602f7b4) — raise the cap past any plausible accumulation
since stacking-items don't cost slots per unit. Original prior cap was
0 (everything deleted, fixed in f1f8941) → 10 (insufficient, still
delete-heavy) → 999 (stack-aware floor)."""

# Items consumed by API actions (not recipes). Keep enough to use them.
ACTION_CONSUMABLES_CAP = {
    # Tasks-coins stack in a single inventory slot regardless of quantity,
    # so capping low (was 9 = 3 batches) frees no actual slots — it just
    # throws away TaskExchange currency. Trace 2026-06-05T02:55: Robby
    # deleted 3 tasks_coin (out of 12 he'd grinded for) because the cap
    # rule kicked in during a DiscardOverstock cycle. Each coin is worth
    # one third of a random-item exchange; deleting them is a real
    # economic loss with no slot benefit. Set to a value larger than any
    # plausible accumulation; the keep-set still ensures coins are
    # protected from bank-deposit too.
    TASKS_COIN_CODE: 999,
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


def _is_equippable_dominated(item_code: str, state: WorldState,
                              game_data: GameData) -> bool:
    """True when strictly-better same-slot peers are owned in numbers
    sufficient to fill every slot this item could fill.

    Dominance is per-(slot, skill-effect-set). A pure combat weapon
    (attack-only, no skill_effects) is dominated by a higher-attack
    pure-combat weapon for the same slot — `wooden_stick` by
    `copper_dagger`. A tool (skill_effects non-empty) is dominated only
    by an item that ALSO carries those same skill_effects at equal-or-
    better magnitude; a combat weapon never dominates a tool because the
    tool's `skill_effects[mining]` is unmatched.

    Multi-slot types (ring×2, artifact×3, utility×2) require enough
    dominator copies to occupy EVERY slot — 1 iron_ring doesn't
    dominate a copper_ring while the bot still needs a second ring to
    wear. The summed owned count (inventory + bank + equipped) of
    qualifying peers must be >= len(slots_for_type).
    """
    stats = game_data.item_stats(item_code)
    if stats is None:
        return False
    slots = ITEM_TYPE_TO_SLOTS.get(stats.type_, [])
    if not slots:
        return False
    slot_count = len(slots)
    my_value = _equip_value(stats)
    my_effects = stats.skill_effects or {}
    candidates: set[str] = set(state.inventory)
    if state.bank_items:
        candidates |= set(state.bank_items)
    candidates |= {c for c in state.equipment.values() if c is not None}
    candidates.discard(item_code)
    equipped_codes = [c for c in state.equipment.values() if c is not None]
    bank_items = state.bank_items or {}
    dominator_owned = 0
    for peer_code in candidates:
        peer = game_data.item_stats(peer_code)
        if peer is None:
            continue
        peer_slots = ITEM_TYPE_TO_SLOTS.get(peer.type_, [])
        # Peer must fit every slot this item fits (so it can substitute everywhere).
        if not all(s in peer_slots for s in slots):
            continue
        if _equip_value(peer) <= my_value:
            continue
        # Peer must cover this item's skill_effects (else dropping a tool
        # in favor of a higher-attack weapon would silently lose a skill
        # bonus the bot relies on). Skill effect values are NEGATIVE
        # cooldown-reduction percentages — bigger magnitude wins, so we
        # compare on `abs` (mirrors `tools.tool_value`). A peer without the
        # skill key contributes 0, which fails the abs comparison and
        # disqualifies the peer as a dominator for tool roles.
        peer_effects = peer.skill_effects or {}
        if any(abs(peer_effects.get(skill, 0)) < abs(magnitude)
               for skill, magnitude in my_effects.items()):
            continue
        peer_count = (
            state.inventory.get(peer_code, 0)
            + bank_items.get(peer_code, 0)
            + sum(1 for c in equipped_codes if c == peer_code)
        )
        dominator_owned += peer_count
        if dominator_owned >= slot_count:
            return True
    return False


def _equip_value(stats: object) -> float:
    """Inline mirror of `tiers/equip_value.equip_value` — kept local here
    to avoid a tiers→inventory_caps import cycle. Same formula:
    attack + resistance + hp_restore."""
    attack = sum(stats.attack.values()) if stats.attack else 0  # type: ignore[attr-defined]
    resistance = sum(stats.resistance.values()) if stats.resistance else 0  # type: ignore[attr-defined]
    hp = getattr(stats, "hp_restore", 0)
    return float(attack + resistance + hp)


def _task_chain_demand(target_item: str, root_item: str, root_qty: int,
                        game_data: GameData,
                        visited: frozenset[str] | None = None) -> int:
    """Recursive count of `target_item` needed to craft `root_qty` of
    `root_item`. Returns 0 when target isn't reachable from root via the
    recipe chain. Cycle-safe via `visited` frozenset path tracking — without
    it a self-referential recipe (e.g. recycle loops) would recurse forever.

    Used to compute how many copies of a mid-chain material the bot still
    needs to complete the active items-task without re-gathering."""
    if visited is None:
        visited = frozenset()
    if target_item == root_item:
        return root_qty
    if root_item in visited:
        return 0
    recipe = game_data.crafting_recipe(root_item) or {}
    sub = visited | {root_item}
    return sum(
        _task_chain_demand(target_item, mat, qty_per * root_qty, game_data, sub)
        for mat, qty_per in recipe.items()
    )


def useful_quantity_cap_excl_equipped(
    item_code: str, state: WorldState, game_data: GameData,
    batch_buffer: int = BATCH_BUFFER, safety_floor: int = SAFETY_FLOOR,
) -> int:
    """useful_quantity_cap without the equipped-floor adjustment."""
    recipe_max = game_data.max_recipe_demand(item_code)
    recipe_cap = recipe_max * batch_buffer if recipe_max > 0 else 0
    if recipe_max > 0:
        recipe_cap = max(recipe_cap, safety_floor)

    # Active items-task demand: keep enough to finish the task. Covers two
    # cases: (a) item_code IS the task item (direct match) and (b) item_code
    # is a transitive recipe input for the task item. Without (b) the bot
    # discards mid-chain materials it could have crafted into the task item
    # — e.g. 67 ash_wood deleted while the active task wants 10 more
    # ash_plank that 1:1 require ash_wood (trace 2026-06-05 inv build-up
    # following the apple-delete bug f1f8941). Bank's _keep_codes already
    # protected the chain; DiscardOverstock must apply the same discipline
    # or the two caps diverge and one or the other wastes resources.
    task_cap = 0
    if state.task_type == "items" and state.task_code:
        remaining = max(0, state.task_total - state.task_progress)
        if remaining > 0:
            task_cap = _task_chain_demand(item_code, state.task_code,
                                           remaining, game_data)

    # Action-consumed items (e.g. tasks_coin for TaskExchange)
    action_cap = ACTION_CONSUMABLES_CAP.get(item_code, 0)

    # Equippable items: keep one of each for the equipment optimizer's
    # candidate pool — unless this code is DOMINATED by another owned
    # item that fills every slot it could and scores strictly higher on
    # equip_value while covering every skill_effect. A dominated item
    # (wooden_stick once copper_dagger is owned) becomes delete-eligible
    # so the discard ladder picks the least-useful redundant weapon
    # first, instead of one-of-each-blindly.
    equippable_cap = 0
    consumable_cap = 0
    stats = game_data.item_stats(item_code)
    if stats is not None:
        if ITEM_TYPE_TO_SLOTS.get(stats.type_):
            if not _is_equippable_dominated(item_code, state, game_data):
                equippable_cap = EQUIPPABLE_KEEP
        if stats.hp_restore > 0:
            consumable_cap = CONSUMABLE_KEEP

    return max(recipe_cap, task_cap, action_cap, equippable_cap, consumable_cap)


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
