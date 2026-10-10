"""Does some utility-potion loadout win a fight the bare stats lose? The drop
route's WINNABLE gate (`obtain_model/drop_routes`; USER 2026-10-10, "judge drop
fights with the chosen loadout", docs/PLAN_drop_fight_loadout.md).

The candidates are the potions `best_loadout.candidate_potions` would offer —
usable (`fight_walk.potion_effects_usable`), at most the character's level —
that the character can STOCK without a price: held (bag, bank, utility slots),
craftable at its skill now, or sold for gold by a located permanent vendor.
`candidate_potions` asks a replacement PRICE, which walks the obtain model,
which asks this gate: the price is the pick's business (the CRAFT_POTIONS guard
stocks the cycle's chosen loadout), the gate's is whether a loadout exists. The
ingredients of a craftable potion are not walked here.

Each loadout (`fight_walk.loadouts`) is walked with a full slot, as the pick
walks it. Food is eaten between fights, so it never decides a win.

The verdict is memoized per catalogue (`CatalogueScope`) on exactly what the
walk reads: the monster, the stockable potions, and the state's fight fields —
level, max HP, the combat stats `project_loadout_stats` reads, the worn gear,
and the bag's equippable codes (`pick_loadout_cached`'s pool). The planner asks
it for every non-bare-winnable dropper on every obtain walk (census 40 s ->
354 s unmemoized, 2026-10-10)."""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.fight_walk import fight_walk, loadouts, potion_effects_usable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.heal_catalog import POTION
from artifactsmmo_cli.ai.held_stock import held_count
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState


def stockable_potions(state: WorldState, game_data: GameData) -> list[str]:
    """The usable potions the character can stock now (see the module doc), in
    catalogue order."""
    out: list[str] = []
    for code, stats in game_data.items.stats.items():
        if stats.type_ != POTION or stats.level > state.level:
            continue
        if not potion_effects_usable(game_data.effect_codes(code)):
            continue
        craftable = (bool(game_data.crafting_recipe(code)) and stats.crafting_skill is not None
                     and state.skills.get(stats.crafting_skill, 0) >= stats.crafting_level)
        sold = any(currency == GOLD_CODE and not game_data.is_event_npc(npc)
                   and game_data.npc_location(npc) is not None
                   for npc, _price, currency in game_data.npc_purchases(code))
        if held_count(code, state) > 0 or craftable or sold:
            out.append(code)
    return out


_WINS: "CatalogueScope[tuple[object, ...], bool]" = CatalogueScope(4096)


def _fight_key(state: WorldState, game_data: GameData) -> tuple[object, ...]:
    """The state fields the fight walk reads (see the module doc)."""
    return (state.level, state.max_hp, state.critical_strike, state.initiative,
            state.dmg, state.wisdom, state.prospecting,
            tuple(sorted(state.attack.items())), tuple(sorted(state.dmg_elements.items())),
            tuple(sorted(state.resistance.items())), tuple(sorted(state.equipment.items())),
            tuple(sorted(code for code, qty in state.inventory.items()
                         if qty > 0 and (stats := game_data.item_stats(code)) is not None
                         and stats.type_ in ITEM_TYPE_TO_SLOTS)))


def wins_with_a_loadout(state: WorldState, game_data: GameData, monster: str) -> bool:
    """Some loadout of stockable potions wins the fight from full HP."""
    stockable = stockable_potions(state, game_data)
    key = (monster, tuple(stockable), _fight_key(state, game_data))
    memo = _WINS.cache_for(game_data)
    hit = memo.get(key)
    if hit is None:
        hit = any(fight_walk(state, game_data, monster,
                             [(code, UTILITY_SLOT_MAX_STACK) for code in codes])[0].win
                  for codes in loadouts(stockable, game_data) if codes)
        _WINS.remember(memo, key, hit)
    return hit
