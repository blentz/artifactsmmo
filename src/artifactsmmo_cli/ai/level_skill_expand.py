"""Expand a LevelSkill plan step into one grind cycle's goal.

The LevelSkill action is a planner abstraction (its apply optimistically levels
the skill); at execution the player runs ONE cycle of the concrete grind — craft
one in-skill rung — and replans, exactly as the retired tree-level skill-grind
dispatch did. This picks the rung and builds the
skill_grind GatherMaterials goal; the caller plans it and executes its first leg.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState


def next_grind_goal(skill: str, state: WorldState,
                    game_data: GameData) -> GatherMaterialsGoal | None:
    """The skill_grind GatherMaterials goal for one grind cycle of `skill`, or
    None when the skill cannot be ground from the current level.

    Prefers a craftable in-skill rung (`skill_grind_target`); falls back to a
    gatherable in-skill resource (`best_gather_resource_drop`) for a gather
    skill whose lowest craftable rung is out of reach (e.g. alchemy at level 1,
    ground by gathering sunflower). Mirrors the retired tree-level skill-grind
    grind/no_grind arms."""
    rung = skill_grind_target(skill, state, game_data)
    if rung is None:
        rung = best_gather_resource_drop(
            skill, state.skills.get(skill, 1), game_data)
    if rung is None:
        return None
    bank = state.bank_items or {}
    held = state.inventory.get(rung, 0) + bank.get(rung, 0)
    return GatherMaterialsGoal(target_item=rung, needed={rung: held + 1},
                               skill_grind=True)
