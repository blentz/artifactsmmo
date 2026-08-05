"""strategic_value's combat input IS the one gear ruler's own COMBAT term.

The retired guarantee was weaker: the economics layer merely SHARED a
`combat_raw` atom with the ruler, which only meant the two read the same stats.
It is now one of the two terms the ruler is the SUM of, so the two layers cannot
reach different verdicts about the same piece at all.
"""

from artifactsmmo_cli.ai.gear_value import gear_components, gear_value
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.tiers.strategic_value import (
    STRATEGIC_SCALE,
    _combat_of_stats,
    strategic_value,
)

KITCHEN_SINK = ItemStats(
    code="kitchen_sink", level=1, type_="amulet",
    resistance={"earth": 4}, hp_restore=5, hp_bonus=6, dmg=7,
    critical_strike=8, lifesteal=9, combat_buff=10,
    wisdom=11, prospecting=12, inventory_space=13, haste=14,
)
WEAPON = ItemStats(code="wpn", level=1, type_="weapon", attack={"fire": 6},
                   critical_strike=20)


def test_strategic_value_combat_input_is_the_rulers_own_term():
    assert _combat_of_stats(KITCHEN_SINK) == gear_components(KITCHEN_SINK, Rank)[0]
    assert _combat_of_stats(WEAPON) == gear_components(WEAPON, Rank)[0]


def test_combat_input_plus_efficiency_term_reconstruct_the_ruler():
    """THE PARTITION (Lean: `GearValue.rankValue_decomp`). Nothing the ruler
    scores is dropped from the economics layer's view, and nothing is counted
    twice — the two terms sum back to the ruler exactly."""
    for stats in (KITCHEN_SINK, WEAPON):
        combat, efficiency = gear_components(stats, Rank)
        assert combat + efficiency == gear_value(stats, Rank)


def test_combat_input_cannot_contain_a_utility_stat():
    """`armor_score_combat_pure` takes no wisdom / prospecting / inventory_space
    / haste parameter, so adding them to an item cannot move the combat term.
    This is the mechanical no-double-count guarantee."""
    bare = ItemStats(code="bare", level=1, type_="amulet", hp_bonus=20)
    plus_utility = ItemStats(code="plus", level=1, type_="amulet", hp_bonus=20,
                             wisdom=50, prospecting=50, inventory_space=50, haste=50)
    assert _combat_of_stats(bare) == _combat_of_stats(plus_utility)
    # ...and the utility IS visible, once, through the efficiency term.
    assert gear_components(plus_utility, Rank)[1] > gear_components(bare, Rank)[1]


def test_strategic_value_combat_part_uses_the_shared_term():
    """The combat slice of strategic_value equals the ruler's combat term ×
    combat_weight; a weapon carries no efficiency term at all, so its default
    strategic value is exactly that product."""
    combat, efficiency = gear_components(WEAPON, Rank)
    assert efficiency == 0
    assert strategic_value(WEAPON) == combat * STRATEGIC_SCALE
