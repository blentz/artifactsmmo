"""min_plan_length: ceil_gathers(mints) + crafts + equip — the is_plannable estimate."""

from artifactsmmo_cli.ai.min_plan_length import min_plan_length

R = {"feather_coat": {"feather": 5, "ash_plank": 2}, "ash_plank": {"ash_wood": 10}}


def test_feather_coat_from_scratch_longer_than_in_hand():
    # mints: 5 feathers + 20 ash_wood... but owned ash_wood=10 -> 5 + 10 = 15 mints
    # (max_gather_yield=1 -> ceil_gathers=15); crafts: ash_plank + coat = 2; equip 1.
    n = min_plan_length("feather_coat", 1, R, {"ash_wood": 10}, 1, equip=True)
    assert n == 18          # 15 + 2 + 1
    assert n <= 32          # within UpgradeEquipmentGoal.max_depth (32) -> admitted


def test_short_chain_when_materials_in_hand():
    # planks in hand, only 5 feathers left: mints 5, crafts 1 (coat), equip 1 = 7
    n = min_plan_length("feather_coat", 1, R, {"ash_plank": 2}, 1, equip=True)
    assert n == 7 and n <= 15


def test_equip_false_drops_one():
    a = min_plan_length("ash_plank", 1, R, {}, 1, equip=False)   # 10 mints + 1 craft
    assert a == 11
