"""TaskExchangeAction: move to the taskmaster and exchange task coins for rewards."""

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
from artifactsmmo_cli.ai.world_state import WorldState

_TASKS_COIN = "tasks_coin"


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
        return state.inventory.get(_TASKS_COIN, 0) >= self.min_coins

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.taskmaster_location
        new_inventory = dict(state.inventory)
        remaining = new_inventory.get(_TASKS_COIN, 0) - self.min_coins
        if remaining <= 0:
            new_inventory.pop(_TASKS_COIN, None)
        else:
            new_inventory[_TASKS_COIN] = remaining
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
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
