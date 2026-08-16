"""The published Rest cooldown — one second per one percent missing, min three."""

from artifactsmmo_cli.ai.actions.cost_core import rest_cost_pure
from artifactsmmo_cli.ai.rest_cooldown_core import (
    REST_MINIMUM_SECONDS,
    rest_cooldown_seconds,
)


def test_one_second_per_percent_missing():
    """The rule itself, at a bar where percent and hit point coincide."""
    assert rest_cooldown_seconds(50, 100) == 50
    assert rest_cooldown_seconds(100, 100) == 100


def test_the_percentage_rounds_up():
    """Rounded UP, so a deficit of a fraction of a percent still costs a whole
    second. Truncating would make a long chain of small rests look free."""
    assert rest_cooldown_seconds(1, 1000) == REST_MINIMUM_SECONDS   # 0.1% -> 1, floored to 3
    assert rest_cooldown_seconds(41, 1000) == 5                     # 4.1% -> 5, not 4


def test_the_floor_binds_below_three_percent():
    """Every Rest costs at least three seconds however small the deficit. This is
    the only regime where BATCHING fights before resting genuinely saves time."""
    assert rest_cooldown_seconds(1, 1000) == REST_MINIMUM_SECONDS
    assert rest_cooldown_seconds(20, 1000) == REST_MINIMUM_SECONDS   # 2% -> 2, floored
    assert rest_cooldown_seconds(31, 1000) == 4                      # 3.1% -> 4, above it


def test_a_full_bar_is_the_ceiling():
    """A Rest restores at most everything, so it can never cost more than a
    hundred seconds — even asked about a whole CHAIN of fights whose total damage
    exceeds one bar, which is exactly how `fight_loop_cost` calls it."""
    assert rest_cooldown_seconds(999, 100) == 100
    assert rest_cooldown_seconds(100, 100) == 100


def test_no_deficit_still_pays_the_floor():
    """Resting at full HP is a wasted action, not a free one."""
    assert rest_cooldown_seconds(0, 100) == REST_MINIMUM_SECONDS
    assert rest_cooldown_seconds(-5, 100) == REST_MINIMUM_SECONDS


def test_the_planner_edge_cost_is_this_formula_unscaled():
    """`rest_cost_pure` must not restate the rule and must not rescale it: the
    planner's edge cost IS this cooldown in seconds. It used to divide by a
    self-declared ten-second unit no other action used, which is how a 100-second
    recovery came to be priced below a single fight."""
    for hp, max_hp in ((0, 100), (50, 100), (99, 100), (137, 280), (280, 280)):
        assert rest_cost_pure(hp, max_hp) == float(
            rest_cooldown_seconds(max_hp - hp, max_hp))
