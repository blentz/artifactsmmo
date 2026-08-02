"""Tests for the role_alignment fifth ranking factor (pure core + inert
threading through progression_tree_core)."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.role_alignment import ALIGNED, MISALIGNED, role_alignment_pure
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
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


def test_default_role_is_inert(gear_candidates: list[GearCandidate]) -> None:
    """The inert-landing proof.

    Comparing the default call against `role=_NO_ROLE` explicitly would be
    VACUOUS: `_NO_ROLE` IS the default, so both sides invoke the identical
    object no matter what that object holds — a `_NO_ROLE` poisoned with a
    real `(slot, code)` entry would still make the two sides equal to each
    other (review finding, Task 13). Comparing against an INDEPENDENTLY
    constructed empty mapping instead means this test actually depends on
    `_NO_ROLE` being empty: if the default sentinel were ever poisoned, the
    poisoned default (left side) would diverge from the genuinely empty map
    (right side) and this test would fail."""
    focus: dict = {}
    seats: dict = {}
    truly_empty: dict[tuple[str, str], Fraction] = {}
    assert (_scaled_weights(gear_candidates, focus)
            == _scaled_weights(gear_candidates, focus, role=truly_empty))
    assert (focus_aging_pick(gear_candidates, focus, seats)
            is focus_aging_pick(gear_candidates, focus, seats, role=truly_empty))
    assert (focus_aging_order(gear_candidates, focus, seats)
            == focus_aging_order(gear_candidates, focus, seats, role=truly_empty))


def test_nonempty_role_map_changes_weight_pick_and_order() -> None:
    """Sanity check for the comparison methodology `test_default_role_is_inert`
    relies on: a role map that actually penalizes a candidate MUST change the
    weight, the pick, AND the order — demonstrating the comparison is capable
    of detecting a difference at all. Without this, a byte-identical assertion
    is evidence of nothing (review finding, Task 13)."""
    off_role = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    on_role = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    cands = [off_role, on_role]
    focus: dict = {}
    seats: dict = {}
    role = {("artifact3_slot", "trophy"): MISALIGNED}

    default_weights = dict(_scaled_weights(cands, focus))
    penalized_weights = dict(_scaled_weights(cands, focus, role=role))
    assert penalized_weights["artifact3_slot"] != default_weights["artifact3_slot"]
    assert penalized_weights["artifact3_slot"] == default_weights["artifact3_slot"] * MISALIGNED
    assert penalized_weights["ring1_slot"] == default_weights["ring1_slot"]

    default_pick = focus_aging_pick(cands, focus, seats)
    penalized_pick = focus_aging_pick(cands, focus, seats, role=role)
    assert default_pick is not None and penalized_pick is not None
    assert default_pick.code == "trophy"
    assert penalized_pick.code == "life_ring"

    default_order = [c.code for c in focus_aging_order(cands, focus, seats)]
    penalized_order = [c.code for c in focus_aging_order(cands, focus, seats, role=role)]
    assert default_order == ["trophy", "life_ring"]
    assert penalized_order == ["life_ring", "trophy"]
    assert default_order != penalized_order
