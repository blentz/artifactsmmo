from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.potion_supply import (
    _cheapest_heal_potion,
    _recipe_producible,
    bootstrap_potion_target,
)
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


def _gd_sunflower_only() -> GameData:
    """sunflower is gatherable; nothing else is obtainable (not in drops, not NPC-bought)."""
    gd = GameData()
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._npc_stock = {}
    return gd


def test_recipe_not_producible_when_one_ingredient_unobtainable():
    # recipe {gatherable_mat:1, unobtainable_mat:1}: old any() said True, new all() says False
    gd = _gd_sunflower_only()
    state = make_state(level=10)
    assert _recipe_producible({"sunflower": 1, "rare_crystal": 1}, state, gd) is False


def test_recipe_producible_when_all_ingredients_obtainable():
    gd = _gd_sunflower_only()
    state = make_state(level=10)
    assert _recipe_producible({"sunflower": 3}, state, gd) is True
