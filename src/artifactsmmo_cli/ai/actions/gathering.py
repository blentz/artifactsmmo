"""Gather action for GOAP planning."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_gathering_my_name_action_gathering_post import sync as action_gathering

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


def _nearest(locations: frozenset[tuple[int, int]], state: WorldState) -> tuple[int, int]:
    return min(locations, key=lambda loc: abs(loc[0] - state.x) + abs(loc[1] - state.y))


@dataclass
class GatherAction(Action):
    """Move to and gather a resource. Movement is folded into cost and execute."""

    resource_code: str
    locations: frozenset[tuple[int, int]] = field(default_factory=frozenset, repr=False)

    _MIN_FREE_SLOTS = 3  # gathering can produce ore + random bonus drops simultaneously

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.locations:
            return False
        skill_req = game_data.resource_skill_level(self.resource_code)
        if skill_req is None:
            return state.inventory_free >= self._MIN_FREE_SLOTS
        skill, level = skill_req
        return state.skills.get(skill, 1) >= level and state.inventory_free >= self._MIN_FREE_SLOTS

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = _nearest(self.locations, state)
        new_inventory = dict(state.inventory)
        drop_item = game_data.resource_drop_item(self.resource_code) or self.resource_code
        new_inventory[drop_item] = new_inventory.get(drop_item, 0) + 1
        new_progress = (
            state.task_progress + 1
            if state.task_type == "items" and state.task_code == drop_item
            else state.task_progress
        )
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
            task_progress=new_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = _nearest(self.locations, state)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 6.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = _nearest(self.locations, state)
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_gathering(client=client, name=state.character)
        result = Action._raise_for_error(result, f"Gather {self.resource_code}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"Gather({self.resource_code})"
