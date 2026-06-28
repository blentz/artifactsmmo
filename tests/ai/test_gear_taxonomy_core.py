from artifactsmmo_cli.ai.gear_taxonomy_core import (
    combat_gear_types, is_combat_bearing, is_consumable,
)


def test_combat_bearing_each_field_independently():
    base = dict(attack={}, resistance={}, hp_bonus=0, dmg=0, dmg_elements={},
                critical_strike=0, initiative=0, lifesteal=0)
    assert not is_combat_bearing(**base)
    for field, val in [("attack", {"fire": 1}), ("resistance", {"air": 1}),
                       ("hp_bonus", 1), ("dmg", 1), ("dmg_elements", {"earth": 1}),
                       ("critical_strike", 1), ("initiative", 1), ("lifesteal", 1)]:
        assert is_combat_bearing(**{**base, field: val}), field


def test_is_consumable_families():
    assert is_consumable(["heal"])
    assert is_consumable(["restore"])
    assert is_consumable(["splash_restore"])
    assert is_consumable(["boost_dmg_fire"])
    assert is_consumable(["boost_res_air"])
    assert is_consumable(["boost_hp"])
    assert is_consumable(["antipoison"])
    assert is_consumable(["teleport"])
    assert not is_consumable(["res_fire"])      # durable armor res, not consumable
    assert not is_consumable([])


def test_combat_gear_excludes_consumable_and_noncombat_types():
    rows = [
        ("weapon", True, False),
        ("ring", True, False),
        ("utility", True, True),    # combat-bearing boost potion BUT consumable
        ("bag", False, False),      # not combat-bearing
    ]
    assert combat_gear_types(rows) == frozenset({"weapon", "ring"})


def test_combat_gear_any_consumable_item_carves_the_type():
    # A type with a durable combat item AND a consumable item is still carved.
    rows = [("utility", True, False), ("utility", False, True)]
    assert combat_gear_types(rows) == frozenset()
