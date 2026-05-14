"""Task actions: accept a new task, complete a finished task, and exchange task coins."""

from dataclasses import dataclass

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_accept_new_task_my_name_action_task_new_post import sync as action_task_new
from artifactsmmo_api_client.api.my_characters.action_complete_task_my_name_action_task_complete_post import sync as action_task_complete
from artifactsmmo_api_client.api.my_characters.action_task_exchange_my_name_action_task_exchange_post import sync as action_task_exchange

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

_TASKS_COIN = "tasks_coin"

_PENDING_TASK = "__pending__"


@dataclass
class AcceptTaskAction(Action):
    """Move to the taskmaster and accept a new task."""

    taskmaster_location: tuple[int, int]

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return not state.task_code and state.task_total == 0

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.taskmaster_location
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
            inventory=state.inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code=_PENDING_TASK,
            task_type=state.task_type,
            task_progress=0,
            task_total=1,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
        )

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.taskmaster_location
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 1.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = self.taskmaster_location
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_task_new(client=client, name=state.character)
        Action._raise_for_error(result, "AcceptTask")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
        )

    def __repr__(self) -> str:
        return "AcceptTask"


@dataclass
class CompleteTaskAction(Action):
    """Move to the taskmaster and turn in a finished task for rewards."""

    taskmaster_location: tuple[int, int]

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return state.task_total > 0 and state.task_progress >= state.task_total

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.taskmaster_location
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
            inventory=state.inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code="",
            task_type="",
            task_progress=0,
            task_total=0,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
        )

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.taskmaster_location
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 1.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = self.taskmaster_location
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_task_complete(client=client, name=state.character)
        Action._raise_for_error(result, "CompleteTask")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
        )

    def __repr__(self) -> str:
        return "CompleteTask"


@dataclass
class TaskExchangeAction(Action):
    """Move to the taskmaster and exchange task coins for rewards."""

    taskmaster_location: tuple[int, int]

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        bank = state.bank_items or {}
        return state.inventory.get(_TASKS_COIN, 0) + bank.get(_TASKS_COIN, 0) > 0

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.taskmaster_location
        new_inventory = dict(state.inventory)
        new_inventory.pop(_TASKS_COIN, None)
        new_bank = dict(state.bank_items or {})
        new_bank.pop(_TASKS_COIN, None)
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
            bank_items=new_bank,
            bank_gold=state.bank_gold,
        )

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = self.taskmaster_location
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 1.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = self.taskmaster_location
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_task_exchange(client=client, name=state.character)
        Action._raise_for_error(result, "TaskExchange")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
        )

    def __repr__(self) -> str:
        return "TaskExchange"
