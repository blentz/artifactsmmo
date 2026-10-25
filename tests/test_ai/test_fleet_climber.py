"""Who climbs which skill for the fleet (spec 2026-10-18 §2.5, ruling T7a):
`fleet_climbers` assigns the demanded craft skills over live coordination
data, and `serving_climbers` keeps the climbers that can serve their skill."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.fleet_climber import fleet_climbers, serving_climbers

ORDER = ("Ana", "Bea", "Cid")
OWNERS = {"gearcrafting": "logger", "jewelrycrafting": "jeweler", "weaponcrafting": "miner"}
RANK = ("weaponcrafting", "gearcrafting", "jewelrycrafting")
"""The role catalogue's declared craft-skill order (miner, logger, jeweler)."""


def _assign(me: str, mine: dict[str, int], siblings: dict[str, dict[str, int]],
            demanded: dict[str, int] | None = None, gain: dict[str, Fraction] | None = None,
            leases: dict[str, frozenset[str]] | None = None,
            order: tuple[str, ...] = ORDER) -> dict[str, str]:
    return fleet_climbers(demanded or {"gearcrafting": 30}, gain or {}, OWNERS, RANK, me, mine,
                          siblings, leases or {}, order)


def test_the_character_highest_in_the_skill_climbs() -> None:
    assert _assign("Bea", {"gearcrafting": 20}, {"Ana": {"gearcrafting": 23}}) == {
        "gearcrafting": "Ana"}
    assert _assign("Ana", {"gearcrafting": 23}, {"Bea": {"gearcrafting": 20}}) == {
        "gearcrafting": "Ana"}


def test_one_character_highest_in_two_skills_climbs_one() -> None:
    """Ana leads both; jewelrycrafting carries more fleet gain, so it takes
    Ana first, and gearcrafting goes to Bea, the only one still free."""
    demanded = {"gearcrafting": 30, "jewelrycrafting": 30}
    gain = {"gearcrafting": Fraction(1), "jewelrycrafting": Fraction(2)}
    ana = {"gearcrafting": 23, "jewelrycrafting": 25}
    bea = {"gearcrafting": 20, "jewelrycrafting": 22}
    assert _assign("Ana", ana, {"Bea": bea}, demanded, gain) == {
        "jewelrycrafting": "Ana", "gearcrafting": "Bea"}
    gain = {"gearcrafting": Fraction(3), "jewelrycrafting": Fraction(2)}
    assert _assign("Ana", ana, {"Bea": bea}, demanded, gain) == {
        "gearcrafting": "Ana", "jewelrycrafting": "Bea"}


def test_equal_gain_takes_the_catalogue_order() -> None:
    """Gearcrafting precedes jewelrycrafting in the role catalogue."""
    demanded = {"gearcrafting": 30, "jewelrycrafting": 30}
    ana = {"gearcrafting": 23, "jewelrycrafting": 25}
    assert _assign("Ana", ana, {"Bea": {}}, demanded) == {
        "gearcrafting": "Ana", "jewelrycrafting": "Bea"}


def test_more_skills_than_characters_leaves_one_unclimbed() -> None:
    demanded = {"gearcrafting": 30, "jewelrycrafting": 30}
    assert _assign("Ana", {}, {}, demanded, order=("Ana",)) == {"gearcrafting": "Ana"}


def test_a_gathering_skill_is_not_climbed_for_the_fleet() -> None:
    assert _assign("Ana", {}, {}, {"woodcutting": 20}) == {}


def test_this_characters_own_levels_are_its_live_ones() -> None:
    """Its own ledger row is stale beside `state.skills`: the live level wins."""
    assert _assign("Ana", {"gearcrafting": 25},
                   {"Ana": {"gearcrafting": 1}, "Bea": {"gearcrafting": 24}}) == {
        "gearcrafting": "Ana"}


def test_levels_past_the_demand_are_no_better() -> None:
    """Both at or past 30 have nothing left to climb: the tie goes to the fleet
    order, not to the higher level."""
    assert _assign("Bea", {"gearcrafting": 35}, {"Ana": {"gearcrafting": 30}}) == {
        "gearcrafting": "Ana"}


def test_a_remaining_tie_goes_to_the_one_with_no_other_role() -> None:
    """Holding the skill's own role is no other work; holding another is."""
    leases = {"miner": frozenset({"Ana"}), "logger": frozenset({"Bea"})}
    assert _assign("Bea", {"gearcrafting": 23}, {"Ana": {"gearcrafting": 23}},
                   leases=leases) == {"gearcrafting": "Bea"}


def test_a_missing_level_reads_zero() -> None:
    assert _assign("Ana", {}, {"Bea": {"mining": 40}, "Cid": {"gearcrafting": 1}}) == {
        "gearcrafting": "Cid"}


def test_a_ledger_row_outside_the_fleet_does_not_compete() -> None:
    assert _assign("Bea", {"gearcrafting": 20}, {"Zed": {"gearcrafting": 29}},
                   order=("Bea",)) == {"gearcrafting": "Bea"}


def test_this_character_must_be_in_the_fleet() -> None:
    with pytest.raises(ValueError, match="outside the fleet order"):
        _assign("Zed", {"gearcrafting": 20}, {}, order=("Ana",))


def test_a_climber_serves_with_its_skills_role_or_none() -> None:
    """Holding the skill's own role, or no role, it serves; holding another
    role it serves nothing for this skill (ruling T7a)."""
    climbers = {"gearcrafting": "Ana", "jewelrycrafting": "Bea", "weaponcrafting": "Cid"}
    leases = {"logger": frozenset({"Ana"}), "miner": frozenset({"Bea"})}
    assert serving_climbers(climbers, OWNERS, leases) == {"gearcrafting": "Ana",
                                                          "weaponcrafting": "Cid"}
