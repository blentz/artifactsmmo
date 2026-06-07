"""Semantic move action: move to a named location type."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.nearest_tile import nearest_tile
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
        # Manhattan-nearest (lex-tie-broken) — the SAME pick `execute` makes, so the
        # planned and executed destinations agree (closes the apply/execute divergence).
        dest = nearest_tile(state.x, state.y, self.destinations)
        if dest is None:
            raise ValueError("no destinations to move to")
        return dataclasses.replace(state, x=dest[0], y=dest[1], cooldown_expires=None)

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return 1.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        nearest = nearest_tile(state.x, state.y, self.destinations)
        if nearest is None:
            raise ValueError("no destinations to move to")
        return MoveAction(x=nearest[0], y=nearest[1]).execute(state, client)

    def __repr__(self) -> str:
        return f"MoveTo({self.name})"
