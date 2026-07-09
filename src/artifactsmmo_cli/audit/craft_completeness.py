"""Crafting-recipe planning-completeness census (spec docs/superpowers/specs/
2026-07-08-craft-planning-completeness-design.md).

Drives the REAL production planner at every craftable recipe across a
level/skill grid and classifies whether it can produce a directional plan.
Pure cores (grid/verdict/classifier) + a thin planner harness (`plan_craft`);
the generator/docs live in scripts/gen_craft_completeness.py."""

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
