"""The tiles a monster is fought on: exactly the tiles the action factory
(`actions/factory.build_actions`) builds a `FightAction` from, on every layer.

Three sources, in the factory's order:

* the legacy index (`GameData.all_monster_locations`: the static overworld
  layer, islands included, plus active event spawns and open raid areas),
  one fight per access region;
* the tiles of an ACTIVE raid whose boss is the monster
  (`GameData.raid_location_tiles`; the boss has no monster-type tile);
* every all-layer tile (`GameData.layered_locations`: interiors, the
  underground) in a region that is neither the overworld nor one the legacy
  index already fights in (fight-odds final review C1: `rat` spawns only on
  `interior`, `bat` and `lich` only `underground`, so the legacy index alone
  said "spawns nowhere" for monsters the factory fights).

The factory and the fight-ahead readers (`loop_rate`, `best_loadout`,
`strategy_driver`) share these functions, so "spawns somewhere" means "is
fought somewhere" and there is no second list to drift.
"""

from collections.abc import Set as AbstractSet

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def by_region(tiles: list[tuple[int, int]], game_data: GameData) -> dict[str, list[tuple[int, int]]]:
    """Overworld-layer `tiles` grouped by access region, in tile order."""
    out: dict[str, list[tuple[int, int]]] = {}
    for x, y in tiles:
        out.setdefault(game_data.region_of(x, y, "overworld"), []).append((x, y))
    return out


def layered_extra(game_data: GameData, code: str,
                  emitted: AbstractSet[str]) -> dict[str, list[tuple[int, int]]]:
    """`code`'s all-layer tiles outside the overworld region and outside the
    regions in `emitted` (the regions the legacy index already acts in),
    grouped by access region, in tile order."""
    out: dict[str, list[tuple[int, int]]] = {}
    for (x, y, layer) in game_data.layered_locations(code):
        region = game_data.region_of(x, y, layer)
        if region == "overworld" or region in emitted:
            continue
        out.setdefault(region, []).append((x, y))
    return out


def fight_tiles(state: WorldState, game_data: GameData, monster: str) -> list[tuple[int, int]]:
    """Every tile the factory fights `monster` on this cycle (see the module
    doc), as (x, y) in source order, without repeats. Empty when no source
    holds the monster (a despawned event, an inactive raid)."""
    legacy = list(game_data.all_monster_locations.get(monster, []))
    raid = [tile for r in state.active_raids if r.monster == monster
            for tile in game_data.raid_location_tiles(r.code)]
    layered = [tile for tiles in layered_extra(game_data, monster,
                                               by_region(legacy, game_data).keys()).values()
               for tile in tiles]
    return list(dict.fromkeys(legacy + raid + layered))
