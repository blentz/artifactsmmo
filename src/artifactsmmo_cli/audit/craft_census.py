"""Craft-completeness census engine (spec 2026-07-08 Phase 2). Drives the
Phase-1 pure cores (census_state -> plan_craft -> craft_cell_verdict ->
classify_gap) over every craftable recipe's grid cells and records a flat,
render-ready CellResult per cell. No decision logic lives here — it is the
orchestration layer between the proven cores and the doc renderers."""

from collections.abc import Callable
from dataclasses import dataclass, replace

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.loadout_win import winning_loadout
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.craft_completeness import (
    CraftCell,
    CraftVerdict,
    advances_a_closure_grind,
    advances_a_heal_prep,
    census_state,
    classify_gap,
    craft_cell_verdict,
    craft_grid,
    event_cells,
    first_work_leg,
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
    events: frozenset[str] = frozenset()
    fights: tuple[tuple[str, str], ...] = ()
    """On a pass, each monster the plan fights, in plan order, with what wins
    it: `BARE`, the winning potion loadout joined by `+`, or `LOSES`."""


def run_cell(recipe: str, cell: CraftCell, game_data: GameData) -> CellResult:
    """Drive the Phase-1 cores for one recipe/cell and record the outcome.
    The recipe's craft_level is read from game data (used only for grouping/
    tier in the renderers)."""
    stats = game_data.item_stats(recipe)
    if stats is None or not stats.crafting_skill:
        raise ValueError(f"{recipe} is not a craftable recipe")
    # The cell's events surface their spawns for the whole cell, as
    # `seed_offline` does live, and the event-free world comes back after.
    world_events = game_data.active_event_codes
    game_data.active_event_codes = set(cell.events)
    try:
        state = census_state(recipe, cell, game_data)
        plan = plan_craft(recipe, state, game_data)
        verdict = craft_cell_verdict(recipe, plan, game_data)
        work = first_work_leg(plan)
        if not verdict.passed and work is not None and (
                advances_a_closure_grind(recipe, work, state, game_data)
                or advances_a_heal_prep(work, plan, state, game_data)):
            verdict = CraftVerdict(True, "")
        gap = None if verdict.passed else classify_gap(recipe, cell, game_data).value
        fights = fight_needs(plan, state, game_data) if verdict.passed else ()
    finally:
        game_data.active_event_codes = world_events
    return CellResult(
        recipe=recipe,
        skill=cell.skill_name,
        craft_level=stats.crafting_level,
        char_level=cell.char_level,
        skill_level=cell.skill_level,
        passed=verdict.passed,
        reason=verdict.reason,
        gap=gap,
        events=cell.events,
        fights=fights,
    )


BARE = "bare"
LOSES = "loses"


def fight_needs(plan: list[Action], state: WorldState,
                game_data: GameData) -> tuple[tuple[str, str], ...]:
    """What wins each monster `plan` fights, from full HP (see
    `CellResult.fights`): the bare stats, else the first winning potion
    loadout (`loadout_win.winning_loadout`, the drop gate's own answer)."""
    rested = replace(state, hp=state.max_hp)
    out: list[tuple[str, str]] = []
    for monster in dict.fromkeys(a.monster_code for a in plan if isinstance(a, FightAction)):
        if is_winnable(rested, game_data, monster):
            out.append((monster, BARE))
            continue
        loadout = winning_loadout(rested, game_data, monster)
        out.append((monster, "+".join(loadout) if loadout is not None else LOSES))
    return tuple(out)


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
    tests pass a tiny explicit list). Event-active cells follow the
    event-free grid (`event_cells`). `progress(done, total, recipe)` is called
    after each recipe if supplied."""
    results: list[CellResult] = []
    for i, recipe in enumerate(recipes):
        for cell in craft_grid(recipe, game_data) + event_cells(recipe, game_data):
            results.append(run_cell(recipe, cell, game_data))
        if progress is not None:
            progress(i + 1, len(recipes), recipe)
    return results
