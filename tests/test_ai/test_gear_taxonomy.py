from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS, stats_is_combat_bearing
from artifactsmmo_cli.ai.item_catalog import ItemStats


def test_stats_is_combat_bearing_reads_itemstats():
    plain = ItemStats(code="x", level=1, type_="ring")
    assert not stats_is_combat_bearing(plain)
    plain.hp_bonus = 10
    assert stats_is_combat_bearing(plain)


def test_equippable_types_are_slot_map_keys():
    assert "weapon" in ITEM_TYPE_TO_SLOTS and "rune" in ITEM_TYPE_TO_SLOTS
