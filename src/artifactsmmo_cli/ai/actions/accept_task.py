"""AcceptTaskAction: move to the taskmaster and accept a new task."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_accept_new_task_my_name_action_task_new_post import (
    sync as action_task_new,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_lifecycle import TaskLifecyclePhase
from artifactsmmo_cli.ai.world_state import WorldState

_PENDING_TASK = "__pending__"


@dataclass
class AcceptTaskAction(Action):
    """Move to the taskmaster and accept a new task."""

    tags: ClassVar[frozenset[str]] = frozenset({"task"})

    taskmaster_location: tuple[int, int]

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return not state.task_code and state.task_total == 0

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.taskmaster_location
        # task_type="monsters" makes the pending in-model task PROGRESSABLE:
        # FightAction.apply advances a monsters-task, and it special-cases the
        # _PENDING_TASK marker (any monster counts). Without a type the pending
        # task could never progress in ANY projection, CompleteTask was never
        # applicable, and every accept→progress→complete plan (ReachCurrency
        # funding, C4) was unfindable — live satchel/jasper stall 2026-07-06.
        # Execution replaces all of this with the server's real task; the
        # per-cycle replan then works the actual requirement.
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            cooldown_expires=None,
            task_code=_PENDING_TASK,
            task_type="monsters",
            task_progress=0,
            task_total=1,
            task_lifecycle_phase=TaskLifecyclePhase.ACCEPTED,
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
        result = action_task_new(client=client, name=state.character)
        result = Action._raise_for_error(result, "AcceptTask")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return "AcceptTask"
