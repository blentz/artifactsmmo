"""Craft-planning completeness core (spec 2026-07-08). plan_craft drives the
REAL planner at one recipe via the production obtain-X path."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.audit.craft_completeness import (
    CraftCell,
    CraftVerdict,
    GapClass,
    _leaf_status,
    census_state,
    classify_gap,
    craft_cell_verdict,
    craft_grid,
    plan_craft,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_classify_gap_real_bundle_new_classes_regression_pin() -> None:
    """Regression pin over the committed bundle. Two honest gap classes are
    stable (classify_gap is pure/deterministic):
      - iron_axe at-skill: needs jasper_crystal, sold only by tasks_trader for
        tasks_coin (task-earned) -> PURCHASE_RECURSION.
      - cooked_chicken at char 12 / cooking 1: raw_chicken's only dropper is the
        grey L1 chicken and a near next-tier food exists -> GREY_FARM_SUPPRESSED.
    And the LevelSkill acceptance (epic P4): an under-skill grindable cell no
    longer classifies as a gap at all — the planner plans a LevelSkill first leg
    and `craft_cell_verdict` PASSes it (was SKILL_PREREQUISITE, now retired)."""
    gd = _gd()
    assert classify_gap("iron_axe", CraftCell(8, "weaponcrafting", 10),
                        gd) is GapClass.PURCHASE_RECURSION
    assert classify_gap("cooked_chicken", CraftCell(12, "cooking", 1),
                        gd) is GapClass.GREY_FARM_SUPPRESSED
    # iron_bar under-skill (mining 5 < craft 10): plans [LevelSkill(mining->10)]
    # and PASSES on that leg — no SKILL_PREREQUISITE classification.
    cell = CraftCell(8, "mining", 5)
    state = census_state("iron_bar", cell, gd)
    plan = plan_craft("iron_bar", state, gd)
    assert plan and isinstance(plan[0], LevelSkill), [repr(a) for a in plan]
    assert craft_cell_verdict("iron_bar", plan, gd).passed


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
    10-2/10/10+2=8,10,12; skill cells max(1,10-5)=5 and 10."""
    gd = _gd()
    cells = craft_grid("iron_boots", gd)
    char_levels = sorted({c.char_level for c in cells})
    skill_levels = sorted({c.skill_level for c in cells})
    assert char_levels == [8, 10, 12]
    assert skill_levels == [5, 10]
    assert all(c.skill_name == "gearcrafting" for c in cells)
    assert len(cells) == 6


def test_craft_grid_tier1_low_recipe_floors_skill_at_1_and_collapses() -> None:
    """A T1 recipe (craft level <= 9): nominal char level is 1; the under-skill
    floor is 1 (skills start at level 1 — skill_level=0 is impossible). For
    copper_bar (mining 1, L=1, T=1), under-skill max(1, 1-5)=1 equals at-skill
    1, so the two skill cells collapse to {1} and the grid yields 3 cells (the
    three-way char set {1, 8, 12}, not just a min-only check), not 6."""
    gd = _gd()
    cells = craft_grid("copper_bar", gd)
    char_levels = sorted({c.char_level for c in cells})
    skill_levels = sorted({c.skill_level for c in cells})
    assert char_levels == [1, 8, 12]
    assert min(c.char_level for c in cells) == 1
    assert skill_levels == [1]
    assert min(c.skill_level for c in cells) == 1  # max(1, 1-5)
    assert all(c.skill_name == "mining" for c in cells)
    assert len(cells) == 3


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


# --- classify_gap -----------------------------------------------------------
#
# Witness catalogs built as bare GameData() instances with only the fields the
# classifier reads populated (the tests/ai/test_grey_farm.py idiom: a real
# GameData whose underscore-backed catalogs are set directly). Each witness is
# minimal and isolates ONE gap class; the precedence tests combine two blocked
# leaves to pin the cascade order.


