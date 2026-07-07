from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem, skill_curve_target_pure


def _items():
    # (craft_skill, craft_level, item_level, gear_relevant)
    return [
        SkillItem("weaponcrafting", 5, 5, True),    # water_bow
        SkillItem("weaponcrafting", 10, 10, True),  # next-tier weapon
        SkillItem("gearcrafting", 5, 5, True),      # copper_legs
        SkillItem("cooking", 3, 3, False),          # not gear-relevant
        SkillItem("weaponcrafting", 1, 1, True),    # low weapon
    ]


def test_target_is_max_craft_level_within_lookahead():
    # char 7, lookahead 3 -> window item_level <= 10. weaponcrafting items at
    # item_level 1,5,10 all qualify; max craft_level = 10.
    assert skill_curve_target_pure("weaponcrafting", 7, _items(), 3, 50) == 10


def test_window_excludes_above_lookahead():
    # char 5, lookahead 3 -> window <= 8. weapon item_level 10 excluded;
    # remaining 1,5 -> max craft_level 5.
    assert skill_curve_target_pure("weaponcrafting", 5, _items(), 3, 50) == 5


def test_non_gear_relevant_excluded_means_zero():
    # cooking's only item is gear_relevant=False -> 0 (not scheduled).
    assert skill_curve_target_pure("cooking", 99, _items(), 3, 50) == 0


def test_absent_skill_is_zero():
    assert skill_curve_target_pure("alchemy", 99, _items(), 3, 50) == 0


def test_clamped_to_max_skill_level():
    items = [SkillItem("mining", 60, 1, True)]  # malformed craft_level > 50
    assert skill_curve_target_pure("mining", 99, items, 3, 50) == 50


def test_qualifying_item_floors_to_one():
    items = [SkillItem("mining", 0, 1, True)]  # craft_level 0 but qualifies
    # best stays 0 -> treated as "no qualifying recipe" -> 0.
    assert skill_curve_target_pure("mining", 99, items, 3, 50) == 0
