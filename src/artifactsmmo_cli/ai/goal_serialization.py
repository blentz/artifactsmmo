"""Serialize/rehydrate the plan-bearing objective goals so a persisted plan can
resume after restart. Transient guard/means goals are not serializable here and
re-plan cold. GameData (and SkillXpCurve) are re-injected from the live arbiter,
never stored. See docs/superpowers/specs/2026-06-23-plan-cache-macro-learning-design.md."""

from typing import cast

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.craft_relief import CraftReliefGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal


def goal_to_dict(goal: object) -> dict[str, object] | None:
    """The goal's serialized form, or None when it is not a plan-bearing type."""
    serialize = getattr(goal, "serialize", None)
    if serialize is None:
        return None
    result: dict[str, object] = serialize()
    return result


def goal_from_dict(data: dict[str, object], game_data: GameData | None) -> Goal:
    """Rehydrate a plan-bearing goal, injecting live GameData where needed."""
    t = data["type"]
    if t == "GatherMaterialsGoal":
        return GatherMaterialsGoal(
            cast(str, data["target_item"]),
            cast(dict[str, int], data["needed"]))
    if t == "CraftReliefGoal":
        return CraftReliefGoal(
            cast(str, data["target_item"]),
            cast(int, data["initial_qty"]),
            cast(int, data["batch"]))
    if t == "PursueTaskGoal":
        return PursueTaskGoal(
            cast(str, data["task_code"]),
            cast(int, data["initial_progress"]),
            cast(int, data["batch"]))
    if t == "GrindCharacterXPGoal":
        return GrindCharacterXPGoal(
            cast(str, data["target_monster"]),
            cast(int, data["initial_xp"]))
    if t == "ReachSkillGoal":
        return ReachSkillGoal(
            cast(str, data["skill_name"]),
            cast(int, data["target_level"]))
    if t == "LevelSkillGoal":
        # COMPAT SHIM: a plan persisted before P3a Task 2 rehydrates as the new
        # ReachSkillGoal (which aims the planner-native LevelSkill action). The
        # old initial_skill_xp/xp_curve fields are dropped — ReachSkillGoal
        # satisfies purely on the skills-level snapshot, so they are unneeded.
        # Without this branch such a plan would hard-raise below on rehydrate.
        return ReachSkillGoal(
            cast(str, data["skill_name"]),
            cast(int, data["target_level"]))
    if t == "UpgradeEquipmentGoal":
        committed_raw = data["committed_target"]
        committed: tuple[str, str] | None = None
        if committed_raw is not None:
            pair = cast(list[str], committed_raw)
            committed = (pair[0], pair[1])
        return UpgradeEquipmentGoal(
            cast(dict[str, str | None], data["initial_equipment"]),
            committed)
    raise ValueError(f"unknown goal type for rehydration: {t}")
