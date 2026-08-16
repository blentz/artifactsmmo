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

    `is_satisfied` is PER-CHARACTER — "I hold none of it any more", worn plus
    carried == 0 — and deliberately does NOT read `state.bank_items`."""

    def __init__(self, currency: str, units: int) -> None:
        self._currency = currency
        self._units = units

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return SURRENDER_PRIORITY

    def is_satisfied(self, state: WorldState) -> bool:
        """This character has surrendered when IT holds none of the currency —
        worn plus carried == 0. The bank is not consulted at all.

        THE LIVELOCK THIS SHAPE EXISTS TO PREVENT (fix-round-3, CRITICAL): the
        prior test was `state.bank_items[currency] >= units`, and
        `state.bank_items` is the ACCOUNT-wide bank every child of a `play
        --all` run reads the same. So the FIRST sibling's deposit satisfied
        the goal for ALL of them and the arbiter skipped the rest
        (`strategy_driver`'s `select_pure` calls `is_satisfied` before it ever
        tries to plan). Live trace: five characters each wearing 2 medals,
        bank 0, price 10, Robby elected — C3P0 banks its 2, bank reads 2, and
        R2D2/HAL/Lor each see `bank(2) >= units(2)` and never unequip. The
        fleet banks `max_i(own_i)` medals instead of the sum, Robby's
        `Withdraw(10 - own)` is never applicable against a bank of 2, and the
        claim renews forever.

        Another character's deposit says NOTHING about whether this one has
        surrendered, so only this character's own holdings can decide it.
        `bank_items is None` ("never fetched") is likewise not a reason to
        keep working: a character wearing and carrying nothing has nothing
        left to give up, whether or not it has looked at the bank."""
        worn = sum(1 for code in state.equipment.values() if code == self._currency)
        return state.inventory.get(self._currency, 0) + worn == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"banked": {self._currency: self._units}}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Every currently-worn copy's Unequip, plus one materialized Deposit
        sized to the full holding. Narrow by construction: an Unequip for a
        slot NOT wearing this currency can never contribute, and no other
        Deposit quantity is what the buyer was told to expect.

        NO BANK TILE ⇒ NO DEPOSIT LEG. The earlier code read
        `bank_location_or_none or (0, 0)`, INVENTING map tile (0,0) as the
        bank whenever the catalog had no bank location — a fabricated game
        fact that CLAUDE.md forbids outright ("use only API data or fail with
        an error"), and one that would route a real Move to a tile the server
        never called a bank. Every precedent in this repo treats `None` as
        "no bank leg" instead (`ai/disposal_route.py`, `ai/bank_drain.py`'s
        drain goal, `ai/goals/sell_inventory.py`); this goal follows it, and
        an un-plannable surrender is the honest outcome when the fleet has no
        bank to surrender into."""
        unequips: list[Action] = [a for a in actions
                                  if isinstance(a, UnequipAction)
                                  and state.equipment.get(a.slot) == self._currency]
        bank_location = game_data.bank_location_or_none
        if bank_location is None:
            return unequips
        deposit = DepositItemAction(code=self._currency, quantity=self._units,
                                    bank_location=bank_location)
        return [*unequips, deposit]

    def __repr__(self) -> str:
        return f"SurrenderCurrency({self._currency}x{self._units})"
