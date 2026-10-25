"""Unit tests for the fleet climb's pure core (spec 2026-10-18 §2.5): the
amortized climb share and the choice of the one character that climbs."""
from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.fleet_climb_core import amortized_climb_seconds, climber


def test_a_climb_is_divided_across_the_units_it_unlocks() -> None:
    assert amortized_climb_seconds(Fraction(100), 4) == 25


def test_one_unit_pays_the_whole_climb() -> None:
    assert amortized_climb_seconds(Fraction(7, 3), 1) == Fraction(7, 3)


def test_a_climb_shared_by_no_unit_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one unit"):
        amortized_climb_seconds(Fraction(100), 0)


def test_the_least_remaining_climb_climbs() -> None:
    assert climber({"a": Fraction(10), "b": Fraction(7)}, {"a": 0, "b": 3},
                   ("a", "b")) == "b"


def test_a_remaining_tie_goes_to_fewer_committed() -> None:
    assert climber({"a": Fraction(7), "b": Fraction(7)}, {"a": 1, "b": 0},
                   ("a", "b")) == "b"


def test_a_full_tie_goes_to_the_fleet_order_not_the_name() -> None:
    """`zed` sorts after `amy` by name; the fleet order puts it first."""
    assert climber({"amy": Fraction(7), "zed": Fraction(7)}, {"amy": 0, "zed": 0},
                   ("zed", "amy")) == "zed"


def test_a_character_outside_the_fleet_order_is_refused() -> None:
    with pytest.raises(ValueError, match="outside the fleet order"):
        climber({"a": Fraction(1), "x": Fraction(0)}, {"a": 0, "x": 0}, ("a",))


def test_an_empty_fleet_has_no_climber() -> None:
    with pytest.raises(ValueError, match="fleet is empty"):
        climber({}, {}, ("a",))


def test_a_candidate_without_a_committed_count_is_refused() -> None:
    with pytest.raises(KeyError):
        climber({"a": Fraction(1), "b": Fraction(2)}, {"b": 0}, ("a", "b"))
