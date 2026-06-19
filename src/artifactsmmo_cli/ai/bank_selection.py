"""Selective bank-deposit policy: what to bank, ordered by sell value."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


def _best_fighting_weapon(state: WorldState, game_data: GameData) -> str | None:
    """Highest-attack non-tool weapon among inventory + equipped, or None.

    Tools (pickaxe/axe/net) have skill_effects and are excluded — they are
    gathering aids, not the combat weapon to protect."""
    candidates: set[str] = set(state.inventory)
    candidates.update(c for c in state.equipment.values() if c)
    best: tuple[int, str] | None = None
    for code in candidates:
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "weapon" or stats.skill_effects:
            continue
        attack = sum(stats.attack.values()) if stats.attack else 0
        # Higher attack wins; tie broken by code ascending (deterministic).
        if best is None or attack > best[0] or (attack == best[0] and code < best[1]):
            best = (attack, code)
    return best[1] if best else None


def _recipe_materials(roots: list[str], game_data: GameData) -> set[str]:
    """All material codes in the recipe trees of the given root items."""
    materials: set[str] = set()
    visited: set[str] = set()

    def walk(item: str) -> None:
        if item in visited:
            return
        visited.add(item)
        recipe = game_data.crafting_recipe(item) or {}
        for mat in recipe:
            materials.add(mat)
            walk(mat)

    for root in roots:
        walk(root)
    return materials


def _keep_codes(state: WorldState, game_data: GameData,
                profile_codes: frozenset[str] = frozenset()) -> set[str]:
    keep: set[str] = {TASKS_COIN_CODE}
    if state.task_code:
        keep.add(state.task_code)
    for code in state.inventory:
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > 0:
            keep.add(code)
    weapon = _best_fighting_weapon(state, game_data)
    if weapon is not None:
        keep.add(weapon)
    # Protect recipe materials for both the equipment crafting target and the
    # active items-task item — banking the task's own inputs starves PursueTask
    # (gather -> craft -> TaskTrade) and freezes task progress.
    recipe_roots: list[str] = []
    if state.crafting_target:
        recipe_roots.append(state.crafting_target)
    if state.task_type == "items" and state.task_code:
        recipe_roots.append(state.task_code)
    keep |= _recipe_materials(recipe_roots, game_data)
    # Per-goal inventory profile: the ACTIVE gather goal's target materials
    # (target_gear / target_tools recipe closures, threaded in by the caller
    # via `profile_codes`). Without this, an active GatherMaterials goal whose
    # materials are NOT the crafting_target/task chain (e.g. ash_wood for a
    # fishing_net tool while the task is copper_ore) gets banked — undoing the
    # withdraw and livelocking the gather (spec 2026-06-07). The profile is a
    # SOFT target; here it just joins the keep-set so deposit never banks it.
    keep |= profile_codes
    return keep


def _sell_value(code: str, game_data: GameData) -> int:
    buyers = game_data.npcs_buying_item(code)
    return max((price for _, price in buyers), default=0)


def _last_resort_deposit(state: WorldState, game_data: GameData,
                         profile_codes: frozenset[str]) -> tuple[str, int] | None:
    """The single least-critical item-stack to bank when the bag is COMPLETELY
    full of keep-set items, to free exactly one slot.

    Last-resort relief (2026-06-19): a bag with zero free slots and nothing
    normally bankable is a hard stall — `FightAction.is_applicable` requires
    `inventory_free >= 1` (combat.py) and no other relief path fires, so the
    planner drops to WAIT and stops leveling (the confirmed full-of-keep-set
    livelock). Banking one keep item is fully recoverable (re-withdrawable), so
    it frees the slot without losing anything.

    Picks the least disruptive stack: NOT immediately critical (best fighting
    weapon / HP consumable / task item / task coins) before anything else, NOT
    in the active goal's profile before profile items, then lowest sell-value,
    then code ascending (deterministic)."""
    hard_critical: set[str] = {TASKS_COIN_CODE}
    if state.task_code:
        hard_critical.add(state.task_code)
    for code in state.inventory:
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > 0:
            hard_critical.add(code)
    weapon = _best_fighting_weapon(state, game_data)
    if weapon is not None:
        hard_critical.add(weapon)

    items = [(code, qty) for code, qty in state.inventory.items() if qty > 0]
    if not items:
        return None
    items.sort(key=lambda cq: (cq[0] in hard_critical, cq[0] in profile_codes,
                               _sell_value(cq[0], game_data), cq[0]))
    return items[0]


def select_bank_deposits(state: WorldState, game_data: GameData,
                         profile_codes: frozenset[str] = frozenset()) -> list[tuple[str, int]]:
    """Items to deposit, ordered (sell_value desc, code asc), excluding the
    keep-set (task item, task coins, HP consumables, best fighting weapon,
    crafting-target materials, AND the active goal's profile codes). Items
    with no known NPC buy-back price get value 0 and sort last.

    LAST-RESORT relief: when the bag has ZERO free slots and nothing is normally
    bankable (the whole bag is keep-set protected), bank ONE least-critical keep
    item to free a slot — otherwise the bot cannot fight (needs a free slot) and
    no other relief fires, stalling leveling. Gated on `inventory_free == 0` so
    the keep-set is untouched while any slack remains."""
    keep = _keep_codes(state, game_data, profile_codes)

    deposits = [
        (code, qty) for code, qty in state.inventory.items()
        if qty > 0 and code not in keep
    ]
    deposits.sort(key=lambda cq: (-_sell_value(cq[0], game_data), cq[0]))
    if deposits:
        return deposits
    if state.inventory_free == 0:
        item = _last_resort_deposit(state, game_data, profile_codes)
        if item is not None:
            return [item]
    return deposits
