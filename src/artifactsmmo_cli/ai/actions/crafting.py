"""Craft action for GOAP planning."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_crafting_my_name_action_crafting_post import (
    sync as action_crafting,
)
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
    history: LearningStore | None = field(default=None, repr=False)

    def effective_quantity(self, state: WorldState, game_data: GameData) -> int:
        """Largest feasible batch to craft NOW: `min(requested, floor(inv / per))`
        over every recipe input. Partial batches count — full satisfaction is the
        ideal, but any unit the on-hand inputs cover contributes. 0 when not even
        one unit is affordable."""
        recipe = game_data.crafting_recipe(self.code)
        if not recipe:
            return 0
        eff = self.quantity
        for mat_code, mat_qty in recipe.items():
            eff = min(eff, state.inventory.get(mat_code, 0) // mat_qty)
        return max(0, eff)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.workshop_location is None:
            return False

        stats = game_data.item_stats(self.code)
        if stats is None or stats.crafting_skill is None:
            return False

        recipe = game_data.crafting_recipe(self.code)
        if recipe is None:
            return False

        skill_level = state.skills.get(stats.crafting_skill, 1)
        if skill_level < stats.crafting_level:
            return False

        # Partial applicability: applicable when the inputs cover >= 1 unit.
        return self.effective_quantity(state, game_data) >= 1

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        recipe = game_data.crafting_recipe(self.code) or {}
        new_inventory = dict(state.inventory)

        # Craft the largest feasible batch the on-hand inputs cover (<= requested).
        eff = self.effective_quantity(state, game_data)
        for mat_code, mat_qty in recipe.items():
            consumed = mat_qty * eff
            new_inventory[mat_code] = new_inventory.get(mat_code, 0) - consumed
            if new_inventory[mat_code] <= 0:
                del new_inventory[mat_code]

        y = game_data.craft_yield(self.code)
        produced = eff * y
        new_inventory[self.code] = new_inventory.get(self.code, 0) + produced

        new_progress = (
            state.task_progress + produced
            if state.task_type == "crafting" and state.task_code == self.code
            else state.task_progress
        )

        dest = self.workshop_location or (state.x, state.y)

        # skill_xp is a server-snapshot baseline field (see WorldState docstring);
        # the planner never simulates it locally — apply preserves it. The next
        # real API call returns the updated server values. Crafting does NOT
        # raise skill levels in-search either; the planner-native skill grind is
        # a separate LevelSkill action leg.
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
            task_progress=new_progress,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.workshop_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        # Cost stays keyed to the REQUESTED quantity (not the effective batch) to
        # match the proved planner-admissibility cost model
        # (formal/Formal/PlannerAdmissibility.lean, qtyCost). A partial craft is
        # merely over-costed, which keeps edge costs >= 0 and the search sound.
        return 5.0 * self.quantity + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.workshop_location and (state.x, state.y) != self.workshop_location:
            state = MoveAction(x=self.workshop_location[0], y=self.workshop_location[1]).execute(state, client)
        body = CraftingSchema(code=self.code, quantity=self.quantity)
        result = action_crafting(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"Craft {self.code}×{self.quantity}")
        if self.history is not None:
            details = result.data.details
            produced = sum(d.quantity for d in details.items if d.code == self.code)
            self.history.record_craft_yield(self.code, produced, details.xp)
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return f"Craft({self.code}×{self.quantity})"
