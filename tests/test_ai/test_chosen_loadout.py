"""The chosen consumable loadout as data, and the stock carried for it
(`docs/PLAN_consumable_utility.md` increment 5)."""

from artifactsmmo_cli.ai.chosen_loadout import (
    CARRY_HORIZON_FIGHTS,
    ChosenLoadout,
    food_carry,
    food_room,
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


def test_a_food_carry_is_the_horizon_when_the_bag_and_the_stock_allow() -> None:
    # (a) one recovery's use × the horizon.
    assert food_carry(2, 1000, None) == 40
    assert food_carry(7, 1000, 500) == 140


def test_a_food_carry_is_capped_by_the_bags_room() -> None:
    """Task 8c ruling C2-food (b): seven a fight asks 140, a bag with room for
    90 carries 90."""
    assert food_carry(7, 90, None) == 90
    assert food_carry(7, 0, None) == 0


def test_a_food_carry_from_held_stock_is_capped_by_the_stock() -> None:
    """(c): priced from held stock, the carry is no more than is held; with no
    stock bound (units past the held ones are made), the room decides."""
    assert food_carry(7, 90, 30) == 30
    assert food_carry(7, 90, 0) == 0
    assert food_carry(1, 90, 30) == 20


def test_the_food_room_is_the_slot_and_quantity_model() -> None:
    """(b) is read off `inventory_room.has_room`: a held stack grows on
    quantity alone, a new stack needs a free slot, and a bag with no room for
    it keeps only the units it holds."""
    assert food_room(10, 0, 25) == 35      # held stack, no slot free: it grows
    assert food_room(0, 1, 25) == 25       # a new stack takes the free slot
    assert food_room(0, 0, 25) == 0        # a new stack with no slot
    assert food_room(10, 3, -4) == 10      # past the cap: only what is held


def test_codes() -> None:
    pick = ChosenLoadout("wolf", (("small_health_potion", 3), ("earth_boost_potion", 1)),
                         (("cooked_chicken", 2),), (("cooked_chicken", 2),))
    assert pick.potion_codes() == frozenset({"small_health_potion", "earth_boost_potion"})
    assert pick.food_codes() == frozenset({"cooked_chicken"})
    assert ChosenLoadout("wolf", (), (), ()).potion_codes() == frozenset()
