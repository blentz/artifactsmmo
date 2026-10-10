"""The conditions census (USER 2026-10-10: "find the loadouts and conditions
required to successfully plan each item"; docs/PLAN_drop_fight_loadout.md
increment 2)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import BARE, LOSES, CellResult, fight_needs
from artifactsmmo_cli.audit.craft_completeness import CraftCell, GapClass, census_state, classify_gap
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
    assert [name for name, _ in rungs] == [
        "cell", "skills", "gold", "level+5", "level+10", "level+15", "level+20", "level+25", "level+30"]
    cell, skills, gold = (c for _, c in rungs[:3])
    assert cell == CraftCell(20, "gearcrafting", 20)
    assert skills.skills_at_level and not cell.skills_at_level
    assert gold.gold == GOLD_GRANT and skills.gold == 0
    assert [c.char_level for _, c in rungs[3:]] == [25, 30, 35, 40, 45, 50]
    assert all(c.skill_level == 20 and c.gold == GOLD_GRANT for _, c in rungs[3:])
    # an event-only leaf adds the events rung
    names = [name for name, _ in ladder("conjurer_cloak", gd)]
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
        result = climb("steel_armor", gd)
        assert result.rung == "gold" and len(seen) == 3

        def never(recipe: str, cell: CraftCell, _gd: GameData) -> CellResult:
            return CellResult(recipe, "gearcrafting", 20, cell.char_level, cell.skill_level,
                              False, "empty", "combat_blocked")

    with patch("artifactsmmo_cli.audit.craft_conditions.run_cell", never):
        result = climb("steel_armor", gd)
        assert result.rung is None and result.result.char_level == 50


def test_fight_needs_name_what_wins() -> None:
    """The real slime_shield chain at the skills rung: the sheep falls bare,
    king_slime to a minor health potion (live data, 2026-10-10)."""
    gd = _gd()
    result = climb("slime_shield", gd)
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
