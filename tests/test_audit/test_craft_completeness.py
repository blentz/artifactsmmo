"""Craft-planning completeness core (spec 2026-07-08). plan_craft drives the
REAL planner at one recipe via the production obtain-X path."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.audit.craft_completeness import CraftCell, craft_grid, plan_craft

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
