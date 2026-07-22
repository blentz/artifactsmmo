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
    taskmaster_code: str = "monsters"
    """Which tasks master this walks to (`"monsters"` / `"items"`).

    ADDED 2026-07-22. The map carries two masters and the one you visit decides
    the task TYPE the server issues. Until now `_build_maps` kept only the last
    tile parsed, which in the live map is the ITEMS master -- so the bot walked
    to the items master while `apply` projected a MONSTERS task. The plan and
    the destination disagreed.

    Defaults to `"monsters"` to match the projection below, which is load-bearing
    (see `apply`). Choosing the master deliberately is synergy Phase 4."""

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return not state.task_code and state.task_total == 0

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.taskmaster_location
        # KEEP THIS "monsters" LITERAL. It is not a placeholder for
        # `self.taskmaster_code`, and projecting the visited master's real type
        # would REGRESS a fixed bug: an items task cannot progress in-model,
        # because TaskTradeAction gates on a SPECIFIC task code and the pending
        # marker is `__pending__`, so CompleteTask would never become applicable
        # and the accept->progress->complete chain would go unfindable again.
        # The action is instead emitted against the monsters master (factory.py),
        # so destination and projection now agree -- which is exactly what the
        # single-tile bug broke.
        #
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
