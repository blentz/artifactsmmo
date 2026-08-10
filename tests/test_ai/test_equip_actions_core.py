"""What a loadout change costs — item movements at the published cooldown."""

import pytest

from artifactsmmo_cli.ai.equipment.equip_actions_core import (
    EQUIP_SECONDS_PER_ITEM,
    equip_cost,
    items_moved,
)
from artifactsmmo_cli.ai.learning.fight_loop_cost import TYPICAL_FIGHT_COOLDOWN_SECONDS


def test_no_change_costs_nothing():
    """A loadout held across rungs is paid for once, not once per rung."""
    worn = {"weapon_slot": "iron_sword", "shield_slot": "wooden_shield"}
    assert items_moved(worn, dict(worn)) == 0
    assert equip_cost(worn, dict(worn)) == 0.0


def test_filling_an_empty_slot_is_one_movement():
    assert items_moved({"shield_slot": None}, {"shield_slot": "iron_shield"}) == 1
    assert items_moved({}, {"shield_slot": "iron_shield"}) == 1


def test_emptying_a_slot_is_one_movement():
    """Taking a piece off is work too — the walk may drop a piece whose slot the
    rung's chosen loadout wants empty."""
    assert items_moved({"shield_slot": "iron_shield"}, {"shield_slot": None}) == 1
    assert items_moved({"shield_slot": "iron_shield"}, {}) == 1


def test_a_swap_costs_two_because_the_server_refuses_an_occupied_slot():
    """THE RULE THIS MODULE FIRST GUESSED WRONG.

    `POST /action/equip` answers `491: The equipment slot is not empty`, so the
    outgoing piece must come off before the new one goes on. Counting differing
    SLOTS — as the first version did, on a docstring asserting the opposite —
    priced every upgrade after a character's first as if the old item evaporated."""
    worn = {"shield_slot": "wooden_shield"}
    target = {"shield_slot": "iron_shield"}
    assert items_moved(worn, target) == 2
    # Premise: this is genuinely the occupied-slot case, not the empty one, or the
    # test proves nothing about the rule it names.
    assert worn["shield_slot"] is not None


def test_the_three_spellings_of_empty_agree():
    """`WorldState.equipment` spells every slot including the empty ones; a picked
    loadout may omit slots it has no opinion about; the API reports unfilled as "".
    Treating those as different would invent a movement per unmentioned empty slot
    — on a sixteen-slot character, a phantom loadout change at every first rung."""
    for absent in ({}, {"shield_slot": None}, {"shield_slot": ""}):
        assert items_moved(absent, {"shield_slot": None}) == 0
        assert items_moved({"shield_slot": ""}, absent) == 0


def test_cost_is_the_published_three_seconds_per_item():
    """Equip is 3 seconds per item, not a whole action. Charging a fight-equivalent
    per piece over-priced a loadout change by roughly ten times."""
    worn = {"shield_slot": "wooden_shield"}
    target = {"shield_slot": "iron_shield"}
    expected = 2 * EQUIP_SECONDS_PER_ITEM / TYPICAL_FIGHT_COOLDOWN_SECONDS
    assert equip_cost(worn, target) == pytest.approx(expected)
    assert equip_cost(worn, target) == pytest.approx(0.2)


def test_outfitting_a_bare_character_is_not_sixteen_fights():
    """The case that made the old count most obviously wrong: a bare character at
    its first rung. Sixteen pieces are 48 published seconds, under two fights'
    worth of time — not sixteen fights."""
    bare = {f"slot{i}": None for i in range(16)}
    dressed = {f"slot{i}": f"item{i}" for i in range(16)}
    assert items_moved(bare, dressed) == 16
    assert equip_cost(bare, dressed) == pytest.approx(16 * 3 / 30)
    assert equip_cost(bare, dressed) < 2.0
