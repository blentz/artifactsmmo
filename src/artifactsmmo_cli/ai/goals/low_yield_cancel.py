"""LowYieldCancelGoal: cancel a task whose projected reward is worse than
alternatives, based on Phase G projections and scalarization.

Companion to (not replacement for) `TaskCancelGoal`, which only handles the
"target monster is too strong" case. This goal is strictly data-driven:
fires only when the learning store has enough samples to make a confident
projection AND a clear alternative beats the current task.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.projections import (
    LOW_YIELD_ALTERNATIVE_MARGIN,
    LOW_YIELD_CONFIDENCE_THRESHOLD,
    low_yield_cancel_fires,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Value returned when the goal fires (inlined from retired priorities.py).
LOW_YIELD_CANCEL = 70.0
"""Beats tactical pursuits (FarmItems=35, GatherMaterials=50, LevelSkill=55)
so a data-confirmed poor task is cancelled before continuing work."""

# Re-export under legacy names so existing importers (tests etc.) still work.
CONFIDENCE_THRESHOLD = LOW_YIELD_CONFIDENCE_THRESHOLD
"""Don't cancel until projection confidence >= this. Delegates to
LOW_YIELD_CONFIDENCE_THRESHOLD in learning/projections.py."""

ALTERNATIVE_MARGIN = LOW_YIELD_ALTERNATIVE_MARGIN
"""Cancel only when the alternative's scalar rate is at least this multiple
of the current task's rate. Delegates to LOW_YIELD_ALTERNATIVE_MARGIN in
learning/projections.py."""


class LowYieldCancelGoal(Goal):
    """Cancel an in-flight task when projection says alternatives pay more."""

    def __init__(self, taskmaster_location: tuple[int, int] | None = None) -> None:
        self._taskmaster_location = taskmaster_location

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if low_yield_cancel_fires(state, history):
            return LOW_YIELD_CANCEL
        return 0.0

    def is_satisfied(self, state: WorldState) -> bool:
        return not state.task_code or state.task_total == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": None, "task_total": 0}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        return [a for a in actions if isinstance(a, TaskCancelAction)]

    def __repr__(self) -> str:
        return "LowYieldCancel"
