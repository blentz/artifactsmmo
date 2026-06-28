"""strategic_value's combat_raw equals the shared combat_raw primitive."""

from artifactsmmo_cli.ai.gear_value import combat_raw_of
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.tiers.strategic_value import (
    STRATEGIC_SCALE,
    _combat_raw_of_stats,
    strategic_value,
)


def test_strategic_value_uses_shared_combat_raw():
    s = ItemStats(code="x", level=1, type_="weapon", attack={"fire": 6},
                  critical_strike=20, hp_bonus=10, dmg=3, lifesteal=2)
    assert _combat_raw_of_stats(s) == combat_raw_of(s)


def test_strategic_value_combat_part_uses_shared_primitive():
    """The combat slice of strategic_value equals combat_raw_of × combat_weight,
    proving the wrapper routes its combat signal through the one shared atom."""
    s = ItemStats(
        code="kitchen_sink", level=1, type_="weapon",
        attack={"fire": 2, "air": 3}, resistance={"earth": 4}, hp_restore=5,
        hp_bonus=6, dmg=7, critical_strike=8, lifesteal=9, combat_buff=10,
    )
    assert strategic_value(s) == combat_raw_of(s) * STRATEGIC_SCALE
