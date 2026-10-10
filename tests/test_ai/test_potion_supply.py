"""Tests for `ai/potion_supply.py`: the heal-target rankers, the walk's
`feasible_runs`, and the CRAFT_POTIONS batch over the CHOSEN loadout
(`potion_batch`, `craft_potions_fires`, `guard_loadout`;
docs/PLAN_consumable_utility.md increment 5)."""

import dataclasses

from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout, potion_carry
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.potion_supply import (
    _cheapest_heal_potion,
    bootstrap_potion_target,
    craft_potions_fires,
    feasible_runs,
    guard_loadout,
    potion_batch,
    potion_level_ramp,
    target_potion_pure,
)
from artifactsmmo_cli.ai.thresholds import POTION_GATHER_BATCH, UTILITY_SLOT_MAX_STACK
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """small (alchemy 5) and enhanced (alchemy 45) heal potions, both craftable."""
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(code="small_health_potion", level=5,
            type_="utility", hp_restore=50, crafting_skill="alchemy", crafting_level=5),
        "enhanced_health_potion": ItemStats(code="enhanced_health_potion", level=45,
            type_="utility", hp_restore=300, crafting_skill="alchemy", crafting_level=45),
    }
    gd._crafting_recipes = {
        "small_health_potion": {"sunflower": 3},
        "enhanced_health_potion": {"sunflower": 3},
    }
    return gd


def test_cheapest_heal_potion_is_lowest_crafting_level():
    assert _cheapest_heal_potion(_gd()) == "small_health_potion"


def test_cheapest_heal_potion_none_when_no_heal():
    gd = GameData()
    gd._item_stats = {"copper_ore": ItemStats(code="copper_ore", level=1, type_="resource")}
    gd._crafting_recipes = {"copper_ore": {}}
    assert _cheapest_heal_potion(gd) is None


def test_cheapest_heal_potion_skips_zero_effect_utility():
    # A craftable utility item that carries NO heal effect (hp_restore == 0) is
    # skipped by the effect guard, so it is never chosen as the cheapest heal.
    gd = GameData()
    gd._item_stats = {
        "fire_boost_potion": ItemStats(code="fire_boost_potion", level=1,
            type_="utility", hp_restore=0, crafting_skill="alchemy", crafting_level=10),
    }
    gd._crafting_recipes = {"fire_boost_potion": {"sunflower": 1}}
    assert _cheapest_heal_potion(gd) is None


def test_bootstrap_target_prefers_craftable_now():
    # alchemy 16: small craftable now, enhanced not -> small.
    gd = _gd()
    state = make_state(level=10, skills={**make_state().skills, "alchemy": 16})
    assert bootstrap_potion_target(state, gd) == "small_health_potion"


def test_bootstrap_target_falls_back_to_cheapest_when_none_craftable():
    # alchemy 1: nothing craftable now -> cheapest-to-unlock (small).
    gd = _gd()
    state = make_state(level=3, skills={**make_state().skills, "alchemy": 1})
    assert bootstrap_potion_target(state, gd) == "small_health_potion"


def test_bootstrap_target_climbs_with_skill():
    # alchemy 45: enhanced now craftable and higher-restore -> enhanced.
    gd = _gd()
    state = make_state(level=45, skills={**make_state().skills, "alchemy": 45})
    assert bootstrap_potion_target(state, gd) == "enhanced_health_potion"


def _gd_brew(**recipe: int) -> GameData:
    """`brew` (alchemy 1) from `recipe`. `sunflower` is gathered at a field that
    spawns; `slimeball` drops only from `slime`; `rare_crystal` has no source."""
    gd = GameData()
    gd._item_stats = {
        "brew": ItemStats(code="brew", level=1, type_="utility", hp_restore=30,
                          crafting_skill="alchemy", crafting_level=1),
        **{code: ItemStats(code=code, level=1, type_="resource")
           for code in ("sunflower", "slimeball", "rare_crystal")},
    }
    gd._crafting_recipes = {"brew": dict(recipe)}
    gd._workshop_locations = {"alchemy": (3, 0)}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_locations = {"sunflower_field": [(2, 0)]}
    gd._monster_level = {"slime": 1}
    gd._monster_drops = {"slime": [("slimeball", 1, 1, 1)]}
    gd._monster_locations = {"slime": [(1, 1)]}
    fill_monster_stat_defaults(gd)
    return gd


