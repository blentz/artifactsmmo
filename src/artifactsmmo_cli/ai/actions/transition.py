"""MapTransitionAction: trigger a map transition on the current tile."""

from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_transition_my_name_action_transition_post import (
    sync as action_transition,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class MapTransitionAction(Action):
    """Trigger a map transition (e.g., enter a dungeon) when standing on a transition tile."""

    tags: ClassVar[frozenset[str]] = frozenset({"movement"})

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return (state.x, state.y) in game_data._transition_tiles

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        # Destination depends on server-side response; cannot predict in pure planner.
        return state

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return 3.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        result = action_transition(client=client, name=state.character)
        result = Action._raise_for_error(result, "MapTransition")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return "Transition"
