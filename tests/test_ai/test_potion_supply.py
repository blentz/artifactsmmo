from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.potion_supply import (
    _cheapest_heal_potion,
    bootstrap_potion_target,
    feasible_runs,
)
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
