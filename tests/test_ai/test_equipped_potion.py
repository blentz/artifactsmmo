"""Tests for equipped_potion_qty helper."""

import dataclasses

from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from tests.test_ai.fixtures import make_state


def test_equipped_potion_qty_sums_matching_slots():
    state = make_state(equipment={"utility1_slot": "small_health_potion", "utility2_slot": "small_health_potion"})
    state = dataclasses.replace(state, utility1_slot_quantity=40, utility2_slot_quantity=10)
    assert equipped_potion_qty(state, "small_health_potion") == 50
    assert equipped_potion_qty(state, "other") == 0
