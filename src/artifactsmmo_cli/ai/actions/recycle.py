"""RecycleAction: break down an item into crafting materials."""

from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_recycling_my_name_action_recycling_post import sync as action_recycling
from artifactsmmo_api_client.models.recycling_schema import RecyclingSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class RecycleAction(Action):
    """Move to the item's workshop and recycle it, recovering a fraction of its materials."""

    code: str
    quantity: int = 1
    workshop_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.workshop_location is None:
            return False
        if state.inventory.get(self.code, 0) < self.quantity:
            return False
        return game_data.crafting_recipe(self.code) is not None

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
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
        )

    def cost(self, state: WorldState, game_data: GameData) -> float:
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
        )

    def __repr__(self) -> str:
        return f"Recycle({self.code}×{self.quantity})"
