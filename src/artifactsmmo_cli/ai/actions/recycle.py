"""RecycleAction: break down an item into crafting materials."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post import (
    sync as action_recycling,
)
from artifactsmmo_api_client.models.recycling_schema import RecyclingSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class RecycleAction(Action):
    """Move to the item's workshop and recycle it, recovering a fraction of its materials."""

    tags: ClassVar[frozenset[str]] = frozenset({"cleanup", "craft"})

    code: str
    quantity: int = 1
    workshop_location: tuple[int, int] | None = field(default=None, repr=False)
    bag_floor: int = field(default=0, repr=False)
    """Bag copies of `code` that must SURVIVE this recycle (`keep_in_bag`).

    The world model does not distinguish WHICH copy a recycle consumes — it just
    decrements the count. Once bank copies are licensed as recycle SOURCES
    (`destructive_license`), a recycle with no floor could satisfy itself by
    eating the working tool sitting alone in the bag instead of withdrawing a
    bank copy. The floor makes the protected bag copies UNREACHABLE, so GOAP is
    forced to Withdraw first. Stamped at licence time, where the ctx is complete
    — exactly as `workshop_location` is baked in. Default 0 = no floor."""

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.workshop_location is None:
            return False
        if state.inventory.get(self.code, 0) < self.quantity:
            return False
        if state.inventory.get(self.code, 0) - self.quantity < self.bag_floor:
            return False
        recipe = game_data.crafting_recipe(self.code)
        if recipe is None:
            return False
        # Server requires the crafting skill at the recipe's level to recycle
        # (mirrors the CraftAction gate). Without this, the planner stages a
        # recycle that the server rejects with HTTP 493 / 478.
        stats = game_data.item_stats(self.code)
        if stats is None or stats.crafting_skill is None:
            return False
        if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
            return False
        # `apply` mints recovered materials into the inventory. Without a
        # slot-floor check, the post-state overflows inventory_max. Net delta
        # = sum(max(1, mat_qty*qty // 2)) - quantity (the recycled item leaves
        # the bag). When the net is positive we need that many free slots.
        recovered = sum(max(1, (mat_qty * self.quantity) // 2) for mat_qty in recipe.values())
        net = recovered - self.quantity
        return not (net > 0 and state.inventory_free < net)

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_inventory = dict(state.inventory)
        new_inventory[self.code] = new_inventory.get(self.code, 0) - self.quantity
        if new_inventory[self.code] <= 0:
            del new_inventory[self.code]

        # Recycling returns approximately half the materials (rounded down per ingredient).
        recipe = game_data.crafting_recipe(self.code) or {}
        for mat_code, mat_qty in recipe.items():
            recovered = max(1, (mat_qty * self.quantity) // 2)
            new_inventory[mat_code] = new_inventory.get(mat_code, 0) + recovered

        dest = self.workshop_location or (state.x, state.y)
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.workshop_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 3.0 * self.quantity + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.workshop_location and (state.x, state.y) != self.workshop_location:
            state = MoveAction(x=self.workshop_location[0], y=self.workshop_location[1]).execute(state, client)
        body = RecyclingSchema(code=self.code, quantity=self.quantity)
        result = action_recycling(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"Recycle {self.code}×{self.quantity}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"Recycle({self.code}×{self.quantity})"
