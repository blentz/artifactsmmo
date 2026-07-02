from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {"copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                              crafting_skill="mining", crafting_level=1),
                      "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource")}
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    return gd


def test_intermediate_rebatched_to_demand():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    # demand 6 bars, ample inventory -> batched to 6 (< BATCH_CAP)
    state = make_state(inventory={"copper_ore": 100}, inventory_max=200)
    out = size_intermediate_craft(a, {"copper_bar": 6}, state, gd)
    assert out.quantity == 6


def test_intermediate_subtracts_held():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    state = make_state(inventory={"copper_bar": 2, "copper_ore": 100}, inventory_max=200)
    out = size_intermediate_craft(a, {"copper_bar": 6}, state, gd)
    assert out.quantity == 4   # 6 demand - 2 held


def test_intermediate_absent_from_chain_unchanged():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    out = size_intermediate_craft(a, {}, make_state(), gd)
    assert out.quantity == 1   # no demand -> floors at 1, action returned as-is


def test_size_intermediate_threads_craft_yields():
    # copper_bar <- copper_ore x10; drops copper_rocks->copper_ore (held_recipe=0).
    # inventory_max=18, empty -> usable = 18 - _MIN_FREE_SLOTS(3) = 15; chain demand = 10.
    #   yield 1 (default):        mats_per_unit = ceil(10/1) = 10 -> fit = 15//10 = 1 -> batch = 1
    #   yield 2 ({copper_bar:2}): mats_per_unit = ceil(10/2) = 5  -> fit = 15//5  = 3 -> batch = min(10,3,10) = 3
    # The yield-2 result (3) differs from the yield-agnostic result (1), proving
    # size_intermediate_craft threads game_data.craft_yields into the fit.
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    state = make_state(inventory={}, inventory_max=18)

    gd_y1 = _gd()  # craft_yields empty -> all Y=1
    out_y1 = size_intermediate_craft(a, {"copper_bar": 10}, state, gd_y1)
    assert out_y1.quantity == 1

    gd_y2 = _gd()
    gd_y2._craft_yields = {"copper_bar": 2}
    out_y2 = size_intermediate_craft(a, {"copper_bar": 10}, state, gd_y2)
    assert out_y2.quantity == 3


def _gd_gem_chain() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        "gem_ring": {"gem_setting": 2},
        "gem_setting": {"gem_bar": 3},
        "gem_bar": {"gem_ore": 4},
    }
    gd._resource_drops = {}
    gd._craft_yields = {}
    return gd


def test_deep_chain_three_level_interleave_safety() -> None:
    """3-level chain: gem_ring <- gem_setting x2 <- gem_bar x3 <- gem_ore x4.

    Verifies each intermediate is sized to its own raw-leaf footprint and that
    each batch's raw footprint fits the usable inventory space
    (interleave-safety invariant).

    closure_demand("gem_ring", 1) gives:
      gem_ring:1, gem_setting:2, gem_bar:6, gem_ore:24

    With inventory_free=50 and no drops (held_recipe=0):
      usable = 50 - _MIN_FREE_SLOTS(3) = 47

    gem_bar:     mats_per_unit=4,  demand=6,  fit=47//4=11,  batch=min(6,11,10)=6
    gem_setting: mats_per_unit=12, demand=2,  fit=47//12=3,  batch=min(2,3,10)=2

    Interleave-safety: 6*4=24<=47 and 2*12=24<=47
    """
    gd = _gd_gem_chain()
    chain: dict[str, int] = {}
    closure_demand("gem_ring", 1, gd, chain, frozenset())
    assert chain == {"gem_ring": 1, "gem_setting": 2, "gem_bar": 6, "gem_ore": 24}

    # Ample inventory space: 50 slots, no items held, no resource drops
    state = make_state(inventory={}, inventory_max=50)
    usable = state.inventory_free - 3  # _MIN_FREE_SLOTS = 3

    # gem_bar: demand=6, mats_per_unit=4 (gem_ore x4)
    a_bar = CraftAction(code="gem_bar", quantity=1, workshop_location=(0, 0))
    out_bar = size_intermediate_craft(a_bar, chain, state, gd)
    assert out_bar.quantity == 6
    # interleave-safety: 6 * 4 = 24 <= 47
    assert out_bar.quantity * 4 <= usable

    # gem_setting: demand=2, mats_per_unit=12 (gem_bar x3 -> gem_ore x12)
    a_setting = CraftAction(code="gem_setting", quantity=1, workshop_location=(0, 0))
    out_setting = size_intermediate_craft(a_setting, chain, state, gd)
    assert out_setting.quantity == 2
    # interleave-safety: 2 * 12 = 24 <= 47
    assert out_setting.quantity * 12 <= usable


def test_deep_chain_tight_inventory_exercises_fit_clamp() -> None:
    """Tight inventory forces fit < demand on every intermediate (non-vacuous).

    Same gem chain: gem_ring <- gem_setting x2 <- gem_bar x3 <- gem_ore x4.
    closure_demand gives: gem_setting=2, gem_bar=6.

    With inventory_max=15, empty inventory:
      inventory_free = 15, usable = 15 - _MIN_FREE_SLOTS(3) = 12

    gem_bar:     mats_per_unit=4,  demand=6,  fit=12//4=3  < demand → batch=3  (FIT-CLAMPED)
    gem_setting: mats_per_unit=12, demand=2,  fit=12//12=1 < demand → batch=1  (FIT-CLAMPED)

    Interleave-safety: 3*4=12<=12 and 1*12=12<=12 (tight — equality holds).

    Discriminates raw-leaf recursion: a buggy direct footprint for gem_setting
    of 3 (gem_bar qty only) would give fit=12//3=4 → batch=min(2,4)=2 ≠ 1,
    so the == 1 assertion proves _raw_units descended to gem_ore.
    """
    gd = _gd_gem_chain()
    chain: dict[str, int] = {}
    closure_demand("gem_ring", 1, gd, chain, frozenset())

    # Tight inventory: 15 slots, no items held, no resource drops
    state = make_state(inventory={}, inventory_max=15)
    usable = state.inventory_free - 3  # _MIN_FREE_SLOTS = 3
    assert usable == 12

    # gem_bar: demand=6, fit=12//4=3 < 6 → FIT-CLAMPED to 3
    a_bar = CraftAction(code="gem_bar", quantity=1, workshop_location=(0, 0))
    out_bar = size_intermediate_craft(a_bar, chain, state, gd)
    assert out_bar.quantity == 3
    assert out_bar.quantity * 4 <= usable  # interleave-safety: 3*4=12<=12

    # gem_setting: demand=2, fit=12//12=1 < 2 → FIT-CLAMPED to 1
    # Also proves raw-leaf recursion: direct footprint 3 would give fit=4 → batch=2 ≠ 1
    a_setting = CraftAction(code="gem_setting", quantity=1, workshop_location=(0, 0))
    out_setting = size_intermediate_craft(a_setting, chain, state, gd)
    assert out_setting.quantity == 1
    assert out_setting.quantity * 12 <= usable  # interleave-safety: 1*12=12<=12
