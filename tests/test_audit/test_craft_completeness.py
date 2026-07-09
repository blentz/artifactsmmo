"""Craft-planning completeness core (spec 2026-07-08). plan_craft drives the
REAL planner at one recipe via the production obtain-X path."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.audit.craft_completeness import plan_craft
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import scenario_state, ScenarioCharacter

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
