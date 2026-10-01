"""Is there an open rung to grind a skill from here? The one predicate the walk's
skill-gate sub-task, the orphan-skill roots and the open-rung census ask
(Phase 2d; it used to be the `LevelSkill` macro's applicability)."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.tiers.skill_grind_target import has_grind_target
from artifactsmmo_cli.ai.world_state import WorldState


def skill_is_grindable(skill: str, target_level: int, state: WorldState,
                       game_data: GameData) -> bool:
    """Can `skill` be ground toward `target_level` from here? False once the
    skill is there. A skill is grindable via EITHER a gatherable resource
    usable now (`best_gather_resource_drop`: gathering grants skill xp, the
    arm that lets alchemy 1 grind before its lowest craftable rung) OR a
    craftable in-skill rung (`has_grind_target`). The cheap arm runs first:
    `has_grind_target` walks recipes and recursive obtainability.

    The "an open rung exists" predicate every grind question asks."""
    current = state.skills.get(skill, 1)
    if current >= target_level:
        return False
    return (best_gather_resource_drop(skill, current, game_data) is not None
            or has_grind_target(skill, state, game_data))
