"""Fight action for GOAP planning."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_fight_my_name_action_fight_post import sync as action_fight
from artifactsmmo_api_client.models.fight_request_schema import FightRequestSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def _nearest(locations: frozenset[tuple[int, int]], state: WorldState) -> tuple[int, int]:
    return min(locations, key=lambda loc: abs(loc[0] - state.x) + abs(loc[1] - state.y))


@dataclass
class FightAction(Action):
    """Move to and fight a monster. Movement is folded into cost and execute."""

    monster_code: str
    locations: frozenset[tuple[int, int]] = field(default_factory=frozenset, repr=False)

    _MIN_FREE_SLOTS = 1  # combat can drop loot; need at least 1 free capacity

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.locations or state.inventory_free < self._MIN_FREE_SLOTS:
            return False
        monster_level = game_data.monster_level(self.monster_code)
        min_level = max(1, state.level - 1)
        if not (state.hp_percent > 0.3 and min_level <= monster_level <= state.level + 2):
            return False
        best_eq = max(
            (s.level for code in state.equipment.values()
             if code and (s := game_data.item_stats(code)) is not None),
            default=0,
        )
        return best_eq >= monster_level - 1

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = _nearest(self.locations, state)
        estimated_hp_cost = max(1, state.max_hp // 5)
        new_hp = max(1, state.hp - estimated_hp_cost)
        new_progress = (
            state.task_progress + 1
            if state.task_type == "monsters" and state.task_code == self.monster_code
            else state.task_progress
        )
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp + 10,
            max_xp=state.max_xp,
            hp=new_hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=dest[0],
            y=dest[1],
            inventory=state.inventory,
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

    def cost(self, state: WorldState, game_data: GameData) -> float:
        dest = _nearest(self.locations, state)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 10.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = _nearest(self.locations, state)
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_fight(client=client, name=state.character, body=FightRequestSchema())
        Action._raise_for_error(result, f"Fight {self.monster_code}")
        return WorldState.from_character_schema(
            result.data.characters[0],
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"Fight({self.monster_code})"
