from artifactsmmo_cli.ai.tiers.next_tier_cap import (
    next_tier_cap_pure,
    next_tier_dampened_pure,
)
from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem


def _item(skill: str, craft_level: int, item_level: int, gear: bool = True) -> SkillItem:
    return SkillItem(craft_skill=skill, craft_level=craft_level,
                     item_level=item_level, gear_relevant=gear)


def test_cap_is_max_craft_level_in_next_tier_band():
    # char_level 6 -> next_tier_floor 10, band [10,19] (iron-ish).
    items = [
        _item("weaponcrafting", 5, 3),    # current tier, ignored
        _item("weaponcrafting", 12, 11),  # next tier
        _item("weaponcrafting", 15, 18),  # next tier, higher craft level
        _item("weaponcrafting", 20, 22),  # tier after next, ignored
    ]
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 15


def test_cap_zero_when_no_gear_in_next_band():
    items = [_item("weaponcrafting", 5, 3)]  # only current-tier gear
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 0


def test_cap_ignores_non_gear_and_other_skills():
    items = [
        _item("weaponcrafting", 15, 12, gear=False),  # non-gear
        _item("gearcrafting", 15, 12, gear=True),     # other skill
    ]
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 0


def test_cap_clamped_to_max_skill_level():
    items = [_item("weaponcrafting", 99, 12)]
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 50


def test_band_rolls_up_across_decade_boundary():
    items = [
        _item("weaponcrafting", 15, 18),  # band [10,19]
        _item("weaponcrafting", 25, 28),  # band [20,29]
    ]
    # char 6 -> band [10,19] -> cap 15
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 15
    # char 12 -> next_tier_floor ((12//10)+1)*10 = 20 -> band [20,29] -> cap 25
    assert next_tier_cap_pure("weaponcrafting", 12, items, 50) == 25


def test_dampened_true_when_skill_covers_next_tier():
    assert next_tier_dampened_pure(15, 15) is True
    assert next_tier_dampened_pure(16, 15) is True


def test_dampened_false_below_cap():
    assert next_tier_dampened_pure(14, 15) is False


def test_dampened_false_when_cap_zero():
    assert next_tier_dampened_pure(99, 0) is False
