"""Rest action for GOAP planning."""

import dataclasses
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_rest_my_name_action_rest_post import sync as action_rest

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class RestAction(Action):
    """Restore HP by resting."""

    tags: ClassVar[frozenset[str]] = frozenset({"recovery"})

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return state.hp < state.max_hp

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        return dataclasses.replace(state, hp=state.max_hp, cooldown_expires=None)

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return 10.0  # ~100s real-world cooldown; UseConsumable (2.0) preferred when food available

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        result = action_rest(client=client, name=state.character)
        result = Action._raise_for_error(result, "Rest")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return "Rest"
