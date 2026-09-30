"""The grind-cycle census (Phase 2d-L3): every class is reachable, and the
catalogue grid holds no cycle without an earning leg."""

import json
from pathlib import Path
from unittest.mock import patch

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit import grind_cycle_census
from artifactsmmo_cli.audit.grind_cycle_census import (
    GrindCycleGap,
    GrindCycleResult,
    classify,
    earned_skill,
    render_matrix,
    run_census,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_the_leg_that_earns_names_its_skill() -> None:
    gd = _gd()
    assert earned_skill(CraftAction(code="copper_bar"), gd) == "mining"
    assert earned_skill(GatherAction(resource_code="copper_rocks", locations=frozenset()), gd) == "mining"
    assert earned_skill(GatherAction(resource_code="no_such_rocks", locations=frozenset()), gd) is None
    assert earned_skill(CraftAction(code="no_such_item"), gd) is None
    assert earned_skill(FightAction(monster_code="chicken"), gd) is None


def test_every_class_is_reachable() -> None:
    gd = _gd()
    bar = CraftAction(code="copper_bar")
    assert classify("mining", [bar], gd) is GrindCycleGap.EARNS
    assert classify("gearcrafting", [bar], gd) is GrindCycleGap.EARNS_SUBSKILL
    assert classify("mining", None, gd) is GrindCycleGap.DECLINED
    assert classify("mining", [bar, FightAction(monster_code="chicken")], gd) is GrindCycleGap.NO_EARNING_LEG


def test_the_catalogue_grid_has_no_cycle_without_an_earning_leg() -> None:
    gd = _gd()
    with patch.object(grind_cycle_census, "SKILL_NAMES", ("mining",)):
        results = run_census(gd)
    assert results and all(r.gap is not GrindCycleGap.NO_EARNING_LEG for r in results)
    odd = GrindCycleResult("x", "mining", 1, ("Fight(chicken)",), GrindCycleGap.NO_EARNING_LEG)
    doc = render_matrix([*results, odd])
    assert "| x | mining | 1 | no_earning_leg | Fight(chicken) |" in doc
    assert summary_line([odd]) == "1 cells; earns 0, earns_subskill 0, declined 0, no_earning_leg 1"
