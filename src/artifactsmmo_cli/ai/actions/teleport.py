"""TeleportAction: use a fast-travel consumable to warp to its destination (PLAN #6b)."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_use_item_my_name_action_use_post import sync as action_use_item
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

TELEPORT_COST: float = 20.0
"""Flat cost of one teleport (seconds-equivalent). Distance-independent: a warp
costs the same regardless of how far the destination is. Priced above a single
MapTransition (3.0) and ~4 walked tiles (Move = 5/tile) so the planner spends a
finite teleport potion only when the warp saves a genuinely long walk — teleport
beats walking iff the destination is ≳4 tiles closer to the goal than the current
tile. Mirrors `Formal/ActionCostNonneg.teleportCost` (a `const` cost tag)."""


@dataclass
class TeleportAction(Action):
    """Use a teleport consumable from inventory to warp to a fixed destination.

    The item's `teleport` effect value is a map id; the factory resolves it to
    ``(dest_x, dest_y)`` via ``game_data.teleport_destination`` and bakes the
    coordinates in. Movement-tagged so movement-aware goals treat it as a travel
    option; the planner's cost search picks teleport-then-walk over a long walk
    when it is cheaper.
    """

    tags: ClassVar[frozenset[str]] = frozenset({"movement"})

    item_code: str
    dest_x: int
    dest_y: int

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if state.inventory.get(self.item_code, 0) <= 0:
            return False  # no potion to consume
        return (state.x, state.y) != (self.dest_x, self.dest_y)  # already there ⇒ pointless

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_inventory = dict(state.inventory)
        new_inventory[self.item_code] -= 1
        if new_inventory[self.item_code] == 0:
            del new_inventory[self.item_code]
        return dataclasses.replace(
            state,
            x=self.dest_x,
            y=self.dest_y,
            inventory=new_inventory,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return TELEPORT_COST

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        result = action_use_item(
            client=client, name=state.character,
            body=SimpleItemSchema(code=self.item_code, quantity=1))
        result = Action._raise_for_error(result, f"Teleport({self.item_code})")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return f"Teleport({self.item_code}->{self.dest_x},{self.dest_y})"
