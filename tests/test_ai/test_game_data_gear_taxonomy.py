from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats


def _gd_with(items):
    gd = GameData()
    for s in items:
        gd._item_stats[s.code] = s
    return gd


def test_properties_classify_durable_vs_consumable():
    weapon = ItemStats(code="sword", level=1, type_="weapon", attack={"fire": 5})
    ring = ItemStats(code="ring1", level=1, type_="ring", hp_bonus=3)
    potion = ItemStats(code="boostpot", level=1, type_="utility", dmg_elements={"fire": 5})
    bag = ItemStats(code="bag1", level=1, type_="bag", inventory_space=10)
    gd = _gd_with([weapon, ring, potion, bag])
    # consumable_types is built from raw effect codes; inject for the utility potion.
    gd._consumable_effect_codes = {"boostpot": ["boost_dmg_fire"]}
    assert "weapon" in gd.combat_gear_types
    assert "ring" in gd.combat_gear_types
    assert "utility" not in gd.combat_gear_types     # consumable
    assert "bag" not in gd.combat_gear_types          # not combat-bearing
    assert "weapon" not in gd.defensive_gear_types
    assert "ring" in gd.defensive_gear_types
