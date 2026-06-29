"""ExpandBankGoal: buy more bank slots when bank fills up."""

from artifactsmmo_cli.ai.bank_expansion_timing import should_expand_bank
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loadout_profiles import active_bank_space_cost
from artifactsmmo_cli.ai.progression_reserve import reserve_floor
from artifactsmmo_cli.ai.world_state import WorldState

# value() activates at or above a 95/100 fill ratio (exact integer threshold,
# evaluated by should_expand_bank's cross-multiply — no float).
_TRIGGER_FILL_NUM = 95
_TRIGGER_FILL_DEN = 100
_SATISFIED_FILL = 0.90  # is_satisfied is True when below this fill ratio


def _bank_fill_known(state: WorldState) -> int | None:
    """Return count of items in bank, or None if bank state is unknown."""
    if state.bank_items is None:
        return None
    return len(state.bank_items)


class ExpandBankGoal(Goal):
    """Buy a bank expansion when current bank is near full and gold is sufficient."""

    def __init__(
        self,
        bank_accessible: bool = True,
        game_data: GameData | None = None,
        history: LearningStore | None = None,
        combat_monster: str | None = None,
        gather_skills: frozenset[str] = frozenset(),
    ) -> None:
        self._bank_accessible = bank_accessible
        # Stashed so is_satisfied (which the Goal protocol calls with state
        # only) can use the ACTUAL bank capacity instead of a fixed slot count.
        self._game_data = game_data
        # Active-profile context for the used-floor calculation (Task 4).
        # When history is None the floor is skipped (backwards-compatible).
        self._history = history
        self._combat_monster = combat_monster
        self._gather_skills = gather_skills

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        # history param is the base-Protocol signature; this goal uses self._history
        # (stashed at construction).
        if not self._bank_accessible:
            return 0.0
        if self.is_satisfied(state):
            return 0.0
        used = _bank_fill_known(state)
        if used is None or game_data.bank_capacity == 0:
            return 0.0
        # Raise `used` to a floor set by the active-profile bank-space demand.
        # Proven by Lean `shouldExpandBank_floor_preserves`: max(used, cost) only
        # ADDS firing — it never suppresses an expansion that would have fired on
        # the real `used` alone, and it never breaks the reserve gate.
        # Guard matches is_satisfied(): both history and game_data must be present.
        if self._history is not None and self._game_data is not None:
            profile_cost = active_bank_space_cost(
                state, game_data, self._history,
                self._combat_monster, self._gather_skills,
            )
            used = max(used, profile_cost)
        # Fire only at/above the fill threshold AND when buying keeps gold at or
        # above the progression reserve floor. A bank expansion is never a
        # reserved gear code so buying=None applies the full floor.
        # Exact integer threshold, no float.
        if not should_expand_bank(
            used, game_data.bank_capacity, state.gold,
            game_data.next_expansion_cost, reserve_floor(state, game_data, None),
            _TRIGGER_FILL_NUM, _TRIGGER_FILL_DEN,
        ):
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
        # back to game_data.bank_capacity preserves the cycle-time snapshot
        # when the projection hasn't run yet (None == "use API as-of-now").
        if state.bank_capacity is not None:
            capacity = state.bank_capacity
        elif self._game_data is not None:
            capacity = self._game_data.bank_capacity
        else:
            capacity = 0
        if capacity <= 0:
            return True
        # Mirror the used-floor from value(): if active-profile gear would
        # consume more bank slots than currently used, raise the floor.
        # Requires both history and game_data to be available; when either is
        # absent the floor is a no-op (backwards-compatible).
        if self._history is not None and self._game_data is not None:
            profile_cost = active_bank_space_cost(
                state, self._game_data, self._history,
                self._combat_monster, self._gather_skills,
            )
            used = max(used, profile_cost)
        return used < capacity * _SATISFIED_FILL

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"bank_capacity": game_data.bank_capacity + 1}

    def __repr__(self) -> str:
        return "ExpandBank"
