"""MapTransitionAction: the sole region-crossing movement edge (P5b)."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_transition_my_name_action_transition_post import (
    sync as action_transition,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class MapTransitionAction(Action):
    """Cross one transition edge: fold movement to the portal tile, satisfy
    its conditions (only `('gold', 'cost', n)` is modeled — any other
    condition code makes the edge inapplicable, never silently passable),
    and teleport to the recorded destination. The ONLY action whose apply
    changes the access region (docs/PLAN_multilayer_nav.md)."""

    tags: ClassVar[frozenset[str]] = frozenset({"movement"})

    portal_x: int = 0
    portal_y: int = 0
    dest_x: int = 0
    dest_y: int = 0
    dest_layer: str = "overworld"
    conditions: tuple[tuple[str, str, int], ...] = ()
    travel_region: str = "overworld"

    def _gold_cost(self) -> int:
        return sum(v for code, op, v in self.conditions
                   if code == "gold" and op == "cost")

    def _conditions_modeled(self) -> bool:
        return all(code == "gold" and op == "cost"
                   for code, op, _v in self.conditions)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return self._conditions_modeled() and state.gold >= self._gold_cost()

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        return dataclasses.replace(
            state, x=self.dest_x, y=self.dest_y, layer=self.dest_layer,
            gold=state.gold - self._gold_cost())

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        walk = abs(state.x - self.portal_x) + abs(state.y - self.portal_y)
        return float(walk) + 3.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if (state.x, state.y) != (self.portal_x, self.portal_y):
            state = MoveAction(x=self.portal_x, y=self.portal_y).execute(state, client)
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
        gold = self._gold_cost()
        fee = f", {gold}g" if gold else ""
        return (f"Transition(({self.portal_x},{self.portal_y})->"
                f"({self.dest_x},{self.dest_y},{self.dest_layer}){fee})")
