"""CompleteTaskAction: move to the taskmaster and turn in a finished task."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_complete_task_my_name_action_task_complete_post import (
    sync as action_task_complete,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.complete_task_core import complete_task_apply_pure
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_lifecycle import TaskLifecyclePhase
from artifactsmmo_cli.ai.world_state import WorldState

TASK_COMPLETE_XP_ESTIMATE: int = 0
"""Planner-side XP projection for CompleteTaskAction.

Empirical observation (user-confirmed 2026-06-03): the server's
``/action/task/complete`` endpoint rewards items + gold only (see
``RewardsSchema`` in artifactsmmo-api-client/models/rewards_schema.py —
fields are ``items`` and ``gold``, no XP field). Character XP is granted
during the per-cycle progress actions (fight/gather/craft), not at
turn-in. The planner-side projection is therefore 0.

Kept as a named constant (rather than inlined) so the Lean
``taskCompleteXpEstimate`` def in ``formal/Formal/Liveness/Measure.lean``
retains a single citation point.
"""


@dataclass
class CompleteTaskAction(Action):
    """Move to the taskmaster and turn in a finished task for rewards."""

    tags: ClassVar[frozenset[str]] = frozenset({"task"})

    taskmaster_location: tuple[int, int]

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return state.task_total > 0 and state.task_progress >= state.task_total

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        """Clear the completed task, move to taskmaster, and mint the task's
        tasks_coin reward into inventory via the proved complete_task_apply_pure
        core (previously inventory was untouched; coins are the planner-relevant
        reward for funding TaskExchangeAction)."""
        dest = self.taskmaster_location
        assert state.task_code is not None, "apply called without an active task"
        coin_reward = game_data.task_coin_reward(state.task_code)
        inventory = complete_task_apply_pure(state.inventory, coin_reward)
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            cooldown_expires=None,
            task_code="",
            task_type="",
            task_progress=0,
            task_total=0,
            task_lifecycle_phase=TaskLifecyclePhase.NONE,
            xp=state.xp + TASK_COMPLETE_XP_ESTIMATE,
            inventory=inventory,
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
        result = action_task_complete(client=client, name=state.character)
        result = Action._raise_for_error(result, "CompleteTask")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return "CompleteTask"
