"""PLAN #4 visibility slice: event-spawned monster/resource content is surfaced to
the planner via the location accessors ONLY while its event is in
`active_event_codes` (set per cycle from WorldState.active_events).

Event monster/resource STATS and DROPS are already loaded (get_all_monsters /
get_all_resources include event content); only the spawn LOCATIONS were missing.
These tests lock that an event spawn is invisible until active, visible while
active, and that producibility (the proven reachability core) follows.
"""
from unittest.mock import MagicMock

from artifactsmmo_api_client.models.map_content_type import MapContentType

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.strategy import _producible
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _winnable_state(**overrides):
    base = dict(level=20, x=0, y=0, max_hp=1000, hp=1000, attack={"fire": 80}, initiative=50)
    base.update(overrides)
    return make_state(**base)


def _make_event(code: str, ctype: MapContentType, content_code: str, tiles):
    ev = MagicMock()
    ev.code = code
    ev.content = MagicMock(type_=ctype, code=content_code)
    ev.maps = [MagicMock(x=x, y=y) for (x, y) in tiles]
    return ev


def test_build_events_parses_monster_and_resource_spawns() -> None:
    """_build_events now records MONSTER and RESOURCE event content (not just NPCs)."""
    gd = GameData()
    events = [
        _make_event("ogre_event", MapContentType.MONSTER, "corrupted_ogre", [(3, 3), (4, 4)]),
        _make_event("magic_event", MapContentType.RESOURCE, "magic_tree", [(5, 5)]),
        _make_event("fish_event", MapContentType.NPC, "fish_merchant", [(1, 1)]),
    ]
    gd._build_events(events)
    assert gd.world.event_monster_locations["corrupted_ogre"] == [(3, 3), (4, 4)]
    assert gd.world.event_resource_locations["magic_tree"] == [(5, 5)]
    assert gd.world.event_code_of_content == {"corrupted_ogre": "ogre_event", "magic_tree": "magic_event"}
    # NPC handling preserved.
    assert gd.world.event_npc_spawns["fish_merchant"] == (1, 1)
    assert gd.world.npc_event_codes["fish_merchant"] == "fish_event"


def test_event_with_no_maps_is_skipped() -> None:
    """An event carrying no spawn tiles records nothing (can't place it)."""
    gd = GameData()
    ev = _make_event("x", MapContentType.MONSTER, "ghost", [])
    gd._build_events([ev])
    assert gd.world.event_monster_locations == {}
    assert gd.world.event_code_of_content == {}


def test_event_monster_invisible_until_active() -> None:
    """An event monster's spawn tiles are hidden from the location accessors until
    its event is active, then revealed; turning it off hides them again."""
    gd = GameData()
    gd.world.event_monster_locations["corrupted_ogre"] = [(3, 3), (4, 4)]
    gd.world.event_code_of_content["corrupted_ogre"] = "ogre_event"

    assert gd.monster_locations("corrupted_ogre") == []
    assert "corrupted_ogre" not in gd.all_monster_locations

    gd.active_event_codes = {"ogre_event"}
    assert gd.monster_locations("corrupted_ogre") == [(3, 3), (4, 4)]
    assert gd.all_monster_locations["corrupted_ogre"] == [(3, 3), (4, 4)]

    gd.active_event_codes = set()
    assert gd.monster_locations("corrupted_ogre") == []
    assert "corrupted_ogre" not in gd.all_monster_locations


def test_event_resource_invisible_until_active() -> None:
    gd = GameData()
    gd.world.event_resource_locations["magic_tree"] = [(5, 5)]
    gd.world.event_code_of_content["magic_tree"] = "magic_event"

    assert gd.resource_locations("magic_tree") == []
    assert "magic_tree" not in gd.all_resource_locations

    gd.active_event_codes = {"magic_event"}
    assert gd.resource_locations("magic_tree") == [(5, 5)]
    assert gd.all_resource_locations["magic_tree"] == [(5, 5)]


def test_active_event_codes_setter_coerces_to_set() -> None:
    """The overlay setter accepts any iterable of codes (cycle passes dict keys)."""
    gd = GameData()
    gd.active_event_codes = ["a", "b", "a"]
    assert gd.active_event_codes == {"a", "b"}


def test_event_monster_drop_producible_only_when_active() -> None:
    """End-to-end through the proven reachability core: a gear material that drops
    only from an event monster is NOT producible while the event is dormant (no
    spawn ⇒ unreachable) and producible once the event is live."""
    gd = GameData()
    gd._monster_level = {"corrupted_ogre": 20}
    gd._monster_drops = {"corrupted_ogre": [("ogre_skin", 10, 1, 1)]}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"corrupted_ogre": 10}  # low HP, no attack ⇒ winnable
    gd.world.event_monster_locations["corrupted_ogre"] = [(3, 3)]
    gd.world.event_code_of_content["corrupted_ogre"] = "ogre_event"
    state = _winnable_state()

    assert _producible("ogre_skin", state, gd) is False
    gd.active_event_codes = {"ogre_event"}
    assert _producible("ogre_skin", state, gd) is True


def test_monster_both_static_and_event_dedups_shared_tile() -> None:
    """A monster that is BOTH a static spawn and an event spawn (e.g. corrupted_ogre)
    can share a tile; the merge must not list that tile twice."""
    gd = GameData()
    gd._monster_level = {"corrupted_ogre": 20}
    fill_monster_stat_defaults(gd)
    gd._monster_locations = {"corrupted_ogre": [(8, -4)]}
    gd.world.event_monster_locations["corrupted_ogre"] = [(8, -4), (8, -2)]  # (8,-4) overlaps static
    gd.world.event_code_of_content["corrupted_ogre"] = "ogre_event"
    gd.active_event_codes = {"ogre_event"}
    assert gd.monster_locations("corrupted_ogre") == [(8, -4), (8, -2)]
    assert gd.all_monster_locations["corrupted_ogre"] == [(8, -4), (8, -2)]


def test_static_monster_locations_unchanged_by_overlay() -> None:
    """A normal (non-event) monster's static locations are returned as-is; the
    overlay only ADDS event tiles, never removes static ones."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    fill_monster_stat_defaults(gd)
    gd._monster_locations = {"chicken": [(0, 1)]}
    assert gd.monster_locations("chicken") == [(0, 1)]
    gd.active_event_codes = {"ogre_event"}  # unrelated event active
    assert gd.monster_locations("chicken") == [(0, 1)]
