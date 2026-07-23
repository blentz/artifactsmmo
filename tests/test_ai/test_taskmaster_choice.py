"""Wave 4: the taskmaster choice (`choose_taskmaster`, spec §4).

Picks the tasks master whose pool best serves the pursued gear. The lever is
binary — combat tasks (char_xp) vs craft/gather tasks (materials + skills) — and
is scored against the live GEAR demand, not the trunk, so a monsters master does
not trivially win. These tests pin the lever both ways, the nearer-tile
tie-break, and the two "no choice" edges that fall back to today's behaviour.
"""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.synergy_core import S_MIN
from artifactsmmo_cli.ai.tiers.taskmaster_choice import choose_taskmaster

from tests.test_ai.fixtures import make_state

_BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


@pytest.fixture(scope="module")
def bundle_game_data() -> GameData:
    return GameData.from_cache_bundle(json.loads(_BUNDLE.read_text()))


class _FakeTask:
    def __init__(self, code: str, type_: str) -> None:
        self.code = code
        self.type_ = type_          # plain str: getattr(str,'value',str) == str


class _FakeMemo:
    def __init__(self, demands: dict[str, dict[str, int]]) -> None:
        self._demands = demands

    def requirement_multiset_for(self, code: str) -> dict[str, int]:
        return self._demands.get(code, {})


class _FakeGameData:
    def __init__(self, tiles, tasks_by_type, demands) -> None:
        self.taskmaster_tiles = tiles
        self._tasks = tasks_by_type
        self.requirement_graph = _FakeMemo(demands)

    def tasks_for(self, task_type, max_level):
        return self._tasks.get(task_type, [])


_TILES = {"monsters": (1, 1), "items": (5, 5)}


def test_one_master_no_choice():
    """Only one master discovered — no distribution to pick, fall back (None).
    This is exactly the pre-Phase-0 world, so Phase 4 was provably inert then."""
    gd = _FakeGameData({"monsters": (1, 1)}, {"monsters": [_FakeTask("w", "monsters")]}, {})
    assert choose_taskmaster(make_state(), gd, frozenset()) is None


def test_both_pools_empty_no_choice():
    """Two masters, but neither has a level-appropriate task — no basis to
    choose, fall back to the nearest/default tile (None)."""
    gd = _FakeGameData(_TILES, {"monsters": [], "items": []}, {})
    assert choose_taskmaster(make_state(), gd, frozenset({"gear"})) is None


def test_monsters_preferred_when_gear_routes_through_drops():
    """Gear whose closure needs monster drops (a char_xp token) aligns with the
    combat master; the unrelated craft task stays at the floor."""
    gd = _FakeGameData(
        _TILES,
        {"monsters": [_FakeTask("wolf", "monsters")],
         "items": [_FakeTask("copper_bar", "items")]},
        {"drop_gear": {"char_xp": 3}, "copper_bar": {"copper_ore": 2}},
    )
    chosen = choose_taskmaster(make_state(x=0, y=0), gd, frozenset({"drop_gear"}))
    assert chosen == ("monsters", (1, 1))


def test_items_preferred_when_gear_needs_materials_and_skills():
    """Gear routed through crafting (shared materials + a skill token) aligns with
    the items master; the combat task does not (the gear needs no char_xp)."""
    gd = _FakeGameData(
        _TILES,
        {"monsters": [_FakeTask("wolf", "monsters")],
         "items": [_FakeTask("copper_bar", "items")]},
        {"craft_gear": {"skill:mining": 2, "copper_ore": 5},
         "copper_bar": {"copper_ore": 3, "skill:mining": 1}},
    )
    chosen = choose_taskmaster(make_state(x=0, y=0), gd, frozenset({"craft_gear"}))
    assert chosen == ("items", (5, 5))


def test_tie_breaks_to_the_nearer_tile():
    """No gear demand → every task scores S_MIN → the masters tie → the nearer
    tile wins (travel is a legitimate tie-break, never part of the score)."""
    gd = _FakeGameData(
        _TILES,
        {"monsters": [_FakeTask("wolf", "monsters")],
         "items": [_FakeTask("copper_bar", "items")]},
        {"copper_bar": {"copper_ore": 1}},
    )
    # character at (0,0): monsters tile (1,1) dist 2 < items (5,5) dist 10
    chosen = choose_taskmaster(make_state(x=0, y=0), gd, frozenset())
    assert chosen == ("monsters", (1, 1))
    # move the character next to the items tile: now items is nearer and wins
    chosen2 = choose_taskmaster(make_state(x=5, y=4), gd, frozenset())
    assert chosen2 == ("items", (5, 5))


def test_choice_fires_on_real_bundle(bundle_game_data: GameData):
    """Runtime activation (spec §7): on the real bundle, with its two discovered
    masters and a level that has tasks, the choice returns one of the real
    taskmaster tiles — proof it is not silently inert."""
    tiles = bundle_game_data.taskmaster_tiles
    assert len(tiles) == 2, "bundle should carry both keyed masters (Phase 0)"
    chosen = choose_taskmaster(make_state(level=40, x=0, y=0), bundle_game_data,
                               frozenset())
    assert chosen is not None, "no task at level 40 in either pool — choice inert"
    code, tile = chosen
    assert code in tiles and tile == tiles[code]
