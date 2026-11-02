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
from artifactsmmo_cli.ai.region_edges import content_reached, doors_to, reachable_regions_now
from artifactsmmo_cli.ai.world_state import WorldState


def vendor_tiles(npc: str, game_data: GameData) -> list[tuple[int, int]]:
    """The overworld tiles `npc` stands on, as a monster's live index lists
    them (`GameData.all_monster_locations`); `content_reached` adds its map
    content on every layer (`GameData.layered_locations`) itself.

    A permanent NPC: its static tile (`GameData.npc_location`) when that is an
    overworld tile no live event takes (the event-tile takeover: the event
    replaces the tile's content while it lasts); an off-overworld NPC's tile is
    its layered content alone. An event NPC: the tiles its live event reads
    (`GameData.event_npc_tiles`, guarded on the event being live), else its
    location (`GameData.npc_location`, its catalogue spawn). Its buy and sell
    actions walk to `npc_location`, which is the first of these tiles: the
    pricer and the executor read one tile (Task 8a I-3)."""
    tile = game_data.npc_location(npc)
    if game_data.npc_event_code(npc) is None:
        if (tile is None or npc in game_data.world.npc_layers
                or (*tile, "overworld") in game_data.world.taken_tiles()):
            return []
        return [tile]
    live = game_data.event_npc_tiles(npc)
    if live:
        return live
    return [] if tile is None else [tile]


def vendor_reached(npc: str, state: WorldState, game_data: GameData) -> bool:
    """`vendor_gate`'s verdict asked of `state`: the walk reaches `npc` from
    here now. The selection and emission sites (a goal's NpcBuy or NpcSell,
    a sale venue, a currency vendor) ask it, so no vendor is offered that the
    gate refuses (Task 8a I-4)."""
    return vendor_gate(npc, game_data, reachable_regions_now(state, game_data), state).satisfied


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
