"""ReachUnlockLevelGoal: drive character XP grinding to satisfy a learned
blocker that requires reaching a specific character level (e.g. the bank
unlock achievement needs level N to kill the gating monster).

Fires only when a blocker is known AND the character is still under the
required level. Priority sits above DepositInventory's ramp so the bot
pivots to combat instead of looping on locked-bank failures.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


PRIORITY_WHEN_BLOCKER_ACTIVE = 85.0
"""Above DepositInventory's max (80) and FarmItems (35+bonus) so the bot
clears the prerequisite first. Below RestoreHP critical (110) and the
hard survival floor."""


class ReachUnlockLevelGoal(Goal):
    """Grind character XP until state.level >= target_level."""

    def __init__(self, target_level: int, blocker_code: str = "bank") -> None:
        self._target_level = target_level
        self._blocker_code = blocker_code

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return self.priority(state, game_data, history)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if self._target_level <= 0:
            return 0.0
        return PRIORITY_WHEN_BLOCKER_ACTIVE

    def is_satisfied(self, state: WorldState) -> bool:
        return state.level >= self._target_level

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"level": self._target_level}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        """Any monster the character can actually beat + HP recovery."""
        result: list[Action] = []
        for action in actions:
            if isinstance(action, FightAction):
                ml = game_data.monster_level(action.monster_code)
                if ml > 0 and state.level >= ml - 1:
                    result.append(action)
            elif isinstance(action, (RestAction, UseConsumableAction)):
                result.append(action)
        return result

    def __repr__(self) -> str:
        return f"ReachUnlockLevel({self._target_level})"
