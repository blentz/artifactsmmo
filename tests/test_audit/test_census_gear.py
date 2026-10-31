"""The census loadout's own mechanics (`craft_completeness.census_gear`):
the parent-computed table and its seed, the growth along the rungs, the
keep-what-it-wore fallback, the rung ladder and the memo key.

The gear objective itself is replaced by a recording stand-in, so each test
asks exactly the property it names on a fresh catalogue (the memo is scoped
per catalogue), independent of test order."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_result import GearObjective
from artifactsmmo_cli.audit import craft_completeness
from artifactsmmo_cli.audit.craft_completeness import (
    CensusGearKey,
    _rung_below,
    census_gear,
    census_gear_table,
    seed_census_gear,
)

Call = tuple[int, frozenset[str], bool, dict[str, str]]


def _objective(loadout: dict[str, str]) -> GearObjective:
    return GearObjective(monster="m", loadout=loadout, rate=Fraction(1), missing=())


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[Call]:
    """Every `_census_objective` call, answered with a loadout naming its key."""
    seen: list[Call] = []

    def stand_in(char_level: int, events: frozenset[str], geared: bool,
                 worn: dict[str, str], _game_data: GameData) -> GearObjective:
        seen.append((char_level, events, geared, dict(worn)))
        return _objective({"weapon_slot": f"w{char_level}-{sorted(events)}-{geared}"})

    monkeypatch.setattr(craft_completeness, "_census_objective", stand_in)
    return seen


def test_a_seeded_table_is_served_without_recomputing(calls: list[Call]) -> None:
    """A worker seeded with the parent's table never asks the objective."""
    gd = GameData()
    table: dict[CensusGearKey, dict[str, str]] = {
        (12, frozenset(), False): {"weapon_slot": "sentinel"}}
    seed_census_gear(table, gd)
    assert census_gear(12, frozenset(), False, gd) == {"weapon_slot": "sentinel"}
    assert calls == []


def test_the_table_holds_every_rung_it_grew_along(calls: list[Call]) -> None:
    """The parent's table is the chain each key grew along, computed once."""
    gd = GameData()
    table = census_gear_table([(12, frozenset(), False)], gd)
    assert sorted(table) == [(level, frozenset(), False) for level in (1, 5, 10, 12)]
    assert [c[0] for c in calls] == [1, 5, 10, 12]
    asked = len(calls)
    assert census_gear_table([(12, frozenset(), False)], gd) == table
    assert len(calls) == asked


def test_each_rung_wears_the_rung_below(calls: list[Call]) -> None:
    """Growth: a level's objective is asked wearing the loadout of the rung
    below; level 1 wears nothing."""
    gd = GameData()
    census_gear(12, frozenset(), False, gd)
    worn = {c[0]: c[3] for c in calls}
    assert worn[1] == {}
    assert worn[5] == {"weapon_slot": "w1-[]-False"}
    assert worn[10] == {"weapon_slot": "w5-[]-False"}
    assert worn[12] == {"weapon_slot": "w10-[]-False"}


def test_a_level_with_no_objective_keeps_what_it_wore(monkeypatch: pytest.MonkeyPatch) -> None:
    """No loadout pays XP at a level: the character keeps the rung below's."""
    def stand_in(char_level: int, _events: frozenset[str], _geared: bool,
                 _worn: dict[str, str], _game_data: GameData) -> GearObjective | None:
        return None if char_level == 12 else _objective({"weapon_slot": f"w{char_level}"})

    monkeypatch.setattr(craft_completeness, "_census_objective", stand_in)
    assert census_gear(12, frozenset(), False, GameData()) == {"weapon_slot": "w10"}


def test_the_rung_ladder_is_one_then_every_step() -> None:
    assert _rung_below(1) is None
    assert _rung_below(2) == 1
    assert _rung_below(5) == 1
    assert _rung_below(6) == 5
    assert _rung_below(10) == 5
    assert _rung_below(12) == 10


def test_the_memo_keys_on_events_and_geared(calls: list[Call]) -> None:
    """Each of `events` and `geared` is part of the key, whichever is asked first."""
    gd = GameData()
    live = frozenset({"full_moon"})
    geared = census_gear(12, frozenset(), True, gd)
    evented = census_gear(12, live, False, gd)
    plain = census_gear(12, frozenset(), False, gd)
    assert geared == {"weapon_slot": "w12-[]-True"}
    assert evented == {"weapon_slot": "w12-['full_moon']-False"}
    assert plain == {"weapon_slot": "w12-[]-False"}
