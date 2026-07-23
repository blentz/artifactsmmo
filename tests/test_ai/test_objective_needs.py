"""Tests for objective_needs: the committed objective's unmet NeedSet."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective_needs import _producible_by_self, objective_needs
from tests.test_ai.fixtures import make_state


def test_needs_closure_is_sourced_from_the_shared_graph():
    """Wave 3 migration: the closure now comes from `RequirementGraph`, not a
    private `recipe_closure` call. Prove the coupling is real — a deep material
    that only the graph closure reaches (iron_ore, two plies down) must appear
    as a need. If objective_needs had kept a shallow private walk this would be
    absent."""
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    # iron_sword -> iron_bar -> iron_ore: the transitive leaf is a material need,
    # in ITEM namespace (iron_ore, never the resource node iron_rocks).
    assert "iron_ore" in needs.materials
    assert "iron_rocks" not in needs.materials
    assert "iron_rocks" not in needs.buy_only


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
        "magic_orb": ItemStats(code="magic_orb", level=5, type_="resource"),
    }
    gd._crafting_recipes = {
        "iron_sword": {"iron_bar": 6, "magic_orb": 1},
        "iron_bar": {"iron_ore": 1},
    }
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 10)}
    return gd


def test_obtain_item_collects_unowned_closure_materials():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "iron_bar" in needs.materials
    assert "iron_ore" in needs.materials
    assert needs.materials and "magic_orb" not in needs.materials


def test_obtain_item_gating_skill_in_skill_xp():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "weaponcrafting" in needs.skill_xp


def test_buy_only_input_recorded():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "magic_orb" in needs.buy_only


def test_owned_material_not_a_need():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 10, "mining": 10},
                       inventory={"iron_bar": 6, "iron_ore": 6})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "iron_bar" not in needs.materials
    assert "weaponcrafting" not in needs.skill_xp


def test_reach_char_level_sets_char_xp():
    gd = _gd()
    state = make_state(level=4)
    needs = objective_needs(ReachCharLevel(6), state, gd)
    assert needs.char_xp is True


def test_empty_when_obtain_item_owned():
    gd = _gd()
    state = make_state(inventory={"iron_sword": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert needs.is_empty


class _OtherMetaGoal:
    """A MetaGoal-conforming objective that is none of the three concrete
    kinds objective_needs special-cases (exercises the empty fallthrough)."""

    def is_satisfied(self, state, game_data) -> bool:
        return False


def test_unknown_meta_goal_kind_yields_empty_needs():
    gd = _gd()
    state = make_state()
    needs = objective_needs(_OtherMetaGoal(), state, gd)  # type: ignore[arg-type]
    assert needs.is_empty


def test_monster_drop_ingredient_is_material_not_buy_only():
    """Run-17 2026-06-12: feather (chicken drop, the copper_legs_armor /
    feather_coat ingredient) classified buy-only because _producible_by_self
    only consulted recipes + resource drops. A monster-drop ingredient is
    farmable (GatherMaterials emits the proven select_monster_for_drop winner
    FightAction) — it must be a material need, not buy-only."""
    gd = _gd()
    gd._crafting_recipes["iron_sword"] = {"iron_bar": 6, "feather": 2}
    gd._monster_level = {"chicken": 1}
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "feather" in needs.materials
    assert "feather" not in needs.buy_only


def test_secondary_drop_ingredient_is_material_not_buy_only():
    """A recipe ingredient that is a SECONDARY resource drop (in the full drop
    table but not the primary `_resource_drops`) is gatherable — it must be a
    material need, never mis-classified as buy-only (which would silently pass
    every task through the worth gate)."""
    gd = _gd()
    gd._item_stats["rare_gem"] = ItemStats(code="rare_gem", level=5, type_="resource")
    gd._crafting_recipes["iron_sword"] = {"iron_bar": 6, "rare_gem": 1}
    gd._resource_drops["gem_rocks"] = "common_stone"  # primary
    gd._resource_drops_full["gem_rocks"] = [
        ("common_stone", 80, 1, 1), ("rare_gem", 5, 1, 1)]  # rare_gem is secondary
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "rare_gem" in needs.materials
    assert "rare_gem" not in needs.buy_only


def test_producible_by_self_via_currency_purchase():
    """P3 (engagement expansion): an item sold by a permanent located vendor
    for a monster-drop currency counts as self-producible."""
    gd = GameData()
    gd.world.npc_stock = {"tailor": {"cloth": 3}}
    gd.world.npc_buy_currency = {"tailor": {"cloth": "wool"}}
    gd._npc_locations = {"tailor": (5, 5)}
    gd._monster_drops = {"sheep": [("wool", 1, 1, 1)]}
    assert _producible_by_self("cloth", gd) is True
    gd._npc_locations = {}
    assert _producible_by_self("cloth", gd) is False