def test_no_run_when_one_ingredient_has_no_source():
    gd = _gd_brew(sunflower=1, rare_crystal=1)
    assert feasible_runs("brew", 5, make_state(level=10), gd) == 0


def test_a_gathered_ingredient_supplies_every_run():
    assert feasible_runs("brew", 5, make_state(level=10), _gd_brew(sunflower=3)) == 5


def test_held_stock_bounds_the_runs_and_a_drop_does_not_count():
    """Robby's shape (2026-09-27): one banked slimeball, whose only other
    source is a drop the potion ladder cannot fight for. One run can be
    supplied, not five."""
    gd = _gd_brew(sunflower=1, slimeball=1)
    state = make_state(level=10, attack={"fire": 50}, bank_items={"slimeball": 1})
    assert feasible_runs("brew", 5, state, gd) == 1
    assert feasible_runs("brew", 5, make_state(level=10, attack={"fire": 50}), gd) == 0


def test_an_item_with_no_recipe_has_no_run():
    gd = _gd_brew(sunflower=1)
    assert feasible_runs("sunflower", 3, make_state(level=10), gd) == 0


def test_a_run_makes_the_recipe_yield():
    """`brew` yields 2 a run: two more runs need two slimeballs, and one is
    banked, so one run can be supplied."""
    gd = _gd_brew(sunflower=1, slimeball=1)
    gd._craft_yields = {"brew": 2}
    state = make_state(level=10, attack={"fire": 50}, bank_items={"slimeball": 1})
    assert feasible_runs("brew", 2, state, gd) == 1


def test_a_banked_potion_is_no_run():
    """A run is a craft: five banked brews do not supply one when the recipe
    cannot be had."""
    gd = _gd_brew(rare_crystal=1)
    assert feasible_runs("brew", 3, make_state(level=10, bank_items={"brew": 5}), gd) == 0


# ── target_potion_pure: the effect-best heal craftable now ──────────────────

def _gd_heals() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(code="small_health_potion", level=1, type_="utility",
                                         hp_restore=30, crafting_skill="alchemy", crafting_level=1),
        "cooked_fish": ItemStats(code="cooked_fish", level=1, type_="consumable",
                                 hp_restore=50, crafting_skill="cooking", crafting_level=1),
    }
    gd._crafting_recipes = {"small_health_potion": {"sunflower": 1},
                            "cooked_fish": {"raw_fish": 1}}
    return gd


def _add_heal(gd: GameData, code: str, restore: int, skill: str | None, level: int = 1) -> None:
    gd._item_stats[code] = ItemStats(code=code, level=1, type_="utility", hp_restore=restore,
                                     crafting_skill=skill, crafting_level=level)
    gd._crafting_recipes[code] = {"sunflower": 1}


def test_target_potion_is_the_utility_heal_not_the_food():
    """`cooked_fish` restores more but is not utility-slot equippable."""
    assert target_potion_pure(make_state(), _gd_heals()) == "small_health_potion"


def test_target_potion_none_when_its_skill_gate_is_unmet():
    gd = _gd_heals()
    gd._item_stats["small_health_potion"] = dataclasses.replace(
        gd._item_stats["small_health_potion"], crafting_level=10)
    assert target_potion_pure(make_state(skills={"alchemy": 1}), gd) is None


def test_target_potion_reads_each_items_own_crafting_skill():
    """A cooking-crafted utility heal with a higher restore wins when ITS skill
    gate is met, and is skipped when it is not; one with no crafting skill is
    never chosen."""
    gd = _gd_heals()
    _add_heal(gd, "cook_potion", 99, "cooking", level=1)
    _add_heal(gd, "skilless_potion", 120, None)
    assert target_potion_pure(make_state(), gd) == "cook_potion"
    _add_heal(gd, "cook_potion", 99, "cooking", level=10)
    assert target_potion_pure(make_state(skills={"cooking": 1, "alchemy": 1}), gd) == "small_health_potion"


