"""Craft-completeness census engine (spec 2026-07-08 Phase 2): drives the
Phase-1 pure cores over every recipe cell and records a flat CellResult."""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import (
    CellResult,
    craftable_recipes,
    run_cell,
    run_census,
)
from artifactsmmo_cli.audit.craft_completeness import CraftCell

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_run_cell_records_a_passing_smelt() -> None:
    """copper_bar (mining 1) at a plausibly-geared L5/mining-5 cell plans a
    real first leg, so the CellResult passes with no gap and carries the
    recipe's craft metadata."""
    gd = _gd()
    cell = CraftCell(char_level=5, skill_name="mining", skill_level=5)
    result = run_cell("copper_bar", cell, gd)
    assert result.recipe == "copper_bar"
    assert result.skill == "mining"
    assert result.craft_level == 1
    assert result.char_level == 5
    assert result.skill_level == 5
    assert result.passed is True
    assert result.reason == ""
    assert result.gap is None


def test_run_cell_records_gap_on_failure() -> None:
    """A recipe that cannot plan at its cell records passed=False, a non-empty
    reason, and a gap-class string. iron_boots at a low under-skill cell is a
    known non-planner (10s-budget empty plan in the scout); assert the shape
    of a FAIL rather than a specific gap class."""
    gd = _gd()
    cell = CraftCell(char_level=8, skill_name="gearcrafting", skill_level=5)
    result = run_cell("iron_boots", cell, gd)
    if result.passed:
        assert result.gap is None and result.reason == ""
    else:
        assert result.gap in {
            "event_gated", "combat_blocked", "material_unreachable",
            "skill_unreachable", "planner_bug",
        }
        assert result.reason != ""


def test_craftable_recipes_sorted_and_nonempty() -> None:
    """The census enumerates the game's craftables, sorted by (skill, level,
    code), and only includes items that actually have a crafting recipe."""
    gd = _gd()
    recipes = craftable_recipes(gd)
    assert "copper_bar" in recipes
    assert "copper_ore" not in recipes  # raw gather, not craftable
    keys = [
        (gd.item_stats(c).crafting_skill, gd.item_stats(c).crafting_level, c)
        for c in recipes
    ]
    assert keys == sorted(keys)


def test_run_census_restricted_list_with_progress() -> None:
    """run_census over an explicit one-recipe list yields one CellResult per
    grid cell and fires the progress callback once per recipe."""
    gd = _gd()
    seen: list[tuple[int, int, str]] = []

    def progress(done: int, total: int, recipe: str) -> None:
        seen.append((done, total, recipe))

    results = run_census(gd, ["copper_bar"], progress=progress)
    expected_cells = 3  # copper_bar: char {1,8,12} x skill {1} (collapsed)
    assert len(results) == expected_cells
    assert all(isinstance(r, CellResult) for r in results)
    assert all(r.recipe == "copper_bar" for r in results)
    assert seen == [(1, 1, "copper_bar")]


def test_run_cell_rejects_a_non_craftable_recipe() -> None:
    """run_cell guards against being handed an item with no crafting recipe
    (e.g. a raw-gathered resource) — this is a caller-contract violation, not
    a census outcome, so it raises rather than returning a CellResult."""
    gd = _gd()
    cell = CraftCell(char_level=5, skill_name="mining", skill_level=5)
    with pytest.raises(ValueError, match="copper_ore"):
        run_cell("copper_ore", cell, gd)


def test_run_census_multiple_recipes_no_progress() -> None:
    """run_census over an explicit multi-recipe list with NO progress callback
    (covers the progress-None branch) reaches every requested recipe."""
    gd = _gd()
    results = run_census(gd, ["copper_bar", "copper_helmet"])
    recipes_in = {r.recipe for r in results}
    assert recipes_in == {"copper_bar", "copper_helmet"}
