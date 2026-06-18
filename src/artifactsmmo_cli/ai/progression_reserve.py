"""Impure progression-reserve target identification and pricing.

Each category SOURCE yields the unmet near-term (level..level+2) progression
items the bot would BUY, mapped to their cheapest gold buy price. The pure
`progression_reserve_core` then sums them and applies the deduction-aware floor.
Craftable-now / unsellable items contribute nothing (no gold needed).
"""
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.world_state import WorldState

_HORIZON = 2  # reserve for upgrades usable within the next 2 character levels


def buy_price(code: str, game_data: GameData) -> int | None:
    """Cheapest gold price to BUY one `code` (min over NPC sellers and the GE
    best SELL order — the standing sell order the player fills when buying),
    or None when nothing sells it."""
    prices: list[int] = [p for _npc, p in game_data.npcs_selling_item(code)]
    ge = game_data.ge_best_sell_order(code)
    if ge is not None:
        prices.append(ge[1])
    return min(prices) if prices else None


def gear_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Unmet gear upgrades usable within the horizon that the bot would BUY,
    mapped to their buy price. Per combat slot, the best equippable of the slot's
    type at level <= state.level + _HORIZON whose value beats the equipped item,
    included only when no crafting recipe exists (pure BUY item) and a seller
    exists. Craftable items are excluded: gold is not needed to acquire them."""
    out: dict[str, int] = {}
    max_level = state.level + _HORIZON
    for _slot, code in _best_per_slot(state, game_data, max_level).items():
        if game_data.crafting_recipe(code) is not None:
            continue
        price = buy_price(code, game_data)
        if price is None:
            continue
        out[code] = price
    return out


def _best_per_slot(state: WorldState, game_data: GameData,
                   max_level: int) -> dict[str, str]:
    """{slot: best_upgrade_code} for combat slots where an in-horizon item beats
    the equipped one. Scans all item stats by the slot's item type."""
    best: dict[str, str] = {}
    for code, stats in game_data.all_item_stats.items():
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_)
        if not slots or stats.level > max_level:
            continue
        for slot in slots:
            equipped = state.equipment.get(slot)
            cur = game_data.item_stats(equipped) if equipped else None
            cur_val = equip_value(cur) if cur is not None else 0
            if equip_value(stats) <= cur_val:
                continue
            incumbent = best.get(slot)
            inc_stats = game_data.item_stats(incumbent) if incumbent else None
            inc_val = equip_value(inc_stats) if inc_stats is not None else cur_val
            if equip_value(stats) > inc_val:
                best[slot] = code
    return best


def _is_gatherable(material: str, game_data: GameData) -> bool:
    """True when some resource node drops `material` (gathering, not gold)."""
    return any(drop == material for drop in game_data.resource_drops.values())


def crafting_unlock_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Buyable recipe INPUTS for in-horizon craftable gear whose final craft is
    skill-reachable: an input the bot must BUY (no gather/craft path) is a real
    upcoming gold need. Maps each such input to qty * buy price.

    A material is a reserved gold need iff ALL of:
      1. it is NOT gatherable (_is_gatherable is False), AND
      2. it has NO crafting recipe of its own (game_data.crafting_recipe is None),
         so gold is the only acquisition path, AND
      3. buy_price returns a non-None value (a seller exists).
    """
    out: dict[str, int] = {}
    max_level = state.level + _HORIZON
    for code, stats in game_data.all_item_stats.items():
        if ITEM_TYPE_TO_SLOTS.get(stats.type_) is None or stats.level > max_level:
            continue
        recipe = game_data.crafting_recipe(code)
        if not recipe:
            continue
        for material, qty in recipe.items():
            if _is_gatherable(material, game_data):
                continue
            if game_data.crafting_recipe(material) is not None:
                continue
            price = buy_price(material, game_data)
            if price is None:
                continue
            out[material] = qty * price
    return out
