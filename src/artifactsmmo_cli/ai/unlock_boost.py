"""Select the craftable utility boost that unlocks a currently-unwinnable
leveling monster. When no in-band monster is beatable bare, owning a boost can
flip predict_win (pick_loadout equips it) — this picks the boost that unlocks the
highest-XP monster. Orchestration over the proven predict_win; no combat change."""

import dataclasses

from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.combat_targets import LEVEL_BAND_BELOW
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

_CacheKey = tuple[int, tuple[str, ...], tuple[str, ...]]

_CACHE: "CatalogueScope[_CacheKey, tuple[str, str] | None]" = CatalogueScope(max_entries=1)
"""Single-entry cache keyed like `combat_target_monsters` (level, equip, owned
boosts) — the caller sweeps one state, so one entry serves it.

PER CATALOGUE, VIA `CatalogueScope`. Until 2026-08-25 this was a bare module dict
whose key carried `id(game_data)` and NOTHING that kept that catalogue alive: the
address of a freed `GameData` is handed straight to the next one, so a fresh
catalogue read the previous catalogue's boost answer. `tests/test_ai/
test_unlock_boost.py` had an autouse fixture clearing this dict between tests
whose docstring said the key "does NOT include id(game_data)" — it did, and the
fixture hid the hole rather than closing it. The scope closes it: entries die
with the catalogue that minted them."""


def _is_craftable_boost(code: str, state: WorldState, game_data: GameData) -> bool:
    stats = game_data.item_stats(code)
    if stats is None or stats.type_ != "utility" or stats.hp_restore > 0:
        return False  # not a utility, or it's a heal (Phase-1 economy owns heals)
    has_boost = bool(stats.dmg_elements) or bool(stats.resistance) or stats.hp_bonus > 0 \
        or stats.antipoison > 0 or stats.combat_buff > 0
    if not has_boost or stats.crafting_skill is None:
        return False
    return state.skills.get(stats.crafting_skill, 0) >= stats.crafting_level


def unlock_boost_target(state: WorldState, game_data: GameData) -> tuple[str, str] | None:
    """(boost_code, monster_code) of the craftable non-heal boost that flips the
    highest-XP in-band monster from unwinnable to winnable; None if some in-band
    monster is already bare-winnable, or no craftable boost unlocks anything.
    Selection: highest xp_per_kill first; deterministic tie-break by fewest recipe
    items, then smallest boost code, then smallest monster code."""
    equip_sig = tuple(sorted(c for c in state.equipment.values() if c is not None))
    owned = tuple(sorted(c for c in state.inventory if _is_craftable_boost(c, state, game_data)))
    cache = _CACHE.cache_for(game_data)
    key: _CacheKey = (state.level, equip_sig, owned)
    if key in cache:  # membership, not `.get`: None is a legal cached answer
        cache.move_to_end(key)
        return cache[key]

    floor = state.level - LEVEL_BAND_BELOW
    monsters = [(code, lvl) for code, lvl in game_data.monster_levels.items() if lvl >= floor]
    # If anything is already bare-winnable, we are not stalled -> no unlock crafting.
    result: tuple[str, str] | None = None
    if not any(predict_win(state, game_data, code) for code, _ in monsters):
        boosts = [c for c in sorted(game_data.crafting_recipes)
                  if _is_craftable_boost(c, state, game_data)]
        best_key: tuple[int, int, str, str] | None = None
        for monster, _lvl in monsters:
            xp = game_data.xp_per_kill(monster, state.level)
            for boost in boosts:
                owned_state = dataclasses.replace(
                    state, inventory={**state.inventory, boost: state.inventory.get(boost, 0) + 1})
                if predict_win(owned_state, game_data, monster):
                    recipe_items = len(game_data.crafting_recipes.get(boost, {}))
                    k = (-xp, recipe_items, boost, monster)   # highest xp first
                    if best_key is None or k < best_key:
                        best_key = k
                        result = (boost, monster)
    return _CACHE.remember(cache, key, result)
