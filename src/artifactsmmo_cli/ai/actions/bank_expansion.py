"""BuyBankExpansionAction: purchase additional bank slots."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_buy_bank_expansion_my_name_action_bank_buy_expansion_post import (
    sync as action_buy_bank_expansion,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Bank expansions grant a fixed slot increment per the OpenAPI contract:
#   POST /my/{name}/action/bank/buy_expansion — "Buy a 20 slots bank expansion."
# (openapi.json line 2843). Mirrored here so apply() can project the
# post-buy bank_capacity for the GOAP planner.
BANK_EXPANSION_SLOTS = 20


@dataclass
class BuyBankExpansionAction(Action):
    """Move to the bank and buy a slot expansion."""

    tags: ClassVar[frozenset[str]] = frozenset({"bank", "expansion"})

    bank_location: tuple[int, int] | None = field(default=None, repr=False)
    accessible: bool = True

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.accessible or self.bank_location is None:
            return False
        return state.gold >= game_data._next_expansion_cost

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location or (state.x, state.y)
        # Project the new bank capacity so ExpandBankGoal.is_satisfied
        # transitions False→True over a chain of applies (the planner needs
        # this to ever build an expansion plan). If we have not yet observed
        # capacity (None), seed from game_data._bank_capacity — the cycle's
        # snapshot — so the projection starts from the real server value.
        pre_cap = state.bank_capacity if state.bank_capacity is not None else game_data._bank_capacity
        return dataclasses.replace(
            state,
            gold=state.gold - game_data._next_expansion_cost,
            x=dest[0],
            y=dest[1],
            cooldown_expires=None,
            bank_capacity=pre_cap + BANK_EXPANSION_SLOTS,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.bank_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        # 1 gold per 100 cost units — expensive because expansions are infrequent
        return 5.0 + dist + game_data._next_expansion_cost / 100.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.bank_location and (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        result = action_buy_bank_expansion(client=client, name=state.character)
        result = Action._raise_for_error(result, "BuyBankExpansion")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return "BuyBankExpansion"
