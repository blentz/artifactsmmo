"""WithdrawGoldAction: withdraw gold from bank to character."""

from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post import (
    sync as action_withdraw_gold,
)
from artifactsmmo_api_client.models.deposit_withdraw_gold_schema import DepositWithdrawGoldSchema

from artifactsmmo_cli.ai.actions.base import Action
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
        if state.bank_gold is None or state.bank_gold < self.quantity:
            return False
        return True

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location or (state.x, state.y)
        return _gold_apply(state, dest, gold_delta=self.quantity, bank_gold_delta=-self.quantity)

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.bank_location or (state.x, state.y)
        return 2.0 + abs(dest[0] - state.x) + abs(dest[1] - state.y)

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
        )

    def __repr__(self) -> str:
        return f"WithdrawGold({self.quantity})"
