"""Craft-planning completeness core (spec 2026-07-08). plan_craft drives the
REAL planner at one recipe via the production obtain-X path."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.audit.craft_completeness import (
    CraftCell,
    CraftVerdict,
    craft_cell_verdict,
    craft_grid,
    plan_craft,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_plan_craft_plans_a_simple_smelt() -> None:
    """copper_bar = smelt copper_ore (mining). A L5/mining-5 char with empty
    inventory must get a real plan whose first leg gathers or crafts toward
    copper_bar — not an empty plan."""
    gd = _gd()
    sc = ScenarioCharacter(name="t", level=5, skills={"mining": 5},
                           derive_combat_stats=True)
    state = scenario_state(sc, gd)
    plan = plan_craft("copper_bar", state, gd)
    assert plan, "expected a non-empty plan for copper_bar"
    # first leg is a gather (copper_ore) or a craft toward copper_bar
    assert isinstance(plan[0], (GatherAction, CraftAction)), repr(plan[0])


def test_craft_grid_cells_for_a_tier2_recipe() -> None:
    """iron_boots: gearcrafting 10 (L=10, decade-boundary tier). char cells
    10-2/10/10+2=8,10,12; skill cells max(0,10-5)=5 and 10."""
    gd = _gd()
    cells = craft_grid("iron_boots", gd)
    char_levels = sorted({c.char_level for c in cells})
    skill_levels = sorted({c.skill_level for c in cells})
    assert char_levels == [8, 10, 12]
    assert skill_levels == [5, 10]
    assert all(c.skill_name == "gearcrafting" for c in cells)
    assert len(cells) == 6


def test_craft_grid_tier1_uses_level_1_and_skill_0() -> None:
    """A T1 recipe (craft level <= 9): nominal char level is 1; under-skill
    clamps to 0 when L-5 < 0. copper_bar: mining 1 (L=1, T=1). nominal 1;
    the boundary offsets 10*T±2 straddle the T1/T2 decade line, giving the
    full three-way set {1, 8, 12} (not just a min-only check)."""
    gd = _gd()
    cells = craft_grid("copper_bar", gd)
    char_levels = sorted({c.char_level for c in cells})
    skill_levels = sorted({c.skill_level for c in cells})
    assert char_levels == [1, 8, 12]
    assert min(c.char_level for c in cells) == 1
    assert skill_levels == [0, 1]
    assert min(c.skill_level for c in cells) == 0  # max(0, 1-5)
    assert all(c.skill_name == "mining" for c in cells)
    assert len(cells) == 6


def test_craft_grid_returns_empty_for_a_non_craftable_item() -> None:
    """An item with no crafting recipe (no crafting_skill) yields no cells —
    the audit skips it rather than emitting a degenerate all-zero grid."""
    gd = _gd()
    stats = gd.item_stats("copper_ore")
    assert stats is not None and not stats.crafting_skill, (
        "fixture assumption: copper_ore is a raw gather, not craftable")
    assert craft_grid("copper_ore", gd) == []


def test_craft_grid_cell_is_frozen_and_field_accessible() -> None:
    """CraftCell exposes its three fields and rejects mutation (frozen)."""
    cell = CraftCell(char_level=8, skill_name="mining", skill_level=0)
    assert cell.char_level == 8
    assert cell.skill_name == "mining"
    assert cell.skill_level == 0
    try:
        cell.char_level = 9  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("CraftCell must be frozen")


# --- craft_cell_verdict -----------------------------------------------------
#
# copper_bar (crafting_skill=mining, level=1): recipe {copper_ore: 10}.
# copper_ore is gathered from copper_rocks (resource_drop_item). closure_items
# = {copper_bar, copper_ore, topaz_stone, emerald_stone, ruby_stone,
#    sapphire_stone} (the last four are copper_rocks' rare secondary drops).
#
# iron_boots (crafting_skill=gearcrafting, level=10): recipe
# {iron_bar: 5, feather: 3}; iron_bar recipe {iron_ore: 10}. iron_ore comes
# from iron_rocks; feather is a MONSTER-ONLY drop (chicken, no resource
# node at all — resource_for_drop('feather') is None). closure_items =
# {iron_boots, iron_bar, iron_ore, feather, topaz_stone, emerald_stone,
#  ruby_stone, sapphire_stone} (iron_rocks' rare secondary drops).
# copper_helmet (crafting_skill=gearcrafting, level=1) is NOT in iron_boots'
# closure but shares its crafting_skill — a skill-grind leg.


def test_craft_cell_verdict_fails_empty_plan() -> None:
    gd = _gd()
    verdict = craft_cell_verdict("copper_bar", [], gd)
    assert verdict == CraftVerdict(False, "empty")


def test_craft_cell_verdict_fails_wait_plan() -> None:
    gd = _gd()
    verdict = craft_cell_verdict("copper_bar", [WaitAction()], gd)
    assert verdict == CraftVerdict(False, "wait")


def test_craft_cell_verdict_passes_gather_of_closure_material() -> None:
    """Gathering copper_rocks yields copper_ore (its resource_drop_item),
    a copper_bar recipe ingredient — plan[0] advances the closure."""
    gd = _gd()
    plan = [GatherAction(resource_code="copper_rocks")]
    verdict = craft_cell_verdict("copper_bar", plan, gd)
    assert verdict == CraftVerdict(True, "")


def test_craft_cell_verdict_passes_craft_of_the_recipe_itself() -> None:
    gd = _gd()
    plan = [CraftAction(code="copper_bar")]
    verdict = craft_cell_verdict("copper_bar", plan, gd)
    assert verdict == CraftVerdict(True, "")


def test_craft_cell_verdict_passes_craft_of_a_closure_intermediate() -> None:
    """iron_boots' closure includes iron_bar (a craftable_mats member, one
    recipe input away from iron_boots) — crafting it advances the closure
    even though it is not the root recipe."""
    gd = _gd()
    plan = [CraftAction(code="iron_bar")]
    verdict = craft_cell_verdict("iron_boots", plan, gd)
    assert verdict == CraftVerdict(True, "")


def test_craft_cell_verdict_passes_fight_for_a_closure_leaf_dropper() -> None:
    """chicken drops feather, a direct iron_boots recipe ingredient with NO
    resource node (monster-only leaf) — recipe_closure's two-set return
    can't see it, but the recipe-ingredient union in _closure_item_set does."""
    gd = _gd()
    plan = [FightAction(monster_code="chicken")]
    verdict = craft_cell_verdict("iron_boots", plan, gd)
    assert verdict == CraftVerdict(True, "")


