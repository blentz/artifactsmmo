"""ExpandBankGoal: buy more bank slots when bank fills up."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
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

    def __init__(self, bank_accessible: bool = True) -> None:
        self._bank_accessible = bank_accessible

    def value(self, state: WorldState, game_data: GameData) -> float:
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
        # Conservative threshold: 90% of an assumed default capacity of 30 slots.
        # (Goal.is_satisfied doesn't receive game_data, so we use a fixed slot count;
        # the value() method uses the actual game_data._bank_capacity for triggering.)
        return used < 27

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"bank_capacity": game_data._bank_capacity + 1}

    def __repr__(self) -> str:
        return "ExpandBank"
