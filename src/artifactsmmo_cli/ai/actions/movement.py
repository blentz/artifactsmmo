"""Movement action for GOAP planning."""

from dataclasses import dataclass

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_move_my_name_action_move_post import sync as action_move
from artifactsmmo_api_client.models.destination_schema import DestinationSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class MoveAction(Action):
    """Move the character to a specific tile."""

    x: int
    y: int

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return state.x != self.x or state.y != self.y

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=self.x,
            y=self.y,
            inventory=state.inventory,
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
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        distance = abs(self.x - state.x) + abs(self.y - state.y)
        return max(distance * 5.0, 1.0)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        body = DestinationSchema(x=self.x, y=self.y)
        result = action_move(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"Move to ({self.x},{self.y})")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"Move({self.x},{self.y})"
