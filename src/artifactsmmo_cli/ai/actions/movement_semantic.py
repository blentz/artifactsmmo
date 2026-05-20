"""Semantic move action: move to a named location type."""

from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class MoveTo(Action):
    """Semantic move: teleports to a named group of destinations for planning.

    Collapses all tile-level Move(x,y) actions into one per destination type
    (monster, resource, workshop, bank), shrinking the planner branching factor
    from ~90 to ~20.
    """

    tags: ClassVar[frozenset[str]] = frozenset({"movement"})

    name: str
    destinations: frozenset[tuple[int, int]]

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return (state.x, state.y) not in self.destinations

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = min(self.destinations)  # deterministic choice for visited-set consistency
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
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return 1.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        nearest = min(
            self.destinations,
            key=lambda loc: abs(loc[0] - state.x) + abs(loc[1] - state.y),
        )
        return MoveAction(x=nearest[0], y=nearest[1]).execute(state, client)

    def __repr__(self) -> str:
        return f"MoveTo({self.name})"
