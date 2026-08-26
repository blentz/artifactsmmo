"""Tests for `ai/utility_slot.py` — the ONE producer of "which utility slot".

Before 2026-08-25 the answer was a hard-coded `_TARGET_SLOT = "utility1_slot"`
in TWO modules (`craft_ladder` and `goals/provision_marginal_fight`), which is
why `CraftPotionsGoal`'s boost-stock arm equipped its boost over the heal stack
whose satisfaction had gated the arm. Each of the three rules below is pinned
here, and the arm's convergence is pinned end-to-end in
`tests/test_ai/scenarios/test_boost_stock_cell.py`.
"""

import dataclasses

import pytest

from artifactsmmo_cli.ai.utility_slot import (
    UTILITY_SLOTS,
    already_provisioned,
    utility_slot_for,
    utility_slot_quantity,
)
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state

HEAL = "small_health_potion"
BOOST = "earth_boost_potion"
OTHER = "minor_health_potion"


def _state(slot1: str | None = None, qty1: int = 0,
           slot2: str | None = None, qty2: int = 0) -> WorldState:
    base = make_state()
    return dataclasses.replace(
        base,
        equipment={**base.equipment,
                   "utility1_slot": slot1, "utility2_slot": slot2},
        utility1_slot_quantity=qty1,
        utility2_slot_quantity=qty2,
    )


def test_the_slot_names_are_declared_once():
    """The tuple every caller reads. `equipped_potion_qty`, `EquipAction` and
    `ProvisionMarginalFightGoal` all import THIS one, so a slot rename is a
    single edit."""
    assert UTILITY_SLOTS == ("utility1_slot", "utility2_slot")


def test_quantity_reads_the_per_slot_field():
    state = _state(HEAL, 40, BOOST, 6)
    assert utility_slot_quantity(state, "utility1_slot") == 40
    assert utility_slot_quantity(state, "utility2_slot") == 6


def test_quantity_of_a_non_utility_slot_is_zero():
    """An equipment slot carries no quantity field at all — it holds exactly
    one item. `EquipAction._displaced_qty` relies on this to keep the
    one-unit-displaced rule for weapons and armour."""
    assert utility_slot_quantity(_state(HEAL, 40), "weapon_slot") == 0


# --- rule 1: the slot already holding the code ------------------------------

def test_rule1_the_slot_already_holding_the_code_wins_slot1():
    """Not a preference, a requirement: utility is not in
    DUPLICATE_SLOT_TYPES, so the server 485s a code worn in the sibling slot,
    and `EquipAction.apply` models the same-code equip as additive."""
    assert utility_slot_for(HEAL, _state(HEAL, 40, None, 0)) == "utility1_slot"


def test_rule1_the_slot_already_holding_the_code_wins_slot2():
    """Rule 1 beats rule 2: slot 1 is FREE and is still not the answer,
    because equipping into it would be refused by the server."""
    state = _state(None, 0, HEAL, 40)
    assert state.equipment["utility1_slot"] is None
    assert utility_slot_for(HEAL, state) == "utility2_slot"


# --- rule 2: a free slot, slot 1 first --------------------------------------

def test_rule2_both_free_picks_slot1():
    assert utility_slot_for(HEAL, _state()) == "utility1_slot"


def test_rule2_prefers_the_free_slot_over_the_occupied_one():
    """THE FIX. Slot 1 holds a 40-potion heal stack and slot 2 is empty: the
    boost goes to slot 2 and nothing is displaced. The pre-fix hard-code
    answered "utility1_slot" here and destroyed the heal stack."""
    assert utility_slot_for(BOOST, _state(HEAL, 40, None, 0)) == "utility2_slot"


# --- rule 3: both occupied — displace the smaller stack ---------------------

def test_rule3_displaces_the_smaller_stack_when_slot2_is_smaller():
    assert utility_slot_for(OTHER, _state(HEAL, 40, BOOST, 6)) == "utility2_slot"


def test_rule3_displaces_the_smaller_stack_when_slot1_is_smaller():
    """Quantity decides, not slot order — 3 < 30, so slot 1 goes."""
    assert utility_slot_for(OTHER, _state(HEAL, 3, BOOST, 30)) == "utility1_slot"


def test_rule3_ties_break_to_slot2_keeping_the_primary_slot_stable():
    """`ObjectiveTiers.utility_potion_targets` designates slot 1 for the
    PRIMARY heal and slot 2 for the secondary, so an equal-sized eviction
    takes the secondary and leaves the heal the character fights with."""
    assert utility_slot_for(OTHER, _state(HEAL, 10, BOOST, 10)) == "utility2_slot"


# ---------------------------------------------------------------------------
# already_provisioned — the predicate the goal and its emitter SHARE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slot1,slot2,expected", [
    (None, None, False),
    (HEAL, None, True),
    (None, BOOST, True),
    (HEAL, BOOST, True),
])
def test_already_provisioned_reads_both_slots(slot1, slot2, expected):
    """EITHER slot counts. A version reading only slot 1 disagrees on the
    (None, BOOST) row — the row that survived the whole suite while
    `_marginal_provision_goal` carried its own hand-copy of this predicate."""
    assert already_provisioned(_state(slot1, 0, slot2, 0)) is expected
