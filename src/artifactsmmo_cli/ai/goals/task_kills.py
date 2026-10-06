"""TaskKillsGoal: one more kill toward the held monsters task (Phase 5-2c-iii-c).

The step of the task objective (`tiers.meta_goal.ReachTaskOutcome`). It is the
task's counterpart to `GrindCharacterXPGoal`, and the difference is the measure:
a grind wants character XP, a task wants its count. A task monster far below the
character pays no XP (the server's zero-XP band) yet every kill still counts, so
the grind cannot serve it and this goal must — live 2026-10-05, R2D2 `ogre`
0/327, Lor `spider` 0/206 and C3P0 `pig` 5/104 were held for 15 days with no
task fight. `FightAction._is_task_fight` is what lets that fight plan.

Constructed fresh each cycle at the current count, like the grind at the current
XP: one kill satisfies it, and the intention keeps re-planning it across the
task's turn. Its repr carries only the task monster, so the commitment survives
the count moving.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

PRIORITY = 30.0
"""The grind's floor (`grind_character_xp.PRIORITY_FLOOR`): a task turn is a
fallback-band intention like any walk alternative, ordered by the turn order,
not by value."""


class TaskKillsGoal(Goal):
    """Kill the held task's monster once more."""

    def __init__(self, task_code: str, initial_progress: int) -> None:
        self._task_code = task_code
        self._initial_progress = initial_progress

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else PRIORITY

    def is_satisfied(self, state: WorldState) -> bool:
        """One kill landed, or the task is no longer this one, or its count is
        met (the turn-in belongs to `CompleteTaskGoal`)."""
        return (state.task_code != self._task_code
                or state.task_progress >= state.task_total
                or state.task_progress > self._initial_progress)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_progress": self._initial_progress + 1}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        """The task monster's fight, HP recovery, and the loadout swap aimed at
        that monster — the grind's set, keyed on the task monster."""
        return [action for action in actions
                if (isinstance(action, FightAction) and action.monster_code == self._task_code)
                or "recovery" in action.tags
                or ("equip" in action.tags
                    and getattr(action, "target_monster_code", None) == self._task_code)]

    def serialize(self) -> dict[str, object]:
        return {"type": "TaskKillsGoal", "task_code": self._task_code,
                "initial_progress": self._initial_progress}

    def __repr__(self) -> str:
        return f"TaskKills({self._task_code})"
