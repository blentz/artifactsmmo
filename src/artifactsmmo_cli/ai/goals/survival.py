"""Survival goals: HP restoration and inventory management."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

MIN_FREE_SLOTS = 5


class RestoreHPGoal(Goal):
    """Restore HP to full. Urgency spikes when HP is low."""

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return (1.0 - state.hp_percent) * 100.0

    def is_satisfied(self, state: WorldState) -> bool:
        return state.hp >= state.max_hp

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"hp": state.max_hp}

    def __repr__(self) -> str:
        return "RestoreHP"


class DepositInventoryGoal(Goal):
    """Deposit inventory to the bank as it fills up.

    Value ramps from 50% used (0) to 100% used (80). Satisfied below 30% used
    so a single deposit drains a meaningful chunk before the goal drops out
    and gathering resumes.
    """

    _RAMP_START = 0.5   # fraction used below which the goal is inactive
    _RESET_TO = 0.3     # fraction used at/below which the goal is satisfied
    _MAX_VALUE = 80.0   # value at 100% used; outranks FarmItems(35) once near cap

    def __init__(self, bank_accessible: bool = True) -> None:
        self._bank_accessible = bank_accessible

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not self._bank_accessible or state.inventory_max == 0:
            return 0.0
        if self.is_satisfied(state):
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        if used_fraction < self._RAMP_START:
            return 0.0
        # Linear ramp from _RAMP_START → 1.0 mapped onto 0 → _MAX_VALUE.
        return (used_fraction - self._RAMP_START) / (1.0 - self._RAMP_START) * self._MAX_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        if state.inventory_max == 0:
            return True
        return state.inventory_used / state.inventory_max <= self._RESET_TO

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # Target the satisfaction threshold so the planner stops once the
        # bank visit drained enough.
        target_used = int(state.inventory_max * self._RESET_TO)
        return {"inventory_used": target_used}

    def __repr__(self) -> str:
        return "DepositInventory"
