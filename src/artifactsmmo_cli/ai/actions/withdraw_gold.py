"""WithdrawGoldAction: withdraw gold from bank to character."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post import (
    sync as action_withdraw_gold,
)
from artifactsmmo_api_client.models.deposit_withdraw_gold_schema import DepositWithdrawGoldSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.cost_core import distance_cost_pure, travel_seconds
from artifactsmmo_cli.ai.actions.deposit_gold import _gold_apply
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class WithdrawGoldAction(Action):
    """Withdraw gold from bank to character."""

    tags: ClassVar[frozenset[str]] = frozenset({"bank"})

    quantity: int = 0
    bank_location: tuple[int, int] | None = field(default=None, repr=False)
    accessible: bool = True

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.accessible or self.bank_location is None:
            return False
        return not (state.bank_gold is None or state.bank_gold < self.quantity)

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location or (state.x, state.y)
        return _gold_apply(state, dest, gold_delta=self.quantity, bank_gold_delta=-self.quantity)

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.bank_location or (state.x, state.y)
        return distance_cost_pure(
            2.0, travel_seconds((state.x, state.y), dest))

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.bank_location and (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        body = DepositWithdrawGoldSchema(quantity=self.quantity)
        result = action_withdraw_gold(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"WithdrawGold {self.quantity}")
        return WorldState.from_character_schema(
            result.data.character, bank_items=state.bank_items,
            bank_gold=state.bank_gold, pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return f"WithdrawGold({self.quantity})"


def gold_ferry(actions: list[Action], state: WorldState, deficit: int) -> WithdrawGoldAction | None:
    """The WithdrawGold that ferries `deficit` gold from the bank to the pocket,
    sized from the pool's own withdraw, or None when nothing is short or
    nothing can be ferried.

    EVERY GOLD SINK PAYS FROM THE POCKET. `can_spend` asks the reserve of the
    ACCOUNT (pocket plus bank), so a buy the account affords can still be one
    the server refuses: HTTP 492, "the character does not have enough gold".
    Live 2026-10-30: HAL held 6,516 in pocket against a 6,550 GE order and the
    plan was a bare `GeBuy` five cycles running, with tens of thousands in the
    bank. The buy actions now gate on the pocket too, and a goal that admits a
    gold buy admits this ferry beside it so A* can chain WithdrawGold -> buy.

    Resized from a pool withdraw so the bank tile and its accessibility survive
    (the factory threads both from the cycle context), and capped at the KNOWN
    bank balance: an unknown bank (`None`) ferries nothing, which is also what
    `WithdrawGoldAction.is_applicable` would say. A ferry the bank cannot fully
    fund still leaves the buy inapplicable, so no buy is planned past it."""
    if deficit <= 0 or state.bank_gold is None or state.bank_gold <= 0:
        return None
    template = next((a for a in actions if isinstance(a, WithdrawGoldAction)), None)
    if template is None:
        return None
    return dataclasses.replace(template, quantity=min(deficit, state.bank_gold))
