"""A vendor's reach: the gate a BUY or SELL route asks of its NPC's tile.

Task 8a (Ruling C-3). A fight's and a gather's SPAWN_KNOWN gate asks the one
reachability authority (`region_edges.content_reached` over
`reachable_regions_now`, rulings T14a-E, I-3) and names the doors past which
the content lies (`region_edges.doors_to`). A vendor route asked nothing: the
island's `sandwhisper_trader`, past a 1100-gold boat fee, was offered and
priced as if it stood next door to a character with no gold. A vendor route
now carries the same gate over its NPC's tiles, so a vendor past a door is
priced and walked through that door (`acquisition_cost._door_options`,
`ObtainModel.walk_graph`), and a vendor no door opens is no route.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.region_edges import content_reached, doors_to
from artifactsmmo_cli.ai.world_state import WorldState


def vendor_tiles(npc: str, game_data: GameData) -> list[tuple[int, int]]:
    """The overworld tiles `npc` stands on, as a monster's live index lists
    them (`GameData.all_monster_locations`); `content_reached` adds its map
    content on every layer (`GameData.layered_locations`) itself.

    A permanent NPC: its static tile (`GameData.npc_location`) when that is an overworld
    tile no live event takes (the event-tile takeover: the event replaces the
    tile's content while it lasts); an off-overworld NPC's tile is its layered
    content alone. An event NPC: its event's read maps while the event is live
    (the event stands on ONE of its maps), else its catalogue spawn
    (`GameData.npc_location`, the tile its actions walk to). The read's layer
    is dropped, as `LocationCatalog._live_tiles` drops it for event monsters."""
    event = game_data.npc_event_code(npc)
    if event is None:
        tile = game_data.npc_location(npc)
        if (tile is None or npc in game_data.world.npc_layers
                or (*tile, "overworld") in game_data.world.taken_tiles()):
            return []
        return [tile]
    read = game_data.active_event_maps.get(event)
    if read is not None:
        return [(x, y) for x, y, _layer in read]
    spawn = game_data.npc_location(npc)
    return [] if spawn is None else [spawn]


def vendor_gate(npc: str, game_data: GameData, reach: frozenset[str],
                crossing: WorldState) -> Gate:
    """`npc`'s SPAWN_KNOWN gate: some tile of it (`vendor_tiles`, and its map
    content on every layer) lies in `reach` (`reachable_regions_now` of
    `crossing`), else the doors past which one does (`doors_to`, asked of
    `crossing`), the gate a fight's monster and a gather's resource carry."""
    tiles = vendor_tiles(npc, game_data)
    known = content_reached(npc, tiles, game_data, reach)
    doors = () if known else doors_to(npc, tiles, crossing, game_data)
    return Gate(GateKind.SPAWN_KNOWN, npc, known, doors=doors)