def test_target_potion_highest_restore_then_smallest_code():
    gd = _gd_heals()
    _add_heal(gd, "aaa_potion", 30, "alchemy")
    assert target_potion_pure(make_state(), gd) == "aaa_potion"
    _add_heal(gd, "big_potion", 80, "alchemy")
    assert target_potion_pure(make_state(), gd) == "big_potion"


def test_target_potion_excludes_the_named_code():
    """The second-utility-slot caller excludes slot 1's pick to get the
    catalog's second-best heal."""
    gd = _gd_heals()
    _add_heal(gd, "big_potion", 80, "alchemy")
    assert target_potion_pure(make_state(), gd, exclude="big_potion") == "small_health_potion"


# ── potion_batch: the chosen loadout's potions, to their carry ──────────────

_MONSTER = "wolf"


def _gd_batch() -> GameData:
    """Three alchemy potions: `heal` and `boost` brew from a gatherable
    sunflower, `walled` from a crystal nothing supplies."""
    gd = _gd_brew(sunflower=1)
    gd._item_stats["boost"] = ItemStats(code="boost", level=1, type_="utility",
                                        dmg_elements={"fire": 10},
                                        crafting_skill="alchemy", crafting_level=1)
    gd._item_stats["walled"] = ItemStats(code="walled", level=1, type_="utility", hp_restore=80,
                                         crafting_skill="alchemy", crafting_level=1)
    gd._crafting_recipes = {"brew": {"sunflower": 1}, "boost": {"sunflower": 1},
                            "walled": {"rare_crystal": 1}}
    return gd


def _loadout(*potions: tuple[str, int]) -> ChosenLoadout:
    return ChosenLoadout(monster=_MONSTER, potions=tuple(potions), food=())


def _worn(code: str, qty: int, **kw):  # type: ignore[no-untyped-def]
    base = make_state(level=10, **kw)
    return dataclasses.replace(base, equipment={**base.equipment, "utility1_slot": code},
                               utility1_slot_quantity=qty)


def test_carry_is_one_fights_use_times_the_horizon_capped_at_a_slot():
    assert potion_carry(1) == 20
    assert potion_carry(3) == 60
    assert potion_carry(10) == UTILITY_SLOT_MAX_STACK


def test_no_loadout_stocks_nothing():
    """No fight ahead: nothing to stock for, however short the slots are."""
    state = make_state(level=10, inventory={"sunflower": 50})
    assert potion_batch(state, _gd_batch(), None) is None
    assert craft_potions_fires(state, _gd_batch(), None) is False


def test_a_potion_at_its_carry_passes_to_the_next_chosen_potion():
    """`brew` (1 a fight) is worn at its carry of 20, so the batch is the
    second chosen potion, `boost`: the bag's sunflowers craft its whole carry."""
    state = _worn("brew", 20, inventory={"sunflower": 50})
    assert potion_batch(state, _gd_batch(), _loadout(("brew", 1), ("boost", 1))) == ("boost", 20, 20)


def test_the_first_chosen_potion_short_of_its_carry_is_the_batch():
    """Both chosen potions are short; the chooser's order decides."""
    state = _worn("brew", 15, inventory={"sunflower": 50})
    assert potion_batch(state, _gd_batch(), _loadout(("brew", 1), ("boost", 1))) == ("brew", 5, 5)


def test_a_potion_nothing_can_supply_is_skipped_for_the_next():
    """`walled` is chosen first, short, not held and not craftable: the batch
    is `brew`."""
    state = make_state(level=10, inventory={"sunflower": 50})
    assert potion_batch(state, _gd_batch(), _loadout(("walled", 1), ("brew", 1))) == ("brew", 20, 20)


