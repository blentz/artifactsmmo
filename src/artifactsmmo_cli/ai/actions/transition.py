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
    its conditions, and teleport to the recorded destination. The ONLY
    action whose apply changes the access region
    (docs/PLAN_multilayer_nav.md).

    Modeled condition operators (docs concepts/maps_and_movement):
    - `cost`: pay gold or a key item, CONSUMED on use (`lich_tomb_key`,
      `sonnengott_key`, the Enchanted Forest's 5000 gold fee). Item costs
      are paid from the inventory.
    - `has_item`: possess the item in inventory OR equipped, NOT consumed
      (`cultist_cloak`).
    Any other operator (achievement_unlocked, stat comparisons) makes the
    edge inapplicable — never silently passable."""

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

    def _item_costs(self) -> dict[str, int]:
        """Key items CONSUMED on use: {item_code: quantity}."""
        out: dict[str, int] = {}
        for code, op, v in self.conditions:
            if op == "cost" and code != "gold":
                out[code] = out.get(code, 0) + v
        return out

    def _possession_requirements(self) -> dict[str, int]:
        """`has_item` requirements: {item_code: quantity}, not consumed."""
        out: dict[str, int] = {}
        for code, op, v in self.conditions:
            if op == "has_item":
                out[code] = max(out.get(code, 0), v)
        return out

    def _conditions_modeled(self) -> bool:
        return all(op in ("cost", "has_item")
                   for _code, op, _v in self.conditions)

    @staticmethod
    def _possessed(state: WorldState, code: str) -> int:
        """Copies held: inventory plus equipped slots (docs: has_item counts
        both)."""
        return state.inventory.get(code, 0) + sum(
            1 for equipped in state.equipment.values() if equipped == code)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self._conditions_modeled():
            return False
        if state.gold < self._gold_cost():
            return False
        if any(state.inventory.get(code, 0) < qty
               for code, qty in self._item_costs().items()):
            return False
        return all(self._possessed(state, code) >= qty
                   for code, qty in self._possession_requirements().items())

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        inventory = state.inventory
        item_costs = self._item_costs()
        if item_costs:
            inventory = dict(inventory)
            for code, qty in item_costs.items():
                remaining = inventory[code] - qty
                if remaining:
                    inventory[code] = remaining
                else:
                    del inventory[code]
        return dataclasses.replace(
            state, x=self.dest_x, y=self.dest_y, layer=self.dest_layer,
            gold=state.gold - self._gold_cost(), inventory=inventory)

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
        parts = [f", {gold}g"] if gold else []
        parts += [f", {code}x{qty}"
                  for code, qty in sorted(self._item_costs().items())]
        parts += [f", holds {code}"
                  for code in sorted(self._possession_requirements())]
        return (f"Transition(({self.portal_x},{self.portal_y})->"
                f"({self.dest_x},{self.dest_y},{self.dest_layer})"
                f"{''.join(parts)})")
