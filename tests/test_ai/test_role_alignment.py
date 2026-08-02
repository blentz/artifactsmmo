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


def test_role_scales_the_weight() -> None:
    """A misaligned candidate with the bigger gain loses to an aligned smaller
    one, mirroring the achievability factor's weight-scaling test."""
    off_role = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    on_role = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    role = {("artifact3_slot", "trophy"): MISALIGNED}
    weights = dict(_scaled_weights([off_role, on_role], {}, role=role))
    assert weights["ring1_slot"] > weights["artifact3_slot"]


def test_role_breaks_the_flat_window_short_circuit() -> None:
    """THE TRAP: while every root is fresh, focus_aging_pick returns the plain
    argmax. Without extending that condition, role is inert for the first
    FOCUS_FLAT cycles — exactly the window a fresh gear decision lives in.
    Same bug synergy's and achievability's docstrings record."""
    off_role = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    on_role = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    role = {("artifact3_slot", "trophy"): MISALIGNED}
    pick = focus_aging_pick([off_role, on_role], {}, {}, role=role)
    assert pick is not None
    assert pick.code == "life_ring", "flat-window fast path ignored role"
