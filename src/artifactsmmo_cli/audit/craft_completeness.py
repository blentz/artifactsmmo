"""Crafting-recipe planning-completeness census (spec docs/superpowers/specs/
2026-07-08-craft-planning-completeness-design.md).

Drives the REAL production planner at every craftable recipe across a
level/skill grid and classifies whether it can produce a directional plan.
Pure cores (grid/verdict/classifier) + a thin planner harness (`plan_craft`);
the generator/docs live in scripts/gen_craft_completeness.py."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState

CRAFT_AUDIT_BUDGET_SECONDS = 10.0
"""Per-cell planner budget — the arbiter's cheap first-pass value; keeps the
~1900-cell offline census bounded (CPU memo + node cap do the rest)."""


@dataclass(frozen=True)
class CraftCell:
    """One planner-drive point in the level/skill census grid for a recipe:
    a character level paired with a crafting-skill level at which to attempt
    `recipe`."""

    char_level: int
    skill_name: str
    skill_level: int


def craft_grid(recipe: str, game_data: GameData) -> list[CraftCell]:
    """The level/skill census cells for `recipe` (spec grid): 3 character
    levels (decade-tier nominal + boundary offsets, clamped [1,50]) x 2
    skill levels (under-skill `craft_level-5` clamped >=0, and at-skill
    `craft_level`) = up to 6 cells. `recipe`'s tier bucket is the decade its
    crafting_level falls into ((craft_level-1)//10+1, so crafting_level=10
    is the LAST level of tier 1, not the first of tier 2) — the boundary
    offsets `10*tier±2` straddle that decade line; for a tier-1 recipe
    (crafting_level<=9) the nominal cell is 1 (any starting character),
    while a decade-boundary recipe like crafting_level=10 gets nominal=10.
    Returns [] when `recipe` has no crafting recipe (not craftable)."""
    stats = game_data.item_stats(recipe)
    if stats is None or not stats.crafting_skill:
        return []
    craft_level = stats.crafting_level
    skill = stats.crafting_skill
    tier = (craft_level - 1) // 10 + 1
    nominal = 1 if craft_level <= 9 else 10 * tier
    char_levels = sorted({
        max(1, min(50, lvl))
        for lvl in (nominal, 10 * tier - 2, 10 * tier + 2)
    })
    skill_levels = sorted({max(0, craft_level - 5), craft_level})
    return [CraftCell(cl, skill, sl)
            for cl in char_levels for sl in skill_levels]


def plan_craft(recipe: str, state: WorldState,
               game_data: GameData) -> list[Action]:
    """The plan the production planner produces for obtaining `recipe` from
    `state` — the exact obtain-X path the tree's gear branch uses, aimed at
    any recipe. task_exchange_min_coins=0: task funding is irrelevant to
    craft planning."""
    objective = CharacterObjective.from_game_data(game_data)
    actions = build_actions(
        game_data, state, objective,
        bank_accessible=True, task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item=recipe, needed={recipe: 1})
    return GOAPPlanner().plan(state, goal, actions, game_data,
                              budget_seconds=CRAFT_AUDIT_BUDGET_SECONDS)