def test_nothing_to_stock_when_no_chosen_potion_can_be_supplied():
    state = make_state(level=10)
    assert potion_batch(state, _gd_batch(), _loadout(("walled", 1))) is None
    assert craft_potions_fires(state, _gd_batch(), _loadout(("walled", 1))) is False


def test_held_potions_cover_the_deficit_with_no_craft():
    """Bag and bank copies are free stock: 5 in the bag and 15 in the bank
    equip the whole carry of 20 and nothing is brewed."""
    state = make_state(level=10, inventory={"brew": 5, "sunflower": 50}, bank_items={"brew": 15})
    assert potion_batch(state, _gd_batch(), _loadout(("brew", 1))) == ("brew", 0, 20)


def test_held_potions_exactly_meeting_the_deficit_need_no_run():
    """The boundary: held == deficit. Nothing more is crafted, though the bag's
    sunflowers could brew more."""
    state = _worn("brew", 12, inventory={"brew": 8, "sunflower": 50})
    assert potion_batch(state, _gd_batch(), _loadout(("brew", 1))) == ("brew", 0, 8)


def test_a_walled_potion_held_in_the_bag_is_still_equipped():
    """Nothing can brew `walled`, but the bag's copies are stock: they equip."""
    state = make_state(level=10, inventory={"walled": 3})
    assert potion_batch(state, _gd_batch(), _loadout(("walled", 1))) == ("walled", 0, 3)


def test_partial_holding_plus_crafted_runs():
    """5 held, 15 short: the bag's sunflowers cover all 15 runs."""
    state = make_state(level=10, inventory={"brew": 5, "sunflower": 50})
    assert potion_batch(state, _gd_batch(), _loadout(("brew", 1))) == ("brew", 15, 20)


def test_a_gathered_batch_is_cut_to_the_gather_batch():
    """No ingredient held and none buyable: one gather batch of runs, and the
    equip is what those runs and the held copies reach."""
    state = make_state(level=10, inventory={"brew": 5})
    assert potion_batch(state, _gd_batch(), _loadout(("brew", 1))) == (
        "brew", POTION_GATHER_BATCH, 5 + POTION_GATHER_BATCH)


def test_runs_are_counted_in_the_recipes_yield():
    """`brew` yields 2 a run: 20 short is 10 runs."""
    gd = _gd_batch()
    gd._craft_yields = {"brew": 2}
    state = make_state(level=10, inventory={"sunflower": 50})
    assert potion_batch(state, gd, _loadout(("brew", 1))) == ("brew", 10, 20)


def test_craft_potions_fires_exactly_when_there_is_a_batch():
    state = make_state(level=10, inventory={"sunflower": 50})
    assert craft_potions_fires(state, _gd_batch(), _loadout(("brew", 1))) is True
    assert craft_potions_fires(_worn("brew", 20), _gd_batch(), _loadout(("brew", 1))) is False


# ── guard_loadout: only the loadout chosen against the fight ahead ─────────

def test_guard_loadout_is_the_chosen_one_for_the_fight_ahead():
    chosen = _loadout(("brew", 1))
    assert guard_loadout(chosen, _MONSTER) is chosen


def test_guard_loadout_none_without_a_loadout():
    assert guard_loadout(None, _MONSTER) is None


def test_guard_loadout_none_without_a_fight_ahead():
    assert guard_loadout(_loadout(("brew", 1)), None) is None


def test_guard_loadout_none_when_chosen_against_another_monster():
    """Live Lor 2026-10-06: potions brewed for a fight never fought."""
    assert guard_loadout(_loadout(("brew", 1)), "cow") is None


def test_potion_level_ramp_is_flat_then_linear_then_full():
    """The batch the consumable pricer amortizes over: 5 through level 5, 100
    from level 45, floored linear between (5 + 95*20//40 = 52 at level 25)."""
    assert potion_level_ramp(1) == 5
    assert potion_level_ramp(25) == 52
    assert potion_level_ramp(50) == UTILITY_SLOT_MAX_STACK
