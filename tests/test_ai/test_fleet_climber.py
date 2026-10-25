"""Who climbs a skill for the fleet (spec 2026-10-18 §2.5): `fleet_climber`
reads live coordination data into the proved `fleet_climb_core.climber`."""

import pytest

from artifactsmmo_cli.ai.fleet_climber import fleet_climber

ORDER = ("Ana", "Bea", "Cid")


def _climber(me: str, mine: dict[str, int], siblings: dict[str, dict[str, int]],
             leases: dict[str, frozenset[str]] | None = None,
             order: tuple[str, ...] = ORDER) -> str:
    return fleet_climber("gearcrafting", 30, me, mine, siblings, leases or {}, "logger", order)


def test_the_character_highest_in_the_skill_climbs() -> None:
    assert _climber("Bea", {"gearcrafting": 20}, {"Ana": {"gearcrafting": 23}}) == "Ana"
    assert _climber("Ana", {"gearcrafting": 23}, {"Bea": {"gearcrafting": 20}}) == "Ana"


def test_this_characters_own_levels_are_its_live_ones() -> None:
    """Its own ledger row is stale beside `state.skills`: the live level wins."""
    assert _climber("Ana", {"gearcrafting": 25},
                    {"Ana": {"gearcrafting": 1}, "Bea": {"gearcrafting": 24}}) == "Ana"


def test_levels_past_the_demand_are_no_better() -> None:
    """Both at or past 30 have nothing left to climb: the tie goes to the fleet
    order, not to the higher level."""
    assert _climber("Bea", {"gearcrafting": 35}, {"Ana": {"gearcrafting": 30}}) == "Ana"


def test_a_remaining_tie_goes_to_the_one_with_no_other_role() -> None:
    """Holding the skill's own role is no other work; holding another is."""
    leases = {"miner": frozenset({"Ana"}), "logger": frozenset({"Bea"})}
    assert _climber("Bea", {"gearcrafting": 23}, {"Ana": {"gearcrafting": 23}}, leases) == "Bea"


def test_a_missing_level_reads_zero() -> None:
    assert _climber("Ana", {}, {"Bea": {"mining": 40}, "Cid": {"gearcrafting": 1}}) == "Cid"


def test_a_ledger_row_outside_the_fleet_does_not_compete() -> None:
    assert _climber("Bea", {"gearcrafting": 20}, {"Zed": {"gearcrafting": 29}},
                    order=("Bea",)) == "Bea"


def test_this_character_must_be_in_the_fleet() -> None:
    with pytest.raises(ValueError, match="outside the fleet order"):
        _climber("Zed", {"gearcrafting": 20}, {}, order=("Ana",))
