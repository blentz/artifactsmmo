"""TaskExchangeAction: move to the taskmaster and exchange task coins for rewards."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_task_exchange_my_name_action_task_exchange_post import (
    sync as action_task_exchange,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


@dataclass
class TaskExchangeAction(Action):
    """Move to the taskmaster and exchange task coins for rewards."""

    tags: ClassVar[frozenset[str]] = frozenset({"task"})

    taskmaster_location: tuple[int, int]
    # Minimum coins worth attempting an exchange with. The real per-exchange
    # cost is not exposed as API data, so the player learns it empirically from
    # HTTP 478 ("missing items") failures and injects the current lower bound
    # here. Never hardcode the cost.
    min_coins: int = 1

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        # Only inventory counts at execute time (bank coins must be withdrawn
        # separately first). Fewer than the learned minimum returns HTTP 478.
        # Defense in depth (chain_safe shape): the exchange grants at least one
        # reward item per execute. Without a slot-free check, a full bag would
        # have the reward overflow inventory_max on the server. The reward
        # grant size is not exposed as API data, so we use the safe lower bound
        # of >= 1 free slot.
        if state.inventory.get(TASKS_COIN_CODE, 0) < self.min_coins:
            return False
        return state.inventory_free >= 1

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        assert (
            state.inventory.get(TASKS_COIN_CODE, 0) >= self.min_coins
            and state.inventory_free >= 1
        ), (
            f"TaskExchangeAction.apply requires coins >= min_coins and "
            f"inventory_free >= 1 "
            f"(coins={state.inventory.get(TASKS_COIN_CODE, 0)}, "
            f"min_coins={self.min_coins}, free={state.inventory_free})"
        )
        dest = self.taskmaster_location
        new_inventory = dict(state.inventory)
        remaining = new_inventory.get(TASKS_COIN_CODE, 0) - self.min_coins
        if remaining <= 0:
            new_inventory.pop(TASKS_COIN_CODE, None)
        else:
            new_inventory[TASKS_COIN_CODE] = remaining
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.taskmaster_location
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 1.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = self.taskmaster_location
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_task_exchange(client=client, name=state.character)
        result = Action._raise_for_error(result, "TaskExchange")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return "TaskExchange"
