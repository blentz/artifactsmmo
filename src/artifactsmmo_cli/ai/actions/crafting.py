"""Craft action for GOAP planning."""

from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post import sync as action_crafting
from artifactsmmo_api_client.models.crafting_schema import CraftingSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class CraftAction(Action):
    """Move to the correct workshop and craft an item. Movement is folded into cost and execute."""

    tags: ClassVar[frozenset[str]] = frozenset({"craft", "produces_skill_xp"})

    code: str
    quantity: int = 1
    workshop_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.workshop_location is None:
            return False

        stats = game_data.item_stats(self.code)
        if stats is None or stats.crafting_skill is None:
            return False

        recipe = game_data.crafting_recipe(self.code)
        if recipe is None:
            return False

        for mat_code, mat_qty in recipe.items():
            if state.inventory.get(mat_code, 0) < mat_qty * self.quantity:
                return False

        skill_level = state.skills.get(stats.crafting_skill, 1)
        return skill_level >= stats.crafting_level

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        recipe = game_data.crafting_recipe(self.code) or {}
        new_inventory = dict(state.inventory)

        for mat_code, mat_qty in recipe.items():
            consumed = mat_qty * self.quantity
            new_inventory[mat_code] = new_inventory.get(mat_code, 0) - consumed
            if new_inventory[mat_code] <= 0:
                del new_inventory[mat_code]

        new_inventory[self.code] = new_inventory.get(self.code, 0) + self.quantity

        new_progress = (
            state.task_progress + self.quantity
            if state.task_type == "crafting" and state.task_code == self.code
            else state.task_progress
        )

        dest = self.workshop_location or (state.x, state.y)

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
        dest = self.workshop_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 5.0 * self.quantity + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.workshop_location and (state.x, state.y) != self.workshop_location:
            state = MoveAction(x=self.workshop_location[0], y=self.workshop_location[1]).execute(state, client)
        body = CraftingSchema(code=self.code, quantity=self.quantity)
        result = action_crafting(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"Craft {self.code}×{self.quantity}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def __repr__(self) -> str:
        return f"Craft({self.code}×{self.quantity})"
