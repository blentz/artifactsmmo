"""Tests for the role_alignment fifth ranking factor (pure core + inert
threading through progression_tree_core)."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.role_alignment import ALIGNED, MISALIGNED, role_alignment_pure
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    _NO_ROLE,
    GearCandidate,
    _scaled_weights,
    focus_aging_order,
    focus_aging_pick,
)


def test_candidate_in_our_skills_is_unpenalised() -> None:
    assert role_alignment_pure(frozenset({"mining", "weaponcrafting"}),
                               "weaponcrafting") == ALIGNED


def test_candidate_outside_our_skills_is_damped() -> None:
    assert role_alignment_pure(frozenset({"mining", "weaponcrafting"}),
                               "gearcrafting") == MISALIGNED


def test_unknown_producing_skill_is_unpenalised() -> None:
    """No signal must never become a penalty — the no-invented-data rule."""
    assert role_alignment_pure(frozenset({"mining"}), None) == ALIGNED


def test_no_role_is_identity() -> None:
    assert role_alignment_pure(frozenset(), "weaponcrafting") == ALIGNED


def test_damping_never_reorders_below_zero() -> None:
    assert MISALIGNED > 0
    assert MISALIGNED < ALIGNED
    assert isinstance(MISALIGNED, Fraction)


@pytest.fixture
def gear_candidates() -> list[GearCandidate]:
    return [
        GearCandidate(slot="weapon_slot", code="iron_sword", gain=Fraction(100), level=10),
        GearCandidate(slot="ring1_slot", code="iron_ring", gain=Fraction(50), level=8),
        GearCandidate(slot="ring2_slot", code="iron_ring", gain=Fraction(50), level=8),
    ]


def test_empty_role_map_is_byte_identical(gear_candidates: list[GearCandidate]) -> None:
    """The inert-landing proof: with _NO_ROLE the weights, pick and order are
    exactly what the four-factor composition produced."""
    focus: dict = {}
    seats: dict = {}
    assert (_scaled_weights(gear_candidates, focus)
            == _scaled_weights(gear_candidates, focus, role=_NO_ROLE))
    assert (focus_aging_pick(gear_candidates, focus, seats)
            is focus_aging_pick(gear_candidates, focus, seats, role=_NO_ROLE))
    assert (focus_aging_order(gear_candidates, focus, seats)
            == focus_aging_order(gear_candidates, focus, seats, role=_NO_ROLE))
