"""SurrenderCurrencyGoal: unequip every worn copy and deposit every carried
copy of a dual-role currency this character lost the fleet's `claim_turn_in`
election for (Task 5, `SelectionContext.recall`).

CONTROLLER RULING this goal implements verbatim: a non-buyer surrenders its
ENTIRE holding of the currency, worn plus carried — `ctx.recall`'s second
element is ALREADY that full count (`GamePlayer._resolve_turn_in`'s non-buyer
branch, fixed 2026-08-16 after Task 5's review found the prior quota-based
formula under-surrendered whenever the fleet held a surplus — see
`selection_context.py`'s `recall` docstring). This goal therefore does NOT
re-derive a quota from `state`: `units` is trusted as given, and the goal's
only job is to make it true that `units` copies are banked.

`relevant_actions` MATERIALIZES its own `DepositItemAction` for the same
reason `ai/goals/currency_turnin.py`'s buyer side materializes a Withdraw:
`build_actions` (factory.py) only emits `DepositAllAction` (an all-codes
sweep), never a single-code `DepositItemAction` sized to a surrender quantity
— that action exists in the factory only as `ai/disposal_route.py`'s DEPOSIT
arm, built the same way, for the same reason. `UnequipAction` needs no such
treatment: `build_actions` already emits one per equipment slot
unconditionally (factory.py's "one per equipment slot" loop), so this goal
only has to pick the ones currently wearing the target currency."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

SURRENDER_PRIORITY = 95.0
"""Fixed urgency when unsatisfied. Same non-meaning as
`currency_turnin.TURN_IN_PRIORITY` — `select_pure` never reads `value()` for
a COLLECT_REWARD_ORDER candidate, only the band's declared order."""


class SurrenderCurrencyGoal(Goal):
    """Bank `units` of `currency` — this character's WHOLE holding, per the
    controller ruling recorded in the module docstring above.

    `is_satisfied` is "my units are in the bank", not "I no longer hold any" —
    a character that already banked its quota stops immediately rather than
    chasing a turn-in it is not the buyer for."""

    def __init__(self, currency: str, units: int) -> None:
        self._currency = currency
        self._units = units

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return SURRENDER_PRIORITY

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items
        if bank is None:
            return False
        return bank.get(self._currency, 0) >= self._units

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"banked": {self._currency: self._units}}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Every currently-worn copy's Unequip, plus one materialized Deposit
        sized to the full holding. Narrow by construction: an Unequip for a
        slot NOT wearing this currency can never contribute, and no other
        Deposit quantity satisfies `is_satisfied`."""
        unequips = [a for a in actions
                   if isinstance(a, UnequipAction)
                   and state.equipment.get(a.slot) == self._currency]
        bank_location = game_data.bank_location_or_none or (0, 0)
        deposit = DepositItemAction(code=self._currency, quantity=self._units,
                                    bank_location=bank_location)
        return [*unequips, deposit]

    def __repr__(self) -> str:
        return f"SurrenderCurrency({self._currency}x{self._units})"
