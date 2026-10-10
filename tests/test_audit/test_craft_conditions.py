"""The conditions census (USER 2026-10-10: "find the loadouts and conditions
required to successfully plan each item"; docs/PLAN_drop_fight_loadout.md
increment 2)."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import BARE, LOSES, CellResult, fight_needs, run_cell
from artifactsmmo_cli.audit.craft_completeness import (
    ARMORY_BAG,
    HELD_LEAF_QTY,
    KEYS_HELD,
    CraftCell,
    GapClass,
    _best_gear,
    census_state,
    classify_gap,
    crossing_keys,
    funding_plan,
    plan_craft,
    unreachable_leaves,
)
from artifactsmmo_cli.audit.craft_conditions import (
    GOLD_GRANT,
    ConditionsResult,
    climb,
    ladder,
    render_conditions,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_the_ladder_grants_one_condition_per_rung() -> None:
    gd = _gd()
    rungs = ladder("steel_armor", gd)  # gearcrafting 20, no event leaf
    names = [name for name, _, _ in rungs]
    assert names[:5] == ["cell", "skills", "gold", "achievements", "gear"]
    sweep = ["-10", "-5", "+5", "+10", "+15", "+20", "+25", "+30"]
    assert names[5:] == ([f"level{k}" for k in sweep] + ["keys"] + [f"keys{k}" for k in sweep]
                         + ["grey"] + [f"grey{k}" for k in sweep])
    cell, skills, gold, achieved, geared = (c for _, c, _ in rungs[:5])
    assert cell == CraftCell(20, "gearcrafting", 20)
    assert skills.skills_at_level and not cell.skills_at_level
    assert gold.gold == GOLD_GRANT and skills.gold == 0
    assert achieved == gold and geared.geared and not achieved.geared
    assert [unlocked for _, _, unlocked in rungs] == [False] * 3 + [True] * (len(rungs) - 3)
    assert [c.char_level for _, c, _ in rungs[5:13]] == [10, 15, 25, 30, 35, 40, 45, 50]
    assert all(c.skill_level == 20 and c.geared for _, c, _ in rungs[5:])
    assert all(c.keys for _, c, _ in rungs[13:]) and not any(c.keys for _, c, _ in rungs[:13])
    assert all(c.grey for _, c, _ in rungs[22:]) and not any(c.grey for _, c, _ in rungs[:22])
    # an event-only leaf adds the events rung
    names = [name for name, _, _ in ladder("conjurer_cloak", gd)]
    assert names[3] == "events"
    assert "portal_demon" in ladder("conjurer_cloak", gd)[3][1].events


def test_a_granted_cell_is_skilled_and_funded() -> None:
    gd = _gd()
    state = census_state("steel_armor", CraftCell(20, "gearcrafting", 15, skills_at_level=True,
                                                  gold=500), gd)
    assert state.skills["alchemy"] == 20 and state.skills["gearcrafting"] == 15
    assert state.gold == 500


def test_the_climb_stops_at_the_first_rung_that_plans() -> None:
    gd = _gd()
    seen: list[CraftCell] = []

    def run(recipe: str, cell: CraftCell, _gd: GameData) -> CellResult:
        seen.append(cell)
        return CellResult(recipe, "gearcrafting", 20, cell.char_level, cell.skill_level,
                          cell.gold > 0, "", None if cell.gold > 0 else "combat_blocked")

    with patch("artifactsmmo_cli.audit.craft_conditions.run_cell", run):
        result = climb("steel_armor", gd, gd)
        assert result.rung == "gold" and len(seen) == 3

        def never(recipe: str, cell: CraftCell, _gd: GameData) -> CellResult:
            return CellResult(recipe, "gearcrafting", 20, cell.char_level, cell.skill_level,
                              False, "empty", "combat_blocked")

    with patch("artifactsmmo_cli.audit.craft_conditions.run_cell", never):
        result = climb("steel_armor", gd, gd)
        assert result.rung is None and result.result.char_level == 50


def test_fight_needs_name_what_wins() -> None:
    """The real slime_shield chain at the skills rung: the sheep falls bare,
    king_slime to a minor health potion (live data, 2026-10-10)."""
    gd = _gd()
    result = climb("slime_shield", gd, gd)
    assert result.rung == "skills"
    assert dict(result.result.fights) == {"king_slime": "minor_health_potion", "sheep": BARE}


def test_a_fight_no_loadout_wins_is_named() -> None:
    gd = _gd()
    state = census_state("cheese", CraftCell(1, "cooking", 1), gd)
    assert fight_needs([], state, gd) == ()
    plan = [FightAction(monster_code=m, locations=frozenset({(0, 0)}))
            for m in ("chicken", "red_dragon", "chicken")]
    assert fight_needs(plan, state, gd) == (("chicken", BARE), ("red_dragon", LOSES))


def test_the_report() -> None:
    planned = ConditionsResult("a", "cell", CellResult("a", "mining", 1, 1, 1, True, "", None,
                                                       fights=(("cow", BARE),)))
    unplanned = ConditionsResult("b", None, CellResult("b", "mining", 5, 50, 5, False, "empty",
                                                       "combat_blocked"))
    line = summary_line([planned, unplanned])
    assert line == "2 recipes; planned 1 (cell 1); unplanned 1 (combat_blocked 1)"
    doc = render_conditions([planned, unplanned])
    assert "| a | mining | 1 | cell | 1 | cow: bare |" in doc
    assert "| b | mining | 5 | **none: combat_blocked** | 50 | - |" in doc


def test_a_non_recipe_has_no_ladder() -> None:
    with pytest.raises(ValueError, match="not a craftable recipe"):
        ladder("copper_ore", _gd())


def test_a_currency_the_grey_policy_refuses_is_no_planner_bug() -> None:
    """At gearcrafting 25 every recipe the tailor's cloth feeds is obsolete, so
    the grey-farm policy refuses wool, cloth's currency: steel_armor is a
    policy limit, not a planner bug."""
    gd = _gd()
    cell = CraftCell(50, "gearcrafting", 25, skills_at_level=True)
    assert classify_gap("steel_armor", cell, gd) is GapClass.GREY_FARM_SUPPRESSED


# --- increment 3: funding, achievements, gear, keys, grey, held -------------

def _achieved() -> GameData:
    bundle = json.loads(BUNDLE.read_text())
    return GameData.from_cache_bundle(bundle, completed_achievements=frozenset(
        str(a["code"]) for a in bundle["achievements"]))


def test_a_task_coin_leaf_plans_through_production_funding() -> None:
    """iron_axe needs jasper_crystal, sold for tasks_coin at the
    tasks_trader (achievement-gated): the gather declines, production funds
    the coin (`ReachCurrencyGoal`), and the cell passes on that plan."""
    gd = _achieved()
    cell = CraftCell(10, "weaponcrafting", 10, skills_at_level=True, gold=GOLD_GRANT)
    state = census_state("iron_axe", cell, gd)
    assert plan_craft("iron_axe", state, gd) == []
    funding = funding_plan("iron_axe", state, gd)
    assert funding and repr(funding[0]) == "AcceptTask"
    assert run_cell("iron_axe", cell, gd).passed
    assert funding_plan("copper_bar", census_state("copper_bar", CraftCell(1, "mining", 1), gd), gd) == []


def test_the_geared_cell_owns_the_catalogue_but_not_the_recipe() -> None:
    gd = _gd()
    cell = CraftCell(20, "gearcrafting", 20, geared=True)
    state = census_state("slime_shield", cell, gd)
    assert state.equipment["shield_slot"] == "slime_shield"  # the best shield is worn
    assert "slime_shield" not in state.inventory              # but never held to "make"
    assert state.inventory.get("iron_sword") == 2
    assert state.inventory_max == ARMORY_BAG


def test_the_keys_cell_holds_every_crossing_key_but_the_recipe() -> None:
    gd = _gd()
    keys = crossing_keys(gd)
    assert {"sonnengott_key", "cultist_cloak"} <= keys and "gold" not in keys
    state = census_state("cultist_cloak", CraftCell(40, "gearcrafting", 40, keys=True), gd)
    assert state.inventory["sonnengott_key"] == KEYS_HELD
    assert "cultist_cloak" not in state.inventory


def test_unreachable_leaves_and_the_held_grant() -> None:
    gd = _achieved()
    cell = ladder("cultist_boots", gd)[-1][1]  # the top: every grant, its events live
    assert cell.grey and cell.keys and cell.events
    assert unreachable_leaves("cultist_boots", cell, gd) == {"enchanted_fabric"}
    held = census_state("cultist_boots", replace(cell, held=frozenset({"enchanted_fabric"})), gd)
    assert held.inventory["enchanted_fabric"] == HELD_LEAF_QTY
    # a grey cell licenses the grey-suppressed leaf the plain cell reports
    top = ladder("cultist_cloak", gd)[-1][1]
    assert "red_cloth" in unreachable_leaves("cultist_cloak", replace(top, grey=False), gd)
    assert "red_cloth" not in unreachable_leaves("cultist_cloak", top, gd)


def test_a_recipe_no_rung_plans_is_named_by_its_held_leaves() -> None:
    """cultist_boots: enchanted_coin (bought enchanted_fabric) is a raid
    reward no route produces; the ladder's last resort names it."""
    gd = _gd()
    result = climb("cultist_boots", gd, _achieved())
    assert result.rung == "held:enchanted_fabric" and result.result.passed


def test_the_held_resort_that_still_fails_stays_unplanned(monkeypatch: pytest.MonkeyPatch) -> None:
    gd = _gd()

    def never(recipe: str, cell: CraftCell, _gd: GameData) -> CellResult:
        return CellResult(recipe, "gearcrafting", 20, cell.char_level, cell.skill_level,
                          False, "empty", "combat_blocked")

    monkeypatch.setattr("artifactsmmo_cli.audit.craft_conditions.run_cell", never)
    monkeypatch.setattr("artifactsmmo_cli.audit.craft_conditions.unreachable_leaves",
                        lambda *a: frozenset())
    assert climb("steel_armor", gd, gd).rung is None


def test_the_catalogue_best_gear_is_suppliable_and_level_capped() -> None:
    gd = _gd()
    gear = _best_gear(30, gd)
    assert gear["weapon_slot"] == "death_knight_sword"
    assert all(gd.item_stats(code).level <= 30 for code in gear.values())
    assert "novice_guide" not in gear.values()  # fixed supply, not suppliable
