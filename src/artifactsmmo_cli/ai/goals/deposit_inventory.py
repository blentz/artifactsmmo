"""DepositInventoryGoal: deposit bankable inventory to the bank as it fills up."""

from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

MIN_FREE_SLOTS = 5


class DepositInventoryGoal(Goal):
    """Deposit bankable inventory to the bank as it fills up.

    Value ramps from 50% used (0) to 100% used (80). Satisfied when nothing
    remains to bank — the keep-set (task item, crafting materials, best weapon,
    task coins, HP consumables) may itself exceed any fixed fraction of the bag,
    so a percentage-based satisfaction rule could never be reached.
    """

    _RAMP_START = 0.5   # fraction used below which the goal is inactive
    _MAX_VALUE = 80.0   # value at 100% used; outranks FarmItems(35) once near cap

    def __init__(self, bank_accessible: bool = True, game_data: GameData | None = None) -> None:
        self._bank_accessible = bank_accessible
        self._game_data = game_data

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
        if state.inventory_max == 0 or self._game_data is None:
            return True
        # Satisfied once nothing remains to bank (see class docstring).
        return not select_bank_deposits(state, self._game_data)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # Post-deposit inventory_used (current minus everything bankable) — this
        # is exactly the satisfied state, keeping the A* heuristic reachable.
        bankable = (
            sum(qty for _, qty in select_bank_deposits(state, self._game_data))
            if self._game_data is not None else 0
        )
        return {"inventory_used": state.inventory_used - bankable}

    def __repr__(self) -> str:
        return "DepositInventory"
