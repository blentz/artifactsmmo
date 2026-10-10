"""The chosen consumable loadout as data, and the stock carried for it
(`docs/PLAN_consumable_utility.md` increment 5)."""

from artifactsmmo_cli.ai.chosen_loadout import (
    CARRY_HORIZON_FIGHTS,
    ChosenLoadout,
    food_carry,
    potion_carry,
)
from artifactsmmo_cli.ai.consumable_floor_core import REFILL_HORIZON_FIGHTS
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK


def test_the_carry_horizon_is_the_measured_mean_run() -> None:
    # 20.2 fights between bank visits (learning.db 2026-09-25..10-09), and one
    # carry is each character's banked share.
    assert CARRY_HORIZON_FIGHTS == 20 == REFILL_HORIZON_FIGHTS


def test_a_potion_carry_is_one_fights_use_over_the_horizon_capped_at_a_slot() -> None:
    assert potion_carry(0) == 0
    assert potion_carry(3) == 60
    assert potion_carry(5) == UTILITY_SLOT_MAX_STACK == 100
    assert potion_carry(7) == UTILITY_SLOT_MAX_STACK


def test_a_food_carry_is_uncapped() -> None:
    assert food_carry(2) == 40
    assert food_carry(7) == 140


def test_codes() -> None:
    pick = ChosenLoadout("wolf", (("small_health_potion", 3), ("earth_boost_potion", 1)),
                         (("cooked_chicken", 2),))
    assert pick.potion_codes() == frozenset({"small_health_potion", "earth_boost_potion"})
    assert pick.food_codes() == frozenset({"cooked_chicken"})
    assert ChosenLoadout("wolf", (), ()).potion_codes() == frozenset()
