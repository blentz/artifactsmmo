"""Tests for skill_grind_target: the shallow in-skill item to craft now."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
        "wooden_staff": ItemStats(code="wooden_staff", level=3, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=3),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "iron_dagger": {"iron_bar": 6},
        "wooden_staff": {"ash_plank": 4},
    }
    # The recipe leaves are gatherable resource drops, so every item is
    # obtainable (the obtainability filter only excludes un-gettable chains).
    gd._resource_drops = {"copper_rocks": "copper_bar", "iron_rocks": "iron_bar",
                          "ash_tree": "ash_plank"}
    return gd


def test_picks_highest_craftable_at_current_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3})
    assert skill_grind_target("weaponcrafting", state, gd) == "wooden_staff"


def test_prefers_materials_in_hand_over_higher_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3},
                       inventory={"copper_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_counts_bank_toward_materials_in_hand():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3},
                       bank_items={"copper_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_none_when_nothing_craftable_at_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 0})
    assert skill_grind_target("weaponcrafting", state, gd) is None


def test_none_for_skill_with_no_recipes():
    gd = _gd()
    state = make_state(skills={"alchemy": 5})
    assert skill_grind_target("alchemy", state, gd) is None


def test_in_skill_item_without_recipe_is_skipped():
    # copper_axe matches the skill and level but has no crafting recipe entry,
    # so it is skipped; the highest item with a recipe wins instead.
    gd = _gd()
    gd._item_stats["copper_axe"] = ItemStats(
        code="copper_axe", level=3, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=3)
    state = make_state(skills={"weaponcrafting": 3})
    assert skill_grind_target("weaponcrafting", state, gd) == "wooden_staff"


def test_reserved_materials_exclude_recipe():
    """Trace 2026-06-11 19:22: the grind picked copper_helmet (6 copper_bar)
    while the committed copper_legs_armor held exactly 5 bars — the grind
    must not consume the committed objective's recipe inputs."""
    gd = _gd()
    # copper_dagger eats copper_bar; with copper_bar reserved, wooden_staff
    # (ash_plank) must win even though dagger has fewer mats missing.
    state = make_state(skills={"weaponcrafting": 3},
                       inventory={"copper_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"
    assert skill_grind_target(
        "weaponcrafting", state, gd, reserved=frozenset({"copper_bar"}),
    ) == "wooden_staff"


def test_reserved_can_exhaust_all_recipes():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 10})
    assert skill_grind_target(
        "weaponcrafting", state, gd,
        reserved=frozenset({"copper_bar", "iron_bar", "ash_plank"}),
    ) is None


def _gd_obtainability() -> GameData:
    """copper_dagger is obtainable (copper_bar <- copper_ore, a gatherable
    resource drop); wooden_staff is NOT (needs wooden_stick, which has no recipe
    and no resource drop / dropper) — the live weaponcrafting bug."""
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "wooden_staff": ItemStats(code="wooden_staff", level=1, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 10},
        "wooden_staff": {"wooden_stick": 1, "ash_wood": 4},
    }
    # copper_ore + ash_wood are gatherable resource drops; wooden_stick is NOT.
    gd._resource_drops = {"copper_rocks": "copper_ore", "ash_tree": "ash_wood"}
    return gd


def test_skips_unobtainable_inskill_item_for_obtainable_one():
    """weaponcrafting grind must pick the OBTAINABLE copper_dagger, NOT
    wooden_staff (needs un-gettable wooden_stick) — even though wooden_staff has
    ash_wood on hand (fewer missing mats) and would win the old tie-break."""
    gd = _gd_obtainability()
    # ash_wood on hand makes wooden_staff "fewer missing" under the old ranking.
    state = make_state(skills={"weaponcrafting": 1, "mining": 1},
                       inventory={"ash_wood": 4, "wooden_stick": 0})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_cyclic_recipe_is_not_obtainable():
    """A recipe cycle (a <- b, b <- a) bottoms out in no gatherable leaf, so the
    item is NOT obtainable and the grind returns None (exercises the _obtainable
    cycle guard)."""
    gd = GameData()
    gd._item_stats = {
        "cyc_a": ItemStats(code="cyc_a", level=1, type_="weapon",
                           crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"cyc_a": {"cyc_b": 1}, "cyc_b": {"cyc_a": 1}}
    state = make_state(skills={"weaponcrafting": 1})
    assert skill_grind_target("weaponcrafting", state, gd) is None
