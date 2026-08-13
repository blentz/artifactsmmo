"""min_plan_length: min_gather_steps(mints) + crafts + equip — the is_plannable estimate."""

from artifactsmmo_cli.ai.min_plan_length import min_plan_length

R = {"feather_coat": {"feather": 5, "ash_plank": 2}, "ash_plank": {"ash_wood": 10}}


def test_feather_coat_from_scratch_longer_than_in_hand():
    # mints: one batched gather step per distinct raw leaf still needed —
    # feather (leaf) and ash_wood (leaf; owned=10 covers only 10 of the 20
    # demanded, so it is still a leaf that must be gathered) = 2 mints;
    # crafts: ash_plank + coat = 2; equip 1.
    n = min_plan_length("feather_coat", 1, R, {"ash_wood": 10}, 1, equip=True)
    assert n == 5           # 2 + 2 + 1
    assert n <= 32          # within UpgradeEquipmentGoal.max_depth (32) -> admitted


def test_short_chain_when_materials_in_hand():
    # planks in hand, only feather is an unmet leaf: mints 1, crafts 1 (coat),
    # equip 1 = 3
    n = min_plan_length("feather_coat", 1, R, {"ash_plank": 2}, 1, equip=True)
    assert n == 3 and n <= 15


def test_equip_false_drops_one():
    a = min_plan_length("ash_plank", 1, R, {}, 1, equip=False)   # 1 mint (ash_wood leaf) + 1 craft
    assert a == 2


_STAFF_RECIPES = {
    "greater_wooden_staff": {"spruce_plank": 6, "blue_slimeball": 2},
    "spruce_plank": {"spruce_wood": 10},
}


def test_deep_chain_is_admissible_under_batching():
    """Pre-batching this was ceil_gathers(60 spruce_wood + 2 slimeball) + 2
    crafts + equip = 65, well past UpgradeEquipmentGoal.max_depth 32, so
    is_plannable rejected the staff before A* ever ran. Batched: 2 gather
    steps (spruce_wood, blue_slimeball) + 2 crafts (spruce_plank,
    greater_wooden_staff) + 1 equip = 5."""
    assert min_plan_length("greater_wooden_staff", 1, _STAFF_RECIPES, {},
                           max_gather_yield=1, equip=True) == 5


def test_owned_materials_shorten_the_bound():
    owned = {"spruce_plank": 6, "blue_slimeball": 2}
    assert min_plan_length("greater_wooden_staff", 1, _STAFF_RECIPES, owned,
                           max_gather_yield=1, equip=True) == 2


def test_equip_flag_adds_exactly_one():
    args = ("greater_wooden_staff", 1, _STAFF_RECIPES, {})
    with_equip = min_plan_length(*args, max_gather_yield=1, equip=True)
    without = min_plan_length(*args, max_gather_yield=1, equip=False)
    assert with_equip - without == 1
