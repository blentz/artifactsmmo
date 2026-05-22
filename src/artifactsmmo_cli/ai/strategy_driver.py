"""Tier-3 → planner bridge: map the strategy's chosen step to a parameterized
existing goal, selected at a fixed priority band.

Lives above goals/ and tiers/ (imports both) to avoid the goals→tiers cycle."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.world_state import WorldState

STRATEGY_BAND = 50.0
"""Fixed selection priority for the strategy-driven goal — tactical-pursuit band,
below survival/economy interrupts (HP 110, complete-task/bank-unlock 90,
deposit-full→80) and above the fallback grind."""

FALLBACK_BAND = 25.0
"""Fixed priority for the safety-net grind: above idle accept-task (20), below
the strategy band so it only drives when the strategy step won't plan."""


class MetaGoalAdapter(Goal):
    """Selects at a fixed priority but delegates all planning to an inner goal."""

    def __init__(self, inner: Goal, priority_band: float) -> None:
        self._inner = inner
        self._priority_band = priority_band

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return self._inner.value(state, game_data, history)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        return self._priority_band

    def is_satisfied(self, state: WorldState) -> bool:
        return self._inner.is_satisfied(state)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return self._inner.desired_state(state, game_data)

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return self._inner.relevant_actions(actions, state, game_data)

    @property
    def max_depth(self) -> int:
        return self._inner.max_depth

    def __repr__(self) -> str:
        return f"Strategy({self._inner!r})"


def strategy_goal(step: MetaGoal | None, state: WorldState, game_data: GameData,
                  priority_band: float, combat_monster: str | None) -> MetaGoalAdapter | None:
    """Map the strategy's chosen step to a parameterized inner goal."""
    inner: Goal | None = None
    if isinstance(step, ObtainItem):
        stats = game_data.item_stats(step.code)
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
        if slots:  # equippable gear → craft + equip
            inner = UpgradeEquipmentGoal(
                initial_equipment=state.equipment,
                committed_target=(step.code, slots[0]),
            )
        else:  # material/raw → obtain qty via gather/craft
            inner = GatherMaterialsGoal(target_item=step.code, needed={step.code: step.quantity})
    elif isinstance(step, ReachSkillLevel):
        inner = LevelSkillGoal(skill_name=step.skill, target_level=step.level)
    elif isinstance(step, ReachCharLevel):
        if combat_monster is None:
            return None
        inner = GrindCharacterXPGoal(target_monster=combat_monster, initial_xp=state.xp)
    if inner is None:
        return None
    return MetaGoalAdapter(inner, priority_band)
