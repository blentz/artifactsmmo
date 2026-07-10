"""Craft-completeness census engine (spec 2026-07-08 Phase 2). Drives the
Phase-1 pure cores (census_state -> plan_craft -> craft_cell_verdict ->
classify_gap) over every craftable recipe's grid cells and records a flat,
render-ready CellResult per cell. No decision logic lives here — it is the
orchestration layer between the proven cores and the doc renderers."""

from collections.abc import Callable
from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_completeness import (
    CraftCell,
    census_state,
    classify_gap,
    craft_cell_verdict,
    craft_grid,
    plan_craft,
)


@dataclass(frozen=True)
class CellResult:
    """One census outcome: a recipe attempted at one (char_level, skill_level)
    cell. `passed`/`reason` mirror the CraftVerdict; `gap` is the GapClass
    value string on failure (None on pass)."""

    recipe: str
    skill: str
    craft_level: int
    char_level: int
    skill_level: int
    passed: bool
    reason: str
    gap: str | None


def run_cell(recipe: str, cell: CraftCell, game_data: GameData) -> CellResult:
    """Drive the Phase-1 cores for one recipe/cell and record the outcome.
    The recipe's craft_level is read from game data (used only for grouping/
    tier in the renderers)."""
    stats = game_data.item_stats(recipe)
    if stats is None or not stats.crafting_skill:
        raise ValueError(f"{recipe} is not a craftable recipe")
    state = census_state(cell, game_data)
    plan = plan_craft(recipe, state, game_data)
    verdict = craft_cell_verdict(recipe, plan, game_data)
    gap = None if verdict.passed else classify_gap(recipe, cell, game_data).value
    return CellResult(
        recipe=recipe,
        skill=cell.skill_name,
        craft_level=stats.crafting_level,
        char_level=cell.char_level,
        skill_level=cell.skill_level,
        passed=verdict.passed,
        reason=verdict.reason,
        gap=gap,
    )


def craftable_recipes(game_data: GameData) -> list[str]:
    """Every item with a non-empty crafting recipe, sorted deterministically
    by (craft skill, craft level, code)."""
    out: list[str] = []
    for code, stats in game_data.all_item_stats.items():
        if stats.crafting_skill and game_data.crafting_recipe(code):
            out.append(code)
    return sorted(
        out,
        key=lambda c: (
            game_data.item_stats(c).crafting_skill,  # type: ignore[union-attr]
            game_data.item_stats(c).crafting_level,  # type: ignore[union-attr]
            c,
        ),
    )


def run_census(
    game_data: GameData,
    recipes: list[str],
    progress: Callable[[int, int, str], None] | None = None,
) -> list[CellResult]:
    """Run the census over `recipes`: for each, every grid cell. The caller
    supplies the recipe list (the generator passes `craftable_recipes(gd)`;
    tests pass a tiny explicit list). `progress(done, total, recipe)` is called
    after each recipe if supplied."""
    results: list[CellResult] = []
    for i, recipe in enumerate(recipes):
        for cell in craft_grid(recipe, game_data):
            results.append(run_cell(recipe, cell, game_data))
        if progress is not None:
            progress(i + 1, len(recipes), recipe)
    return results