def test_craft_cell_verdict_passes_skill_grind_craft() -> None:
    """copper_helmet (gearcrafting 1) never enters iron_boots' (gearcrafting
    10) recipe tree, but crafting it levels the exact skill gate iron_boots
    needs — the skill-grind arm of _advances_closure."""
    gd = _gd()
    stats = gd.item_stats("copper_helmet")
    assert stats is not None and stats.crafting_skill == "gearcrafting"
    assert "copper_helmet" not in gd.crafting_recipe("iron_boots")  # sanity: off-closure
    plan = [CraftAction(code="copper_helmet")]
    verdict = craft_cell_verdict("iron_boots", plan, gd)
    assert verdict == CraftVerdict(True, "")


def test_craft_cell_verdict_passes_npc_buy_of_closure_material() -> None:
    """An NpcBuyAction buying a closure material (copper_ore, the copper_bar
    recipe ingredient) advances the closure via .item_code."""
    gd = _gd()
    plan = [NpcBuyAction(npc_code="some_merchant", item_code="copper_ore")]
    verdict = craft_cell_verdict("copper_bar", plan, gd)
    assert verdict == CraftVerdict(True, "")


def test_craft_cell_verdict_passes_withdraw_of_closure_material() -> None:
    """A WithdrawItemAction pulling a closure material (copper_ore) from the
    bank advances the closure via .code."""
    gd = _gd()
    plan = [WithdrawItemAction(code="copper_ore", quantity=1)]
    verdict = craft_cell_verdict("copper_bar", plan, gd)
    assert verdict == CraftVerdict(True, "")


def test_craft_cell_verdict_fails_unrelated_gather() -> None:
    """ash_tree (woodcutting) neither drops an iron_boots closure material
    nor shares iron_boots' gearcrafting skill."""
    gd = _gd()
    plan = [GatherAction(resource_code="ash_tree")]
    verdict = craft_cell_verdict("iron_boots", plan, gd)
    assert verdict == CraftVerdict(False, f"unrelated:{plan[0]!r}")
    assert verdict.reason == "unrelated:Gather(ash_tree)"


def test_craft_cell_verdict_fails_unrelated_rest() -> None:
    gd = _gd()
    plan = [RestAction()]
    verdict = craft_cell_verdict("iron_boots", plan, gd)
    assert verdict == CraftVerdict(False, f"unrelated:{plan[0]!r}")
    assert verdict.reason == "unrelated:Rest"


def test_craft_verdict_is_frozen() -> None:
    verdict = CraftVerdict(passed=True, reason="")
    try:
        verdict.passed = False  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("CraftVerdict must be frozen")


def test_craft_cell_verdict_rejects_higher_tier_same_skill_craft() -> None:
    """Tier-aware skill-grind: crafting a HIGHER-tier same-skill item is NOT a
    grind toward a lower-tier target (you can't make it yet, not directional).
    iron_boots is gearcrafting 10; a gearcrafting item above level 10 crafted
    as plan[0] must FAIL, not pass via the skill-grind arm."""
    gd = _gd()
    # find a real gearcrafting item above iron_boots' level 10
    higher = next(c for c, st in gd.all_item_stats.items()
                  if st.crafting_skill == "gearcrafting"
                  and (st.crafting_level or 0) > 10
                  and gd.crafting_recipe(c))
    assert higher not in (gd.crafting_recipe("iron_boots") or {})  # not a real ingredient
    v = craft_cell_verdict("iron_boots", [CraftAction(code=higher)], gd)
    assert v.passed is False, (higher, v)
    assert v.reason.startswith("unrelated:"), v
