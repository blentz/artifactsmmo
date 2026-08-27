"""Tests for objective_needs: the committed objective's unmet NeedSet."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective_needs import _producible_by_self, link_demand, objective_needs
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


def test_reach_skill_level_names_that_skill_as_the_unmet_need():
    """WAVE 3a. Before the flip nothing could hand this function a
    `ReachSkillLevel`, so it fell through to the empty `NeedSet` — and an empty
    NeedSet switches the arbiter's PURSUE_TASK worth gate OFF entirely
    (`means_serves` returns True unconditionally on `needs.is_empty`). The
    moment the root graph could resolve a skill climb, that fallthrough would
    have disabled a live gate for the whole climb with nothing saying so.

    `skill_xp` is the set `means_worth._task_need_overlap` intersects the held
    task's craft/gather chain against, so naming the skill there is what makes
    a task that exercises it count as serving the objective."""
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 10})
    needs = objective_needs(ReachSkillLevel(skill="weaponcrafting", level=11),
                            state, gd)
    assert needs.skill_xp == frozenset({"weaponcrafting"})
    assert not needs.is_empty
    assert needs.char_xp is False
    assert needs.materials == frozenset() and needs.buy_only == frozenset()


def test_reach_skill_level_already_met_is_no_need():
    """Mirrors the `ReachCharLevel` arm: the need is stated only while it is
    UNMET, so a satisfied climb reports nothing rather than keeping the worth
    gate armed on work that is already done."""
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 11})
    needs = objective_needs(ReachSkillLevel(skill="weaponcrafting", level=11),
                            state, gd)
    assert needs.is_empty


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


_LN_BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures"
              / "gamedata_bundle.json")


def _ln_gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(_LN_BUNDLE.read_text()))


def _ln_state(game_data: GameData):
    return scenario_state(SCENARIOS["l32_held_task_closable"], game_data)


# ---------------------------------------------------------------------------
# link_demand (wave 6, increment 5.5)
#
# The task pool used to be scored against `ctx.target_gear` -- everything the
# objective will EVER want. `link_demand` is what it is blocked on NOW. Scoring
# against the whole sheet makes every taskmaster look equally useful, because
# the sheet always contains something each one can serve.
# ---------------------------------------------------------------------------

def test_link_demand_is_materials_and_buy_only() -> None:
    """The projection, asserted against the NeedSet it projects rather than a
    literal so the two cannot drift."""
    gd = _ln_gd()
    state = _ln_state(gd)
    needs = objective_needs(ObtainItem("copper_helmet", 1), state, gd)
    assert link_demand(needs) == needs.materials | needs.buy_only


def test_link_demand_is_not_empty_for_a_blocked_craft() -> None:
    """NOT VACUOUS. `copper_helmet` genuinely lacks its closure at this cell --
    measured, `copper_bar` and `copper_ore` -- so the assertions above are over
    a populated set, not an empty one that would satisfy any projection."""
    gd = _ln_gd()
    needs = objective_needs(ObtainItem("copper_helmet", 1), _ln_state(gd), gd)
    demand = link_demand(needs)
    assert demand, "fixture drift: this root no longer has unmet demand"
    assert {"copper_bar", "copper_ore"} <= demand


def test_char_xp_is_excluded_by_the_TOKEN_not_the_root() -> None:
    """A `ReachCharLevel` root yields EMPTY demand, so `choose_taskmaster`
    returns None and the default master is used -- rather than every monsters
    task scoring a perfect 1.

    Excluding the token rather than the root is what makes this hold: the
    endgame sheet reaches CHAR_XP through its own drop-routed materials, so a
    root-level exclusion would not have bitten."""
    gd = _ln_gd()
    needs = objective_needs(ReachCharLevel(level=40), _ln_state(gd), gd)
    assert needs.char_xp is True
    assert link_demand(needs) == frozenset()


def test_no_committed_root_yields_empty_demand() -> None:
    """`None` is the no-root case and takes the same arm: nothing is blocked, so
    no task pool is preferred."""
    assert link_demand(None) == frozenset()


def test_skill_xp_is_excluded_because_it_is_a_DIFFERENT_NAMESPACE() -> None:
    """`skill_xp` names SKILLS; the pool is scored on item CODES. Mixing the two
    namespaces is the defect `requirement_parity` exists to catch, so a skill
    gate must not leak into the demand set."""
    gd = _ln_gd()
    state = _ln_state(gd)
    for code in ("copper_helmet", "fishing_net", "cooked_chicken"):
        needs = objective_needs(ObtainItem(code, 1), state, gd)
        assert not (link_demand(needs) & needs.skill_xp)
