"""potion_stock_target_pure: the ONE target both the CRAFT_POTIONS guard and
CraftPotionsGoal size themselves from.

Before this core existed the two disagreed: the guard fired on the bare level
ramp (`potion_baseline_pure`) while the goal targeted
`min(max(level_baseline, monster_demand), stack)`. So the guard could fire with
nothing for the goal to do, and the ramp acted as a FLOOR -- which is why a
level-45 bot pursued 100 potions whether or not it ever drank one.

Here the ramp is the CAP on speculation and projected combat consumption is the
driver, per the 2026-07-19 design decisions in
docs/PLAN_potion_combat_justification.md.
"""

from artifactsmmo_cli.ai.potion_stock_target import potion_stock_target_pure
from artifactsmmo_cli.ai.thresholds import POTION_LEAD_FIGHTS


def test_no_projected_consumption_targets_zero():
    """The whole point: a bot that never needs healing stocks nothing, however
    high its level ramp. This is the case that had it gathering potion mats at
    full HP."""
    assert potion_stock_target_pure(hp_need_per_fight=0, potion_restore=50,
                                    level_baseline=100) == 0


def test_demand_covers_the_lead_time_window():
    """Speculative by design (decision 1): stock for POTION_LEAD_FIGHTS fights
    ahead, not just the next one, because crafting has lead time."""
    # 10 HP needed per fight, potions restore 50 -> 10*10/50 = 2 potions.
    assert POTION_LEAD_FIGHTS == 10
    assert potion_stock_target_pure(hp_need_per_fight=10, potion_restore=50,
                                    level_baseline=100) == 2


def test_demand_ceils_partial_potions():
    """A partial potion is no potion -- round UP or the bot is short mid-fight."""
    # 11*10 = 110 HP over the window, /50 = 2.2 -> 3.
    assert potion_stock_target_pure(hp_need_per_fight=11, potion_restore=50,
                                    level_baseline=100) == 3


def test_level_ramp_is_a_cap_not_a_floor():
    """The ramp bounds speculation; it does NOT raise a small demand up to itself.
    Inverting this is the over-stocking bug."""
    # Demand 10*10/50 = 2, ramp 100 -> capped at demand, NOT lifted to 100.
    assert potion_stock_target_pure(hp_need_per_fight=10, potion_restore=50,
                                    level_baseline=100) == 2
    # Demand 200*10/50 = 40, ramp 5 -> capped DOWN to the ramp.
    assert potion_stock_target_pure(hp_need_per_fight=200, potion_restore=50,
                                    level_baseline=5) == 5


def test_zero_restore_targets_zero():
    """Guard against divide-by-zero on an item with no hp_restore: a potion that
    heals nothing can never satisfy demand, so it is not a stocking target."""
    assert potion_stock_target_pure(hp_need_per_fight=50, potion_restore=0,
                                    level_baseline=100) == 0


def test_negative_inputs_clamp_to_zero():
    """Learned stats are medians over rows and must never drive a negative
    target; clamp rather than trusting the caller."""
    assert potion_stock_target_pure(hp_need_per_fight=-5, potion_restore=50,
                                    level_baseline=100) == 0
    assert potion_stock_target_pure(hp_need_per_fight=10, potion_restore=50,
                                    level_baseline=-1) == 0


def test_target_never_exceeds_the_cap():
    """Sweep: the cap holds for every shape, so the goal can never be handed a
    target the ramp forbids."""
    for hp_need in range(0, 60, 7):
        for restore in (1, 10, 50, 200):
            for cap in (0, 5, 37, 100):
                out = potion_stock_target_pure(hp_need_per_fight=hp_need,
                                               potion_restore=restore,
                                               level_baseline=cap)
                assert 0 <= out <= cap
