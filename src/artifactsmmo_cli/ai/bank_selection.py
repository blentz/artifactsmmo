"""Selective bank-deposit policy: what to bank, ordered by sell value."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

TASK_COIN_CODE = "tasks_coin"


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


def _crafting_target_materials(state: WorldState, game_data: GameData) -> set[str]:
    """All material codes in the crafting target's recipe tree."""
    materials: set[str] = set()
    if not state.crafting_target:
        return materials
    visited: set[str] = set()

    def walk(item: str) -> None:
        if item in visited:
            return
        visited.add(item)
        recipe = game_data._crafting_recipes.get(item) or {}
        for mat in recipe:
            materials.add(mat)
            walk(mat)

    walk(state.crafting_target)
    return materials


def _keep_codes(state: WorldState, game_data: GameData) -> set[str]:
    keep: set[str] = {TASK_COIN_CODE}
    if state.task_code:
        keep.add(state.task_code)
    for code in state.inventory:
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > 0:
            keep.add(code)
    weapon = _best_fighting_weapon(state, game_data)
    if weapon is not None:
        keep.add(weapon)
    keep |= _crafting_target_materials(state, game_data)
    return keep


def select_bank_deposits(state: WorldState, game_data: GameData) -> list[tuple[str, int]]:
    """Items to deposit, ordered (sell_value desc, code asc), excluding the
    keep-set (task item, task coins, HP consumables, best fighting weapon,
    crafting-target materials). Items with no known NPC buy-back price get
    value 0 and sort last."""
    keep = _keep_codes(state, game_data)

    def sell_value(code: str) -> int:
        buyers = game_data.npcs_buying_item(code)
        return max((price for _, price in buyers), default=0)

    deposits = [
        (code, qty) for code, qty in state.inventory.items()
        if qty > 0 and code not in keep
    ]
    deposits.sort(key=lambda cq: (-sell_value(cq[0]), cq[0]))
    return deposits