def _fill_monster_defaults(gd: GameData) -> None:
    """Give every declared monster the combat-stat defaults predict_win reads,
    so is_winnable never KeyErrors on a sparsely-specified fixture monster."""
    for code in gd._monster_level:
        gd._monster_hp.setdefault(code, 0)
        gd._monster_attack.setdefault(code, {})
        gd._monster_resistance.setdefault(code, {})
        gd._monster_critical_strike.setdefault(code, 0)
        gd._monster_initiative.setdefault(code, 0)


def _mat(code: str) -> ItemStats:
    """A non-craftable base material item (a closure leaf)."""
    return ItemStats(code=code, level=1, type_="resource", subtype="mob")


def _craftable(code: str, skill: str, level: int) -> ItemStats:
    return ItemStats(code=code, level=level, type_="resource", subtype="craft",
                     crafting_skill=skill, crafting_level=level)


def _cell(char_level: int = 5, skill: str = "gearcrafting",
          skill_level: int = 1) -> CraftCell:
    return CraftCell(char_level=char_level, skill_name=skill,
                     skill_level=skill_level)


def test_classify_gap_planner_bug_when_under_skill_grindable_fails() -> None:
    """widget (gearcrafting 5) crafts from gear_ore, a gatherable ore; the skill
    has a lower-tier grind item (trinket, gearcrafting 1). Every leaf is
    reachable and the skill IS grindable, but the cell is UNDER-SKILL
    (gearcrafting 1 < 5). Post-LevelSkill (epic P4) a grindable under-skill cell
    is NO LONGER a gap class: the planner plans a LevelSkill leg and the cell
    PASSES `craft_cell_verdict`, so it never reaches classify. If it IS
    classified (a FAIL despite LevelSkill being in reach), that is the actionable
    PLANNER_BUG residual — NOT the retired SKILL_PREREQUISITE."""
    gd = GameData()
    gd._item_stats = {
        "widget": _craftable("widget", "gearcrafting", 5),
        "trinket": _craftable("trinket", "gearcrafting", 1),
        "gear_ore": _mat("gear_ore"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    assert classify_gap("widget", _cell(skill_level=1), gd) is GapClass.PLANNER_BUG


def test_classify_gap_planner_bug_when_all_reachable_at_skill() -> None:
    """At-skill (gearcrafting 5 == widget's level): every leaf reachable, no
    skill grind needed, yet no directional plan — the actionable PLANNER_BUG
    residual (the class the census exists to surface)."""
    gd = GameData()
    gd._item_stats = {
        "widget": _craftable("widget", "gearcrafting", 5),
        "gear_ore": _mat("gear_ore"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    assert classify_gap("widget", _cell(skill_level=5), gd) is GapClass.PLANNER_BUG


def test_classify_gap_grey_farm_suppressed_when_only_dropper_is_grey_and_obsolete() -> None:
    """low_food (cooking 1) needs raw_meat, dropped only by hen (level 1). At a
    char_level=12 cell the hen is GREY (11 levels below → zero xp-per-kill), and
    a near next-tier same-family food (mid_food, cooking 5) exists, so
    `grey_farm_allowed(raw_meat)` is False: production grinds cooking toward the
    better food instead of farming the obsolete drop. The FAIL is the intended
    grey-farm policy, not a planner hole — GREY_FARM_SUPPRESSED. (Live census
    2026-07-11: cooked_chicken at char 12 / cooking 1.)"""
    gd = GameData()
    gd._item_stats = {
        "low_food": ItemStats(code="low_food", level=1, type_="consumable",
                              subtype="food", crafting_skill="cooking",
                              crafting_level=1, hp_restore=80),
        "mid_food": ItemStats(code="mid_food", level=5, type_="consumable",
                              subtype="food", crafting_skill="cooking",
                              crafting_level=5, hp_restore=120),
        "raw_meat": _mat("raw_meat"),
        "other_mat": _mat("other_mat"),
        "iron_blade": ItemStats(code="iron_blade", level=1, type_="weapon",
                                subtype="", attack={"fire": 50}),
    }
    gd._crafting_recipes = {"low_food": {"raw_meat": 1},
                            "mid_food": {"other_mat": 1}}
    gd._resource_drops = {"blade_vein": "iron_blade"}
    gd._monster_locations = {"hen": (0, 1)}
    gd._monster_level = {"hen": 1}
    gd._monster_hp = {"hen": 10}
    gd._monster_drops = {"hen": [("raw_meat", 50, 1, 1)]}
    _fill_monster_defaults(gd)
    cell = _cell(char_level=12, skill="cooking", skill_level=1)
    assert classify_gap("low_food", cell, gd) is GapClass.GREY_FARM_SUPPRESSED


def test_classify_gap_material_unreachable_when_dropping_resource_unlocated() -> None:
    """A leaf whose sole gather source is a resource that carries a skill and a
    drop table but is UNPLACED (no location) is NOT actually gatherable —
    MATERIAL_UNREACHABLE, not PLANNER_BUG. Mirrors the live diamond_stone case
    (strange_rocks is unplaced in the bundle). `gatherable_drop_items()` alone
    would count `rare_stone` as gatherable and let the cascade fall through to a
    phantom PLANNER_BUG; the location check in `_has_located_gather_source`
    prevents that."""
    gd = GameData()
    gd._item_stats = {
        "rare_gem": _craftable("rare_gem", "jewelrycrafting", 1),
        "rare_stone": _mat("rare_stone"),
    }
    gd._crafting_recipes = {"rare_gem": {"rare_stone": 2}}
    gd._resource_drops = {"strange_rocks": "rare_stone"}
    gd._resource_skill = {"strange_rocks": ("mining", 1)}
    # strange_rocks is deliberately UNLOCATED (no _resource_locations entry).
    assert classify_gap("rare_gem", _cell(), gd) is GapClass.MATERIAL_UNREACHABLE


def test_classify_gap_material_unreachable_dead_end_leaf() -> None:
    """phantom_mat has NO source at all — not gatherable, not craftable, no
    dropper, no vendor, not task-earnable — a static-catalog dead end."""
    gd = GameData()
    gd._item_stats = {
        "relic": _craftable("relic", "gearcrafting", 1),
        "phantom_mat": _mat("phantom_mat"),
    }
    gd._crafting_recipes = {"relic": {"phantom_mat": 1}}
    assert classify_gap("relic", _cell(), gd) is GapClass.MATERIAL_UNREACHABLE


def test_classify_gap_combat_blocked_unwinnable_dropper() -> None:
    """beast_hide drops only from cow, a PERMANENTLY-spawning monster that is
    unwinnable at the bare cell loadout (zero attack) — COMBAT_BLOCKED, a
    strength limit at a real, always-present source."""
    gd = GameData()
    gd._item_stats = {
        "beast_armor": _craftable("beast_armor", "gearcrafting", 5),
        "beast_hide": _mat("beast_hide"),
    }
    gd._crafting_recipes = {"beast_armor": {"beast_hide": 2}}
    gd._monster_locations = {"cow": (1, 0)}
    gd._monster_level = {"cow": 30}
    gd._monster_hp = {"cow": 2000}
    gd._monster_attack = {"cow": {"earth": 200}}
    gd._monster_drops = {"cow": [("beast_hide", 10, 1, 1)]}
    _fill_monster_defaults(gd)
    assert classify_gap("beast_armor", _cell(), gd) is GapClass.COMBAT_BLOCKED


def test_classify_gap_event_gated_event_monster_dropper() -> None:
    """event_gem drops only from event_ogre, an EVENT monster with no
    permanent spawn (unknown spawn in the event-free audit) — EVENT_GATED, the
    most-specific expected limit."""
    gd = GameData()
    gd._item_stats = {
        "crown": _craftable("crown", "gearcrafting", 5),
        "event_gem": _mat("event_gem"),
    }
    gd._crafting_recipes = {"crown": {"event_gem": 1}}
    gd._monster_level = {"event_ogre": 20}
    gd._monster_drops = {"event_ogre": [("event_gem", 10, 1, 1)]}
    gd.world.event_monster_locations = {"event_ogre": [(5, 5)]}
    gd.world.event_code_of_content = {"event_ogre": "corrupt"}
    _fill_monster_defaults(gd)
    assert classify_gap("crown", _cell(), gd) is GapClass.EVENT_GATED


def test_classify_gap_skill_unreachable_no_grind_ladder() -> None:
    """lonely_blade (gearcrafting 10) is the ONLY gearcrafting item; its leaf
    is a gatherable ore (reachable), so no material class fires, but at
    gearcrafting 5 there is nothing of that skill below level 10 to grind on —
    SKILL_UNREACHABLE."""
    gd = GameData()
    gd._item_stats = {
        "lonely_blade": _craftable("lonely_blade", "gearcrafting", 10),
        "gear_ore": _mat("gear_ore"),
    }
    gd._crafting_recipes = {"lonely_blade": {"gear_ore": 2}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    verdict = classify_gap("lonely_blade", _cell(skill_level=5), gd)
    assert verdict is GapClass.SKILL_UNREACHABLE


def test_classify_gap_event_gated_outranks_combat_blocked() -> None:
    """A recipe with BOTH an event-gated leaf and a combat-blocked leaf is
    reported EVENT_GATED — the cascade ranks the expected event limit first."""
    gd = GameData()
    gd._item_stats = {
        "dual": _craftable("dual", "gearcrafting", 5),
        "event_gem": _mat("event_gem"),
        "beast_hide": _mat("beast_hide"),
    }
    gd._crafting_recipes = {"dual": {"event_gem": 1, "beast_hide": 1}}
    gd._monster_locations = {"cow": (1, 0)}
    gd._monster_level = {"cow": 30, "event_ogre": 20}
    gd._monster_hp = {"cow": 2000}
    gd._monster_attack = {"cow": {"earth": 200}}
    gd._monster_drops = {
        "cow": [("beast_hide", 10, 1, 1)],
        "event_ogre": [("event_gem", 10, 1, 1)],
    }
    gd.world.event_monster_locations = {"event_ogre": [(5, 5)]}
    gd.world.event_code_of_content = {"event_ogre": "corrupt"}
    _fill_monster_defaults(gd)
    assert classify_gap("dual", _cell(), gd) is GapClass.EVENT_GATED


def test_classify_gap_combat_blocked_outranks_material_unreachable() -> None:
    """A combat-blocked leaf (beatable-later source) outranks a dead-end
    material leaf — COMBAT_BLOCKED is the softer, more-specific game limit."""
    gd = GameData()
    gd._item_stats = {
        "mix": _craftable("mix", "gearcrafting", 5),
        "beast_hide": _mat("beast_hide"),
        "phantom_mat": _mat("phantom_mat"),
    }
    gd._crafting_recipes = {"mix": {"beast_hide": 1, "phantom_mat": 1}}
    gd._monster_locations = {"cow": (1, 0)}
    gd._monster_level = {"cow": 30}
    gd._monster_hp = {"cow": 2000}
    gd._monster_attack = {"cow": {"earth": 200}}
    gd._monster_drops = {"cow": [("beast_hide", 10, 1, 1)]}
    _fill_monster_defaults(gd)
    assert classify_gap("mix", _cell(), gd) is GapClass.COMBAT_BLOCKED


def test_classify_gap_reachable_via_permanent_gold_vendor() -> None:
    """A leaf sold by a permanent gold vendor is reachable — no material class
    fires. With the skill grindable the residual is PLANNER_BUG (the vendor
    buyable arm of _leaf_status returned None)."""
    gd = GameData()
    gd._item_stats = {
        "bought_gear": _craftable("bought_gear", "gearcrafting", 1),
        "shop_mat": _mat("shop_mat"),
        "grind_item": _craftable("grind_item", "gearcrafting", 1),
    }
    gd._crafting_recipes = {
        "bought_gear": {"shop_mat": 1},
        "grind_item": {"shop_mat": 1},
    }
    gd.world.npc_stock = {"merchant": {"shop_mat": 5}}
    gd.world.npc_tiles = {"merchant": (2, 2)}
    assert classify_gap("bought_gear", _cell(), gd) is GapClass.PLANNER_BUG


def test_classify_gap_reachable_via_vendor_for_directly_attainable_currency() -> None:
    """A leaf sold for a non-gold currency the planner can DIRECTLY acquire (a
    LOCATED gatherable coin — Gather → NpcBuy) is reachable via the vendor arm,
    so the residual is PLANNER_BUG. Contrast PURCHASE_RECURSION, where the
    currency is task-only."""
    gd = GameData()
    gd._item_stats = {
        "coin_gear": _craftable("coin_gear", "gearcrafting", 1),
        "coin_mat": _mat("coin_mat"),
        "trade_coin": _mat("trade_coin"),
        "grind_item": _craftable("grind_item", "gearcrafting", 1),
    }
    gd._crafting_recipes = {
        "coin_gear": {"coin_mat": 1},
        "grind_item": {"coin_mat": 1},
    }
    gd._resource_drops = {"coin_vein": "trade_coin"}
    gd._resource_skill = {"coin_vein": ("mining", 1)}
    gd._resource_locations = {"coin_vein": [(3, 3)]}
    gd.world.npc_stock = {"trader": {"coin_mat": 3}}
    gd.world.npc_tiles = {"trader": (4, 4)}
    gd.world.npc_buy_currency = {"trader": {"coin_mat": "trade_coin"}}
    assert classify_gap("coin_gear", _cell(), gd) is GapClass.PLANNER_BUG


def test_classify_gap_purchase_recursion_when_currency_is_task_only() -> None:
    """A leaf whose ONLY source is a permanent vendor selling it for a TASK-only
    currency (a coin earned solely by completing tasks — not gatherable, not a
    monster drop) is PURCHASE_RECURSION: the planner does not yet plan the
    recursive Task → earn-coin → NpcBuy edge (npc_purchase_acquisition Phase
    2-4). Mirrors the live jasper_crystal @ tasks_trader (tasks_coin) case."""
    gd = GameData()
    gd._item_stats = {
        "coin_gear": _craftable("coin_gear", "gearcrafting", 1),
        "vendor_mat": _mat("vendor_mat"),
        "task_coin": _mat("task_coin"),
    }
    gd._crafting_recipes = {"coin_gear": {"vendor_mat": 1}}
    gd.world.npc_stock = {"tasks_trader": {"vendor_mat": 8}}
    gd.world.npc_tiles = {"tasks_trader": (4, 4)}
    gd.world.npc_buy_currency = {"tasks_trader": {"vendor_mat": "task_coin"}}
    # task_coin has NO gather source and NO dropper — only task rewards would
    # yield it, which the planner cannot recursively plan.
    assert classify_gap("coin_gear", _cell(), gd) is GapClass.PURCHASE_RECURSION


def test_classify_gap_event_gated_via_event_only_vendor() -> None:
    """A leaf sold ONLY by an event-window NPC (no permanent vendor, no
    dropper) is EVENT_GATED through the event-vendor arm."""
    gd = GameData()
    gd._item_stats = {
        "festival_gear": _craftable("festival_gear", "gearcrafting", 5),
        "festival_token": _mat("festival_token"),
    }
    gd._crafting_recipes = {"festival_gear": {"festival_token": 1}}
    gd.world.npc_stock = {"festival_vendor": {"festival_token": 10}}
    gd.world.event_npc_spawns = {"festival_vendor": (7, 7)}
    gd.world.npc_event_codes = {"festival_vendor": "festival"}
    assert classify_gap("festival_gear", _cell(), gd) is GapClass.EVENT_GATED


def test_classify_gap_reachable_via_task_earnable_leaf() -> None:
    """A task-earnable leaf (awarded by the always-available task loop) is
    reachable — the task arm of _leaf_status returns None."""
    gd = GameData()
    gd._item_stats = {
        "task_gear": _craftable("task_gear", "gearcrafting", 1),
        "task_mat": _mat("task_mat"),
        "grind_item": _craftable("grind_item", "gearcrafting", 1),
    }
    gd._crafting_recipes = {
        "task_gear": {"task_mat": 1},
        "grind_item": {"task_mat": 1},
    }
    gd._task_reward_item_codes = frozenset({"task_mat"})
    assert classify_gap("task_gear", _cell(), gd) is GapClass.PLANNER_BUG


def test_classify_gap_skill_grindable_via_gatherable_of_skill() -> None:
    """A mining-skill recipe (a smelt) is grindable through a gatherable
    resource of the mining skill even with no lower craftable — pins the
    resource arm of _skill_grindable (GRINDABLE under-skill is NOT
    SKILL_UNREACHABLE; post-LevelSkill it falls through to the PLANNER_BUG
    residual rather than the retired SKILL_PREREQUISITE)."""
    gd = GameData()
    gd._item_stats = {
        "ore_bar": _craftable("ore_bar", "mining", 5),
        "raw_ore": _mat("raw_ore"),
    }
    gd._crafting_recipes = {"ore_bar": {"raw_ore": 2}}
    gd._resource_drops = {"ore_rocks": "raw_ore"}
    gd._resource_skill = {"ore_rocks": ("mining", 1)}
    gd._resource_locations = {"ore_rocks": [(3, 3)]}
    verdict = classify_gap("ore_bar", _cell(skill="mining", skill_level=1), gd)
    assert verdict is GapClass.PLANNER_BUG


def test_classify_gap_skill_unreachable_when_lowest_rung_above_current_skill() -> None:
    """Classifier-soundness (`_skill_grindable` bounds the grind rung to the
    cell's current `skill_level`, not the target). lonely_bar needs mining 2;
    the cell is at mining 1 (a real under-skill grid cell — skills start at 1).
    Mining's only grind rung here — ore_vein at mining 2 — is NOT actionable at
    skill 1 (you need mining 2 to gather it), and there is no lower rung to
    bootstrap from. A `<= target_level` bound would let the level-2 rung pass
    against a target of 2 and wrongly surface a phantom PLANNER_BUG; the honest
    read is that the skill cannot be leveled from here — SKILL_UNREACHABLE."""
    gd = GameData()
    gd._item_stats = {
        "lonely_bar": _craftable("lonely_bar", "mining", 2),
        "raw_ore": _mat("raw_ore"),
    }
    gd._crafting_recipes = {"lonely_bar": {"raw_ore": 2}}
    gd._resource_drops = {"ore_vein": "raw_ore"}
    gd._resource_skill = {"ore_vein": ("mining", 2)}
    gd._resource_locations = {"ore_vein": [(3, 3)]}
    verdict = classify_gap("lonely_bar", _cell(skill="mining", skill_level=1), gd)
    assert verdict is GapClass.SKILL_UNREACHABLE


def test_classify_gap_skill_grindable_true_positive_survives_at_nonzero_skill() -> None:
    """Regression pin for the `_skill_grindable` bound (must NOT over-correct):
    iron_bar-shaped true positive. mining's lowest grind rung sits at level 1
    (copper_rocks-equivalent); the target craft level is 10 (iron_bar-style);
    the under-skill cell is skill_level=5 (`max(1, 10-5)`). mining IS
    bootstrappable from 5 (the level-1 rung is well within reach at skill 5), so
    this is NOT SKILL_UNREACHABLE — the `_skill_grindable` bound is `<= skill_
    level`, not "nothing below target is ever grindable". A grindable under-skill
    cell falls through to the PLANNER_BUG residual (the retired
    SKILL_PREREQUISITE): post-LevelSkill the planner should plan it, so a FAIL is
    actionable, not an expected skill gap."""
    gd = GameData()
    gd._item_stats = {
        "iron_bar_like": _craftable("iron_bar_like", "mining", 10),
        "iron_ore": _mat("iron_ore"),
    }
    gd._crafting_recipes = {"iron_bar_like": {"iron_ore": 2}}
    gd._resource_drops = {"copper_rocks": "iron_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._resource_locations = {"copper_rocks": [(3, 3)]}
    verdict = classify_gap("iron_bar_like", _cell(skill="mining", skill_level=5), gd)
    assert verdict is GapClass.PLANNER_BUG


def test_classify_gap_skill_already_at_target_is_grindable() -> None:
    """When the cell skill already meets the recipe's craft level, no grind is
    needed — the skill_level >= target early-return keeps it out of
    SKILL_UNREACHABLE (PLANNER_BUG residual)."""
    gd = GameData()
    gd._item_stats = {
        "atlevel_blade": _craftable("atlevel_blade", "gearcrafting", 10),
        "gear_ore": _mat("gear_ore"),
    }
    gd._crafting_recipes = {"atlevel_blade": {"gear_ore": 2}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    verdict = classify_gap("atlevel_blade", _cell(skill_level=10), gd)
    assert verdict is GapClass.PLANNER_BUG


def test_leaf_status_reachable_via_winnable_permanent_dropper() -> None:
    """A leaf whose permanent dropper IS winnable at the (geared) cell loadout
    is reachable — _leaf_status returns None via the winnable-drop arm.
    Exercised directly on _leaf_status with a hand-built combat-capable
    state (classify_gap's own census_state loadout is pinned separately by
    test_census_state_gears_the_cell_and_flips_combat_blocked_to_reachable)."""
    gd = GameData()
    gd._item_stats = {
        "meat": _mat("meat"),
        "blade": ItemStats(code="blade", level=1, type_="weapon", subtype="",
                           attack={"fire": 100}),
    }
    gd._monster_locations = {"rat": (1, 0)}
    gd._monster_level = {"rat": 1}
    gd._monster_hp = {"rat": 10}
    gd._monster_drops = {"rat": [("meat", 10, 1, 1)]}
    _fill_monster_defaults(gd)
    sc = ScenarioCharacter(name="fighter", level=5,
                           equipment={"weapon_slot": "blade"},
                           derive_combat_stats=True)
    state = scenario_state(sc, gd)
    assert _leaf_status("meat", state, gd) is None


def test_classify_gap_unknown_recipe_is_its_own_unreachable_leaf() -> None:
    """An item with no catalog stats collapses to a closure whose sole 'leaf'
    is itself, with no acquisition source — the classifier returns
    MATERIAL_UNREACHABLE rather than raising on the missing stats."""
    gd = GameData()
    assert classify_gap("nonexistent_item", _cell(), gd) is GapClass.MATERIAL_UNREACHABLE


# --- census_state -----------------------------------------------------------
#
# Review finding: classify_gap used to build its cell state with an EMPTY
# loadout, so is_winnable was uniformly False and every monster-drop-only
# closure leaf classified COMBAT_BLOCKED regardless of whether a plausible
# starter/tier loadout could actually beat the dropper (masking real
# PLANNER_BUGs). census_state fixes this per the spec's grid State
# definition ("realistic combat stats from the equipped starter/tier gear
# via derive_combat_stats"). These tests pin that gear ACTUALLY changes the
# verdict — not merely that the plumbing compiles.


def test_census_state_equips_near_term_gear_and_derives_combat_stats() -> None:
    """census_state picks the best attainable-now item per slot at the
    cell's level (near_term_gear, seeded from a bare same-level state) and
    equips it with derive_combat_stats=True, so the resulting state carries
    non-zero attack/max_hp from the gear rather than the zero-stat empty
    loadout."""
    gd = GameData()
    gd._item_stats = {
        "iron_blade": ItemStats(code="iron_blade", level=1, type_="weapon",
                                subtype="", attack={"fire": 50}),
    }
    gd._resource_drops = {"blade_vein": "iron_blade"}
    cell = _cell(char_level=5, skill_level=1)
    state = census_state("iron_blade", cell, gd)
    assert state.equipment.get("weapon_slot") == "iron_blade"
    assert state.attack.get("fire") == 50
    assert state.level == 5
    assert state.skills["gearcrafting"] == 1
    assert state.inventory == {}
    assert state.bank_items == {}


def test_census_state_gears_the_cell_and_flips_combat_blocked_to_reachable() -> None:
    """critter (a permanent, zero-attack, 5-HP monster) is UNWINNABLE at the
    OLD empty-loadout state (raw_player == 0 never kills anything) but
    winnable once census_state equips iron_blade (a level-1, gatherable
    weapon near_term_gear picks up). At-skill (gearcrafting 5) with the leaf
    reachable, the recipe now classifies PLANNER_BUG (the actionable residual)
    instead of the false COMBAT_BLOCKED the empty loadout produced."""
    gd = GameData()
    gd._item_stats = {
        "trinket_gear": _craftable("trinket_gear", "gearcrafting", 5),
        "basic_gear": _craftable("basic_gear", "gearcrafting", 1),
        "critter_meat": _mat("critter_meat"),
        "iron_blade": ItemStats(code="iron_blade", level=1, type_="weapon",
                                subtype="", attack={"fire": 50}),
    }
    gd._crafting_recipes = {
        "trinket_gear": {"critter_meat": 2},
        "basic_gear": {"critter_meat": 1},
    }
    gd._resource_drops = {"blade_vein": "iron_blade"}
    gd._monster_locations = {"critter": (1, 0)}
    gd._monster_level = {"critter": 1}
    gd._monster_hp = {"critter": 5}
    gd._monster_drops = {"critter": [("critter_meat", 10, 1, 1)]}
    _fill_monster_defaults(gd)
    cell = _cell(char_level=5, skill_level=5)

    # The pre-fix empty-loadout state cannot win: zero attack never kills
    # anything (the exact bug the finding describes).
    bare = scenario_state(
        ScenarioCharacter(name="bare", level=cell.char_level,
                          skills={cell.skill_name: cell.skill_level}), gd)
    assert not is_winnable(bare, gd, "critter")

    # The fixed census state equips iron_blade and CAN win.
    geared = census_state("trinket_gear", cell, gd)
    assert geared.equipment.get("weapon_slot") == "iron_blade"
    assert is_winnable(geared, gd, "critter")

    assert classify_gap("trinket_gear", cell, gd) is GapClass.PLANNER_BUG


def test_classify_gap_combat_blocked_survives_geared_loadout_against_overleveled_monster() -> None:
    """A real near_term_gear loadout (iron_blade, attack 50 at the cell's
    level) is still nowhere near enough to beat cow (level 30, 2000 HP, 200
    attack) — COMBAT_BLOCKED must survive the gear fix for a genuinely
    over-leveled dropper, pinning that census_state does not silently flip
    every combat leaf to reachable regardless of the opponent."""
    gd = GameData()
    gd._item_stats = {
        "beast_armor": _craftable("beast_armor", "gearcrafting", 5),
        "beast_hide": _mat("beast_hide"),
        "iron_blade": ItemStats(code="iron_blade", level=1, type_="weapon",
                                subtype="", attack={"fire": 50}),
    }
    gd._crafting_recipes = {"beast_armor": {"beast_hide": 2}}
    gd._resource_drops = {"blade_vein": "iron_blade"}
    gd._monster_locations = {"cow": (1, 0)}
    gd._monster_level = {"cow": 30}
    gd._monster_hp = {"cow": 2000}
    gd._monster_attack = {"cow": {"earth": 200}}
    gd._monster_drops = {"cow": [("beast_hide", 10, 1, 1)]}
    _fill_monster_defaults(gd)
    cell = _cell()

    geared = census_state("beast_armor", cell, gd)
    assert geared.equipment.get("weapon_slot") == "iron_blade"
    assert not is_winnable(geared, gd, "cow")

    assert classify_gap("beast_armor", cell, gd) is GapClass.COMBAT_BLOCKED
