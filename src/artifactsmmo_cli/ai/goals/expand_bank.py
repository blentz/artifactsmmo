"""ExpandBankGoal: buy more bank slots when bank fills up."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

_TRIGGER_FILL = 0.95   # value() activates at or above this fill ratio
_SATISFIED_FILL = 0.90  # is_satisfied is True when below this fill ratio


def _bank_fill_known(state: WorldState) -> int | None:
    """Return count of items in bank, or None if bank state is unknown."""
    if state.bank_items is None:
        return None
    return len(state.bank_items)


class ExpandBankGoal(Goal):
    """Buy a bank expansion when current bank is near full and gold is sufficient."""

    def __init__(self, bank_accessible: bool = True, game_data: GameData | None = None) -> None:
        self._bank_accessible = bank_accessible
        # Stashed so is_satisfied (which the Goal protocol calls with state
        # only) can use the ACTUAL bank capacity instead of a fixed slot count.
        self._game_data = game_data

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not self._bank_accessible:
            return 0.0
        if self.is_satisfied(state):
            return 0.0
        used = _bank_fill_known(state)
        if used is None or game_data._bank_capacity == 0:
            return 0.0
        fill = used / game_data._bank_capacity
        if fill < _TRIGGER_FILL:
            return 0.0
        if state.gold < game_data._next_expansion_cost:
            return 0.0
        return 40.0

    def is_satisfied(self, state: WorldState) -> bool:
        # Unknown bank state → treat as satisfied (no urgency to expand)
        used = _bank_fill_known(state)
        if used is None:
            return True
        # Read capacity from the projected WorldState so the planner can flip
        # this goal False→True by simulating BuyBankExpansionAction.apply
        # (which mints +BANK_EXPANSION_SLOTS into state.bank_capacity). Falling
        # back to game_data._bank_capacity preserves the cycle-time snapshot
        # when the projection hasn't run yet (None == "use API as-of-now").
        if state.bank_capacity is not None:
            capacity = state.bank_capacity
        elif self._game_data is not None:
            capacity = self._game_data._bank_capacity
        else:
            capacity = 0
        if capacity <= 0:
            return True
        return used < capacity * _SATISFIED_FILL

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"bank_capacity": game_data._bank_capacity + 1}

    def __repr__(self) -> str:
        return "ExpandBank"
