"""LevelSkill action: optimistic skill-level apply so CraftAction's gate is
satisfiable in-search. Phase 1 of the LevelSkill epic (spec 2026-07-11)."""

import dataclasses

import pytest

from artifactsmmo_cli.ai.actions.level_skill import (
    PER_LEVEL_COST,
    LevelSkill,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.world_state import WorldState


def _state(gd: GameData, skills: dict[str, int]) -> WorldState:
    # scenario_state builds a valid WorldState with all required fields
    # (inventory slots, projected_skill_xp_delta, etc.) — never hand-build.
    return scenario_state(ScenarioCharacter(name="t", level=5, skills=skills), gd)


def _gd_with_grind_rung() -> GameData:
    """gearcrafting: target 'widget' (level 5) + a grind rung 'trinket'
    (level 1) crafted from a located gatherable ore, so skill_grind_target
    finds a feasible rung."""
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=5),
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    return gd


def test_apply_sets_skill_to_target() -> None:
    gd = _gd_with_grind_rung()
    state = _state(gd, {"gearcrafting": 1})
    out = LevelSkill(skill="gearcrafting", target_level=5).apply(state, gd)
    assert out.skills["gearcrafting"] == 5
    # every other field preserved
    assert dataclasses.replace(out, skills=state.skills) == state


def test_applicable_when_under_skill_and_grindable() -> None:
    gd = _gd_with_grind_rung()
    action = LevelSkill(skill="gearcrafting", target_level=5)
    assert action.is_applicable(_state(gd, {"gearcrafting": 1}), gd) is True


def test_not_applicable_when_already_at_target() -> None:
    gd = _gd_with_grind_rung()
    action = LevelSkill(skill="gearcrafting", target_level=5)
    assert action.is_applicable(_state(gd, {"gearcrafting": 5}), gd) is False


def test_not_applicable_when_no_grind_rung() -> None:
    """No craftable at/below current in the skill → not grindable from here."""
    gd = GameData()
    gd._item_stats = {
        "lonely": ItemStats(code="lonely", level=10, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=10),
    }
    gd._crafting_recipes = {"lonely": {"gear_ore": 2}}
    action = LevelSkill(skill="gearcrafting", target_level=10)
    assert action.is_applicable(_state(gd, {"gearcrafting": 5}), gd) is False


def test_cost_positive_and_monotone_in_gap() -> None:
    gd = _gd_with_grind_rung()
    c_small = LevelSkill("gearcrafting", 2).cost(_state(gd, {"gearcrafting": 1}), gd)
    c_big = LevelSkill("gearcrafting", 5).cost(_state(gd, {"gearcrafting": 1}), gd)
    assert c_small > 0
    assert c_big > c_small
    # no-curve fallback is exactly gap * PER_LEVEL_COST
    assert c_big == (5 - 1) * PER_LEVEL_COST


def test_cost_uses_curve_when_observed() -> None:
    gd = _gd_with_grind_rung()
    curve = SkillXpCurve(observed={1: 100, 2: 150, 3: 225, 4: 340})
    action = LevelSkill("gearcrafting", 5, xp_curve=curve)
    assert action.cost(_state(gd, {"gearcrafting": 1}), gd) > 0


def test_repr_uses_arrow() -> None:
    assert repr(LevelSkill("gearcrafting", 5)) == "LevelSkill(gearcrafting→5)"


def test_execute_raises_direct_call_guard() -> None:
    gd = _gd_with_grind_rung()
    with pytest.raises(RuntimeError, match="player skill-grind hook"):
        LevelSkill("gearcrafting", 5).execute(_state(gd, {"gearcrafting": 1}), None)
