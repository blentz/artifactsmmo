from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value


def test_sums_attack_resistance_hp_restore():
    s = ItemStats(code="x", level=1, type_="weapon",
                  attack={"fire": 10, "air": 2}, resistance={"earth": 3}, hp_restore=5)
    assert equip_value(s) == 20.0


def test_zero_when_no_stats():
    assert equip_value(ItemStats(code="x", level=1, type_="resource")) == 0.0
