"""The census loadout's own mechanics (`craft_completeness.census_gear`):
the parent-computed table and its seed.

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
