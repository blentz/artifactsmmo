"""GameData retains the full resource drop table (item, rate, min_q, max_q)."""
from artifactsmmo_cli.ai.game_data import GameData


def test_resource_drop_table_returns_rows():
    gd = GameData()
    gd._resource_drops_full = {"copper_rocks": [("copper_ore", 1, 1, 1), ("topaz", 600, 1, 1)]}
    assert gd.resource_drop_table("copper_rocks") == [("copper_ore", 1, 1, 1), ("topaz", 600, 1, 1)]


def test_resource_drop_table_unknown_is_empty():
    assert GameData().resource_drop_table("nope") == []
