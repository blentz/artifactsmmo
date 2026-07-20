"""TaskCancelAction: move to the taskmaster and cancel the current task."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_task_cancel_my_name_action_task_cancel_post import (
    sync as action_task_cancel,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_lifecycle import TaskLifecyclePhase
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


@dataclass
class TaskCancelAction(Action):
    """Move to the taskmaster and cancel the current task (costs one task coin)."""

    tags: ClassVar[frozenset[str]] = frozenset({"task"})

    taskmaster_location: tuple[int, int]

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        # Server requires 1 task coin to cancel (HTTP 478 otherwise). Without
        # the coin gate, the planner would propose a cancel that the server
        # then refuses, freezing the agent on the failed step.
        if not state.task_code or state.task_total <= 0:
            return False
        return state.inventory.get(TASKS_COIN_CODE, 0) >= 1

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        assert state.inventory.get(TASKS_COIN_CODE, 0) >= 1, (
            f"TaskCancelAction.apply requires a task coin "
            f"(have {state.inventory.get(TASKS_COIN_CODE, 0)})"
        )
        dest = self.taskmaster_location
        new_inventory = dict(state.inventory)
        remaining = new_inventory.get(TASKS_COIN_CODE, 0) - 1
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
            task_code=None,
            task_type=None,
            task_progress=0,
            task_total=0,
            task_lifecycle_phase=TaskLifecyclePhase.NONE,
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
        result = action_task_cancel(client=client, name=state.character)
        result = Action._raise_for_error(result, "TaskCancel")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return "TaskCancel"
