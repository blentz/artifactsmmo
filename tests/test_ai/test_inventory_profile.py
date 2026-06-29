"""Tests for the per-goal inventory profile (soft targets) + the space-driven
overstock core.

The profile is the recipe-closure quantity map of what the ACTIVE goal/
objective-step wants on hand. `overstock_excess` is the pure space-driven
overstock decision: an item is overstock only when held exceeds
max(profile_target, useful_floor) AND the bag is under real space pressure.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_caps import (
    DISCARD_WATERMARK,
    overstock_excess,
)
from artifactsmmo_cli.ai.inventory_profile import inventory_profile
from tests.test_ai.fixtures import make_state


class TestOverstockExcessCore:
    """Pure space-driven overstock function (exact integer domain).

    overstock_excess(held, profile_target, useful_floor, used, cap,
    watermark_num, watermark_den) returns held - max(profile_target,
    useful_floor) when held exceeds that floor AND
    used/cap >= watermark_num/watermark_den (cross-multiplied); else 0.
    Watermark defaults to 17/20 (0.85).
    """

    def test_below_watermark_never_overstock(self):
        # Free slots (low pressure: 1/20 = 5% < 85%) → nothing overstock.
        assert overstock_excess(100, profile_target=0, useful_floor=0,
                                used=1, cap=20) == 0

    def test_at_or_below_profile_target_never_overstock(self):
        # held <= profile_target → never overstock, regardless of pressure.
        assert overstock_excess(10, profile_target=10, useful_floor=0,
                                used=20, cap=20) == 0
        assert overstock_excess(5, profile_target=10, useful_floor=0,
                                used=20, cap=20) == 0

    def test_over_floor_under_pressure_is_excess(self):
        # held 30 > max(target 10, floor 5) = 10, pressure 18/20=90% → excess 20.
        assert overstock_excess(30, profile_target=10, useful_floor=5,
                                used=18, cap=20) == 20

    def test_useful_floor_binds_when_higher_than_profile(self):
        # useful_floor 12 > profile 3 → floor is 12 → excess 8.
        assert overstock_excess(20, profile_target=3, useful_floor=12,
                                used=20, cap=20) == 8

    def test_profile_floor_binds_when_higher_than_useful(self):
        # profile 25 > useful_floor 5 → floor is 25 → 20 held not overstock.
        assert overstock_excess(20, profile_target=25, useful_floor=5,
                                used=20, cap=20) == 0

    def test_exactly_at_watermark_is_pressure(self):
        # used/cap == watermark (17/20) counts as pressure (>=).
        assert overstock_excess(10, profile_target=0, useful_floor=0,
                                used=17, cap=20) == 10

    def test_just_below_watermark_not_pressure(self):
        # 16/20 = 80% < 85% watermark → not pressure → no overstock.
        assert overstock_excess(10, profile_target=0, useful_floor=0,
                                used=16, cap=20) == 0

    def test_zero_held_never_overstock(self):
        assert overstock_excess(0, profile_target=0, useful_floor=0,
                                used=20, cap=20) == 0

    def test_zero_cap_never_overstock(self):
        # No capacity → no pressure → no overstock (avoids div-by-zero).
        assert overstock_excess(10, profile_target=0, useful_floor=0,
                                used=0, cap=0) == 0


class TestInventoryProfile:
    def test_empty_when_no_active_targets(self):
        gd = GameData()
        gd._item_stats = {}
        gd._crafting_recipes = {}
        state = make_state()
        assert inventory_profile(state, gd) == {}

    def test_gather_target_recipe_closure_quantities(self):
        """crafting_target = fishing_net needs ash_wood x10 (recipe). Profile
        holds ash_wood at its recipe demand."""
        gd = GameData()
        gd._item_stats = {
            "fishing_net": ItemStats(code="fishing_net", level=1, type_="utility"),
            "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"fishing_net": {"ash_wood": 10}}
        state = make_state(crafting_target="fishing_net")
        profile = inventory_profile(state, gd)
        assert profile.get("ash_wood", 0) == 10

    def test_task_item_and_inputs_in_profile(self):
        """Active items-task copper_bar (needs 4 copper_ore) → both the task
        item and its inputs appear in the profile."""
        gd = GameData()
        gd._item_stats = {
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 4}}
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=5, task_progress=2)
        profile = inventory_profile(state, gd)
        # task wants 3 more copper_bar → 3 copper_bar, 12 copper_ore.
        assert profile.get("copper_bar", 0) >= 3
        assert profile.get("copper_ore", 0) >= 12

    def test_target_gear_and_tools_in_profile(self):
        """target_gear / target_tools recipe closures join the profile."""
        gd = GameData()
        gd._item_stats = {
            "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet"),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6}}
        state = make_state()
        # Task 5 migration (spec 2026-06-28-gear-loadout-profiles): the gear
        # roots are now the active-profile gear set, passed via `gear_codes`
        # (replaces the former `target_gear`/`target_tools` kwargs). Closure
        # behavior is unchanged.
        profile = inventory_profile(state, gd,
                                    gear_codes=frozenset({"copper_helmet"}))
        assert profile.get("copper_bar", 0) == 6

    def test_deep_chain_multiplies_quantities(self):
        """wooden_shield<-ash_plank x6, ash_plank<-ash_wood x1. Profile for
        crafting_target wooden_shield holds 6 ash_plank and 6 ash_wood."""
        gd = GameData()
        gd._item_stats = {
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield"),
            "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
            "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        }
        gd._crafting_recipes = {
            "wooden_shield": {"ash_plank": 6},
            "ash_plank": {"ash_wood": 1},
        }
        state = make_state(crafting_target="wooden_shield")
        profile = inventory_profile(state, gd)
        assert profile.get("ash_plank", 0) == 6
        assert profile.get("ash_wood", 0) == 6

    def test_cycle_safe(self):
        """Self-referential recipe terminates."""
        gd = GameData()
        gd._item_stats = {
            "a": ItemStats(code="a", level=1, type_="resource"),
            "b": ItemStats(code="b", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"a": {"b": 1}, "b": {"a": 1}}
        state = make_state(crafting_target="a")
        # Must terminate without RecursionError.
        profile = inventory_profile(state, gd)
        assert "a" in profile

    def test_non_positive_recipe_quantity_skipped(self):
        """A recipe entry with a non-positive quantity is skipped (defensive —
        a 0/negative qty_per contributes no demand and isn't recursed)."""
        gd = GameData()
        gd._item_stats = {
            "thing": ItemStats(code="thing", level=1, type_="resource"),
            "ghost_mat": ItemStats(code="ghost_mat", level=1, type_="resource"),
            "real_mat": ItemStats(code="real_mat", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"thing": {"ghost_mat": 0, "real_mat": 2}}
        state = make_state(crafting_target="thing")
        profile = inventory_profile(state, gd)
        assert "ghost_mat" not in profile  # 0 qty → skipped
        assert profile.get("real_mat", 0) == 2

    def test_watermark_constant_is_high(self):
        # Space-driven: deposit/discard only under genuine pressure.
        assert DISCARD_WATERMARK >= 0.85
